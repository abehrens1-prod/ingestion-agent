"""
validate_whitepaper_json.py — Validate normalized_whitepaper.json and contentstack_entry.json.

Generates output/validation_report.md with PASS / WARN / ERROR per check.

Usage:
    python scripts/validate_whitepaper_json.py \
        output/normalized_whitepaper.json \
        output/contentstack_entry.json \
        --output output/validation_report.md
"""

import re
import sys
import json
import logging
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ingestion_common.console import enable_utf8

enable_utf8()

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    level: str  # "PASS", "WARN", "ERROR"
    message: str


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_title(n: dict) -> CheckResult:
    t = n.get("title", "")
    if not t.strip():
        return CheckResult("Title present", "ERROR", "Missing title — required.")
    return CheckResult("Title present", "PASS", f"Title: \"{t[:60]}\"")


def check_url(n: dict) -> CheckResult:
    url = n.get("url", "")
    if not url:
        return CheckResult("URL present", "ERROR", "Missing URL.")
    if not url.startswith("/"):
        return CheckResult("URL format", "ERROR", f"URL must start with '/': {url}")
    return CheckResult("URL present", "PASS", f"URL: {url}")


def check_brief(n: dict) -> CheckResult:
    brief = n.get("brief", [])
    if not brief:
        return CheckResult("The Brief present", "ERROR", "brief array is empty — The Brief is required on every whitepaper page.")
    if len(brief) < 3:
        return CheckResult("The Brief count", "WARN", f"The Brief has {len(brief)} bullet(s) — minimum is 3.")
    if len(brief) > 5:
        return CheckResult("The Brief count", "WARN", f"The Brief has {len(brief)} bullet(s) — maximum is 5. Trim to the most impactful.")
    broken = [i + 1 for i, b in enumerate(brief) if not b.get("boldSentence") or not b.get("supportingText")]
    if broken:
        return CheckResult("The Brief structure", "ERROR", f"Brief items {broken} are missing boldSentence or supportingText.")
    return CheckResult("The Brief", "PASS", f"{len(brief)} brief bullet(s) with boldSentence + supportingText.")


def check_description(n: dict) -> CheckResult:
    desc = n.get("description", "")
    if not desc.strip():
        return CheckResult("Hero description", "WARN", "Missing description — hero section will have no intro paragraph.")
    return CheckResult("Hero description", "PASS", f"Description: {len(desc)} chars")


def check_sections(n: dict) -> CheckResult:
    body = n.get("body", [])
    if not body:
        return CheckResult("Body sections", "ERROR", "body array is empty — no content sections extracted.")
    headings = [s.get("heading", "") for s in body if s.get("heading")]
    if len(headings) < 2:
        return CheckResult("Body sections", "WARN", f"Only {len(body)} section(s) with headings — expected several for a whitepaper.")
    return CheckResult("Body sections", "PASS", f"{len(body)} section(s), {len(headings)} with headings.")


def check_tables(n: dict) -> CheckResult:
    table_count = 0
    broken = []
    for i, section in enumerate(n.get("body", [])):
        for block in section.get("blocks", []):
            if block.get("type") == "table":
                table_count += 1
                rows = block.get("rows", [])
                if not rows:
                    broken.append(f"Section {i+1}")
    if broken:
        return CheckResult("Table integrity", "WARN", f"Empty table rows in: {broken[:3]}")
    return CheckResult("Tables", "PASS", f"{table_count} table(s) extracted.")


def check_callout_count(n: dict) -> CheckResult:
    callouts = [s for s in n.get("body", []) if s.get("isCallout")]
    if len(callouts) > 5:
        return CheckResult("Callout count", "WARN", f"{len(callouts)} callout sections — consider trimming to 3-4 for visual balance.")
    return CheckResult("Callout count", "PASS", f"{len(callouts)} callout section(s).")


def check_seo_title(n: dict) -> CheckResult:
    mt = n.get("seo", {}).get("metaTitle", "")
    if not mt:
        return CheckResult("SEO meta title", "WARN", "Missing seo.metaTitle.")
    if len(mt) > 70:
        return CheckResult("SEO meta title length", "WARN", f"SEO title is {len(mt)} chars (recommended ≤70).")
    return CheckResult("SEO meta title", "PASS", f"\"{mt[:60]}\"")


def check_seo_description(n: dict) -> CheckResult:
    md = n.get("seo", {}).get("metaDescription", "")
    if not md:
        return CheckResult("SEO meta description", "WARN", "Missing seo.metaDescription.")
    if len(md) > 160:
        return CheckResult("SEO meta description length", "WARN", f"Meta description is {len(md)} chars (recommended ≤160).")
    return CheckResult("SEO meta description", "PASS", f"{len(md)} chars")


def check_target_keywords(n: dict) -> CheckResult:
    kw = n.get("seo", {}).get("targetKeywords", [])
    if not kw:
        return CheckResult("Target keywords", "WARN", "No target keywords in seo.targetKeywords.")
    return CheckResult("Target keywords", "PASS", f"{len(kw)} keyword(s): {', '.join(str(k) for k in kw[:5])}")


def check_cta(n: dict) -> CheckResult:
    cta = n.get("cta")
    if not cta:
        return CheckResult("CTA present", "WARN", "No CTA detected — add manually if needed.")
    missing = [f for f in ("headline",) if not cta.get(f)]
    if missing:
        return CheckResult("CTA completeness", "WARN", f"CTA missing: {', '.join(missing)}")
    return CheckResult("CTA", "PASS", f"CTA headline: \"{cta.get('headline', '')[:50]}\"")


def check_multiple_h1(n: dict) -> CheckResult:
    h1_count = sum(1 for s in n.get("body", []) if s.get("level") == 1 and s.get("heading"))
    if h1_count > 1:
        return CheckResult("Single H1", "ERROR", f"{h1_count} H1 sections — only one H1 is valid.")
    return CheckResult("Single H1", "PASS", "No duplicate H1s.")


def check_empty_headings(n: dict) -> CheckResult:
    empty = []
    for i, section in enumerate(n.get("body", [])):
        for block in section.get("blocks", []):
            if block.get("type") == "heading" and not block.get("text", "").strip():
                empty.append(f"Section {i+1}")
    if empty:
        return CheckResult("Empty headings", "WARN", f"Empty heading blocks in: {', '.join(empty[:5])}")
    return CheckResult("Empty headings", "PASS", "No empty headings.")


def check_entry_wrapper(entry: dict) -> CheckResult:
    if "entry" not in entry:
        return CheckResult("Entry wrapper", "ERROR", "contentstack_entry.json missing top-level {\"entry\": {...}} wrapper.")
    return CheckResult("Entry wrapper", "PASS", "Entry correctly wrapped.")


def check_entry_required_fields(entry: dict) -> CheckResult:
    e = entry.get("entry", {})
    missing = [f for f in ("title", "url") if not e.get(f)]
    if missing:
        return CheckResult("Entry required fields", "ERROR", f"Missing required entry fields: {missing}")
    return CheckResult("Entry required fields", "PASS", "title and url present in entry.")


def check_parse_warnings(n: dict) -> CheckResult:
    warnings = n.get("validationWarnings", [])
    if not warnings:
        return CheckResult("Parser warnings", "PASS", "No parser warnings.")
    return CheckResult("Parser warnings", "WARN", f"{len(warnings)} warning(s):\n" + "\n".join(f"  - {w}" for w in warnings[:5]))


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def validate_all(normalized: dict, entry_json: dict, config: Optional[dict] = None) -> list:
    return [
        check_title(normalized),
        check_url(normalized),
        check_brief(normalized),
        check_description(normalized),
        check_sections(normalized),
        check_tables(normalized),
        check_callout_count(normalized),
        check_seo_title(normalized),
        check_seo_description(normalized),
        check_target_keywords(normalized),
        check_cta(normalized),
        check_multiple_h1(normalized),
        check_empty_headings(normalized),
        check_entry_wrapper(entry_json),
        check_entry_required_fields(entry_json),
        check_parse_warnings(normalized),
    ]


_HUMAN_ACTION_KEYWORDS = (
    "confirm", "manually", "review", "upload", "before publishing", "add a promo",
)


def _build_review_summary(normalized: dict, entry_json: dict, results: list) -> list:
    entry = entry_json.get("entry", {})
    seo = normalized.get("seo", {})
    lines = [
        "## Ready to Publish? — Review Checklist",
        "",
        f"**Whitepaper:** {normalized.get('title', '(no title)')}",
        f"**URL:** {entry.get('url') or normalized.get('url') or '(not set)'}",
        "",
    ]

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
        lines += ["", "**Alternatives:**"]
        for i, alt in enumerate(alts[:3], 1):
            lines.append(f"{i}. {alt} *({len(alt)} chars)*")
    lines.append("")

    primary = seo.get("primaryKeywords") or seo.get("targetKeywords", [])
    secondary = seo.get("secondaryKeywords", [])
    longtail = seo.get("longTailKeywords", [])
    if any([primary, secondary, longtail]):
        lines += ["### Keywords", ""]
        if primary:
            lines.append(f"**Primary:** {', '.join(primary)}")
        if secondary:
            lines.append(f"**Secondary:** {', '.join(secondary)}")
        if longtail:
            lines.append(f"**Long-tail / AIO:** {', '.join(longtail)}")
        lines.append("")

    brief = normalized.get("brief", [])
    if brief:
        lines += ["### The Brief (review before publishing)", ""]
        for i, b in enumerate(brief, 1):
            lines.append(f"{i}. **{b.get('boldSentence', '')}** {b.get('supportingText', '')}")
        lines.append("")

    pending = []
    for r in results:
        if r.level == "ERROR":
            pending.append(f"BLOCKER — {r.name}: {r.message.splitlines()[0]}")
    for w in normalized.get("validationWarnings", []):
        if any(kw in w.lower() for kw in _HUMAN_ACTION_KEYWORDS):
            pending.append(w.splitlines()[0][:160])

    lines += ["### Pending Before Publishing", ""]
    if pending:
        for item in pending:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- Nothing outstanding — ready to publish.")
    lines += ["", "---", ""]
    return lines


def write_report(results: list, output_path: str, normalized: Optional[dict] = None, entry_json: Optional[dict] = None) -> str:
    errors = [r for r in results if r.level == "ERROR"]
    warns = [r for r in results if r.level == "WARN"]
    passes = [r for r in results if r.level == "PASS"]

    status = "ERRORS FOUND" if errors else ("WARNINGS" if warns else "ALL CHECKS PASSED")
    icon = "❌" if errors else ("⚠️" if warns else "✅")

    lines = ["# Whitepaper Validation Report", ""]
    if normalized is not None and entry_json is not None:
        lines += _build_review_summary(normalized, entry_json, results)

    lines += [
        f"## Technical Summary {icon}",
        "",
        f"**Status:** {status}",
        "",
        "| Level | Count |",
        "|---|---|",
        f"| ❌ ERROR | {len(errors)} |",
        f"| ⚠ WARN  | {len(warns)} |",
        f"| ✅ PASS  | {len(passes)} |",
        "",
    ]

    if errors:
        lines += ["## Errors (must fix before upload)", ""]
        for r in errors:
            lines += [f"### ❌ {r.name}", r.message, ""]

    if warns:
        lines += ["## Warnings (review recommended)", ""]
        for r in warns:
            lines += [f"### ⚠ {r.name}", r.message, ""]

    lines += ["## All Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
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
    with open(normalized_path) as f:
        normalized = json.load(f)
    with open(entry_path) as f:
        entry_json = json.load(f)
    config = None
    if config_path:
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            pass
    results = validate_all(normalized, entry_json, config)
    write_report(results, output_path, normalized=normalized, entry_json=entry_json)
    errors = sum(1 for r in results if r.level == "ERROR")
    warns = sum(1 for r in results if r.level == "WARN")
    logger.info(f"Validation: {errors} errors, {warns} warnings → {output_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate normalized whitepaper and Contentstack entry JSON.")
    parser.add_argument("normalized_path")
    parser.add_argument("entry_path")
    parser.add_argument("--output", "-o", default="output/validation_report.md")
    parser.add_argument("--config", "-c", default="config.yaml")
    args = parser.parse_args()
    results = main(args.normalized_path, args.entry_path, args.output, args.config)
    errors = sum(1 for r in results if r.level == "ERROR")
    warns = sum(1 for r in results if r.level == "WARN")
    print(f"Validation report: {args.output}")
    print(f"  {errors} error(s), {warns} warning(s)")
    sys.exit(1 if errors else 0)
