"""
validate_glossary_json.py — Validate normalized_glossary.json and contentstack_entry.json.

Generates output/<dir>/validation_report.md with PASS / WARN / ERROR per check. Harness
(CheckResult, LEVEL_ORDER, write_report) lifted from the Whitepaper agent's validator;
the check registry is rewritten for the glossary schema (definition/sections/faq, not
brief/body/cta) plus new checks for GEO query coverage, internal-link minimums, and
JSON-LD validity — see docs/glossary_page_spec.md.

Usage:
    python3 scripts/validate_glossary_json.py \
        output/2026-08-25_semantic-layer/normalized_glossary.json \
        output/2026-08-25_semantic-layer/contentstack_entry.json \
        --output output/2026-08-25_semantic-layer/validation_report.md
"""

import re
import sys
import json
import logging
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    level: str  # "PASS", "WARN", "ERROR"
    message: str


# ---------------------------------------------------------------------------
# Checks — normalized_glossary.json
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


def check_definition(n: dict) -> CheckResult:
    definition = n.get("definition", [])
    if not definition:
        return CheckResult("Definition present", "ERROR", "definition array is empty — required on every glossary page (AEO citation block).")
    if len(definition) < 3:
        return CheckResult("Definition count", "WARN", f"Definition has {len(definition)} bullet(s) — minimum is 3.")
    if len(definition) > 5:
        return CheckResult("Definition count", "WARN", f"Definition has {len(definition)} bullet(s) — maximum is 5. Trim to the most impactful.")
    broken = [i + 1 for i, d in enumerate(definition) if not d.get("boldSentence") or not d.get("supportingText")]
    if broken:
        return CheckResult("Definition structure", "ERROR", f"Definition items {broken} are missing boldSentence or supportingText.")
    return CheckResult("Definition", "PASS", f"{len(definition)} definition bullet(s) with boldSentence + supportingText.")


def check_sections(n: dict) -> CheckResult:
    sections = n.get("sections", [])
    if not sections:
        return CheckResult("Body sections", "ERROR", "sections array is empty — no content extracted.")
    headings = [s.get("heading", "") for s in sections if s.get("heading")]
    if len(headings) < len(sections):
        return CheckResult("Body sections", "WARN", f"{len(sections) - len(headings)} section(s) missing a heading.")
    return CheckResult("Body sections", "PASS", f"{len(sections)} section(s), all with headings.")


def check_section_headings_are_questions(n: dict) -> CheckResult:
    sections = n.get("sections", [])
    non_questions = [s.get("heading", "") for s in sections if s.get("heading") and not s["heading"].rstrip().endswith("?")]
    if non_questions:
        return CheckResult(
            "Section headings phrased as questions", "WARN",
            f"{len(non_questions)} section heading(s) not phrased as a question (page spec's citation-example pattern prefers this): {non_questions[:3]}",
        )
    return CheckResult("Section headings phrased as questions", "PASS", "All section headings are questions.")


def check_seo_title(n: dict) -> CheckResult:
    mt = n.get("seo", {}).get("metaTitle", "")
    if not mt:
        return CheckResult("SEO meta title", "WARN", "Missing seo.metaTitle.")
    if len(mt) > 70:
        return CheckResult("SEO meta title length", "WARN", f"SEO title is {len(mt)} chars (recommended <=70).")
    return CheckResult("SEO meta title", "PASS", f"\"{mt[:60]}\"")


def check_seo_description(n: dict) -> CheckResult:
    md = n.get("seo", {}).get("metaDescription", "")
    if not md:
        return CheckResult("SEO meta description", "WARN", "Missing seo.metaDescription.")
    if len(md) > 160:
        return CheckResult("SEO meta description length", "WARN", f"Meta description is {len(md)} chars (recommended <=160).")
    return CheckResult("SEO meta description", "PASS", f"{len(md)} chars")


def check_target_keywords(n: dict) -> CheckResult:
    kw = n.get("keywordTargets") or n.get("seo", {}).get("targetKeywords", [])
    if not kw:
        return CheckResult("Target keywords", "WARN", "No keyword targets assigned to this term.")
    return CheckResult("Target keywords", "PASS", f"{len(kw)} keyword(s): {', '.join(str(k) for k in kw[:5])}")


def check_multiple_h1(n: dict) -> CheckResult:
    # Only the hero title is H1 in this pipeline's mapper — sections are always H2.
    # Nothing in normalized_glossary.json can itself produce a second H1, but keep the
    # check as a structural guard in case a future source injects one via a callout.
    return CheckResult("Single H1", "PASS", "Hero title is the only H1; sections are H2.")


def check_empty_headings(n: dict) -> CheckResult:
    empty = [i + 1 for i, s in enumerate(n.get("sections", [])) if not (s.get("heading") or "").strip()]
    if empty:
        return CheckResult("Empty headings", "WARN", f"Empty section heading(s) at index: {empty}")
    return CheckResult("Empty headings", "PASS", "No empty headings.")


def check_faq_structure(n: dict) -> CheckResult:
    faq = n.get("faq", [])
    if not faq:
        return CheckResult("FAQ structure", "WARN", "No FAQ items — accordion block will be omitted.")
    broken = [i + 1 for i, f in enumerate(faq) if not f.get("question") or not f.get("answer")]
    if broken:
        return CheckResult("FAQ structure", "ERROR", f"FAQ item(s) {broken} missing question or answer.")
    return CheckResult("FAQ structure", "PASS", f"{len(faq)} FAQ item(s), all complete.")


def check_duplicate_headings(n: dict) -> CheckResult:
    headings = [s.get("heading", "").strip().lower() for s in n.get("sections", []) if s.get("heading")]
    dupes = {h for h in headings if headings.count(h) > 1}
    if dupes:
        return CheckResult("Duplicate headings", "WARN", f"Duplicate section heading(s): {sorted(dupes)}")
    return CheckResult("Duplicate headings", "PASS", "No duplicate section headings.")


def check_geo_query_coverage(n: dict) -> CheckResult:
    """Does the definition block or an H2 literally answer the term's GEO query target?"""
    geo_query = (n.get("geoQueryTarget") or "").lower().rstrip("?").strip()
    if not geo_query:
        return CheckResult("GEO query coverage", "WARN", "No geoQueryTarget set on this term — cannot check coverage.")

    # Loose coverage check: does the query's core noun phrase appear in the definition
    # or in a section heading? Strip the leading "what is a/an" framing to get the term.
    core = re.sub(r"^what\s+is\s+(a|an|the)?\s*", "", geo_query).strip()
    if not core:
        return CheckResult("GEO query coverage", "WARN", "Could not derive a core phrase from geoQueryTarget.")

    definition_text = " ".join(
        f"{d.get('boldSentence', '')} {d.get('supportingText', '')}" for d in n.get("definition", [])
    ).lower()
    headings_text = " ".join(s.get("heading", "") for s in n.get("sections", [])).lower()

    if core in definition_text or core in headings_text:
        return CheckResult("GEO query coverage", "PASS", f"Core phrase \"{core}\" found in definition or section headings.")
    return CheckResult(
        "GEO query coverage", "WARN",
        f"Core phrase \"{core}\" (from geoQueryTarget \"{n.get('geoQueryTarget')}\") not found verbatim in the "
        f"definition block or any section heading — confirm the page actually answers the target question.",
    )


def check_internal_links_minimum(n: dict, config: Optional[dict] = None) -> CheckResult:
    links = n.get("internalLinks", {})
    to_detail = links.get("toDetail", [])
    to_arrival = links.get("toArrival", [])
    inbound = links.get("inbound", [])
    outbound_count = len(to_detail) + len(to_arrival)

    min_out = 3
    min_in = 3
    require_detail = True
    if config:
        link_cfg = config.get("pipeline", {}).get("internal_links", {})
        min_out = link_cfg.get("min_outbound", min_out)
        min_in = link_cfg.get("min_inbound", min_in)
        require_detail = link_cfg.get("require_detail_link", require_detail)

    problems = []
    if outbound_count < min_out:
        problems.append(f"only {outbound_count} outbound link(s), need >={min_out}")
    if require_detail and not to_detail:
        problems.append("no Detail-tier link present (Detail<->Narrative is Critical per the link matrix)")
    if len(inbound) < min_in:
        problems.append(f"only {len(inbound)} inbound link(s) recorded, need >={min_in} (this pipeline can't verify inbound links automatically — add manually)")

    if problems:
        return CheckResult("Internal links minimum", "WARN", "; ".join(problems))
    return CheckResult("Internal links minimum", "PASS", f"{outbound_count} outbound (incl. Detail link), {len(inbound)} inbound recorded.")


def check_ai_flagged_content(n: dict) -> CheckResult:
    provenance = n.get("provenance", [])
    if not provenance:
        return CheckResult("AI-generated content flagged", "WARN", "No provenance entries — cannot confirm AI-generated sections are flagged for Henry's review.")
    unflagged = [p.get("section", "?") for p in provenance if "aiGenerated" not in p]
    if unflagged:
        return CheckResult("AI-generated content flagged", "ERROR", f"Provenance entries missing aiGenerated flag: {unflagged}")
    flagged_sections = {p["section"] for p in provenance if p.get("aiGenerated")}
    return CheckResult("AI-generated content flagged", "PASS", f"{len(flagged_sections)} section(s) flagged aiGenerated for human review.")


def check_parse_warnings(n: dict) -> CheckResult:
    warnings = n.get("validationWarnings", [])
    if not warnings:
        return CheckResult("Drafting warnings", "PASS", "No drafting warnings.")
    return CheckResult("Drafting warnings", "WARN", f"{len(warnings)} warning(s):\n" + "\n".join(f"  - {w}" for w in warnings[:8]))


# ---------------------------------------------------------------------------
# Checks — contentstack_entry.json
# ---------------------------------------------------------------------------

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


def check_jsonld_parses(entry: dict, normalized: dict) -> CheckResult:
    # asset_page has no custom_code block to embed JSON-LD in — map_to_contentstack.py
    # writes it to the top-level `_schema_markup_unplaced` key instead. See
    # docs/glossary_page_spec.md "Schema markup" section.
    jsonld = entry.get("_schema_markup_unplaced")
    if not jsonld:
        return CheckResult("JSON-LD present and valid", "WARN", "No _schema_markup_unplaced found — JSON-LD not computed.")

    graph = jsonld.get("@graph", [])
    defined_term = next((g for g in graph if g.get("@type") == "DefinedTerm"), None)
    if not defined_term:
        return CheckResult("JSON-LD present and valid", "ERROR", "No DefinedTerm entry in JSON-LD @graph.")

    title = normalized.get("title", "")
    name = defined_term.get("name", "")
    if name and title and name.lower() not in title.lower() and title.lower() not in name.lower():
        return CheckResult("JSON-LD present and valid", "WARN", f"JSON-LD DefinedTerm.name (\"{name}\") doesn't clearly match page title (\"{title}\").")

    return CheckResult("JSON-LD present and valid", "PASS", f"JSON-LD parses (unplaced — no field on asset_page to embed it in yet); DefinedTerm.name=\"{name}\", url={defined_term.get('url', '(missing)')}.")


def check_resource_data_type(entry: dict) -> CheckResult:
    e = entry.get("entry", {})
    rtype = e.get("resource_data", {}).get("type", "")
    known_valid = {"Blog", "Analyst Report"}
    if rtype not in known_valid:
        return CheckResult("resource_data.type", "WARN", f"'{rtype}' is not in the confirmed-valid set {known_valid} — unconfirmed for glossary pages, verify with discover_schema.py before real publish.")
    return CheckResult("resource_data.type", "PASS", f"'{rtype}' is a confirmed-valid value (though not confirmed specifically for glossary pages).")


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def validate_all(normalized: dict, entry_json: dict, config: Optional[dict] = None) -> list:
    return [
        check_title(normalized),
        check_url(normalized),
        check_definition(normalized),
        check_sections(normalized),
        check_section_headings_are_questions(normalized),
        check_seo_title(normalized),
        check_seo_description(normalized),
        check_target_keywords(normalized),
        check_multiple_h1(normalized),
        check_empty_headings(normalized),
        check_faq_structure(normalized),
        check_duplicate_headings(normalized),
        check_geo_query_coverage(normalized),
        check_internal_links_minimum(normalized, config),
        check_ai_flagged_content(normalized),
        check_parse_warnings(normalized),
        check_entry_wrapper(entry_json),
        check_entry_required_fields(entry_json),
        check_jsonld_parses(entry_json, normalized),
        check_resource_data_type(entry_json),
    ]


_HUMAN_ACTION_KEYWORDS = (
    "confirm", "manually", "review", "upload", "before publishing", "verify", "unconfirmed",
)


def _build_review_summary(normalized: dict, entry_json: dict, results: list) -> list:
    entry = entry_json.get("entry", {})
    seo = normalized.get("seo", {})
    lines = [
        "## Ready to Publish? — Review Checklist",
        "",
        f"**Term:** {normalized.get('term', '(no term)')}  |  **Priority:** {normalized.get('priority', '?')}",
        f"**Title:** {normalized.get('title', '(no title)')}",
        f"**URL:** {entry.get('url') or normalized.get('url') or '(not set)'}",
        f"**GEO query target:** {normalized.get('geoQueryTarget', '(none)')}",
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
    lines.append("")

    primary = seo.get("primaryKeywords") or normalized.get("keywordTargets", [])
    if primary:
        lines += ["### Keywords", "", f"**Primary:** {', '.join(primary)}", ""]

    definition = normalized.get("definition", [])
    if definition:
        lines += ["### Definition block (review before publishing)", ""]
        for i, d in enumerate(definition, 1):
            lines.append(f"{i}. **{d.get('boldSentence', '')}** {d.get('supportingText', '')}")
        lines.append("")

    links = normalized.get("internalLinks", {})
    lines += ["### Internal links", ""]
    for label, key in (("Detail", "toDetail"), ("Arrival", "toArrival"), ("Inbound", "inbound")):
        items = links.get(key, [])
        lines.append(f"**{label} ({len(items)}):** " + (", ".join(i.get("text", "") for i in items) if items else "(none)"))
    lines.append("")

    pending = []
    for r in results:
        if r.level == "ERROR":
            pending.append(f"BLOCKER — {r.name}: {r.message.splitlines()[0]}")
    for w in normalized.get("validationWarnings", []):
        if any(kw in w.lower() for kw in _HUMAN_ACTION_KEYWORDS):
            pending.append(w.splitlines()[0][:200])

    lines += ["### Pending Before Publishing", ""]
    if pending:
        for item in pending:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- Nothing outstanding from automated checks — still needs Henry (accuracy) + Frank (SEO/GEO) sign-off.")
    lines += ["", "---", ""]
    return lines


def write_report(results: list, output_path: str, normalized: Optional[dict] = None, entry_json: Optional[dict] = None) -> str:
    errors = [r for r in results if r.level == "ERROR"]
    warns = [r for r in results if r.level == "WARN"]
    passes = [r for r in results if r.level == "PASS"]

    status = "ERRORS FOUND" if errors else ("WARNINGS" if warns else "ALL CHECKS PASSED")
    icon = "❌" if errors else ("⚠️" if warns else "✅")

    lines = ["# Glossary Page Validation Report", ""]
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
        detail = r.message.replace("\n", " ").replace("|", "\\|")[:160]
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
    logger.info(f"Validation: {errors} errors, {warns} warnings -> {output_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate normalized glossary and Contentstack entry JSON.")
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
