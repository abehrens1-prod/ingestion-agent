"""
run_pipeline.py — Orchestrate the full blog ingestion pipeline.

Steps:
    1. parse_with_claude.py  → <author>-blog-post-<date>/normalized_blog.json
    2. map_to_contentstack   → <author>-blog-post-<date>/contentstack_entry.json
    3. validate_blog_json    → <author>-blog-post-<date>/validation_report.md
    4. upload_to_contentstack (optional, --upload) → upload_response.json
       publish (optional, --publish) → published to stage

Output folder is auto-named from the parsed author and publish date unless
--output-dir is given explicitly.

Requires: ANTHROPIC_API_KEY environment variable.
          MSTR_API_KEY environment variable (for --upload).

Usage:
    # From the blog-ingestion-automation/ directory:
    python scripts/run_pipeline.py input/blog.docx
    python scripts/run_pipeline.py input/blog.docx --upload
    python scripts/run_pipeline.py input/blog.docx --upload --publish
    python scripts/run_pipeline.py input/blog.docx --config config.yaml --output-dir output/my-blog
"""

import re
import sys
import json
import shutil
import logging
import argparse
import traceback
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _date_slug(date_str: str) -> str:
    """Convert 'May 2026', '2026-05-01', etc. → 'YYYY-MM'."""
    s = (date_str or "").strip()
    m = re.match(r'([a-zA-Z]+)\s+(\d{4})', s)
    if m:
        return f"{m.group(2)}-{_MONTH_MAP.get(m.group(1).lower(), '01')}"
    m = re.match(r'(\d{4})\s+([a-zA-Z]+)', s)
    if m:
        return f"{m.group(1)}-{_MONTH_MAP.get(m.group(2).lower(), '01')}"
    m = re.match(r'(\d{4})-(\d{2})', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s or "unknown-date"


def _derive_output_dir(normalized: dict) -> Path:
    author = normalized.get("author", "unknown") or "unknown"
    author_slug = re.sub(r'[^a-z0-9]+', '-', author.lower()).strip('-') or "unknown"
    folder = f"{author_slug}-blog-post-{_date_slug(normalized.get('publishDate', ''))}"
    return Path("output") / folder


def _import_script(name: str):
    import importlib.util
    scripts_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, scripts_dir / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_pipeline(
    docx_path: str,
    config_path: str = "config.yaml",
    output_dir: str = None,
    upload: bool = False,
    publish: bool = False,
    locale: str = None,
) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    docx_path = str(Path(docx_path).resolve())
    if not Path(docx_path).exists():
        logger.error(f"File not found: {docx_path}")
        return 1

    config_path_resolved = Path(config_path)
    if not config_path_resolved.is_absolute():
        config_path_resolved = Path.cwd() / config_path
    if not config_path_resolved.exists():
        config_path_resolved = Path(__file__).parent.parent / config_path
    if not config_path_resolved.exists():
        logger.error(f"Config not found: {config_path}")
        return 1

    with open(config_path_resolved, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    auto_name = output_dir is None
    staging_dir = Path("output") / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    normalized_path = staging_dir / "normalized_blog.json"

    total_steps = 4 if upload else 3

    print("\n" + "=" * 60)
    print("Blog Ingestion Pipeline")
    print(f"  Input:  {docx_path}")
    print("=" * 60 + "\n")

    # ----------------------------------------------------------------
    # Step 1: Parse + normalize with Claude
    # ----------------------------------------------------------------
    print(f"Step 1/{total_steps}: Parsing and normalizing with Claude...")
    try:
        parse_mod = _import_script("parse_with_claude")
        normalized = parse_mod.main(docx_path, str(normalized_path), config, locale=locale)
        normalized["_source_file"] = Path(docx_path).name
        print(f"  ✓ Title: {normalized.get('title', '(none)')[:60]}")
        print(f"  ✓ Sections: {len(normalized.get('body', []))}")
        print(f"  ✓ FAQ items: {len(normalized.get('faq', []))}")
        print(f"  ✓ CTA: {'Yes' if normalized.get('cta_list') else 'No'}")
        print(f"  ✓ Meta description: {'Yes' if normalized.get('seo', {}).get('metaDescription') else 'No'}")
        if normalized.get("validationWarnings"):
            print(f"  ⚠ Warnings: {len(normalized['validationWarnings'])}")
    except Exception as e:
        logger.error(f"Parse step failed: {e}")
        traceback.print_exc()
        shutil.rmtree(staging_dir, ignore_errors=True)
        _write_failure_report(Path("output") / "parse_failure_report.md", "Parse step", str(e))
        return 1

    # Resolve final output dir (auto-named or explicit)
    if auto_name:
        output_dir = _derive_output_dir(normalized)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Move normalized file from staging to final dir
    final_normalized = output_dir / "normalized_blog.json"
    shutil.move(str(normalized_path), str(final_normalized))
    try:
        staging_dir.rmdir()
    except OSError:
        pass

    normalized_path = final_normalized

    # Re-write with _source_file stamped in (move copied the pre-stamp version)
    with open(normalized_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    # Write a visible marker so the output folder is self-describing
    (output_dir / "_source.txt").write_text(Path(docx_path).name, encoding="utf-8")

    entry_path = output_dir / "contentstack_entry.json"
    report_path = output_dir / "validation_report.md"
    print(f"  ✓ Output: {output_dir}/")

    # ----------------------------------------------------------------
    # Step 1b: Extract and upload embedded images
    # Skipped if api.assets_url is not configured or MSTR_API_KEY is missing.
    # ----------------------------------------------------------------
    assets_url_configured = bool(
        config.get("api", {}).get("assets_url", "").strip()
    )
    if assets_url_configured:
        try:
            upload_assets_mod = _import_script("upload_assets")
            uid_map = upload_assets_mod.upload_assets(
                output_dir=str(output_dir),
                docx_path=docx_path,
                config=config,
            )
            if uid_map:
                # Re-read normalized with patched UIDs before mapping
                normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
        except Exception as e_:
            logger.warning(f"Asset upload step failed: {e_}")
            print(f"  ⚠ Asset upload failed (continuing): {e_}")
    else:
        print("  ℹ Asset upload skipped — set api.assets_url in config.yaml to enable")

    # ----------------------------------------------------------------
    # Step 2: Map to Contentstack
    # ----------------------------------------------------------------
    print(f"\nStep 2/{total_steps}: Mapping to Contentstack entry format...")
    try:
        map_mod = _import_script("map_to_contentstack")
        entry = map_mod.map_normalized_to_entry(normalized, config)
        with open(entry_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        e = entry.get("entry", {})
        print(f"  ✓ Entry URL: {e.get('url', '(none)')}")
        body_field = config.get("contentstack", {}).get("field_map", {}).get("body", "body")
        body_val = e.get(body_field)
        if isinstance(body_val, list):
            print(f"  ✓ Body nodes: {len(body_val)}")
        mapping_warns = e.get("_mapping_warnings", [])
        if mapping_warns:
            print(f"  ⚠ Mapping warnings: {len(mapping_warns)}")
    except Exception as e_:
        logger.error(f"Mapping step failed: {e_}")
        traceback.print_exc()
        _write_failure_report(report_path, "Mapping step", str(e_))
        return 1

    # ----------------------------------------------------------------
    # Step 3: Validate
    # ----------------------------------------------------------------
    print(f"\nStep 3/{total_steps}: Validating...")
    try:
        validate_mod = _import_script("validate_blog_json")
        results = validate_mod.validate_all(normalized, entry, config)
        validate_mod.write_report(results, str(report_path), normalized=normalized, entry_json=entry)
        errors = sum(1 for r in results if r.level == "ERROR")
        warns = sum(1 for r in results if r.level == "WARN")
        passes = sum(1 for r in results if r.level == "PASS")
        print(f"  ✓ {passes} passed, {warns} warnings, {errors} errors")
        if errors:
            print(f"  ❌ Errors found — review {report_path} before uploading")
    except Exception as e_:
        logger.warning(f"Validation step failed (non-fatal): {e_}")
        print(f"  ⚠ Validation failed (continuing): {e_}")
        errors = 0

    # ----------------------------------------------------------------
    # Step 4: Upload to Contentstack (optional)
    # ----------------------------------------------------------------
    entry_uid = None
    published = False
    if upload:
        print(f"\nStep 4/{total_steps}: Uploading to Contentstack...")
        try:
            upload_mod = _import_script("upload_to_contentstack")
            result = upload_mod.upload_entry(
                entry_file=str(entry_path),
                config=config,
                publish=publish,
            )
            entry_uid = result.get("entry_uid")
            published = result.get("published", False)
        except Exception as e_:
            logger.error(f"Upload step failed: {e_}")
            traceback.print_exc()
            return 1

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"Pipeline complete → {output_dir}/")
    output_files = [normalized_path, entry_path, report_path]
    response_path = output_dir / "upload_response.json"
    if upload:
        output_files.append(response_path)
    for f in output_files:
        exists = "✓" if Path(f).exists() else "✗"
        print(f"  {exists} {f.name}")
    if entry_uid:
        print(f"  Entry UID: {entry_uid}")
    if published:
        print(f"  Published: https://stage.strategysoftware.com")
    print("=" * 60)

    return 1 if errors else 0


def _write_failure_report(report_path: Path, step: str, error: str):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Validation Report\n\n## Pipeline Failure\n\n**Step:** {step}\n\n**Error:**\n```\n{error}\n```\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full blog ingestion pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_pipeline.py input/blog.docx
  python scripts/run_pipeline.py input/blog.docx --upload
  python scripts/run_pipeline.py input/blog.docx --upload --publish
  python scripts/run_pipeline.py input/blog.docx --output-dir output/my-blog
        """,
    )
    parser.add_argument("docx_path", help="Path to input .docx file")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--output-dir", "-o", default=None, help="Output directory (default: auto-named output/[author]-blog-post-[date])")
    parser.add_argument("--upload", action="store_true", help="Upload the entry to Contentstack after validation (requires MSTR_API_KEY)")
    parser.add_argument("--publish", action="store_true", help="Publish the entry to stage after upload (implies --upload)")
    parser.add_argument("--locale", default=None, help="Locale code (e.g. es, fr) — defaults to contentstack.default_locale in config.yaml")
    args = parser.parse_args()

    exit_code = run_pipeline(
        docx_path=args.docx_path,
        config_path=args.config,
        output_dir=args.output_dir,
        upload=args.upload or args.publish,
        publish=args.publish,
        locale=args.locale,
    )
    sys.exit(exit_code)
