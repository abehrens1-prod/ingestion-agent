"""
upload_assets.py — Extract embedded images from a .docx and upload to Contentstack Assets.

Extracts images in document order (matching image_0, image_1, … naming Claude uses),
uploads each to Contentstack Assets via the MicroStrategy API proxy, then patches
assetUid back into normalized_blog.json so the mapping step picks them up automatically.

Usage (standalone):
    python scripts/upload_assets.py output/igor-freitas-blog-post-2026-06/ input/blog.docx
    python scripts/upload_assets.py output/my-blog/ input/blog.docx --dry-run

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
from docx import Document
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

_CONTENT_TYPE_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}

_EXT_FROM_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/tiff": "tif",
    "image/bmp": "bmp",
}


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


def _guess_content_type(path: Path) -> str:
    return _CONTENT_TYPE_MAP.get(path.suffix.lstrip(".").lower(), "image/png")


def extract_images(docx_path: str, output_dir: str) -> dict:
    """
    Extract embedded images from docx in document order.

    Returns a dict mapping canonical names (image_0.png, image_1.png, …) to the
    Path of the extracted file on disk. The canonical names match the sourcePath
    values Claude writes into normalized_blog.json.
    """
    doc = Document(docx_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    seen_rel_ids = []
    image_map = {}
    counter = 0

    for child in doc.element.body:
        for blip in child.findall(".//" + qn("a:blip")):
            rel_id = blip.get(qn("r:embed"))
            if not rel_id or rel_id in seen_rel_ids:
                continue
            seen_rel_ids.append(rel_id)

            try:
                rel = doc.part.rels.get(rel_id)
                if rel is None:
                    continue
                image_part = rel.target_part
                blob = image_part.blob
                ct = getattr(image_part, "content_type", "image/png")
                ext = _EXT_FROM_MIME.get(ct, ct.split("/")[-1] if "/" in ct else "png")

                actual_filename = f"image_{counter}.{ext}"
                dest = output_path / actual_filename
                dest.write_bytes(blob)

                canonical = f"image_{counter}.png"
                image_map[canonical] = dest
                counter += 1
                logger.info(f"Extracted {actual_filename} ({len(blob):,} bytes)")
            except Exception as e:
                logger.warning(f"Could not extract image rel {rel_id}: {e}")

    return image_map


def _patch_normalized(normalized: dict, uid_map: dict, asset_urls: dict) -> int:
    """Recursively patch assetUid (and url if available) on image blocks. Returns count patched."""
    patched = 0

    def _walk(obj):
        nonlocal patched
        if isinstance(obj, dict):
            if obj.get("type") == "image":
                src = obj.get("sourcePath", "")
                if src in uid_map and not obj.get("assetUid"):
                    obj["assetUid"] = uid_map[src]
                    if src in asset_urls:
                        obj["url"] = asset_urls[src]
                    patched += 1
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(normalized)

    # Also patch heroMedia if present
    hero = normalized.get("heroMedia")
    if isinstance(hero, dict):
        src = hero.get("sourcePath", "")
        if src in uid_map and not hero.get("assetUid"):
            hero["assetUid"] = uid_map[src]
            if src in asset_urls:
                hero["url"] = asset_urls[src]
            patched += 1

    return patched


def upload_assets(
    output_dir: str,
    docx_path: str,
    config: dict = None,
    config_path: str = "config.yaml",
    dry_run: bool = False,
) -> dict:
    """
    Extract images from docx, upload to Contentstack Assets, patch normalized_blog.json.

    Returns {canonical_name: asset_uid} for all successfully uploaded images.
    """
    if config is None:
        config = _load_config(config_path)

    output_path = Path(output_dir)
    normalized_path = output_path / "normalized_blog.json"

    if not normalized_path.exists():
        raise FileNotFoundError(f"normalized_blog.json not found in {output_dir}")

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))

    # Extract images to output dir
    print("Extracting images from docx...")
    image_map = extract_images(docx_path, output_dir)

    if not image_map:
        print("  No embedded images found — skipping asset upload.")
        return {}

    print(f"  Extracted {len(image_map)} image(s): {', '.join(image_map.keys())}")

    if dry_run:
        print(f"[Dry run] Would upload: {', '.join(str(p) for p in image_map.values())}")
        return {}

    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("MSTR_API_KEY")
    if not api_key:
        raise ValueError("MSTR_API_KEY is not set. Add it to .env:\n  MSTR_API_KEY=<your-key>")

    api_cfg = config.get("api", {})
    assets_url = api_cfg.get("assets_url", "").strip()
    if not assets_url:
        base_url = api_cfg.get("base_url", "").rstrip("/")
        if not base_url:
            raise ValueError("api.base_url is not set in config.yaml")
        assets_url = f"{base_url}/assets"

    auth_headers = {"x-mstr-key": api_key}

    uid_map = {}
    asset_urls = {}

    for canonical_name, img_path in image_map.items():
        print(f"  Uploading {img_path.name}...")
        try:
            with open(img_path, "rb") as f:
                ct = _guess_content_type(img_path)
                r = requests.post(
                    assets_url,
                    headers=auth_headers,
                    files={"body": (img_path.name, f, ct)},
                    timeout=60,
                )

            if r.status_code not in (200, 201):
                print(f"  ❌ Upload failed (HTTP {r.status_code}): {r.text[:300]}")
                continue

            resp_json = r.json()
            # Response shape from this endpoint hasn't been confirmed yet — try the
            # common spots (top-level, or nested under "asset") before giving up.
            asset = resp_json.get("asset", resp_json) if isinstance(resp_json, dict) else {}
            asset_uid = asset.get("uid")
            asset_url = asset.get("url", "")

            if not asset_uid:
                print(f"  ❌ No UID found in response — check response shape: {r.text[:300]}")
                continue

            uid_map[canonical_name] = asset_uid
            if asset_url:
                asset_urls[canonical_name] = asset_url

            print(f"  ✓ {canonical_name} → {asset_uid}")

        except Exception as e:
            print(f"  ❌ Error uploading {img_path.name}: {e}")

    if not uid_map:
        print("  No assets uploaded successfully.")
        return uid_map

    # Patch normalized_blog.json with UIDs
    patched = _patch_normalized(normalized, uid_map, asset_urls)
    normalized_path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  ✓ Patched {patched} image block(s) in normalized_blog.json")

    return uid_map


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Extract and upload embedded images from a .docx to Contentstack Assets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/upload_assets.py output/igor-freitas-blog-post-2026-06/ input/blog.docx
  python scripts/upload_assets.py output/my-blog/ input/blog.docx --dry-run
        """,
    )
    parser.add_argument("output_dir", help="Output directory containing normalized_blog.json")
    parser.add_argument("docx_path", help="Path to the original .docx file")
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Extract images but don't upload")
    args = parser.parse_args()

    try:
        result = upload_assets(
            output_dir=args.output_dir,
            docx_path=args.docx_path,
            config_path=args.config,
            dry_run=args.dry_run,
        )
        print(f"\nDone. {len(result)} asset(s) uploaded.")
        sys.exit(0)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
