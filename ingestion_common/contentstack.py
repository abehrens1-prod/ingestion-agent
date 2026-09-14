"""Shared Contentstack proxy behavior for ingestion pipelines."""

import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

from .config import load_config


UPDATE_UNSUPPORTED = (
    "Updating existing entries is not supported because the API proxy has no PUT endpoint. "
    "Create a new version instead. See "
    "Glossary Agent/docs/session_2026_06_16_mcp_v2_fixes.md."
)


def build_headers(project_root=None) -> dict:
    """Build authenticated proxy headers from the project's .env file."""
    root = Path(project_root) if project_root is not None else Path.cwd()
    load_dotenv(root / ".env")
    api_key = os.getenv("MSTR_API_KEY")
    if not api_key:
        raise ValueError(
            "MSTR_API_KEY is not set. Add it to .env:\n  MSTR_API_KEY=<your-key>"
        )
    return {
        "x-mstr-key": api_key,
        "Content-Type": "application/json",
    }


def preflight_schema_check(
    base_url: str, content_type: str, entry_fields, headers: dict
) -> None:
    """GET the live content type schema and warn on field name mismatches."""
    url = f"{base_url}/content_types/{content_type}"
    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as exc:
        print(f"  ⚠ Schema check skipped (request error: {exc})")
        return

    if response.status_code != 200:
        print(f"  ⚠ Schema check skipped (HTTP {response.status_code})")
        return

    try:
        data = response.json()
        schema = data.get("content_type", {}).get("schema", []) or data.get(
            "schema", []
        )
        schema_uids = {
            field["uid"]
            for field in schema
            if isinstance(field, dict) and "uid" in field
        }
    except ValueError:
        print("  ⚠ Schema check skipped (response was not valid JSON)")
        return

    if not schema_uids:
        print("  ⚠ Schema check skipped (empty schema in response)")
        return

    unknown = set(entry_fields) - schema_uids
    if unknown:
        print(f"  ⚠ Fields in payload not in schema: {', '.join(sorted(unknown))}")
    else:
        print(
            f"  ✓ All {len(entry_fields)} fields match schema "
            f"({len(schema_uids)} schema fields)"
        )


def publish_entry(
    base_url: str, content_type: str, entry_uid: str, headers: dict
) -> bool:
    """Publish an entry to the stage environment."""
    publish_url = f"{base_url}/entries/{content_type}/{entry_uid}/publish"
    try:
        response = requests.post(publish_url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        print(f"  ⚠ Publish request failed: {exc}")
        return False

    if response.status_code in (200, 201):
        print("  ✓ Published → https://stage.strategysoftware.com")
        return True

    print(
        f"  ❌ Publish failed (HTTP {response.status_code}): "
        f"{response.text[:500]}"
    )
    return False


def upload_entry(
    entry_file: str,
    config: dict = None,
    config_path: str = "config.yaml",
    publish: bool = False,
    dry_run: bool = False,
    entry_uid: str = None,
    project_root=None,
    content_type_uid: str = None,
    title_versioning: bool = False,
    use_locale: bool = False,
) -> dict:
    """Upload a mapped entry through the Contentstack proxy."""
    if entry_uid:
        raise RuntimeError(UPDATE_UNSUPPORTED)

    if config is None:
        config = load_config(config_path, project_root=project_root)

    entry_path = Path(entry_file)
    if not entry_path.exists():
        raise FileNotFoundError(f"Entry file not found: {entry_file}")

    with open(entry_path, "r", encoding="utf-8") as entry_file_handle:
        payload = json.load(entry_file_handle)

    entry = payload.get("entry")
    warnings = payload.get("_mapping_warnings", [])
    if not entry:
        raise ValueError(
            f"No 'entry' key in {entry_file}. Expected {{\"entry\": {{...}}}}."
        )

    base_url = config.get("api", {}).get("base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("api.base_url is not set in config.yaml")

    content_type = content_type_uid or config.get("contentstack", {}).get(
        "content_type_uid", "asset_page"
    )

    if warnings:
        print(f"\n⚠  {len(warnings)} mapping warning(s) from pipeline:")
        for warning in warnings:
            print(f"   • {warning}")

    if dry_run:
        print(f"\n[Dry run] Would POST to: {base_url}/entries/{content_type}")
        print(f"[Dry run] Entry title: {entry.get('title', '(none)')}")
        print(f"[Dry run] Entry fields: {', '.join(sorted(entry.keys()))}")
        return {"entry_uid": None, "published": False, "dry_run": True}

    headers = build_headers(project_root=project_root)
    print(f"\nPre-flight: Checking schema for '{content_type}'...")
    preflight_schema_check(base_url, content_type, set(entry.keys()), headers)

    request_kwargs = {"headers": headers, "json": {"entry": entry}, "timeout": 30}
    if use_locale:
        locale = entry.get("locale") or config.get("contentstack", {}).get(
            "default_locale", "en"
        )
        request_kwargs["params"] = {"locale": locale}
        print(
            f"\nUploading to Contentstack (content type: {content_type}, "
            f"locale: {locale})..."
        )
    else:
        print(f"\nUploading to Contentstack (content type: {content_type})...")

    url = f"{base_url}/entries/{content_type}"
    if title_versioning:
        response, versioned_title = _post_versioned_entry(url, entry, request_kwargs)
        if versioned_title is None:
            print(f"  ❌ Upload failed (HTTP {response.status_code})")
            print(f"  Response: {response.text[:1000]}")
            raise RuntimeError(
                f"Entry creation failed with HTTP {response.status_code}"
            )
        payload["entry"]["title"] = versioned_title
        with open(entry_path, "w", encoding="utf-8") as entry_file_handle:
            json.dump(payload, entry_file_handle, indent=2, ensure_ascii=False)
    else:
        try:
            response = requests.post(url, **request_kwargs)
        except requests.RequestException as exc:
            raise RuntimeError(f"Upload request failed: {exc}") from exc
        if response.status_code not in (200, 201):
            print(f"  ❌ Upload failed (HTTP {response.status_code})")
            print(f"  Response: {response.text[:1000]}")
            raise RuntimeError(
                f"Entry created failed with HTTP {response.status_code}"
            )

    response_data = response.json()
    created_entry = response_data.get("entry", response_data)
    uploaded_uid = created_entry.get("uid")
    entry_title = created_entry.get("title", entry.get("title", "(unknown)"))
    print(f"  ✓ Entry created: {entry_title}")
    print(f"  ✓ Entry UID: {uploaded_uid}")

    response_path = entry_path.parent / "upload_response.json"
    with open(response_path, "w", encoding="utf-8") as response_file:
        json.dump(response_data, response_file, indent=2, ensure_ascii=False)
    print(f"  ✓ Response saved: {response_path.name}")

    published = False
    if publish:
        if not uploaded_uid:
            print("  ⚠ Cannot publish — no entry UID in response")
        else:
            print("\nPublishing to stage environment...")
            published = publish_entry(
                base_url, content_type, uploaded_uid, headers
            )

    return {
        "entry_uid": uploaded_uid,
        "published": published,
        "response": response_data,
    }


def _post_versioned_entry(url, entry, request_kwargs):
    raw_title = entry.get("title", "")
    base_title = re.sub(r"^v\d+\s*(?:\||--)\s*", "", raw_title)
    base_title = re.sub(r"\s*\(v\d+(?:\s*-\s*[^)]*)?\)\s*$", "", base_title).strip()

    response = None
    for version in range(1, 20):
        candidate = f"v{version} | {base_title}"
        entry["title"] = candidate
        try:
            response = requests.post(url, **request_kwargs)
        except requests.RequestException as exc:
            raise RuntimeError(f"Upload request failed: {exc}") from exc
        if response.status_code in (200, 201):
            return response, candidate
        try:
            title_errors = response.json().get("errors", {}).get("title", [])
        except ValueError:
            title_errors = []
        if not isinstance(title_errors, list):
            title_errors = [title_errors]
        is_title_collision = response.status_code == 422 and any(
            isinstance(message, str)
            and ("not unique" in message.lower() or "already exists" in message.lower())
            for message in title_errors
        )
        if not is_title_collision:
            break
        print(f"  {candidate} — title taken, trying next version...")
    return response, None
