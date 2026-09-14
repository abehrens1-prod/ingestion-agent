"""
update_registry.py — Append a new entry to glossary_registry.md after a successful upload.

Adapted from the Whitepaper Ingestion Agent's update_registry.py. Fixes a bug present
in the original: its header declared 6 columns but new_row only ever wrote 5 (Preview URL
was never populated). This version's header and row are kept in sync.

Usage:
    python3 scripts/update_registry.py <output_dir>

Reads upload_response.json, normalized_glossary.json, and contentstack_entry.json
from the given output directory and appends a new row to glossary_registry.md.

The registry is also the related-terms source for later pages' internal links — see
draft_with_claude.py, which reads it to populate normalized_glossary.json's related_terms.
"""

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ingestion_common.console import enable_utf8

enable_utf8()


REGISTRY_PATH = Path(__file__).parent.parent / "glossary_registry.md"


def main(output_dir: str) -> None:
    out = Path(output_dir)

    resp_path = out / "upload_response.json"
    if not resp_path.exists():
        print(f"ERROR: {resp_path} not found — run upload first.")
        sys.exit(1)
    resp = json.loads(resp_path.read_text())
    entry = resp.get("entry", resp)
    uid = entry.get("uid", "(unknown)")

    norm_path = out / "normalized_glossary.json"
    title = "(unknown)"
    priority = "(unknown)"
    geo_query = "(unknown)"
    if norm_path.exists():
        norm = json.loads(norm_path.read_text())
        title = norm.get("title", title)
        priority = norm.get("priority", priority)
        geo_query = norm.get("geoQueryTarget", geo_query)

    cs_path = out / "contentstack_entry.json"
    url = "(unknown)"
    if cs_path.exists():
        cs = json.loads(cs_path.read_text())
        url = cs.get("entry", {}).get("url", url)

    dir_name = out.name
    ingest_date = dir_name[:10] if len(dir_name) >= 10 and dir_name[4] == "-" else date.today().isoformat()

    rel_dir = f"output/{out.name}/"

    # Draft-only pipeline (see CLAUDE.md) — never auto-published, so status is always
    # "Draft — pending review" until a human updates this row after the Henry/Frank pass.
    new_row = (
        f"| {ingest_date} | {title} | {priority} | Draft — pending review "
        f"| `{url}` | `{uid}` | \"{geo_query}\" | `{rel_dir}` |"
    )

    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    if uid in registry_text:
        print(f"Registry already contains UID {uid} — skipping.")
        return

    updated = registry_text.rstrip("\n") + "\n" + new_row + "\n"
    REGISTRY_PATH.write_text(updated, encoding="utf-8")
    print(f"Registry updated: {title} ({uid})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/update_registry.py <output_dir>")
        sys.exit(1)
    main(sys.argv[1])
