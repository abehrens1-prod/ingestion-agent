"""
upload_assets.py — Upload image and video files to Contentstack Assets via the
MicroStrategy API proxy, using the same corrected multipart shape as the Blog Ingestion
Agent's version (2026-08-27: POST, multipart/form-data with a single "body" field
holding the file).

Video support (2026-08-27): Blog Ingestion Agent's own upload_assets.py is hardcoded to
images only — it extracts inline pictures from a .docx via Word's <a:blip r:embed> XML,
which is not how video ever gets into a .docx, and its content-type map has no video
extensions. That's a code restriction, not a Contentstack one — the Assets API itself is
file-type agnostic. This version isn't docx-driven (glossary sources are mostly URLs,
not embedded Word images — see input/sources/<slug>/), so it never had that restriction
baked in structurally; it just needed video extensions added to the content-type map.

Wired in (2026-08-27): normalized_glossary.schema.json now allows "image" and "video"
block types (each with sourcePath/assetUid/altText/caption/url), and
map_to_contentstack.py's block handler builds a real embedded-asset RTE node
(rte_builder.img_node / video_node) when assetUid is set, falling back to a
[PLACEHOLDER] callout otherwise. This script closes the loop: point it at a directory of
loose image/video files, it uploads each one, and — if given --normalized — patches the
resulting assetUid back into the matching block (matched by sourcePath == filename).

Convention: drop files for a term's page in input/sources/<slug>/assets/, add
image/video blocks referencing them by filename in normalized_glossary.json's
sections[].blocks[] (sourcePath: "<filename>", assetUid: ""), then run:

    python scripts/upload_assets.py input/sources/<slug>/assets/ \\
        --normalized output/<date>_<slug>/normalized_glossary.json

and re-run map_to_contentstack.py to pick up the real embeds.

STILL UNCONFIRMED: config.yaml's api.assets_url is blank — no glossary/page assets
folder endpoint has been requested from or confirmed by Dale (ITS) the way the blog
one was. Ask before relying on this for a real upload. Video asset embedding in the RTE
(rte_builder.video_node, asset-type: "video") is also unconfirmed against a real upload
— verify the first time a video actually goes through this.

Usage (standalone):
    python scripts/upload_assets.py input/sources/semantic-layer/assets/
    python scripts/upload_assets.py input/sources/semantic-layer/assets/ --dry-run
    python scripts/upload_assets.py input/sources/semantic-layer/assets/ --output output/2026-08-25_semantic-layer/asset_uids.json
    python scripts/upload_assets.py input/sources/semantic-layer/assets/ --normalized output/2026-08-25_semantic-layer/normalized_glossary.json

Requires: MSTR_API_KEY in .env
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ingestion_common.config import load_config
from ingestion_common.console import enable_utf8

enable_utf8()

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_CONTENT_TYPE_MAP = {
    # Images
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    # Video
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "m4v": "video/x-m4v",
    "avi": "video/x-msvideo",
}

_VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "m4v", "avi"}


def _guess_content_type(path: Path) -> str:
    return _CONTENT_TYPE_MAP.get(path.suffix.lstrip(".").lower(), "application/octet-stream")


def _asset_kind(path: Path) -> str:
    return "video" if path.suffix.lstrip(".").lower() in _VIDEO_EXTENSIONS else "image"


def _patch_normalized(normalized_path: Path, uid_map: dict) -> int:
    """Patch assetUid into any image/video block whose sourcePath matches an uploaded
    filename. Matches Blog Ingestion Agent's _patch_normalized behavior, adapted to this
    project's sections[].blocks[] shape (no top-level heroMedia block here)."""
    data = json.loads(normalized_path.read_text(encoding="utf-8"))
    patched = 0
    for section in data.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("type") in ("image", "video"):
                source = block.get("sourcePath")
                if source and source in uid_map and not block.get("assetUid"):
                    block["assetUid"] = uid_map[source]
                    patched += 1
    if patched:
        normalized_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return patched


def upload_assets(
    media_dir: str,
    config: dict = None,
    config_path: str = "config.yaml",
    dry_run: bool = False,
) -> dict:
    """Upload every image/video file directly inside media_dir to Contentstack Assets.

    Returns {filename: asset_uid} for all successfully uploaded files.
    """
    if config is None:
        config = load_config(config_path, project_root=PROJECT_ROOT)

    media_path = Path(media_dir)
    if not media_path.is_dir():
        raise FileNotFoundError(f"Not a directory: {media_dir}")

    files = sorted(
        p for p in media_path.iterdir()
        if p.is_file() and p.suffix.lstrip(".").lower() in _CONTENT_TYPE_MAP
    )
    if not files:
        print(f"  No image/video files found in {media_dir} — nothing to upload.")
        return {}

    print(f"Found {len(files)} file(s): {', '.join(f'{p.name} ({_asset_kind(p)})' for p in files)}")

    if dry_run:
        print(f"[Dry run] Would upload: {', '.join(str(p) for p in files)}")
        return {}

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("MSTR_API_KEY")
    if not api_key:
        raise ValueError("MSTR_API_KEY is not set. Add it to .env:\n  MSTR_API_KEY=<your-key>")

    assets_url = config.get("api", {}).get("assets_url", "").strip()
    if not assets_url:
        raise ValueError(
            "api.assets_url is not set in config.yaml — no confirmed glossary/page "
            "assets endpoint exists yet. Ask Dale (ITS) for one before uploading."
        )

    auth_headers = {"x-mstr-key": api_key}
    uid_map = {}

    for file_path in files:
        kind = _asset_kind(file_path)
        print(f"  Uploading {file_path.name} ({kind})...")
        try:
            with open(file_path, "rb") as f:
                ct = _guess_content_type(file_path)
                r = requests.post(
                    assets_url,
                    headers=auth_headers,
                    files={"body": (file_path.name, f, ct)},
                    timeout=120 if kind == "video" else 60,
                )

            if r.status_code not in (200, 201):
                print(f"  ❌ Upload failed (HTTP {r.status_code}): {r.text[:300]}")
                continue

            resp_json = r.json()
            # Response shape is unconfirmed for this endpoint — try the common spots
            # (top-level, or nested under "asset") before giving up.
            asset = resp_json.get("asset", resp_json) if isinstance(resp_json, dict) else {}
            asset_uid = asset.get("uid")

            if not asset_uid:
                print(f"  ❌ No UID found in response — check response shape: {r.text[:300]}")
                continue

            uid_map[file_path.name] = asset_uid
            print(f"  ✓ {file_path.name} → {asset_uid}")

        except Exception as e:
            print(f"  ❌ Error uploading {file_path.name}: {e}")

    if not uid_map:
        print("  No assets uploaded successfully.")

    return uid_map


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Upload image and video files to Contentstack Assets, optionally patching the result into a normalized_glossary.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/upload_assets.py input/sources/semantic-layer/assets/
  python scripts/upload_assets.py input/sources/semantic-layer/assets/ --dry-run
  python scripts/upload_assets.py input/sources/semantic-layer/assets/ --normalized output/2026-08-25_semantic-layer/normalized_glossary.json
        """,
    )
    parser.add_argument("media_dir", help="Directory containing image/video files to upload")
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--output", "-o", default=None, help="Optional path to save the {filename: asset_uid} map as JSON")
    parser.add_argument("--normalized", "-n", default=None, help="Path to a normalized_glossary.json to patch assetUid into, matched by sourcePath == filename")
    parser.add_argument("--dry-run", action="store_true", help="List files but don't upload")
    args = parser.parse_args()

    try:
        result = upload_assets(
            media_dir=args.media_dir,
            config_path=args.config,
            dry_run=args.dry_run,
        )
        if args.output and result:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"  ✓ UID map saved: {args.output}")
        if args.normalized and result:
            normalized_path = Path(args.normalized)
            if not normalized_path.exists():
                print(f"  ⚠ --normalized path not found, skipping patch: {normalized_path}")
            else:
                patched = _patch_normalized(normalized_path, result)
                print(f"  ✓ Patched {patched} block(s) in {normalized_path.name} — re-run map_to_contentstack.py to pick up the changes.")
        print(f"\nDone. {len(result)} asset(s) uploaded.")
        sys.exit(0)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
