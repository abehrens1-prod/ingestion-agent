"""
run_pipeline.py — Orchestrate the full whitepaper ingestion pipeline.

Steps:
    1. parse_document.py       → tagged plaintext (internal)
    2. parse_with_claude.py    → <slug>/normalized_whitepaper.json
    3. map_to_contentstack.py  → <slug>/contentstack_entry.json
    4. validate               → <slug>/validation_report.md
    5. upload (optional, --upload) → upload_response.json
       publish (optional, --publish) → published to stage

Output folder is auto-named from the whitepaper slug unless --output-dir is given.

Usage:
    python scripts/run_pipeline.py input/whitepaper.pdf
    python scripts/run_pipeline.py input/whitepaper.pdf --upload
    python scripts/run_pipeline.py input/whitepaper.pdf --upload --publish
    python scripts/run_pipeline.py input/whitepaper.docx --output-dir output/my-whitepaper
"""

import sys
import json
import shutil
import logging
import argparse
import traceback
from datetime import date
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _import_script(name: str):
    import importlib.util
    scripts_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, scripts_dir / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _derive_output_dir(normalized: dict) -> Path:
    slug = normalized.get("slug") or "whitepaper"
    today = date.today().strftime("%Y-%m-%d")
    return Path("output") / f"{today}_{slug}"


def _print_entry_review(entry_path: Path):
    """Print a human-readable design review of the generated entry JSON."""
    with open(entry_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    e = data.get("entry", {})
    blocks = e.get("content_blocks", [])

    print("\n" + "─" * 60)
    print("  ENTRY REVIEW — verify before uploading")
    print("─" * 60)
    print(f"  Title : {e.get('title', '')}")
    print(f"  URL   : {e.get('url', '')}")
    print(f"  Blocks: {len(blocks)}")
    print()

    for b in blocks:
        sec = b.get("section")
        if not sec:
            continue
        sid = sec.get("section_id", "?")
        bg = sec.get("more_section_options", {}).get("bg_color", "?")
        ncols = len(sec.get("columns", []))
        sh = sec.get("section_header", [])

        if sid == "hero":
            # Show section_header content
            header_types = []
            if sh:
                kids = sh[0].get("text", {}).get("text_content", {}).get("children", [])
                header_types = [f"{k['type']}({k.get('children', [{}])[0].get('text', '')[:30]})" for k in kids]
            brief_col = sec["columns"][0]["mod_column"] if sec.get("columns") else {}
            has_box = bool(brief_col.get("accent_box_options"))
            print(f"  [hero]  bg={bg}  section_header: {header_types}")
            print(f"          The Brief: accent_box={'✓ Orange outlined' if has_box else '✗ MISSING'}  {ncols} col(s)")
        elif sid == "cta":
            print(f"  [cta]   bg={bg} ✓")
        else:
            col_names = [c["mod_column"]["column_name"] for c in sec.get("columns", []) if "mod_column" in c]
            has_divider = any(
                "divider" in item
                for c in sec.get("columns", [])[:1]
                for item in c.get("mod_column", {}).get("content", [])
            )
            print(f"  [{sid[:40]}]  {ncols} col(s)  divider={'✓' if has_divider else '─'}  cols: {col_names[:4]}")

    print()
    # Design spec spot-check
    hero_sec = next((b["section"] for b in blocks if b.get("section", {}).get("section_id") == "hero"), None)
    if hero_sec and hero_sec.get("section_header"):
        kids = hero_sec["section_header"][0].get("text", {}).get("text_content", {}).get("children", [])
        h1_color = kids[0].get("children", [{}])[0].get("attrs", {}).get("style", {}).get("color", "?") if kids else "?"
        h3_color = kids[1].get("children", [{}])[0].get("attrs", {}).get("style", {}).get("color", "?") if len(kids) > 1 else "?"
        p_color  = kids[2].get("children", [{}])[0].get("attrs", {}).get("style", {}).get("color", "?") if len(kids) > 2 else "?"
        print(f"  Design colors:  H1={h1_color}  H3={h3_color}  desc={p_color}")

    body_sections = [b["section"] for b in blocks if b.get("section", {}).get("section_id") not in ("hero", "cta")]
    if body_sections:
        first_sub = body_sections[0].get("columns", [{}])[1].get("mod_column", {}) if len(body_sections[0].get("columns", [])) > 1 else {}
        if first_sub:
            h3_node = first_sub.get("content", [{}])[0].get("text", {}).get("text_block", {}).get("children", [{}])[0]
            h3_color = h3_node.get("children", [{}])[0].get("attrs", {}).get("style", {}).get("color", "?") if h3_node else "?"
            h3_bold = h3_node.get("children", [{}])[0].get("bold", False) if h3_node else False
            print(f"                  H3 subsection={h3_color}  bold={h3_bold}")

    print(f"\n  File: {entry_path}")
    print("─" * 60)
    print("  Review the file above, then upload when ready.")
    print("─" * 60 + "\n")


def _write_failure_report(report_path: Path, step: str, error: str):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Validation Report\n\n## Pipeline Failure\n\n**Step:** {step}\n\n**Error:**\n```\n{error}\n```\n")


def run_pipeline(
    file_path: str,
    config_path: str = "config.yaml",
    output_dir: str = None,
    upload: bool = False,
    publish: bool = False,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")

    file_path = str(Path(file_path).resolve())
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
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

    # Warn if content type UID not yet configured
    ct_uid = config.get("contentstack", {}).get("content_type_uid", "")
    if "UNKNOWN" in ct_uid or not ct_uid:
        logger.warning("content_type_uid not set in config.yaml — run discover_schema.py first")
        if upload:
            logger.error("Cannot upload without a valid content_type_uid. Aborting.")
            return 1

    auto_name = output_dir is None
    staging_dir = Path("output") / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    total_steps = 5 if upload else 4

    print("\n" + "=" * 60)
    print("Whitepaper Ingestion Pipeline")
    print(f"  Input: {file_path}")
    print("=" * 60 + "\n")

    # ----------------------------------------------------------------
    # Step 1: Parse + normalize with Claude
    # ----------------------------------------------------------------
    print(f"Step 1/{total_steps}: Parsing and normalizing with Claude...")
    normalized_path = staging_dir / "normalized_whitepaper.json"
    try:
        parse_mod = _import_script("parse_with_claude")
        normalized = parse_mod.main(file_path, str(normalized_path), config)
        normalized["_source_file"] = Path(file_path).name
        print(f"  ✓ Title: {normalized.get('title', '(none)')[:60]}")
        print(f"  ✓ Brief bullets: {len(normalized.get('brief', []))}")
        print(f"  ✓ Sections: {len(normalized.get('body', []))}")
        if normalized.get("validationWarnings"):
            print(f"  ⚠ Warnings: {len(normalized['validationWarnings'])}")
    except Exception as e:
        logger.error(f"Parse step failed: {e}")
        traceback.print_exc()
        shutil.rmtree(staging_dir, ignore_errors=True)
        _write_failure_report(Path("output") / "parse_failure_report.md", "Parse step", str(e))
        return 1

    # Resolve output dir
    if auto_name:
        output_dir = _derive_output_dir(normalized)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_normalized = output_dir / "normalized_whitepaper.json"
    shutil.move(str(normalized_path), str(final_normalized))
    try:
        staging_dir.rmdir()
    except OSError:
        pass

    # Re-write with _source_file stamped in
    with open(final_normalized, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    # Copy source document into the output folder
    source_dest = output_dir / Path(file_path).name
    if not source_dest.exists():
        shutil.copy2(file_path, source_dest)

    entry_path = output_dir / "contentstack_entry.json"
    report_path = output_dir / "validation_report.md"
    print(f"  ✓ Output: {output_dir}/")

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
        mapping_warns = entry.get("_mapping_warnings", [])
        if mapping_warns:
            print(f"  ⚠ Mapping warnings: {len(mapping_warns)}")
    except Exception as e_:
        logger.error(f"Mapping step failed: {e_}")
        traceback.print_exc()
        _write_failure_report(report_path, "Mapping step", str(e_))
        return 1

    # Review print — always shown after mapping so user can verify before uploading
    _print_entry_review(entry_path)

    # ----------------------------------------------------------------
    # Step 3: Validate
    # ----------------------------------------------------------------
    print(f"\nStep 3/{total_steps}: Validating...")
    try:
        validate_mod = _import_script("validate_whitepaper_json")
        results = validate_mod.validate_all(normalized, entry, config)
        validate_mod.write_report(results, str(report_path), normalized=normalized, entry_json=entry)
        errors = sum(1 for r in results if r.level == "ERROR")
        warns = sum(1 for r in results if r.level == "WARN")
        passes = sum(1 for r in results if r.level == "PASS")
        print(f"  ✓ {passes} passed, {warns} warnings, {errors} errors")
        if errors:
            print(f"  ❌ Errors found — review {report_path} before uploading")
    except Exception as e_:
        logger.warning(f"Validation failed (non-fatal): {e_}")
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
    for f in [final_normalized, entry_path, report_path]:
        exists = "✓" if Path(f).exists() else "✗"
        print(f"  {exists} {f.name}")
    if upload:
        response_path = output_dir / "upload_response.json"
        exists = "✓" if response_path.exists() else "✗"
        print(f"  {exists} upload_response.json")
    if entry_uid:
        print(f"  Entry UID: {entry_uid}")
    if published:
        print("  Published: https://stage.strategysoftware.com")
    print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full whitepaper ingestion pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_pipeline.py input/whitepaper.pdf
  python scripts/run_pipeline.py input/whitepaper.pdf --upload
  python scripts/run_pipeline.py input/whitepaper.pdf --upload --publish
  python scripts/run_pipeline.py input/whitepaper.docx --output-dir output/my-whitepaper
        """,
    )
    parser.add_argument("file_path", help="Path to input .pdf or .docx whitepaper")
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--output-dir", "-o", default=None)
    parser.add_argument("--upload", action="store_true", help="Upload to Contentstack after validation")
    parser.add_argument("--publish", action="store_true", help="Publish to stage after upload (implies --upload)")
    args = parser.parse_args()

    exit_code = run_pipeline(
        file_path=args.file_path,
        config_path=args.config,
        output_dir=args.output_dir,
        upload=args.upload or args.publish,
        publish=args.publish,
    )
    sys.exit(exit_code)
