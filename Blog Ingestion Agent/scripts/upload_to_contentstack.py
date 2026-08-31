"""
upload_to_contentstack.py — Upload a Contentstack entry via the MicroStrategy API proxy.

Reads contentstack_entry.json, runs a pre-flight schema check, POSTs the entry,
and optionally publishes it to the stage environment.

Usage (standalone):
    python scripts/upload_to_contentstack.py output/contentstack_entry.json
    python scripts/upload_to_contentstack.py output/henry-guo-blog-post-2026-05/contentstack_entry.json --publish
    python scripts/upload_to_contentstack.py output/contentstack_entry.json --dry-run

Requires: MSTR_API_KEY in .env
"""

import os
import sys

if sys.platform == "win32":
    # Native Windows consoles default to a legacy codepage, not UTF-8 — without
    # this, the ✓/⚠/❌ status glyphs below crash with UnicodeEncodeError mid-run.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
import json
import logging
import argparse
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _find_config(config_path: str = "config.yaml") -> Path:
    p = Path(config_path)
    for base in [Path.cwd(), Path(__file__).parent.parent]:
        candidate = base / p if not p.is_absolute() else p
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Config not found: {config_path}")


def _load_config(config_path: str = "config.yaml") -> dict:
    with open(_find_config(config_path), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_headers() -> dict:
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("MSTR_API_KEY")
    if not api_key:
        raise ValueError(
            "MSTR_API_KEY is not set. Add it to .env:\n  MSTR_API_KEY=<your-key>"
        )
    return {
        "x-mstr-key": api_key,
        "Content-Type": "application/json",
    }


def _preflight_schema_check(base_url: str, content_type: str, entry_fields: set, headers: dict):
    """GET the live content type schema and warn on field name mismatches."""
    url = f"{base_url}/content_types/{content_type}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as e:
        print(f"  ⚠ Schema check skipped (request error: {e})")
        return

    if r.status_code != 200:
        print(f"  ⚠ Schema check skipped (HTTP {r.status_code})")
        return

    try:
        data = r.json()
        # Contentstack returns content_type.schema[] with uid per field
        schema = (
            data.get("content_type", {}).get("schema", [])
            or data.get("schema", [])
        )
        schema_uids = {f["uid"] for f in schema if isinstance(f, dict) and "uid" in f}
    except ValueError:
        print("  ⚠ Schema check skipped (response was not valid JSON)")
        return

    if not schema_uids:
        print("  ⚠ Schema check skipped (empty schema in response)")
        return

    unknown = entry_fields - schema_uids
    if unknown:
        print(f"  ⚠ Fields in payload not in schema: {', '.join(sorted(unknown))}")
    else:
        print(f"  ✓ All {len(entry_fields)} fields match schema ({len(schema_uids)} schema fields)")


def upload_entry(
    entry_file: str,
    config: dict = None,
    config_path: str = "config.yaml",
    publish: bool = False,
    dry_run: bool = False,
    entry_uid: str = None,
) -> dict:
    """Upload contentstack_entry.json and optionally publish.

    If entry_uid is provided, updates the existing entry via PUT instead of creating a new one.
    Returns dict with entry_uid, published, and response keys.
    """
    if config is None:
        config = _load_config(config_path)

    entry_path = Path(entry_file)
    if not entry_path.exists():
        raise FileNotFoundError(f"Entry file not found: {entry_file}")

    with open(entry_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    entry = payload.get("entry")
    warnings = payload.get("_mapping_warnings", [])

    if not entry:
        raise ValueError(f"No 'entry' key in {entry_file}. Expected {{\"entry\": {{...}}}}.")

    base_url = config.get("api", {}).get("base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("api.base_url is not set in config.yaml")

    content_type = config.get("contentstack", {}).get("content_type_uid", "blog_post")

    # Surface mapping warnings
    if warnings:
        print(f"\n⚠  {len(warnings)} mapping warning(s) from pipeline:")
        for w in warnings:
            print(f"   • {w}")

    if dry_run:
        print(f"\n[Dry run] Would POST to: {base_url}/entries/{content_type}")
        print(f"[Dry run] Entry title: {entry.get('title', '(none)')}")
        print(f"[Dry run] Entry fields: {', '.join(sorted(entry.keys()))}")
        return {"entry_uid": None, "published": False, "dry_run": True}

    headers = _build_headers()

    # Pre-flight schema check
    print(f"\nPre-flight: Checking schema for '{content_type}'...")
    _preflight_schema_check(base_url, content_type, set(entry.keys()), headers)

    # Locale: Contentstack's documented CMA contract takes this as a query param on
    # create/update (entry.locale in the body isn't necessarily enough on its own).
    # Unverified against a real non-"en" upload — this org's only confirmed locale
    # value in the wild so far is "en" (see live upload_response.json files).
    locale = entry.get("locale") or config.get("contentstack", {}).get("default_locale", "en")

    # Create or update entry
    print(f"\nUploading to Contentstack (content type: {content_type}, locale: {locale})...")
    if entry_uid:
        url = f"{base_url}/entries/{content_type}/{entry_uid}"
        print(f"  Updating existing entry: {entry_uid}")
        try:
            r = requests.put(url, headers=headers, params={"locale": locale}, json={"entry": entry}, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"Update request failed: {e}") from e
        action = "updated"
    else:
        url = f"{base_url}/entries/{content_type}"
        try:
            r = requests.post(url, headers=headers, params={"locale": locale}, json={"entry": entry}, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"Upload request failed: {e}") from e
        action = "created"

    if r.status_code not in (200, 201):
        print(f"  ❌ Upload failed (HTTP {r.status_code})")
        print(f"  Response: {r.text[:1000]}")
        raise RuntimeError(f"Entry {action} failed with HTTP {r.status_code}")

    response_data = r.json()
    created_entry = response_data.get("entry", response_data)
    entry_uid = created_entry.get("uid", entry_uid)
    entry_title = created_entry.get("title", entry.get("title", "(unknown)"))
    print(f"  ✓ Entry {action}: {entry_title}")
    print(f"  ✓ Entry UID: {entry_uid}")

    # Save API response
    response_path = entry_path.parent / "upload_response.json"
    with open(response_path, "w", encoding="utf-8") as f:
        json.dump(response_data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Response saved: {response_path.name}")

    # Publish
    published = False
    if publish:
        if not entry_uid:
            print("  ⚠ Cannot publish — no entry UID in response")
        else:
            print("\nPublishing to stage environment...")
            publish_url = f"{base_url}/entries/{content_type}/{entry_uid}/publish"
            try:
                rp = requests.post(publish_url, headers=headers, timeout=30)
            except requests.RequestException as e:
                print(f"  ⚠ Publish request failed: {e}")
            else:
                if rp.status_code in (200, 201):
                    print("  ✓ Published → https://stage.strategysoftware.com")
                    published = True
                else:
                    print(f"  ❌ Publish failed (HTTP {rp.status_code}): {rp.text[:500]}")

    return {"entry_uid": entry_uid, "published": published, "response": response_data}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(
        description="Upload a contentstack_entry.json to Contentstack via the MicroStrategy API proxy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/upload_to_contentstack.py output/contentstack_entry.json
  python scripts/upload_to_contentstack.py output/henry-guo-blog-post-2026-05/contentstack_entry.json --publish
  python scripts/upload_to_contentstack.py output/contentstack_entry.json --dry-run
        """,
    )
    parser.add_argument("entry_file", help="Path to contentstack_entry.json")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--publish", action="store_true", help="Publish the entry to stage after upload")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be sent without uploading")
    parser.add_argument("--entry-uid", default=None, help="Update an existing entry by UID instead of creating a new one")
    args = parser.parse_args()

    try:
        result = upload_entry(
            entry_file=args.entry_file,
            config_path=args.config,
            publish=args.publish,
            dry_run=args.dry_run,
            entry_uid=args.entry_uid,
        )
        if not args.dry_run:
            print(f"\n{'=' * 60}")
            print(f"Upload complete")
            print(f"  Entry UID: {result['entry_uid']}")
            print(f"  Published: {'Yes' if result['published'] else 'No'}")
            print(f"{'=' * 60}")
        sys.exit(0)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
