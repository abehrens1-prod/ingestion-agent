"""
harvest_sources.py — Assemble input/sources/<slug>/harvested_sources.json from a
per-term sources.yaml manifest.

This script is deliberately offline: it does NOT fetch URLs itself. Frank's framing for
a glossary page is "aggregate whichever current content we have on the website now" —
so the fetching step is done once, interactively (WebSearch to find candidate pages,
then a fetch-and-cache tool to save their text under input/sources/<slug>/raw/*.md),
and this script just assembles what's already been cached into a normalized,
provenance-tagged JSON file. Keeping the network call out of the script keeps this step
deterministic and re-runnable without hitting strategy.com repeatedly.

sources.yaml source_type values:
  live_url     — cached_text_path points at a locally saved snapshot under raw/
  local_doc    — url_or_path points at a .docx/.md/.txt file anywhere on disk
  wiki_concept — url_or_path points at a Strategy Brain wiki/concepts/*.md file

A source with no cached_text_path / url_or_path (e.g. "nominated but not yet located")
is recorded in harvested_sources.json with empty text and a warning, not silently
dropped — draft_with_claude.py should know a nominated source is still missing.

Usage:
    python3 scripts/harvest_sources.py <slug>
    python3 scripts/harvest_sources.py semantic-layer --sources-dir input/sources
"""

import json
import logging
import argparse
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _read_local_doc(path: Path) -> str:
    if not path.exists():
        return ""
    if path.suffix.lower() == ".docx":
        import docx
        doc = docx.Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return path.read_text(encoding="utf-8", errors="ignore")


def harvest(term_dir: Path) -> dict:
    manifest_path = term_dir / "sources.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"{manifest_path} not found — create it first (see sources.yaml examples "
            f"for other terms, or docs/glossary_page_spec.md)."
        )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    chunks = []
    warnings = []

    for src in manifest.get("sources", []):
        source_type = src.get("source_type", "")
        title = src.get("title", "")
        text = ""

        if source_type == "live_url":
            cached_path = src.get("cached_text_path")
            if cached_path:
                full_path = term_dir / cached_path
                text = _read_local_doc(full_path)
            if not text:
                warnings.append(f"live_url source '{title}' has no cached text — fetch and cache it before drafting.")

        elif source_type == "local_doc":
            raw_path = src.get("url_or_path")
            if raw_path:
                text = _read_local_doc(Path(raw_path))
            if not text:
                warnings.append(f"local_doc source '{title}' not found on disk — {raw_path or '(no path given)'}.")

        elif source_type == "wiki_concept":
            raw_path = src.get("url_or_path")
            if raw_path:
                resolved = (term_dir / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path)
                text = _read_local_doc(resolved)
            if not text:
                warnings.append(f"wiki_concept source '{title}' not found — {raw_path or '(no path given)'}.")

        else:
            warnings.append(f"Unknown source_type '{source_type}' for '{title}' — skipped.")
            continue

        chunks.append({
            "sourceType": source_type,
            "title": title,
            "urlOrPath": src.get("url") or src.get("url_or_path") or "",
            "notes": (src.get("notes") or "").strip(),
            "text": text.strip(),
            "hasText": bool(text.strip()),
        })

    result = {
        "term": manifest.get("term", ""),
        "slug": manifest.get("slug", term_dir.name),
        "sources": chunks,
        "internalLinkCandidates": manifest.get("internal_link_candidates", {}),
        "warnings": warnings,
    }
    return result


def main(slug: str, sources_dir: str = "input/sources") -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    term_dir = Path(sources_dir) / slug
    result = harvest(term_dir)
    output_path = term_dir / "harvested_sources.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    n_with_text = sum(1 for s in result["sources"] if s["hasText"])
    logger.info(
        "Harvested %d source(s), %d with usable text -> %s",
        len(result["sources"]), n_with_text, output_path,
    )
    for w in result["warnings"]:
        logger.warning(w)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble harvested_sources.json from a term's sources.yaml manifest.")
    parser.add_argument("slug", help="Term slug, e.g. semantic-layer")
    parser.add_argument("--sources-dir", default="input/sources")
    args = parser.parse_args()
    main(args.slug, args.sources_dir)
