"""
map_to_contentstack.py — Convert normalized_glossary.json -> contentstack_entry.json.

Content type: `asset_page` (uid confirmed via schemas/contentstack_asset_page.schema.json,
provided 2026-09-01). This is the new standard — it replaces the earlier `page`-based
mapper that improvised a hero and TOC by combining the Whitepaper agent's `page`-schema
pattern (hero + section + mod_column) with the Blog agent's accordion builder. Do not
revert to that pattern; see docs/glossary_page_spec.md open item history for why.

Structure:

  page_header (native field group — no more improvised hero)
    headline: page title (H1)
    subhead: the term's GEO query target (e.g. "What is a semantic layer?") — a
      deliberate mapping choice, not an unconfirmed value; reinforces the AEO framing
      right under the H1. Revisit if Frank/Jessica want something else here.
    brief_content: normalized["definition"] as a bulleted list (bold + supporting
      sentence per item) — this field's own instruction text says "should be formatted
      as a bulleted list," so this is the native replacement for the old hand-built
      accent-box "Definition" block.
  content (blocks array, one entry per normalized["sections"] item)
    section_anchor block: native TOC entry (header_text, section_id) — replaces the
      old section_id-on-a-whitepaper-section workaround.
    divider block
    text/image blocks: paragraphs, lists, and tables go into a `text` block's RTE;
      images with a known Contentstack asset uid become their own native `image`
      block (asset_page has a first-class file-reference image block, unlike `page`'s
      RTE-only approach). Video sub-blocks and images without an uploaded asset yet
      stay as an inline placeholder paragraph — see NOTES below.
  FAQ -> accordion block (same shape as the old `page` mapper — `accordion` is a
    modular block on both content types with the same accordion_item structure)

NOTES — things this content type changed or removed vs. the old `page` mapper:

  CTA: asset_page's `cta_section` field and its in-body `promo` block are both
  references to a Contentstack `promo` ENTRY, not freeform RTE content. This pipeline
  has no promo entries to reference, so cta_section is left empty with a mapping
  warning instead of guessing at an entry UID. See docs/glossary_page_spec.md.

  JSON-LD schema markup: asset_page has no `custom_code` block (the old `page` mapper
  used one for the DefinedTerm/FAQPage JSON-LD). There is nowhere on this content type
  to embed it. The JSON-LD is still computed and written to the top-level
  `_schema_markup_unplaced` key of the output file (sibling of "entry") so it isn't
  silently dropped, plus a mapping warning. See docs/glossary_page_spec.md.

  Video: asset_page's `video` content block references a Contentstack `video` ENTRY,
  not a raw file/URL. This pipeline doesn't create video entries, so a video sub-block
  always becomes an inline placeholder paragraph (bold "[VIDEO PLACEHOLDER]" text) in
  the surrounding text block, same as an image with no uploaded asset yet.

  Callouts (normalized "callout" blocks — asides, stat call-outs): asset_page's text
  block RTE toolbar options don't include "blockquote" (the old rte_builder.callout_node
  shape), so callouts are rendered instead as their own `text` block using the native
  `accent_box` field (max 1 per block) — a bordered box, same visual intent, built from
  confirmed fields on this content type rather than an RTE node type of uncertain
  support here.

Usage:
    python scripts/map_to_contentstack.py output/2026-08-25_semantic-layer/normalized_glossary.json \
        --output output/2026-08-25_semantic-layer/contentstack_entry.json
"""

import json
import uuid
import secrets
import logging
import argparse
from pathlib import Path
from typing import Optional

import yaml
from slugify import slugify

logger = logging.getLogger(__name__)

_rte_builder = None


def _get_rte():
    global _rte_builder
    if _rte_builder is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rte_builder", Path(__file__).parent / "rte_builder.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _rte_builder = mod
    return _rte_builder


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# UID helpers — matching Contentstack internal formats
# ---------------------------------------------------------------------------

def _cs_uid() -> str:
    return "cs" + secrets.token_hex(8)


def _doc_uid() -> str:
    return uuid.uuid4().hex


def _rte_doc(nodes: list) -> dict:
    return {
        "type": "doc",
        "uid": _doc_uid(),
        "attrs": {},
        "children": nodes or [{"text": ""}],
        "_version": 98,
    }


# ---------------------------------------------------------------------------
# page_header — native hero/Brief block
# ---------------------------------------------------------------------------

def _build_page_header(normalized: dict) -> dict:
    rte = _get_rte()

    li_items = []
    for d in normalized.get("definition", []):
        bold_sentence = (d.get("boldSentence") or "").strip()
        support = (d.get("supportingText") or "").strip()
        runs = []
        if bold_sentence:
            runs.append({"text": bold_sentence, "bold": True})
        if support:
            runs.append({"text": " " + support})
        if runs:
            li_items.append(runs)

    brief_nodes = [rte.ul_node(li_items, text_color=rte.BODY_TEXT)] if li_items else []

    return {
        "headline": normalized.get("title", ""),
        "subhead": normalized.get("geoQueryTarget", "") or "",
        "description": _rte_doc([]),
        "brief_header": "",
        "brief_content": _rte_doc(brief_nodes),
    }


# ---------------------------------------------------------------------------
# Body content blocks
# ---------------------------------------------------------------------------

def _make_text_block(nodes: list, accent_box: Optional[list] = None) -> dict:
    return {
        "text": {
            "accent_box": accent_box or [],
            "text_content": _rte_doc(nodes),
            "text_override": None,
            "table_styles": [],
            "_metadata": {"uid": _cs_uid()},
        }
    }


def _make_section_anchor(header_text: str, section_id: str) -> dict:
    return {
        "section_anchor": {
            "header_text": header_text,
            "section_id": section_id,
            "no_toc": False,
            "no_numbering": False,
            "_metadata": {"uid": _cs_uid()},
        }
    }


def _make_divider() -> dict:
    return {
        "divider": {
            "color": "colorOrange",
            "spacing": "spacingDefault",
            "_metadata": {"uid": _cs_uid()},
        }
    }


def _make_image_block(block: dict) -> dict:
    return {
        "image": {
            "reference": [{"uid": block["assetUid"], "_content_type_uid": "sys_assets"}],
            "caption": block.get("caption") or block.get("altText", ""),
            "limit_width": None,
            "alignment": "Center",
            "rounded_corners": "Medium",
            "drop_shadow": "None",
            "outline": False,
            "highest_priority": False,
            "link": [],
            "_metadata": {"uid": _cs_uid()},
        }
    }


def _placeholder_node(rte, kind: str, block: dict):
    label = block.get("sourcePath") or block.get("url") or block.get("altText") or kind.lower()
    detail = f"Drop the file in the term's assets/ folder and run upload_assets.py --normalized to fill this in — source: {label}"
    return rte.p_node(
        runs=[{"text": f"[{kind} PLACEHOLDER] ", "bold": True}, {"text": detail}],
        color=rte.BODY_TEXT,
    )


def _make_callout_block(block: dict, rte) -> dict:
    """
    Plain bold-lead paragraph, not an accent-box text block. asset_page's `text.accent_box`
    references a global field (`accent_box_styles`) whose valid enum values are unconfirmed
    — a real upload rejected bg_color="White" and styles=["Outlined"] (copied from the old
    `page`-mapper's hero accent box, which turned out not to share the same global field).
    The API proxy also can't be queried for the real enum values (/global_fields/ 404s;
    content_types/accent_box_styles is 403, same allowlist gap asset_page itself had).
    Revert to accent_box once Dale/Jessica confirm valid values — see docs/glossary_page_spec.md.
    """
    label = (block.get("label") or "").strip()
    text = (block.get("text") or "").strip()
    runs = []
    if label:
        runs.append({"text": label, "bold": True})
        if text:
            runs.append({"text": " " + text})
    elif text:
        runs.append({"text": text})
    nodes = [rte.p_node(runs=runs, color=rte.BODY_TEXT)] if runs else []
    return _make_text_block(nodes)


def _build_section_content_blocks(section_blocks: list, rte) -> list:
    result = []
    current_nodes: list = []

    def flush():
        nonlocal current_nodes
        if current_nodes:
            result.append(_make_text_block(current_nodes))
            current_nodes = []

    for blk in section_blocks:
        btype = blk.get("type", "")
        if btype == "paragraph":
            current_nodes.append(rte.p_node(runs=blk.get("runs"), text=blk.get("text", ""), color=rte.BODY_TEXT))
        elif btype == "list":
            items = blk.get("items", [])
            if blk.get("style") == "numbered":
                current_nodes.append(rte.ol_node(items, text_color=rte.BODY_TEXT))
            else:
                current_nodes.append(rte.ul_node(items, text_color=rte.BODY_TEXT))
        elif btype == "table":
            current_nodes.append(rte.table_node(blk.get("rows", []), blk.get("headers")))
        elif btype == "callout":
            flush()
            result.append(_make_callout_block(blk, rte))
        elif btype == "image":
            if blk.get("assetUid"):
                flush()
                result.append(_make_image_block(blk))
            else:
                current_nodes.append(_placeholder_node(rte, "IMAGE", blk))
        elif btype == "video":
            current_nodes.append(_placeholder_node(rte, "VIDEO", blk))

    flush()
    return result


def _build_body_content(sections: list) -> list:
    rte = _get_rte()
    result = []

    for section in sections:
        heading = (section.get("heading") or "").strip()
        section_id = slugify(heading) if heading else f"section-{len(result) + 1}"
        if section_id and section_id[0].isdigit():
            section_id = "section-" + section_id

        result.append(_make_section_anchor(heading, section_id))
        result.append(_make_divider())
        result.extend(_build_section_content_blocks(section.get("blocks", []), rte))

    return result


# ---------------------------------------------------------------------------
# FAQ -> accordion (unchanged shape — same block type on both content types)
# ---------------------------------------------------------------------------

def _build_faq_accordion(faq_items: list) -> Optional[dict]:
    items = []
    for item in faq_items:
        q, a = item.get("question", "").strip(), item.get("answer", "").strip()
        if not q or not a:
            continue
        items.append({
            "title": q,
            "_metadata": {"uid": _cs_uid()},
            "content": _rte_doc([{"type": "p", "uid": _doc_uid(), "attrs": {}, "children": [{"text": a}]}]),
        })
    if not items:
        return None
    return {"accordion": {"accordion_item": items, "_metadata": {"uid": _cs_uid()}, "accordion_options": "closed"}}


# ---------------------------------------------------------------------------
# Schema markup — computed but unplaced (asset_page has no custom_code block)
# ---------------------------------------------------------------------------

def _canonical_url(full_url: str, config: dict) -> str:
    """
    Absolute live-site URL for JSON-LD/canonical use. Only the "/software" segment is
    confirmed elided on the live software.strategy.com domain (see config.yaml's
    cms_domain_prefix comment) — the rest of url_prefix is our own taxonomy choice and
    stays in the path. Do NOT strip the whole url_prefix here.
    """
    base = config.get("api", {}).get("canonical_base_url", "").rstrip("/")
    domain_prefix = config.get("api", {}).get("cms_domain_prefix", "").rstrip("/")
    path = full_url
    if domain_prefix and path.startswith(domain_prefix):
        path = path[len(domain_prefix):]
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}" if base else path


def _build_jsonld_graph(normalized: dict, full_url: str, config: dict) -> dict:
    """
    Provisional — see docs/glossary_page_spec.md "Schema markup" section. No schema type
    has been confirmed by Frank/Doug/Dale/Jessica. DefinedTerm + FAQPage is a reasonable
    default, not a confirmed decision. Computed regardless of whether it can be placed
    anywhere yet (see module docstring NOTES) so the data isn't lost once it can be.
    """
    canonical = _canonical_url(full_url, config)
    definition = normalized.get("definition", [])
    description = ""
    if definition:
        first = definition[0]
        description = f"{first.get('boldSentence', '')} {first.get('supportingText', '')}".strip()

    graph = [{
        "@type": "DefinedTerm",
        "name": normalized.get("term", normalized.get("title", "")),
        "description": description,
        "url": canonical,
        "inDefinedTermSet": {
            "@type": "DefinedTermSet",
            "name": "Strategy Software Glossary",
        },
    }]

    faq_items = normalized.get("faq", [])
    if faq_items:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item.get("question", ""),
                    "acceptedAnswer": {"@type": "Answer", "text": item.get("answer", "")},
                }
                for item in faq_items if item.get("question") and item.get("answer")
            ],
        })

    return {"@context": "https://schema.org", "@graph": graph}


# ---------------------------------------------------------------------------
# SEO + page_properties + resource_data (unchanged)
# ---------------------------------------------------------------------------

def _build_seo(seo: dict, keyword_targets: list) -> dict:
    primary = seo.get("targetKeywords") or seo.get("primaryKeywords") or keyword_targets
    return {
        "meta_title": seo.get("metaTitle", ""),
        "meta_description": seo.get("metaDescription", ""),
        "keywords": ", ".join(primary) if primary else "",
        "social_thumbnail_override": None,
        "enable_search_indexing": True,
    }


def _build_page_properties() -> dict:
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


def _build_resource_data(normalized: dict, config: dict) -> dict:
    resource_type = config.get("contentstack", {}).get("resource_type", "Blog")
    return {
        "date": "",
        "type": resource_type,  # UNCONFIRMED — see docs/glossary_page_spec.md
        "title": normalized.get("title", ""),
        "description": normalized.get("seo", {}).get("metaDescription", ""),
        "featured": False,
    }


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------

def map_normalized_to_entry(normalized: dict, config: dict) -> dict:
    cs_config = config.get("contentstack", {})
    url_prefix = cs_config.get("url_prefix", "").rstrip("/")
    warnings = list(normalized.get("validationWarnings", []))

    slug = normalized.get("slug") or slugify(normalized.get("title", "untitled"))
    url = normalized.get("url") or f"/{slug}"
    if not url.startswith("/"):
        url = f"/{url}"
    full_url = f"{url_prefix}/{url.lstrip('/')}" if url_prefix and not url.startswith(url_prefix) else url

    if not normalized.get("definition"):
        warnings.append("definition array is empty — page_header.brief_content will be empty.")
    page_header = _build_page_header(normalized)

    content_blocks = _build_body_content(normalized.get("sections", []))

    faq_block = _build_faq_accordion(normalized.get("faq", []))
    if faq_block:
        content_blocks.append(faq_block)
    else:
        warnings.append("No FAQ items — accordion block not added.")

    cta_section: list = []
    if normalized.get("internalLinks", {}).get("toArrival"):
        warnings.append(
            "Arrival-tier internal link available but cta_section (and the in-body "
            "'promo' block) requires a reference to an existing Contentstack `promo` "
            "entry — asset_page has no freeform-CTA field. Add manually once a promo "
            "entry exists. See docs/glossary_page_spec.md."
        )

    entry: dict = {
        "title": normalized.get("title", ""),
        "url": full_url,
        "page_header": page_header,
        "anchor_styles": "anchorsNumbered",
        "toc_header": "",
        "content": content_blocks,
        "cta_section": cta_section,
        "seo": _build_seo(normalized.get("seo", {}), normalized.get("keywordTargets", [])),
        "resource_data": _build_resource_data(normalized, config),
        "taxonomies": [],
        "page_properties": _build_page_properties(),
        "locale": normalized.get("locale") or cs_config.get("default_locale", "en"),
    }

    warnings.append(
        "SCHEMA MARKUP — asset_page has no custom_code block, so JSON-LD can't be "
        "embedded on this content type. Computed JSON-LD saved under "
        "_schema_markup_unplaced for manual placement once Jessica/Dale confirm where "
        "per-page schema markup goes. See docs/glossary_page_spec.md."
    )

    result: dict = {"entry": entry}
    result["_schema_markup_unplaced"] = _build_jsonld_graph(normalized, full_url, config)
    if warnings:
        result["_mapping_warnings"] = warnings
    return result


def main(normalized_path: str, output_path: Optional[str] = None, config_path: str = "config.yaml") -> dict:
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
    parser = argparse.ArgumentParser(description="Map normalized glossary JSON to a Contentstack asset_page entry.")
    parser.add_argument("normalized_path", help="Path to normalized_glossary.json")
    parser.add_argument("--output", "-o", default="output/contentstack_entry.json")
    parser.add_argument("--config", "-c", default="config.yaml")
    args = parser.parse_args()
    result = main(args.normalized_path, args.output, args.config)
    entry = result.get("entry", {})
    print(f"Done. Title: {entry.get('title', '(none)')}")
    print(f"  URL: {entry.get('url', '(none)')}")
    print(f"  content blocks: {len(entry.get('content', []))}")
    for w in result.get("_mapping_warnings", []):
        print(f"  ⚠ {w}")
