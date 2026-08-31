"""
validate_blog_json.py — Validate normalized_blog.json and contentstack_entry.json.

Generates output/validation_report.md with PASS / WARN / ERROR per check.

Usage:
    python scripts/validate_blog_json.py \
        output/normalized_blog.json \
        output/contentstack_entry.json \
        --output output/validation_report.md
"""

import re
import sys

if sys.platform == "win32":
    # Native Windows consoles default to a legacy codepage, not UTF-8 — without
    # this, the ✓/⚠/❌ status glyphs below crash with UnicodeEncodeError mid-run.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
import json
import logging
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "PASS": 2}


@dataclass
class CheckResult:
    name: str
    level: str  # "PASS", "WARN", "ERROR"
    message: str


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_title(normalized: dict) -> CheckResult:
    title = normalized.get("title", "")
    if not title or not title.strip():
        return CheckResult("Title present", "ERROR", "Missing title — required for Contentstack entry.")
    return CheckResult("Title present", "PASS", f"Title: \"{title[:60]}\"")


def check_url(normalized: dict) -> CheckResult:
    url = normalized.get("url", "")
    if not url:
        return CheckResult("URL present", "ERROR", "Missing URL — will be auto-generated from slug but should be reviewed.")
    if not url.startswith("/"):
        return CheckResult("URL format", "ERROR", f"URL does not start with '/': {url}")
    return CheckResult("URL present", "PASS", f"URL: {url}")


def check_seo_title(normalized: dict) -> CheckResult:
    meta_title = normalized.get("seo", {}).get("metaTitle", "")
    if not meta_title:
        return CheckResult("SEO meta title", "WARN", "Missing seo.metaTitle — use Claude enrichment or add manually.")
    if len(meta_title) > 70:
        return CheckResult("SEO meta title length", "WARN", f"SEO title is {len(meta_title)} chars (recommended ≤70): \"{meta_title[:70]}...\"")
    return CheckResult("SEO meta title", "PASS", f"Meta title: \"{meta_title[:60]}\"")


def check_seo_description(normalized: dict) -> CheckResult:
    meta_desc = normalized.get("seo", {}).get("metaDescription", "")
    if not meta_desc:
        return CheckResult("SEO meta description", "WARN", "Missing seo.metaDescription — use Claude enrichment or add manually.")
    if len(meta_desc) > 160:
        return CheckResult("SEO meta description length", "WARN", f"Meta description is {len(meta_desc)} chars (recommended ≤160).")
    return CheckResult("SEO meta description", "PASS", f"Meta description ({len(meta_desc)} chars)")


def check_target_keywords(normalized: dict) -> CheckResult:
    kw = normalized.get("seo", {}).get("targetKeywords", [])
    if not kw:
        return CheckResult("Target keywords", "WARN", "No target keywords set in seo.targetKeywords.")
    return CheckResult("Target keywords", "PASS", f"{len(kw)} keyword(s): {', '.join(str(k) for k in kw[:5])}")


def check_quick_answer(normalized: dict) -> CheckResult:
    qa = normalized.get("quickAnswer", [])
    if not qa:
        return CheckResult("Quick answer", "WARN", "quickAnswer is empty — detected from 'Quick Answer' / 'Short Answer' box.")
    if len(qa) < 2:
        return CheckResult("Quick answer completeness", "WARN", f"quickAnswer has {len(qa)} item(s) — ideally 2-3 bullet sentences.")
    return CheckResult("Quick answer", "PASS", f"{len(qa)} quick answer sentence(s) present.")


def check_cta(normalized: dict) -> CheckResult:
    cta_list = normalized.get("cta_list") or []
    if not cta_list:
        return CheckResult("CTA present", "WARN", "No CTA detected — add manually or use Claude enrichment.")
    missing_by_item = []
    for i, cta in enumerate(cta_list):
        missing = [f for f in ("headline", "buttonText", "buttonUrl") if not cta.get(f)]
        if missing:
            missing_by_item.append(f"CTA {i+1} missing: {', '.join(missing)}")
    if missing_by_item:
        return CheckResult("CTA completeness", "WARN", "; ".join(missing_by_item))
    summary = "; ".join(f"\"{c.get('buttonText', '')}\" → {c.get('buttonUrl', '')}" for c in cta_list)
    return CheckResult("CTA", "PASS", f"{len(cta_list)} CTA(s): {summary}")


def check_multiple_h1(normalized: dict) -> CheckResult:
    h1_count = 0
    for section in normalized.get("body", []):
        if section.get("level") == 1 and section.get("heading"):
            h1_count += 1
    if h1_count > 1:
        return CheckResult("Single H1", "ERROR", f"{h1_count} H1-level sections found — only one H1 is valid per page.")
    return CheckResult("Single H1", "PASS", "No duplicate H1s detected.")


def check_empty_headings(normalized: dict) -> CheckResult:
    empty = []
    for i, section in enumerate(normalized.get("body", [])):
        if "heading" in section and section["heading"] == "":
            empty.append(f"Section {i+1}")
        for block in section.get("blocks", []):
            if block.get("type") == "heading" and not block.get("text", "").strip():
                empty.append(f"Inline heading in section {i+1}")
    if empty:
        return CheckResult("Empty headings", "WARN", f"Empty heading text found: {', '.join(empty[:5])}")
    return CheckResult("Empty headings", "PASS", "No empty headings found.")


def check_duplicate_headings(normalized: dict) -> CheckResult:
    seen = []
    dupes = []
    for section in normalized.get("body", []):
        h = section.get("heading", "").strip().lower()
        if h:
            if h in seen:
                dupes.append(section["heading"][:50])
            else:
                seen.append(h)
    if dupes:
        return CheckResult("Duplicate headings", "WARN", f"Duplicate section headings: {dupes}")
    return CheckResult("Duplicate headings", "PASS", "No duplicate headings.")


def check_malformed_links(normalized: dict) -> CheckResult:
    _url_re = re.compile(r"^https?://\S+|^/\S*$")
    bad = []
    for url in normalized.get("internalLinks", []) + normalized.get("externalLinks", []):
        if url and not _url_re.match(url):
            bad.append(url[:60])
    if bad:
        return CheckResult("Link format", "WARN", f"Malformed links detected: {bad[:3]}")
    return CheckResult("Link format", "PASS", "All links appear well-formed.")


def check_missing_asset_uids(normalized: dict) -> CheckResult:
    missing = []
    for section in normalized.get("body", []):
        for block in section.get("blocks", []):
            if block.get("type") == "image" and not block.get("assetUid"):
                src = block.get("sourcePath") or block.get("url") or "unknown"
                missing.append(src[:50])
    hero = normalized.get("heroMedia")
    if hero and hero.get("type") == "image" and not hero.get("assetUid"):
        missing.append("heroMedia")
    if missing:
        return CheckResult(
            "Image asset UIDs",
            "WARN",
            f"{len(missing)} image(s) missing assetUid — upload to Contentstack Assets and fill in manually: {missing[:3]}",
        )
    return CheckResult("Image asset UIDs", "PASS", "All images have assetUid (or no images present).")


def check_faq_structure(normalized: dict) -> CheckResult:
    faq = normalized.get("faq", [])
    if not faq:
        return CheckResult("FAQ structure", "PASS", "No FAQ section (optional).")
    broken = [i + 1 for i, item in enumerate(faq) if not item.get("question") or not item.get("answer")]
    if broken:
        return CheckResult("FAQ structure", "ERROR", f"FAQ items {broken} are missing question or answer.")
    no_accordion = [i + 1 for i, item in enumerate(faq) if not isinstance(item.get("accordionEnabled"), bool)]
    if no_accordion:
        return CheckResult("FAQ accordion flag", "WARN", f"FAQ items {no_accordion} missing accordionEnabled boolean.")
    return CheckResult("FAQ structure", "PASS", f"{len(faq)} FAQ item(s) with question + answer.")


def check_entry_wrapper(entry_json: dict) -> CheckResult:
    if "entry" not in entry_json:
        return CheckResult("Contentstack entry wrapper", "ERROR", "contentstack_entry.json is not wrapped in {\"entry\": {...}}.")
    return CheckResult("Contentstack entry wrapper", "PASS", "Entry is correctly wrapped in {\"entry\": {...}}.")


def check_entry_required_fields(entry_json: dict) -> CheckResult:
    entry = entry_json.get("entry", {})
    missing = [f for f in ("title", "url") if not entry.get(f)]
    if missing:
        return CheckResult("Entry required fields", "ERROR", f"Contentstack entry missing required fields: {missing}")
    return CheckResult("Entry required fields", "PASS", "Required entry fields (title, url) present.")


def check_field_map_coverage(config: Optional[dict]) -> CheckResult:
    if not config:
        return CheckResult("Field map coverage", "WARN", "No config provided — cannot check field_map coverage.")
    field_map = config.get("contentstack", {}).get("field_map", {})
    required_internal = ["title", "url", "content"]
    missing = [k for k in required_internal if k not in field_map]
    if missing:
        return CheckResult("Field map coverage", "WARN", f"config.yaml field_map missing entries for: {missing}")
    return CheckResult("Field map coverage", "PASS", f"All {len(field_map)} field mappings present in config.yaml.")


def check_parse_warnings(normalized: dict) -> CheckResult:
    warnings = normalized.get("validationWarnings", [])
    if not warnings:
        return CheckResult("Parser warnings", "PASS", "No parser warnings.")
    return CheckResult("Parser warnings", "WARN", f"{len(warnings)} parser warning(s):\n" + "\n".join(f"  - {w}" for w in warnings[:5]))


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def validate_all(
    normalized: dict,
    entry_json: dict,
    config: Optional[dict] = None,
) -> list:
    checks = [
        check_title(normalized),
        check_url(normalized),
        check_seo_title(normalized),
        check_seo_description(normalized),
        check_target_keywords(normalized),
        check_quick_answer(normalized),
        check_cta(normalized),
        check_multiple_h1(normalized),
        check_empty_headings(normalized),
        check_duplicate_headings(normalized),
        check_malformed_links(normalized),
        check_missing_asset_uids(normalized),
        check_faq_structure(normalized),
        check_entry_wrapper(entry_json),
        check_entry_required_fields(entry_json),
        check_field_map_coverage(config),
        check_parse_warnings(normalized),
    ]
    return checks


_HUMAN_ACTION_KEYWORDS = (
    "confirm", "manually", "requires human", "human input", "review", "add a promo",
    "upload", "defaulted to", "before publishing", "internal links",
)


def _build_review_summary(normalized: dict, entry_json: dict, results: list) -> list:
    """Return lines for the human-facing pre-publish checklist at the top of the report."""
    entry = entry_json.get("entry", {})
    seo = normalized.get("seo", {})
    lines = []

    lines += [
        "## Ready to Post? — Review Checklist",
        "",
        f"**Post:** {normalized.get('title', '(no title)')}",
        f"**Author:** {normalized.get('author', '(unknown)')}",
        f"**Publish Date:** {entry.get('publish_date') or normalized.get('publishDate') or '(not set)'}",
        f"**URL:** {entry.get('url') or normalized.get('url') or '(not set)'}",
        "",
    ]

    # Meta description
    meta_desc = seo.get("metaDescription", "")
    lines.append("### Meta Description")
    lines.append("")
    if meta_desc:
        lines.append(f"> {meta_desc}")
        lines.append(f"*({len(meta_desc)} chars)*")
    else:
        lines.append("*(missing)*")
    alts = seo.get("metaDescriptionAlternatives", [])
    if alts:
        lines.append("")
        lines.append("**Alternatives to consider:**")
        for i, alt in enumerate(alts[:3], 1):
            lines.append(f"{i}. {alt} *({len(alt)} chars)*")
    lines.append("")

    # Keywords
    primary = seo.get("primaryKeywords") or seo.get("targetKeywords", [])
    secondary = seo.get("secondaryKeywords", [])
    longtail = seo.get("longTailKeywords", [])
    branded = seo.get("brandedKeywords", [])
    if any([primary, secondary, longtail, branded]):
        lines.append("### Keywords")
        lines.append("")
        if primary:
            lines.append(f"**Primary:** {', '.join(primary)}")
        if secondary:
            lines.append(f"**Secondary:** {', '.join(secondary)}")
        if longtail:
            lines.append(f"**Long-tail / AIO:** {', '.join(longtail)}")
        if branded:
            lines.append(f"**Branded:** {', '.join(branded)}")
        lines.append("")

    # Pending items checklist
    pending = []
    # ERRORs are always blockers
    for r in results:
        if r.level == "ERROR":
            pending.append(f"BLOCKER — {r.name}: {r.message.splitlines()[0]}")
    # Parser warnings that require human action
    for w in normalized.get("validationWarnings", []):
        wl = w.lower()
        if any(kw in wl for kw in _HUMAN_ACTION_KEYWORDS):
            pending.append(w.splitlines()[0][:160])

    lines.append("### Pending Before Publishing")
    lines.append("")
    if pending:
        for item in pending:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- Nothing outstanding — ready to publish.")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def write_report(results: list, output_path: str, normalized: Optional[dict] = None, entry_json: Optional[dict] = None) -> str:
    errors = [r for r in results if r.level == "ERROR"]
    warns = [r for r in results if r.level == "WARN"]
    passes = [r for r in results if r.level == "PASS"]

    status = "ERRORS FOUND — review before uploading" if errors else ("WARNINGS — review recommended" if warns else "ALL CHECKS PASSED")
    icon = "❌" if errors else ("⚠️" if warns else "✅")

    lines = ["# Blog Validation Report", ""]

    # Human-facing review summary at the top
    if normalized is not None and entry_json is not None:
        lines += _build_review_summary(normalized, entry_json, results)

    lines += [
        f"## Technical Summary {icon}",
        "",
        f"**Status:** {status}",
        "",
        f"| Level | Count |",
        f"|---|---|",
        f"| ❌ ERROR | {len(errors)} |",
        f"| ⚠ WARN  | {len(warns)} |",
        f"| ✅ PASS  | {len(passes)} |",
        "",
    ]

    if errors:
        lines.append("## Errors (must fix before upload)")
        lines.append("")
        for r in errors:
            lines.append(f"### ❌ {r.name}")
            lines.append(f"{r.message}")
            lines.append("")

    if warns:
        lines.append("## Warnings (review recommended)")
        lines.append("")
        for r in warns:
            lines.append(f"### ⚠ {r.name}")
            lines.append(f"{r.message}")
            lines.append("")

    lines.append("## All Checks")
    lines.append("")
    lines.append("| Check | Result | Detail |")
    lines.append("|---|---|---|")
    for r in results:
        icon_cell = "❌" if r.level == "ERROR" else ("⚠" if r.level == "WARN" else "✅")
        detail = r.message.replace("\n", " ").replace("|", "\\|")[:120]
        lines.append(f"| {r.name} | {icon_cell} {r.level} | {detail} |")

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report


def main(
    normalized_path: str,
    entry_path: str,
    output_path: str = "output/validation_report.md",
    config_path: Optional[str] = "config.yaml",
) -> list:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    with open(normalized_path, "r", encoding="utf-8") as f:
        normalized = json.load(f)
    with open(entry_path, "r", encoding="utf-8") as f:
        entry_json = json.load(f)
    config = None
    if config_path:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config not found: {config_path}")
    results = validate_all(normalized, entry_json, config)
    write_report(results, output_path, normalized=normalized, entry_json=entry_json)
    errors = sum(1 for r in results if r.level == "ERROR")
    warns = sum(1 for r in results if r.level == "WARN")
    logger.info(f"Validation complete: {errors} errors, {warns} warnings → {output_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate normalized and Contentstack blog JSON.")
    parser.add_argument("normalized_path", help="Path to normalized_blog.json")
    parser.add_argument("entry_path", help="Path to contentstack_entry.json")
    parser.add_argument("--output", "-o", default="output/validation_report.md")
    parser.add_argument("--config", "-c", default="config.yaml")
    args = parser.parse_args()
    results = main(args.normalized_path, args.entry_path, args.output, args.config)
    errors = sum(1 for r in results if r.level == "ERROR")
    warns = sum(1 for r in results if r.level == "WARN")
    print(f"Validation report: {args.output}")
    print(f"  {errors} error(s), {warns} warning(s)")
    sys.exit(1 if errors else 0)
