"""
discover_schema.py — Phase 1: Discover the whitepaper content type UID and field structure.

This script queries the Contentstack API to:
  1. List all content types and find the whitepaper type
  2. Print the full field schema (UIDs, types, sub-fields)
  3. Optionally fetch Claire's existing whitepaper entry to see the live payload shape

Run this ONCE before building the mapper. Results go into config.yaml.

Usage:
    python scripts/discover_schema.py
    python scripts/discover_schema.py --list-types        # just list all content types
    python scripts/discover_schema.py --type whitepaper   # inspect a specific content type
    python scripts/discover_schema.py --entries whitepaper --limit 3   # fetch live entries

Requires: MSTR_API_KEY in .env
"""

import os
import sys
import json
import argparse
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


def _headers() -> dict:
    api_key = os.getenv("MSTR_API_KEY")
    if not api_key:
        print("❌ MSTR_API_KEY not set in .env")
        sys.exit(1)
    return {"x-mstr-key": api_key, "Content-Type": "application/json"}


def _base_url() -> str:
    with open(BASE_DIR / "config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("api", {}).get("base_url", "").rstrip("/")


def list_content_types(base_url: str, headers: dict):
    """List all content types. Useful for finding the whitepaper UID."""
    url = f"{base_url}/content_types"
    print(f"\nGET {url}\n")
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:500]}")
        return

    data = r.json()
    types = data.get("content_types", [])
    if not types:
        print("No content types returned. Full response:")
        print(json.dumps(data, indent=2))
        return

    print(f"{'UID':<40} {'Title'}")
    print("-" * 70)
    for ct in sorted(types, key=lambda x: x.get("uid", "")):
        print(f"{ct.get('uid', '?'):<40} {ct.get('title', '?')}")

    print(f"\nTotal: {len(types)} content types")
    print("\nLook for anything containing 'white', 'paper', 'resource', 'asset', or 'content'.")


def inspect_content_type(base_url: str, content_type_uid: str, headers: dict):
    """Print the full schema for a content type, including nested fields."""
    url = f"{base_url}/content_types/{content_type_uid}"
    print(f"\nGET {url}\n")
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:500]}")
        return

    data = r.json()
    ct = data.get("content_type", data)
    schema = ct.get("schema", [])

    print(f"Content Type: {ct.get('title', '?')} (uid: {ct.get('uid', '?')})")
    print(f"Description: {ct.get('description', '(none)')}")
    print(f"\nField Schema ({len(schema)} top-level fields):")
    print("-" * 70)
    _print_schema(schema, indent=0)

    # Also save raw JSON for offline review
    out_path = BASE_DIR / "output" / f"schema_{content_type_uid}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Full schema saved to: output/schema_{content_type_uid}.json")


def _print_schema(fields: list, indent: int):
    prefix = "  " * indent
    for f in fields:
        if not isinstance(f, dict):
            continue
        uid = f.get("uid", "?")
        display = f.get("display_name", "")
        ftype = f.get("data_type", f.get("field_metadata", {}).get("ref_multiple", "?"))
        # Use field_metadata.ref_multiple or data_type
        actual_type = f.get("data_type", "?")
        multiple = f.get("multiple", False)
        mandatory = f.get("mandatory", False)
        flags = []
        if multiple:
            flags.append("multiple")
        if mandatory:
            flags.append("required")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{prefix}• {uid:<35} {actual_type:<20} {display}{flag_str}")

        # Print sub-fields for blocks / groups
        sub_fields = f.get("blocks", f.get("schema", f.get("fields", [])))
        if sub_fields and isinstance(sub_fields, list):
            for block in sub_fields:
                if isinstance(block, dict):
                    block_uid = block.get("uid", "?")
                    block_title = block.get("title", "")
                    block_schema = block.get("schema", [])
                    if block_schema:
                        print(f"{prefix}  ↳ [{block_uid}] {block_title}")
                        _print_schema(block_schema, indent + 2)
                    else:
                        print(f"{prefix}  ↳ {block_uid}: {block.get('data_type', '?')} {block_title}")


def fetch_entries(base_url: str, content_type_uid: str, headers: dict, limit: int = 3):
    """Fetch a few live entries to see the real payload shape."""
    url = f"{base_url}/entries/{content_type_uid}?limit={limit}"
    print(f"\nGET {url}\n")
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:500]}")
        return

    data = r.json()
    entries = data.get("entries", [])
    if not entries:
        print("No entries returned. Full response:")
        print(json.dumps(data, indent=2)[:2000])
        return

    print(f"Found {len(entries)} entries (showing first {min(limit, len(entries))}):\n")
    for entry in entries[:limit]:
        uid = entry.get("uid", "?")
        title = entry.get("title", "?")
        url_field = entry.get("url", "?")
        print(f"  UID: {uid}")
        print(f"  Title: {title}")
        print(f"  URL: {url_field}")
        print(f"  Fields: {', '.join(sorted(entry.keys()))}")
        print()

    # Save first entry for deep inspection
    if entries:
        out_path = BASE_DIR / "output" / f"sample_entry_{content_type_uid}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(entries[0], f, indent=2, ensure_ascii=False)
        print(f"✓ First entry saved to: output/sample_entry_{content_type_uid}.json")


def fetch_entry_by_uid(base_url: str, content_type_uid: str, entry_uid: str, headers: dict):
    """Fetch a specific entry by UID to inspect its full structure."""
    url = f"{base_url}/entries/{content_type_uid}/{entry_uid}"
    print(f"\nGET {url}\n")
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:500]}")
        return

    data = r.json()
    out_path = BASE_DIR / "output" / f"entry_{entry_uid}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✓ Entry saved to: output/entry_{entry_uid}.json")
    entry = data.get("entry", data)
    print(f"Fields: {', '.join(sorted(entry.keys()))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Discover the Contentstack whitepaper content type schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/discover_schema.py --list-types
  python scripts/discover_schema.py --type whitepaper_page
  python scripts/discover_schema.py --entries whitepaper_page --limit 5
  python scripts/discover_schema.py --entry whitepaper_page bltXXXXXXXXXXXXXX
        """,
    )
    parser.add_argument("--list-types", action="store_true", help="List all content types")
    parser.add_argument("--type", metavar="UID", help="Inspect schema for a specific content type UID")
    parser.add_argument("--entries", metavar="UID", help="Fetch sample entries for a content type UID")
    parser.add_argument("--limit", type=int, default=3, help="Number of entries to fetch (default: 3)")
    parser.add_argument("--entry", nargs=2, metavar=("TYPE_UID", "ENTRY_UID"), help="Fetch a specific entry by UID")
    args = parser.parse_args()

    headers = _headers()
    base_url = _base_url()
    print(f"API base: {base_url}")

    if args.list_types:
        list_content_types(base_url, headers)
    elif args.type:
        inspect_content_type(base_url, args.type, headers)
    elif args.entries:
        fetch_entries(base_url, args.entries, headers, limit=args.limit)
    elif args.entry:
        fetch_entry_by_uid(base_url, args.entry[0], args.entry[1], headers)
    else:
        # Default: list types to get started
        print("No flag provided — defaulting to --list-types")
        print("Once you identify the whitepaper content type UID, run:")
        print("  python scripts/discover_schema.py --type <uid>")
        print("  python scripts/discover_schema.py --entries <uid> --limit 3\n")
        list_content_types(base_url, headers)
