"""Discover Contentstack content types, schemas, and sample entries."""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from .config import load_config


def _headers(project_root) -> dict:
    load_dotenv(Path(project_root) / ".env")
    api_key = os.getenv("MSTR_API_KEY")
    if not api_key:
        print("❌ MSTR_API_KEY not set in .env")
        return None
    return {"x-mstr-key": api_key, "Content-Type": "application/json"}


def _base_url(project_root) -> str:
    config = load_config(Path(project_root) / "config.yaml")
    return config.get("api", {}).get("base_url", "").rstrip("/")


def list_content_types(base_url: str, headers: dict):
    """List all content types. Useful for finding the whitepaper UID."""
    url = f"{base_url}/content_types"
    print(f"\nGET {url}\n")
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:500]}")
        return

    data = response.json()
    types = data.get("content_types", [])
    if not types:
        print("No content types returned. Full response:")
        print(json.dumps(data, indent=2))
        return

    print(f"{'UID':<40} {'Title'}")
    print("-" * 70)
    for content_type in sorted(types, key=lambda item: item.get("uid", "")):
        print(f"{content_type.get('uid', '?'):<40} {content_type.get('title', '?')}")

    print(f"\nTotal: {len(types)} content types")
    print(
        "\nLook for anything containing 'white', 'paper', 'resource', "
        "'asset', or 'content'."
    )


def inspect_content_type(base_url, content_type_uid, headers, project_root=None):
    """Print the full schema for a content type, including nested fields."""
    url = f"{base_url}/content_types/{content_type_uid}"
    print(f"\nGET {url}\n")
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:500]}")
        return

    data = response.json()
    content_type = data.get("content_type", data)
    schema = content_type.get("schema", [])

    print(
        f"Content Type: {content_type.get('title', '?')} "
        f"(uid: {content_type.get('uid', '?')})"
    )
    print(f"Description: {content_type.get('description', '(none)')}")
    print(f"\nField Schema ({len(schema)} top-level fields):")
    print("-" * 70)
    _print_schema(schema, indent=0)

    root = Path(project_root) if project_root is not None else Path.cwd()
    out_path = root / "output" / f"schema_{content_type_uid}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2, ensure_ascii=False)
    print(f"\n✓ Full schema saved to: output/schema_{content_type_uid}.json")


def _print_schema(fields: list, indent: int):
    prefix = "  " * indent
    for field in fields:
        if not isinstance(field, dict):
            continue
        uid = field.get("uid", "?")
        display = field.get("display_name", "")
        actual_type = field.get("data_type", "?")
        flags = []
        if field.get("multiple", False):
            flags.append("multiple")
        if field.get("mandatory", False):
            flags.append("required")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{prefix}• {uid:<35} {actual_type:<20} {display}{flag_str}")

        sub_fields = field.get("blocks", field.get("schema", field.get("fields", [])))
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
                        print(
                            f"{prefix}  ↳ {block_uid}: "
                            f"{block.get('data_type', '?')} {block_title}"
                        )


def fetch_entries(
    base_url, content_type_uid, headers, limit=3, project_root=None
):
    """Fetch a few live entries to see the real payload shape."""
    url = f"{base_url}/entries/{content_type_uid}?limit={limit}"
    print(f"\nGET {url}\n")
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:500]}")
        return

    data = response.json()
    entries = data.get("entries", [])
    if not entries:
        print("No entries returned. Full response:")
        print(json.dumps(data, indent=2)[:2000])
        return

    print(
        f"Found {len(entries)} entries "
        f"(showing first {min(limit, len(entries))}):\n"
    )
    for entry in entries[:limit]:
        print(f"  UID: {entry.get('uid', '?')}")
        print(f"  Title: {entry.get('title', '?')}")
        print(f"  URL: {entry.get('url', '?')}")
        print(f"  Fields: {', '.join(sorted(entry.keys()))}")
        print()

    root = Path(project_root) if project_root is not None else Path.cwd()
    out_path = root / "output" / f"sample_entry_{content_type_uid}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as output_file:
        json.dump(entries[0], output_file, indent=2, ensure_ascii=False)
    print(f"✓ First entry saved to: output/sample_entry_{content_type_uid}.json")


def fetch_entry_by_uid(
    base_url, content_type_uid, entry_uid, headers, project_root=None
):
    """Fetch a specific entry by UID to inspect its full structure."""
    url = f"{base_url}/entries/{content_type_uid}/{entry_uid}"
    print(f"\nGET {url}\n")
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:500]}")
        return

    data = response.json()
    root = Path(project_root) if project_root is not None else Path.cwd()
    out_path = root / "output" / f"entry_{entry_uid}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2, ensure_ascii=False)
    print(f"✓ Entry saved to: output/entry_{entry_uid}.json")
    entry = data.get("entry", data)
    print(f"Fields: {', '.join(sorted(entry.keys()))}")


def main(project_root, argv=None) -> int:
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
    parser.add_argument(
        "--type", metavar="UID", help="Inspect schema for a specific content type UID"
    )
    parser.add_argument(
        "--entries", metavar="UID", help="Fetch sample entries for a content type UID"
    )
    parser.add_argument(
        "--limit", type=int, default=3, help="Number of entries to fetch (default: 3)"
    )
    parser.add_argument(
        "--entry",
        nargs=2,
        metavar=("TYPE_UID", "ENTRY_UID"),
        help="Fetch a specific entry by UID",
    )
    args = parser.parse_args(argv)

    root = Path(project_root)
    headers = _headers(root)
    if headers is None:
        return 1
    base_url = _base_url(root)
    print(f"API base: {base_url}")

    if args.list_types:
        list_content_types(base_url, headers)
    elif args.type:
        inspect_content_type(base_url, args.type, headers, project_root=root)
    elif args.entries:
        fetch_entries(
            base_url, args.entries, headers, limit=args.limit, project_root=root
        )
    elif args.entry:
        fetch_entry_by_uid(
            base_url, args.entry[0], args.entry[1], headers, project_root=root
        )
    else:
        print("No flag provided — defaulting to --list-types")
        print("Once you identify the whitepaper content type UID, run:")
        print("  python scripts/discover_schema.py --type <uid>")
        print("  python scripts/discover_schema.py --entries <uid> --limit 3\n")
        list_content_types(base_url, headers)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path.cwd()))
