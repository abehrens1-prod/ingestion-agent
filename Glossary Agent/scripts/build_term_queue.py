"""
build_term_queue.py — Extract glossary-page rows from the Q3 content-needs spreadsheet
into input/term_queue.json.

Source: input/Content needs - Remaining Q3.xlsx (copied from Frank's "Content needs -
Remaining Q3.xlsx" — the closest artifact found to the "Q3 Content Strategy doc" his
operating plan references; that doc itself wasn't located on disk. See
docs/glossary_page_spec.md.)

Column quirk worth knowing (confirmed by inspecting the workbook column-by-column, not by
skipping blank cells): for the first 4 glossary rows, the GEO query target lives in the
"GEO query target" column. For the remaining rows, that column is empty and the same
question text is in "Commnets" instead. This script checks both.

Usage:
    python3 scripts/build_term_queue.py
    python3 scripts/build_term_queue.py --input "input/Content needs - Remaining Q3.xlsx" \
        --output input/term_queue.json
"""

import json
import re
import argparse
import logging
from pathlib import Path

import openpyxl
from slugify import slugify

logger = logging.getLogger(__name__)

DEFAULT_INPUT = "input/Content needs - Remaining Q3.xlsx"
DEFAULT_OUTPUT = "input/term_queue.json"

# Frank explicitly parked ontology work (2026-08-18 call): "we're holding on that for
# now." Exclude it even if it shows up in a future version of the source sheet.
EXCLUDED_TERMS = {"ontology"}

_LEADING_Q = re.compile(r"^\s*what\s+is\s+(a|an|the)?\s*", re.IGNORECASE)
_TRAILING_Q = re.compile(r"\s*\?\s*$")

# Known typos in Frank's "quick and dirty" sheet — narrow, targeted patterns, not a
# general spellchecker. "later" is a real word so this only fires next to "semantic"
# (every observed instance in this sheet is "semantic layer" mistyped); "goverened"
# isn't a real word so it's safe to fix everywhere.
_TYPO_FIXES = [
    (re.compile(r"\bsemantic\s+later\b", re.IGNORECASE), "semantic layer"),
    (re.compile(r"\bgoverened\b", re.IGNORECASE), "governed"),
]


def _fix_known_typos(text: str) -> str:
    fixed = text
    for pattern, replacement in _TYPO_FIXES:
        fixed = pattern.sub(replacement, fixed)
    return fixed


def _clean_cell(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\t", " ").strip()


def _split_keyword_targets(raw: str) -> list:
    if not raw:
        return []
    parts = re.split(r"[\n/]", raw)
    seen = []
    for p in parts:
        p = p.strip()
        if p and p not in seen:
            seen.append(p)
    return seen


def _term_from_geo_query(geo_query: str) -> str:
    t = _LEADING_Q.sub("", geo_query)
    t = _TRAILING_Q.sub("", t)
    return t.strip()


def _pick_term(keyword_targets: list, geo_query: str) -> str:
    """
    Prefer keyword targets over the GEO query text for the term name. The source sheet
    is Frank's own "quick and dirty" doc and the GEO query / Comments columns carry real
    typos (row 2: "semantic later" for "semantic layer"; row 9: "Goverened AI"). The
    keyword-target column is consistently clean across every glossary row observed, so it
    wins whenever present — this is not a general typo-correction heuristic, just a
    column-preference rule for this specific sheet.
    """
    for kt in keyword_targets:
        cleaned = _term_from_geo_query(kt)
        if cleaned:
            return cleaned
    if geo_query:
        return _term_from_geo_query(geo_query)
    return ""


def build_queue(input_path: str, type_filter: str = "Glossary") -> list:
    wb = openpyxl.load_workbook(input_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [_clean_cell(h) for h in rows[0]]

    queue = []
    for raw_row in rows[1:]:
        d = dict(zip(headers, raw_row))
        row_type = _clean_cell(d.get("Type"))
        if type_filter.lower() not in row_type.lower():
            continue

        keyword_targets = _split_keyword_targets(_clean_cell(d.get("Keyword/phrase target")))
        geo_query_raw = _clean_cell(d.get("GEO query target")) or _clean_cell(d.get("Commnets"))
        geo_query = _fix_known_typos(geo_query_raw) if geo_query_raw else ""

        term = _pick_term(keyword_targets, geo_query)
        if not term:
            logger.warning("Row skipped — no term derivable: %s", d)
            continue

        if term.lower() in EXCLUDED_TERMS:
            logger.info("Skipping excluded term: %s", term)
            continue

        row = {
            "term": term,
            "slug": slugify(term),
            "priority": _clean_cell(d.get("Priority")) or None,
            "status": _clean_cell(d.get("Status")) or "Not started",
            "keywordTargets": keyword_targets,
            "geoQueryTarget": geo_query or None,
            "creator": _clean_cell(d.get("Creator")) or None,
            "sourceType": row_type,
        }
        if geo_query_raw and geo_query_raw != geo_query:
            row["geoQueryTargetRaw"] = geo_query_raw
        queue.append(row)

    # Stable sort by priority (P1 first), preserving spreadsheet order within a tier.
    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    queue.sort(key=lambda r: priority_order.get(r["priority"], 99))
    return queue


def main(input_path: str = DEFAULT_INPUT, output_path: str = DEFAULT_OUTPUT) -> list:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    queue = build_queue(input_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %d glossary term(s) to %s", len(queue), output_path)
    return queue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the glossary term queue from the Q3 content-needs spreadsheet.")
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT)
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    queue = main(args.input, args.output)
    print(f"Terms: {len(queue)}")
    for row in queue:
        print(f"  [{row['priority']}] {row['term']}  (slug: {row['slug']})")
