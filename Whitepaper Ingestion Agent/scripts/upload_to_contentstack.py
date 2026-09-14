"""Upload a Whitepaper Contentstack entry through the shared proxy client."""

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ingestion_common.config import load_config
from ingestion_common.console import enable_utf8
from ingestion_common.contentstack import upload_entry as shared_upload_entry

enable_utf8()


def upload_entry(
    entry_file: str,
    config: dict = None,
    config_path: str = "config.yaml",
    publish: bool = False,
    dry_run: bool = False,
    entry_uid: str = None,
) -> dict:
    """Upload a Whitepaper entry while preserving the pipeline's public interface."""
    if config is None:
        config = load_config(config_path, project_root=PROJECT_ROOT)
    content_type = config.get("contentstack", {}).get("content_type_uid", "page")
    return shared_upload_entry(
        entry_file,
        config=config,
        config_path=config_path,
        publish=publish,
        dry_run=dry_run,
        entry_uid=entry_uid,
        project_root=PROJECT_ROOT,
        content_type_uid=content_type,
        title_versioning=True,
        use_locale=False,
    )


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
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
    parser.add_argument(
        "--config", "-c", default="config.yaml", help="Path to config.yaml"
    )
    parser.add_argument(
        "--publish", action="store_true", help="Publish the entry to stage after upload"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be sent without uploading"
    )
    parser.add_argument(
        "--entry-uid",
        default=None,
        help="Update an existing entry by UID instead of creating a new one",
    )
    args = parser.parse_args(argv)

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
            print("Upload complete")
            print(f"  Entry UID: {result['entry_uid']}")
            print(f"  Published: {'Yes' if result['published'] else 'No'}")
            print(f"{'=' * 60}")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"\n❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
