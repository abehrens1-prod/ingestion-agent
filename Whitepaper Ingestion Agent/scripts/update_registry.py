"""
update_registry.py — Append a new entry to whitepaper_registry.md after a successful upload.

Usage:
    python3 scripts/update_registry.py <output_dir>

Reads upload_response.json, normalized_whitepaper.json, and contentstack_entry.json
from the given output directory and appends a new row to whitepaper_registry.md.
"""

import json
import sys
from datetime import date
from pathlib import Path


REGISTRY_PATH = Path(__file__).parent.parent / "whitepaper_registry.md"


def main(output_dir: str) -> None:
    out = Path(output_dir)

    # Load UID from upload response
    resp_path = out / "upload_response.json"
    if not resp_path.exists():
        print(f"ERROR: {resp_path} not found — run upload first.")
        sys.exit(1)
    resp = json.loads(resp_path.read_text())
    entry = resp.get("entry", resp)
    uid = entry.get("uid", "(unknown)")

    # Load title from normalized JSON (clean title without v1/v2 prefix)
    norm_path = out / "normalized_whitepaper.json"
    title = "(unknown)"
    if norm_path.exists():
        norm = json.loads(norm_path.read_text())
        title = norm.get("title", title)

    # Load URL from contentstack entry
    cs_path = out / "contentstack_entry.json"
    url = "(unknown)"
    if cs_path.exists():
        cs = json.loads(cs_path.read_text())
        url = cs.get("entry", {}).get("url", url)

    # Derive ingestion date from output dir name (YYYY-MM-DD_slug) or fall back to today
    dir_name = out.name
    ingest_date = dir_name[:10] if len(dir_name) >= 10 and dir_name[4] == "-" else date.today().isoformat()

    # Relative output dir path for the registry
    rel_dir = f"output/{out.name}/"

    # Build new row
    new_row = f"| {ingest_date} | {title} | `{url}` | `{uid}` | `{rel_dir}` |"

    # Check for duplicate UID — don't add the same entry twice
    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    if uid in registry_text:
        print(f"Registry already contains UID {uid} — skipping.")
        return

    # Append row (preserve trailing newline)
    updated = registry_text.rstrip("\n") + "\n" + new_row + "\n"
    REGISTRY_PATH.write_text(updated, encoding="utf-8")
    print(f"Registry updated: {title} ({uid})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/update_registry.py <output_dir>")
        sys.exit(1)
    main(sys.argv[1])
