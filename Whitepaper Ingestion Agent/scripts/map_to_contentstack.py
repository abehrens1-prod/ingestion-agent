"""
map_to_contentstack.py — Convert normalized_whitepaper.json → contentstack_entry.json.

Content type: `page` (same generic type as all strategy.com pages)
Main field: content_blocks (modular blocks: section)

Structure matches the approved Contentstack entry for the AI Token Cost and Accuracy
Benchmark page (strategy.com), confirmed 2026-06-17.

Section layout:
  Hero section
    section_header: H1 + H3 subtitle + P description (centered, text_content key)
    columns: one "The Brief" mod_column with orange outlined accent box
  Body sections (one per top-level heading)
    "banner" mod_column: H2 text_block + orange divider block + intro paragraph text_block
    One mod_column per H3 subsection: H3 + body paragraphs
  CTA section
    One mod_column, bg_color: "Brass"

Usage:
    python scripts/map_to_contentstack.py output/normalized_whitepaper.json \
        --output output/contentstack_entry.json
"""

import sys
import json
import re
import uuid
import secrets
import logging
import argparse
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ingestion_common.console import enable_utf8

enable_utf8()

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
    """'cs' + 16 hex — used for _metadata.uid fields in modular blocks."""
    return "cs" + secrets.token_hex(8)


def _doc_uid() -> str:
    """32-char hex — used for JSON RTE doc and node uid fields."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# JSON RTE doc wrapper
# ---------------------------------------------------------------------------

def _rte_doc(nodes: list) -> dict:
    """Wrap RTE nodes in a top-level doc container."""
    return {
        "type": "doc",
        "uid": _doc_uid(),
        "attrs": {},
        "children": nodes or [{"text": ""}],
        "_version": 98,
    }


# ---------------------------------------------------------------------------
# Content block helpers
# ---------------------------------------------------------------------------

def _make_col_text(rte_nodes: list) -> dict:
    """Text content block using text_block key — used in mod_column content."""
    return {
        "text": {
            "text_block": _rte_doc(rte_nodes),
            "_metadata": {"uid": _cs_uid()},
            "text_override": None,
            "table_styles": [],
        }
    }


def _make_hero_header_item(rte_nodes: list) -> dict:
    """Text content block using text_content key — used only in hero section_header."""
    return {
        "text": {
            "text_content": _rte_doc(rte_nodes),
            "_metadata": {"uid": _cs_uid()},
        }
    }


def _make_divider() -> dict:
    """Orange thin divider — placed between H2 and intro paragraph in every body section."""
    return {
        "divider": {
            "style": "thin",
            "spacing": "12",
            "custom_spacing": None,
            "_metadata": {"uid": _cs_uid()},
            "color": "colorOrange",
            "opacity": "1",
            "width": "100",
        }
    }


def _make_mod_column(
    column_name: str,
    content_items: list,
    accent_box_options: Optional[list] = None,
) -> dict:
    return {
        "mod_column": {
            "column_name": column_name,
            "_metadata": {"uid": _cs_uid()},
            "accent_box_options": accent_box_options or [],
            "content": content_items,
        }
    }


def _make_section(
    section_id: str,
    mod_columns: list,
    section_header_items: Optional[list] = None,
    bg_color: str = "White",
    text_color: str = "Dark",
    padding: str = "Short",
    limit_header_width: Optional[str] = None,
) -> dict:
    return {
        "section": {
            "section_id": section_id,
            "_metadata": {"uid": _cs_uid()},
            "section_header": section_header_items or [],
            "limit_header_width": limit_header_width,
            "columns": mod_columns,
            "columns_per_row": 1,
            "column_alignment": "Center, Top",
            "section_footer": [],
            "limit_footer_width": None,
            "more_column_options": {
                "column_spacing": "Default",
                "one_column_limit_width": "75%",
                "two_column_split": None,
                "reverse_column_order_mobile": False,
                "accent_box_stretch": False,
            },
            "more_section_options": {
                "text_color": text_color,
                "padding": padding,
                "add_divider": [],
                "bg_color": bg_color,
                "bg_custom_color": "",
                "bg_image": None,
                "mobile_bg_image": None,
                "parallax_bg": False,
                "bg_video_id": "",
            },
        }
    }


# ---------------------------------------------------------------------------
# Hero section — includes The Brief as a mod_column
# ---------------------------------------------------------------------------

def _build_hero_section(normalized: dict, brief: list) -> dict:
    """
    Hero section with:
    - section_header: H1 title + H3 subtitle + P description (centered, text_content key)
    - columns: one "The Brief" mod_column with orange outlined accent box and ul bullet list
    """
    rte = _get_rte()

    # section_header — centered title block (uses text_content, not text_block)
    header_nodes = []
    title = normalized.get("title", "")
    if title:
        header_nodes.append(rte.heading_node(
            title, level=1,
            color="rgb(0, 0, 0)",
            centered=True,
        ))
    subtitle = normalized.get("subtitle", "")
    if subtitle:
        header_nodes.append(rte.heading_node(
            subtitle, level=3,
            color="rgb(250, 102, 15)",
            centered=True,
            font_color="#fa660f",
        ))
    description = normalized.get("description", "")
    if description:
        header_nodes.append(rte.p_node(
            text=description,
            color="rgb(85, 85, 85)",
            centered=True,
        ))

    section_header_items = [_make_hero_header_item(header_nodes)] if header_nodes else []

    # The Brief mod_column — orange outlined accent box
    brief_accent_box = [{
        "size": "Medium",
        "styles": ["Outlined"],
        "outline_styles": ["outlineThin", "outlineColorOrange"],
        "flag": "",
        "_metadata": {"uid": _cs_uid()},
        "align": None,
        "bg_color": "White",
        "bg_custom_color": "",
        "bg_image": None,
        "text_color": None,
        "add_link": [],
    }]

    brief_nodes = [rte.heading_node("The Brief", level=3, font_color="#000000")]

    if brief:
        li_items = []
        for b in brief:
            bold_sentence = b.get("boldSentence", "").strip()
            support = b.get("supportingText", "").strip()
            runs = []
            if bold_sentence:
                runs.append({"text": bold_sentence, "bold": True})
            if support:
                runs.append({"text": " " + support})
            if runs:
                li_items.append(runs)
        if li_items:
            brief_nodes.append(rte.ul_node(li_items))

    brief_col = _make_mod_column(
        "The Brief",
        [_make_col_text(brief_nodes)],
        accent_box_options=brief_accent_box,
    )

    return _make_section(
        section_id="hero",
        mod_columns=[brief_col],
        section_header_items=section_header_items,
        bg_color="White",
        text_color="Dark",
        padding="Default",
        limit_header_width="75%",  # constrains the section_header title block to match content width
    )


# ---------------------------------------------------------------------------
# Body content sections
# ---------------------------------------------------------------------------

def _block_to_node(block: dict, rte):
    """Convert a normalized block to an RTE node (or list of nodes)."""
    btype = block.get("type", "")
    if btype == "paragraph":
        return rte.p_node(
            runs=block.get("runs"),
            text=block.get("text", ""),
            color="rgb(26, 26, 26)",
        )
    elif btype == "heading":
        level = block.get("level", 3)
        text = block.get("text", "")
        if level <= 2:
            return rte.heading_node(text, level=2, color="rgb(0, 0, 0)")
        return rte.heading_node(
            text, level=3,
            color="rgb(250, 102, 15)",
            bold=True,
            font_color="#fa660f",
        )
    elif btype == "list":
        items = block.get("items", [])
        if block.get("style") == "numbered":
            return rte.ol_node(items, text_color="rgb(26, 26, 26)")
        return rte.ul_node(items, text_color="rgb(26, 26, 26)")
    elif btype == "table":
        return rte.table_node(block.get("rows", []), block.get("headers"))
    elif btype == "callout":
        return rte.callout_node(
            label=block.get("label", ""),
            text=block.get("text", ""),
        )
    return None


def _build_faq_accordion(section: dict) -> dict:
    """
    Convert a FAQ section into an accordion content block.

    Expects alternating Q/A paragraph blocks:
      {"type": "paragraph", "runs": [{"text": "Q: ...", "bold": true}]}
      {"type": "paragraph", "text": "A: ..."}
    """
    blocks = section.get("blocks", [])
    items = []
    i = 0
    while i < len(blocks):
        q_block = blocks[i]
        a_block = blocks[i + 1] if i + 1 < len(blocks) else None

        # Extract question text (may be in runs or text)
        if q_block.get("runs"):
            q_text = " ".join(r.get("text", "") for r in q_block["runs"])
        else:
            q_text = q_block.get("text", "")
        q_text = re.sub(r"^Q:\s*", "", q_text).strip()

        # Extract answer text
        a_text = ""
        if a_block:
            if a_block.get("runs"):
                a_text = " ".join(r.get("text", "") for r in a_block["runs"])
            else:
                a_text = a_block.get("text", "")
            a_text = re.sub(r"^A:\s*", "", a_text).strip()

        if q_text:
            items.append({
                "title": q_text,
                "_metadata": {"uid": _cs_uid()},
                "content": {
                    "type": "doc",
                    "attrs": {},
                    "uid": _doc_uid(),
                    "children": [
                        {
                            "type": "p",
                            "attrs": {},
                            "uid": _doc_uid(),
                            "children": [{"text": a_text}]
                        }
                    ],
                    "_version": 1
                }
            })

        i += 2  # advance past Q + A pair

    return {
        "accordion": {
            "accordion_item": items,
            "_metadata": {"uid": _cs_uid()},
            "accordion_options": "closed"
        }
    }


def _build_body_sections(body: list) -> list:
    """
    Convert normalized body sections to section content_blocks.

    Each section becomes one Contentstack section block with multiple stacked mod_columns:
      "banner": H2 text_block + orange divider + intro paragraphs text_block
      One mod_column per H3 subsection: H3 + its following blocks

    Headingless preamble sections (no H2 extractable from blocks) are merged forward
    into the next headed section's banner intro. This ensures all content lives inside
    a proper H2+divider structure, which is required for the 75% width constraint to apply.
    """
    rte = _get_rte()
    result = []
    pending_preamble_blocks = []  # blocks from headingless sections, carried forward

    for section in body:
        heading = section.get("heading", "").strip()
        section_id = slugify(heading) if heading else f"section-{len(result)+1}"
        if section_id and section_id[0].isdigit():
            section_id = "section-" + section_id

        raw_blocks = list(section.get("blocks", []))

        # If section.heading is empty but first block is a heading, extract it
        if not heading and raw_blocks and raw_blocks[0].get("type") == "heading":
            heading = raw_blocks.pop(0).get("text", "").strip()
            section_id = slugify(heading) if heading else section_id
            if section_id and section_id[0].isdigit():
                section_id = "section-" + section_id

        # FAQ section → accordion block (not a regular section)
        if heading.lower() == "faq":
            result.append(_build_faq_accordion(section))
            pending_preamble_blocks = []
            continue

        # If still no heading, this is a preamble section — carry its blocks forward
        # into the next headed section's banner intro rather than creating a naked section.
        # Naked sections (no H2) do not get the 75% width constraint applied by CS.
        if not heading:
            pending_preamble_blocks.extend(raw_blocks)
            continue

        # Prepend any carried-over preamble blocks to this section's intro
        if pending_preamble_blocks:
            raw_blocks = pending_preamble_blocks + raw_blocks
            pending_preamble_blocks = []

        # Split blocks into intro (pre-H3) and subsection groups
        intro_blocks = []
        subsections = []  # list of (h3_block, [following_blocks])
        current_sub = None

        for blk in raw_blocks:
            if blk.get("type") == "heading" and blk.get("level", 3) >= 3:
                current_sub = (blk, [])
                subsections.append(current_sub)
            elif current_sub is not None:
                current_sub[1].append(blk)
            else:
                intro_blocks.append(blk)

        # When there are no intro paragraphs but there ARE subsections, merge the first
        # subsection's H3+content into the banner intro. This avoids a visually thin banner
        # (H2 + divider with nothing below) and matches the approved editorial pattern.
        if not intro_blocks and subsections:
            first_h3, first_sub_blocks = subsections.pop(0)
            h3_node = rte.heading_node(
                first_h3.get("text", ""), level=3,
                color="rgb(250, 102, 15)",
                bold=True,
                font_color="#fa660f",
            )
            intro_nodes = [h3_node]
            for blk in first_sub_blocks:
                node = _block_to_node(blk, rte)
                if node is None:
                    continue
                if isinstance(node, list):
                    intro_nodes.extend(node)
                else:
                    intro_nodes.append(node)
        else:
            intro_nodes = []
            for blk in intro_blocks:
                node = _block_to_node(blk, rte)
                if node is None:
                    continue
                if isinstance(node, list):
                    intro_nodes.extend(node)
                else:
                    intro_nodes.append(node)

        # Banner mod_column: H2 + divider + intro content
        # Divider only added when an H2 heading is present (matches approved template pattern)
        banner_content = []

        if heading:
            banner_content.append(_make_col_text([
                rte.heading_node(heading, level=2, color="rgb(0, 0, 0)")
            ]))
            banner_content.append(_make_divider())

        if intro_nodes:
            banner_content.append(_make_col_text(intro_nodes))

        mod_columns = [_make_mod_column("banner", banner_content)]

        # One mod_column per remaining H3 subsection
        for h3_block, sub_blocks in subsections:
            h3_text = h3_block.get("text", "")
            col_name = (h3_text[:50] if h3_text else "subsection").strip()

            sub_nodes = [
                rte.heading_node(
                    h3_text, level=3,
                    color="rgb(250, 102, 15)",
                    bold=True,
                    font_color="#fa660f",
                )
            ]
            for blk in sub_blocks:
                node = _block_to_node(blk, rte)
                if node is None:
                    continue
                if isinstance(node, list):
                    sub_nodes.extend(node)
                else:
                    sub_nodes.append(node)

            mod_columns.append(_make_mod_column(col_name, [_make_col_text(sub_nodes)]))

        result.append(_make_section(
            section_id=section_id,
            mod_columns=mod_columns,
            bg_color="White",
            text_color="Dark",
            padding="Short bottom only",
        ))

    # If preamble blocks were never merged (edge case: only headingless sections),
    # attach them to the last section's banner rather than dropping them silently.
    if pending_preamble_blocks and result:
        last_banner = result[-1]["section"]["columns"][0]["mod_column"]["content"]
        extra_nodes = []
        for blk in pending_preamble_blocks:
            node = _block_to_node(blk, rte)
            if node is None:
                continue
            if isinstance(node, list):
                extra_nodes.extend(node)
            else:
                extra_nodes.append(node)
        if extra_nodes:
            last_banner.append(_make_col_text(extra_nodes))

    return result


# ---------------------------------------------------------------------------
# CTA section
# ---------------------------------------------------------------------------

def _build_cta_section(cta: dict) -> dict:
    """CTA as a regular section block with Brass background."""
    rte = _get_rte()
    nodes = []
    headline = cta.get("headline", "")
    if headline:
        nodes.append(rte.heading_node(headline, level=2))
    body_text = cta.get("body", "")
    if body_text:
        nodes.append(rte.p_node(text=body_text))
    button_text = cta.get("buttonText", "")
    button_url = cta.get("buttonUrl", "")
    if button_text and button_url:
        nodes.append(rte.p_node(runs=[{"text": button_text, "url": button_url}]))

    return _make_section(
        section_id="cta",
        mod_columns=[_make_mod_column("cta", [_make_col_text(nodes)])],
        bg_color="Brass",
        text_color="Dark",
        padding="Default",
    )


# ---------------------------------------------------------------------------
# SEO + page_properties + resource_data
# ---------------------------------------------------------------------------

def _build_seo(seo: dict) -> dict:
    keywords = seo.get("targetKeywords") or seo.get("primaryKeywords", [])
    return {
        "meta_title": seo.get("metaTitle", ""),
        "meta_description": seo.get("metaDescription", ""),
        "keywords": ", ".join(keywords) if keywords else "",
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


def _build_resource_data(normalized: dict) -> dict:
    year = normalized.get("publishedYear", "")
    iso_date = f"{year}-01-01T00:00:00.000Z" if year and year.isdigit() and len(year) == 4 else ""
    return {
        "date": iso_date,
        "type": "Analyst Report",
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

    # URL
    slug = normalized.get("slug") or slugify(normalized.get("title", "untitled"))
    url = normalized.get("url") or f"/{slug}"
    if not url.startswith("/"):
        url = f"/{url}"
    if url_prefix and not url.startswith(url_prefix):
        full_url = f"{url_prefix}/{url.lstrip('/')}"
    else:
        full_url = url

    # Assemble content_blocks
    content_blocks = []

    # 1. Hero (includes The Brief as a mod_column)
    brief = normalized.get("brief", [])
    if not brief:
        warnings.append("brief array is empty — The Brief accordion in the hero will be empty.")
    content_blocks.append(_build_hero_section(normalized, brief))

    # 2. Body sections
    body = normalized.get("body", [])
    content_blocks.extend(_build_body_sections(body))

    # 3. CTA section
    cta = normalized.get("cta")
    if cta:
        content_blocks.append(_build_cta_section(cta))
    else:
        warnings.append("No CTA found — cta section not added. Add manually in CS editor.")

    # Assemble entry
    entry: dict = {
        "title": normalized.get("title", ""),
        "url": full_url,
        "content_blocks": content_blocks,
        "page_properties": _build_page_properties(),
        "seo": _build_seo(normalized.get("seo", {})),
        "resource_data": _build_resource_data(normalized),
        "taxonomies": [],
        "tags": [],
    }

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
    parser = argparse.ArgumentParser(description="Map normalized whitepaper JSON to Contentstack page entry.")
    parser.add_argument("normalized_path", help="Path to normalized_whitepaper.json")
    parser.add_argument("--output", "-o", default="output/contentstack_entry.json")
    parser.add_argument("--config", "-c", default="config.yaml")
    args = parser.parse_args()
    result = main(args.normalized_path, args.output, args.config)
    entry = result.get("entry", {})
    print(f"Done. Title: {entry.get('title', '(none)')}")
    print(f"  URL: {entry.get('url', '(none)')}")
    print(f"  content_blocks: {len(entry.get('content_blocks', []))}")
    for w in result.get("_mapping_warnings", []):
        print(f"  ⚠ {w}")
