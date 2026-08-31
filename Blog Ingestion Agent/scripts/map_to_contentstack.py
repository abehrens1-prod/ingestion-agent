"""
map_to_contentstack.py — Convert normalized_blog.json → contentstack_entry.json.

Schema confirmed from a live published Blog Post entry (blt3cd0f47c06e1cf66, June 2026).
Content structure:
  - Quick Answer text block (h3 label + ul)
  - Intro text block (pre-H2 paragraphs)
  - Per H2 section: section_anchor + intro text block + one text block per H3 feature
  - Images/videos → standalone content blocks between feature text blocks
  - Videos skipped (no asset UID available; add manually in Contentstack editor)
  - Accordion for FAQ

H3 headings in normalized JSON → H4 pairs in Contentstack: an empty spacer h4 followed
by the content h4, both with font-color "#fa660f". Each H3 starts a new text block.

Usage:
    python scripts/map_to_contentstack.py output/normalized_blog.json \
        --output output/contentstack_entry.json
"""

import sys

if sys.platform == "win32":
    # Native Windows consoles default to a legacy codepage, not UTF-8 — without
    # this, the ✓/⚠/❌ status glyphs below crash with UnicodeEncodeError mid-run.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
import json
import uuid
import secrets
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml
from slugify import slugify

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

logger = logging.getLogger(__name__)

_rte_builder = None


def _get_rte():
    global _rte_builder
    if _rte_builder is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rte_builder",
            Path(__file__).parent / "rte_builder.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _rte_builder = mod
    return _rte_builder


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# UID helpers — matching Contentstack's internal formats
# ---------------------------------------------------------------------------

def _cs_meta_uid() -> str:
    """'cs' + 16 hex chars — used for modular block _metadata.uid fields."""
    return "cs" + secrets.token_hex(8)


def _doc_uid() -> str:
    """32-char hex UUID — used for JSON RTE doc and node uid fields."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# JSON RTE doc wrapper
# ---------------------------------------------------------------------------

def _wrap_in_doc(rte_nodes: list) -> dict:
    """Wrap RTE nodes in a JSON RTE doc container (version 1 for new entries)."""
    return {
        "type": "doc",
        "attrs": {},
        "uid": _doc_uid(),
        "children": rte_nodes or [{"text": ""}],
        "_version": 1,
    }


# ---------------------------------------------------------------------------
# H4 feature heading helpers
# Each H3 in normalized JSON → two h4 nodes in Contentstack:
#   1. Empty spacer h4 (font-color orange, text="")
#   2. Content h4 (font-color orange, actual heading text)
# ---------------------------------------------------------------------------

def _make_h4_pair(text: str) -> list:
    """Return [empty spacer h4, content h4] per confirmed live entry pattern."""
    return [
        {"type": "h4", "uid": _doc_uid(), "attrs": {}, "children": [{"text": "", "font-color": "#fa660f"}]},
        {"type": "h4", "uid": _doc_uid(), "attrs": {}, "children": [{"font-color": "#fa660f", "text": text}]},
    ]


def _make_image_content_block(block: dict) -> Optional[dict]:
    """Standalone image modular block. Only created when assetUid is known."""
    asset_uid = block.get("assetUid", "")
    if not asset_uid:
        return None
    return {
        "image": {
            "reference": asset_uid,
            "_metadata": {"uid": _cs_meta_uid()},
            "caption": block.get("caption", ""),
            "limit_width": None,
            "alignment": "Center",
            "rounded_corners": "Medium",
            "drop_shadow": "None",
            "outline": False,
            "link": [],
        }
    }


# ---------------------------------------------------------------------------
# Modular block builders
# ---------------------------------------------------------------------------

def _make_section_anchor(heading_text: str) -> dict:
    section_id = slugify(heading_text)
    # Contentstack rejects section_ids that start with a digit
    if section_id and section_id[0].isdigit():
        section_id = f"section-{section_id}"
    return {
        "section_anchor": {
            "header_text": heading_text,
            "_metadata": {"uid": _cs_meta_uid()},
            "section_id": section_id,
        }
    }


def _make_text_block(rte_nodes: list) -> dict:
    return {
        "text": {
            "text_content": _wrap_in_doc(rte_nodes),
            "_metadata": {"uid": _cs_meta_uid()},
        }
    }


def _make_accordion_block(faq_items: list) -> dict:
    accordion_items = []
    for item in faq_items:
        if not item.get("question") or not item.get("answer"):
            continue
        answer_p = {
            "type": "p",
            "attrs": {},
            "uid": _doc_uid(),
            "children": [{"text": item["answer"]}],
        }
        accordion_items.append({
            "title": item["question"],
            "_metadata": {"uid": _cs_meta_uid()},
            "content": _wrap_in_doc([answer_p]),
        })
    return {
        "accordion": {
            "accordion_item": accordion_items,
            "_metadata": {"uid": _cs_meta_uid()},
            "accordion_options": "closed",
        }
    }


# ---------------------------------------------------------------------------
# Field-level builders
# ---------------------------------------------------------------------------

def _build_lead_paragraph(body_nodes: list) -> dict:
    """All nodes before the first H2, wrapped in a doc RTE (confirmed from live entry)."""
    first_h2_idx = next((i for i, n in enumerate(body_nodes) if n.get("type") == "h2"), None)
    intro_nodes = body_nodes[:first_h2_idx] if first_h2_idx is not None else body_nodes
    return _wrap_in_doc(intro_nodes if intro_nodes else [{"text": ""}])


def _build_quick_answer_block(items: list, label: str = "Quick Answer") -> Optional[dict]:
    if not items:
        return None
    rte = _get_rte()
    h3 = {
        "type": "h3",
        "uid": rte._uid(),
        "attrs": {},
        "children": [
            {
                "text": label,
                "attrs": {"style": {"color": "rgb(26, 78, 159)"}},
                "bold": True,
                "font-color": "#fa660f",
            },
        ],
    }
    li_nodes = []
    for item in items:
        if isinstance(item, dict):
            headline = item.get("headline", "").strip()
            body = item.get("body", "").strip()
            if body:
                # Synthesized format: bold headline + plain body sentence
                runs = [{"text": headline, "bold": True}, {"text": " " + body}]
            else:
                # Doc-sourced format: plain text, no bold (preserves exact doc bullet)
                runs = [{"text": headline}]
            p = {"type": "p", "uid": rte._uid(), "attrs": {}, "children": runs}
        else:
            p = rte.p_node(text=str(item).strip())
        li_nodes.append({
            "type": "li",
            "uid": rte._uid(),
            "attrs": {},
            "children": [p],
        })
    ul = {"type": "ul", "uid": rte._uid(), "attrs": {}, "children": li_nodes}
    return _make_text_block([h3, ul])


def _make_cta_placeholder_block(cta: dict) -> dict:
    """Placeholder text block for a CTA that requires a manual Promo entry in Contentstack."""
    rte = _get_rte()
    headline = cta.get("headline", "")
    button_text = cta.get("buttonText", "")
    button_url = cta.get("buttonUrl", "")
    lines = [
        rte.p_node(text="[ PROMO PLACEHOLDER — Replace with Promo block in Contentstack editor ]"),
    ]
    if headline:
        lines.append(rte.p_node(text=f"CTA: \"{headline}\""))
    if button_text:
        btn = f"Button: {button_text}"
        if button_url:
            btn += f"  →  {button_url}"
        lines.append(rte.p_node(text=btn))
    return _make_text_block(lines)


def _build_content_blocks(sections: list, faq_items: list, post_faq: list = None, cta_list: list = None) -> list:
    """
    Build content blocks directly from raw normalized sections (not pre-converted RTE nodes).

    Per confirmed live entry structure:
    - H2 section heading → section_anchor block
    - Content before first H3 in a section → text block (intro paragraphs)
    - H3 heading → flush current text block; new text block starting with H4 pair
    - Image block (assetUid known) → flush; standalone image content block
    - Image block (no assetUid) → skipped (add manually after uploading asset)
    - Video block → skipped entirely (no asset UID available from pipeline)
    - Everything else → accumulated into current text block
    """
    rte = _get_rte()
    blocks = []

    for section in sections:
        heading = section.get("heading", "")
        if heading:
            blocks.append(_make_section_anchor(heading))

        current_nodes: list = []

        for block in section.get("blocks", []):
            btype = block.get("type", "")

            if btype == "heading" and block.get("level", 2) == 3:
                # H3 → flush, start new text block with H4 pair
                if current_nodes:
                    blocks.append(_make_text_block(current_nodes))
                current_nodes = _make_h4_pair(block.get("text", ""))

            elif btype == "image":
                # Flush current text block, then add standalone image block (if assetUid known)
                if current_nodes:
                    blocks.append(_make_text_block(current_nodes))
                    current_nodes = []
                img_block = _make_image_content_block(block)
                if img_block:
                    blocks.append(img_block)
                else:
                    # No assetUid yet — render placeholder text block so position is marked in editor
                    node = rte._block_to_node(block)
                    if node is not None:
                        nodes = node if isinstance(node, list) else [node]
                        blocks.append(_make_text_block(nodes))

            elif btype == "video":
                # Flush current text block; skip video (must be added manually in CS editor)
                if current_nodes:
                    blocks.append(_make_text_block(current_nodes))
                    current_nodes = []

            else:
                node = rte._block_to_node(block)
                if node is not None:
                    if isinstance(node, list):
                        current_nodes.extend(node)
                    else:
                        current_nodes.append(node)

        if current_nodes:
            blocks.append(_make_text_block(current_nodes))

    # CTA placeholder blocks — inserted before FAQ so editors see them in context.
    # Each CTA extracted by the parser becomes a visible placeholder text block.
    # Editor creates a Promo entry in CS using the extracted content, then swaps the
    # placeholder for the Promo block and drags it to the right position in the article.
    for cta in (cta_list or []):
        blocks.append(_make_cta_placeholder_block(cta))

    if faq_items:
        blocks.append(_make_section_anchor("Frequently Asked Questions"))
        blocks.append(_make_accordion_block(faq_items))

    if post_faq:
        post_nodes = [rte.p_node(text=s.strip()) for s in post_faq if s.strip()]
        if post_nodes:
            blocks.append(_make_text_block(post_nodes))

    return blocks


def _build_seo(seo: dict, target_keywords: list) -> dict:
    # thumbnail omitted — CS rejects null uploads; add manually after uploading the image.
    return {
        "meta_title": seo.get("metaTitle", ""),
        "meta_description": seo.get("metaDescription", ""),
        "keywords": ", ".join(target_keywords) if target_keywords else "",
        "social_thumbnail_override": None,
        "enable_search_indexing": True,
    }


def _build_page_properties() -> dict:
    """Default page_properties — required field confirmed from live entry."""
    return {
        "navigation_title": "",
        "header_color": None,
        "hide_header_nav": False,
        "hide_header_cta": False,
        "hide_footer": False,
        "disable_global_promo_banner": False,
        "hide_auto_expert": False,
        "sfid": "",
        "marketo_id": "",
        "cta_section": [],
    }


def _build_resource_data(normalized: dict, publish_date: str) -> dict:
    """resource_data block — required field confirmed from live entry."""
    return {
        "date": publish_date or "",
        "type": "Blog",
        "title": normalized.get("title", ""),
        "description": normalized.get("seo", {}).get("metaDescription", ""),
        "featured": False,
    }


def _normalize_date(raw: str) -> Optional[str]:
    """Convert date strings to YYYY-MM-DD (confirmed CS format from live entry)."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    parts = raw.split()
    if len(parts) == 2:
        month_str, year_str = parts
        month_num = _MONTH_MAP.get(month_str.lower())
        if month_num and year_str.isdigit():
            return f"{year_str}-{month_num:02d}-01"
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _map_author(author_name: str, config: dict, warnings: list) -> Optional[list]:
    if not author_name:
        return None
    cs_config = config.get("contentstack", {})
    authors = cs_config.get("authors") or {}
    uid = authors.get(author_name)
    author_ct_uid = cs_config.get("author_content_type_uid", "blog_author")
    if uid:
        return [{"uid": uid, "_content_type_uid": author_ct_uid}]
    warnings.append(
        f"Author '{author_name}' has no UID in config.yaml authors lookup. "
        "Add their Contentstack UID to config.yaml → contentstack.authors to generate a valid reference."
    )
    return None


def _map_taxonomy(config: dict, suggested_terms: list, warnings: list) -> Optional[list]:
    """Apply only the configured terms that match this post's AI-suggested topics.

    config.yaml's taxonomy_terms is the full catalog of terms with known UIDs, not a
    per-post selection — applying all of it to every entry would tag unrelated posts
    (e.g. a customer case study) with terms like "Mosaic" or "Product Updates".
    """
    cs_config = config.get("contentstack", {})
    taxonomy_uid = cs_config.get("taxonomy_uid", "")
    taxonomy_terms = cs_config.get("taxonomy_terms") or {}
    if not taxonomy_uid:
        warnings.append(
            "taxonomy_uid is not set in config.yaml. "
            "Add contentstack.taxonomy_uid (from Contentstack Settings → Taxonomies) to enable taxonomy mapping."
        )
        return None
    if not taxonomy_terms:
        return None

    suggested_lower = [s.lower() for s in suggested_terms]
    matched = {
        display_name: term_uid
        for display_name, term_uid in taxonomy_terms.items()
        if any(
            display_name.lower() in s or s in display_name.lower()
            for s in suggested_lower
        )
    }
    unmatched_suggestions = [
        s for s in suggested_terms
        if not any(
            s.lower() in name.lower() or name.lower() in s.lower()
            for name in taxonomy_terms
        )
    ]
    if unmatched_suggestions:
        warnings.append(
            f"Suggested taxonomy terms with no configured match: {', '.join(unmatched_suggestions)}. "
            "Add them to contentstack.taxonomy_terms in config.yaml (with UID from Contentstack) if relevant, "
            "or apply manually in the CS editor."
        )
    if not matched:
        return None
    return [
        {"taxonomy_uid": taxonomy_uid, "term_uid": term_uid}
        for term_uid in matched.values()
    ]


def _warn_missing_image_assets(sections: list, warnings: list):
    for section in sections:
        for block in section.get("blocks", []):
            if block.get("type") == "image" and not block.get("assetUid"):
                source = block.get("sourcePath") or block.get("url") or "unknown"
                warnings.append(f"Image block missing assetUid — source: {source}")


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------

def map_normalized_to_entry(normalized: dict, config: dict) -> dict:
    cs_config = config.get("contentstack", {})
    url_prefix = cs_config.get("url_prefix", "").rstrip("/")

    warnings = list(normalized.get("validationWarnings", []))

    # --- URL ---
    slug = normalized.get("slug") or slugify(normalized.get("title", "untitled"))
    url = normalized.get("url") or f"/{slug}"
    if not url.startswith("/"):
        url = f"/{url}"
    full_url = f"{url_prefix}/{url.lstrip('/')}" if url_prefix else url

    # --- Body → content modular blocks ---
    sections = normalized.get("body", [])
    _warn_missing_image_assets(sections, warnings)

    # lead_paragraph is intentionally empty; Quick Answer is the first content block.
    lead_paragraph = _wrap_in_doc([{"text": ""}])

    # _build_content_blocks processes raw sections: intro paragraphs get their own text
    # block naturally (they precede the first H3 in their section), H3 headings become
    # H4 pairs starting new text blocks, images/videos become standalone content blocks.
    content_blocks = _build_content_blocks(
        sections,
        normalized.get("faq", []),
        post_faq=normalized.get("postFaqContent") or [],
        cta_list=normalized.get("cta_list") or [],
    )

    # Prepend Quick Answer as the very first content block
    quick_answer = normalized.get("quickAnswer") or []
    qa_block = _build_quick_answer_block(quick_answer)
    if qa_block:
        content_blocks = [qa_block] + content_blocks

    # --- SEO ---
    seo_data = normalized.get("seo", {})
    seo = _build_seo(seo_data, seo_data.get("targetKeywords", []))

    # --- Author ---
    author_ref = _map_author(normalized.get("author", ""), config, warnings)

    # --- Date ---
    raw_date = normalized.get("publishDate", "") or normalized.get("publish_date", "")
    publish_date = _normalize_date(raw_date)
    # Contentstack stores dates one day behind local — bump +1 so the intended date lands correctly
    if publish_date:
        try:
            publish_date = (datetime.strptime(publish_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # --- Taxonomy ---
    suggested_terms = normalized.get("suggestedTaxonomyTerms") or []
    taxonomy = _map_taxonomy(config, suggested_terms, warnings)
    if suggested_terms and not taxonomy and config.get("contentstack", {}).get("taxonomy_terms"):
        warnings.append(
            f"Suggested taxonomy terms (AI): {', '.join(suggested_terms)}. "
            "None matched a configured term — populate contentstack.taxonomy_terms in config.yaml with term UIDs to auto-apply on future runs."
        )

    # --- CTA warnings ---
    for i, cta in enumerate(normalized.get("cta_list", []), start=1):
        headline = cta.get("headline", "") or cta.get("body", "")[:60]
        warnings.append(
            f"CTA {i} ('{headline}') — placeholder text block inserted before FAQ. "
            "Create a Promo entry in CS using the extracted headline and button text, "
            "then replace the placeholder with the Promo block and move it to the correct position."
        )

    # --- Assemble entry (field order matches live Blog Post schema) ---
    entry: dict = {
        "title": normalized.get("title", ""),
        "url": full_url,
        "lead_paragraph": lead_paragraph,
        "content": content_blocks,
        "cta_section": [],
        "related_posts": [],
        "seo": seo,
        "page_properties": _build_page_properties(),
        "resource_data": _build_resource_data(normalized, publish_date or ""),
        "locale": normalized.get("locale") or config.get("contentstack", {}).get("default_locale", "en"),
    }
    if publish_date:
        entry["publish_date"] = publish_date
    if author_ref:
        entry["author"] = author_ref
    if taxonomy:
        entry["taxonomies"] = taxonomy

    result: dict = {"entry": entry}
    if warnings:
        result["_mapping_warnings"] = warnings
    return result


def main(
    normalized_path: str,
    output_path: Optional[str] = None,
    config_path: str = "config.yaml",
) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    config = load_config(config_path)
    with open(normalized_path, "r", encoding="utf-8") as f:
        normalized = json.load(f)
    result = map_normalized_to_entry(normalized, config)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Written: {output_path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map normalized blog JSON to Contentstack entry JSON.")
    parser.add_argument("normalized_path", help="Path to normalized_blog.json")
    parser.add_argument("--output", "-o", default="output/contentstack_entry.json")
    parser.add_argument("--config", "-c", default="config.yaml")
    args = parser.parse_args()
    result = main(args.normalized_path, args.output, args.config)
    entry = result.get("entry", {})
    print(f"Done. Entry title: {entry.get('title', '(none)')}")
    print(f"  URL: {entry.get('url', '(none)')}")
    warnings = result.get("_mapping_warnings", [])
    if warnings:
        print(f"  Mapping warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
