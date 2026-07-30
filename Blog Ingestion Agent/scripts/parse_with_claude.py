"""
parse_with_claude.py — Extract and normalize a .docx blog using Claude.

Replaces parse_docx.py + enrich_with_claude.py. Claude handles all content
understanding: structure detection, FAQ/CTA/Quick Answer extraction, SEO field
generation, and edge cases. No heuristics, no regex tuning required.

Requires: ANTHROPIC_API_KEY environment variable.

Usage:
    python scripts/parse_with_claude.py input/blog.docx
    python scripts/parse_with_claude.py input/blog.docx --output output/normalized_blog.json
"""

import re
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table
from slugify import slugify

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1: Deterministic docx → structured text
# ---------------------------------------------------------------------------

def _xml_toggle_on(rpr, tag: str) -> bool:
    """Return True if a Word XML toggle property (w:b, w:i, etc.) is present and ON.

    Absent val attribute = on. val='0'/'false'/'off' = explicitly turned off (style override).
    This prevents <w:b w:val="0"/> (style-inherited bold turned off) from being misread as bold.
    """
    el = rpr.find(tag)
    if el is None:
        return False
    val = el.get(qn("w:val"))
    return val is None or val.lower() not in ("0", "false", "off")


def _element_text_with_links(element, part) -> str:
    """
    Walk an XML element and return its text with inline [LINK:anchor|url] markers.
    Hyperlinks are emitted as [LINK:anchor text|https://url] so Claude can reconstruct
    runs with url fields. Regular runs just contribute their text.
    """
    parts = []
    for child in element:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if child_tag == "hyperlink":
            rel_id = child.get(qn("r:id"))
            url = None
            if rel_id:
                try:
                    url = part.rels[rel_id].target_ref
                except Exception:
                    pass
            anchor_parts = []
            for r in child.findall(".//" + qn("w:r")):
                for t in r.findall(qn("w:t")):
                    anchor_parts.append(t.text or "")
            anchor = "".join(anchor_parts)
            if url and anchor.strip():
                parts.append(f"[LINK:{anchor}|{url}]")
            elif anchor:
                parts.append(anchor)

        elif child_tag == "r":
            rpr = child.find(qn("w:rPr"))
            is_bold = rpr is not None and (
                _xml_toggle_on(rpr, qn("w:b")) or _xml_toggle_on(rpr, qn("w:bCs"))
            )
            is_italic = rpr is not None and (
                _xml_toggle_on(rpr, qn("w:i")) or _xml_toggle_on(rpr, qn("w:iCs"))
            )
            run_text = "".join(t.text for t in child.findall(qn("w:t")) if t.text)
            if run_text:
                if is_bold and is_italic:
                    parts.append(f"[BI]{run_text}[/BI]")
                elif is_bold:
                    parts.append(f"[B]{run_text}[/B]")
                elif is_italic:
                    parts.append(f"[I]{run_text}[/I]")
                else:
                    parts.append(run_text)

        elif child_tag == "ins":
            # Track-changes insertion — include the content
            parts.append(_element_text_with_links(child, part))

        elif child_tag == "del":
            pass  # Skip deleted content

        elif child_tag == "sdt":
            # Structured document tag — recurse into sdtContent
            sdt_content = child.find(qn("w:sdtContent"))
            if sdt_content is not None:
                parts.append(_element_text_with_links(sdt_content, part))

    return "".join(parts)


def _get_list_type(para, doc) -> str:
    """Return 'numbered' or 'bullet' by inspecting the paragraph's numFmt in numbering.xml."""
    num_pr = para._element.find(".//" + qn("w:numPr"))
    if num_pr is None:
        return "bullet"
    num_id_el = num_pr.find(qn("w:numId"))
    ilvl_el = num_pr.find(qn("w:ilvl"))
    if num_id_el is None:
        return "bullet"
    num_id = num_id_el.get(qn("w:val"))
    ilvl = ilvl_el.get(qn("w:val"), "0") if ilvl_el is not None else "0"
    try:
        npart = doc.part.numbering_part
        for num_el in npart._element.findall(qn("w:num")):
            if num_el.get(qn("w:numId")) == num_id:
                abs_id_el = num_el.find(qn("w:abstractNumId"))
                if abs_id_el is None:
                    break
                abs_id = abs_id_el.get(qn("w:val"))
                for abs_el in npart._element.findall(qn("w:abstractNum")):
                    if abs_el.get(qn("w:abstractNumId")) == abs_id:
                        for lvl_el in abs_el.findall(qn("w:lvl")):
                            if lvl_el.get(qn("w:ilvl")) == ilvl:
                                fmt_el = lvl_el.find(qn("w:numFmt"))
                                if fmt_el is not None:
                                    fmt = fmt_el.get(qn("w:val"), "bullet")
                                    return "numbered" if fmt not in ("bullet", "none") else "bullet"
    except Exception:
        pass
    return "bullet"


def _extract_document_text(docx_path: str) -> str:
    """
    Walk docx body in document order and produce structured plain text.
    No heuristics — faithfully represents what's in the document.
    Each element gets a type tag so Claude knows what it's looking at.
    """
    doc = Document(docx_path)
    lines = []

    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            try:
                para = Paragraph(child, doc)
            except Exception:
                continue

            text = para.text.strip()

            # Check for embedded images before skipping empty paragraphs
            if child.findall(".//" + qn("a:blip")):
                lines.append("[IMAGE_EMBEDDED]")
                if not text:
                    continue
            elif not text:
                continue

            style = para.style.name if para.style else "Normal"
            level_m = re.search(r"(\d+)", style) if style.startswith("Heading") else None

            if level_m:
                label = f"[H{level_m.group(1)}]"
            else:
                all_bold = all(r.bold for r in para.runs if r.text.strip())
                is_bold = all_bold and any(r.text.strip() for r in para.runs)
                num_pr = child.find(".//" + qn("w:numPr"))
                is_list = num_pr is not None or style in ("List Paragraph", "List Bullet", "List Number", "List Number 2", "List Number 3")
                is_quote = "quote" in style.lower() or style in ("Block Text", "Quotation", "Pull Quote")
                if is_list:
                    list_type = _get_list_type(para, doc)
                    label = "[LIST_NUMBERED]" if list_type == "numbered" else "[LIST_BULLET]"
                elif is_quote:
                    label = "[BLOCKQUOTE]"
                elif is_bold:
                    label = "[BOLD]"
                else:
                    label = "[P]"

            # Use inline [LINK:anchor|url] markers instead of a trailing [URLS: ...] annotation
            linked_text = _element_text_with_links(para._element, para.part).strip() or text
            lines.append(f"{label} {linked_text}")

        elif tag == "tbl":
            try:
                tbl = Table(child, doc)
            except Exception:
                continue

            nrows = len(tbl.rows)
            ncols = len(tbl.rows[0].cells) if tbl.rows else 0

            if nrows == 1 and ncols == 1:
                # Single-cell box — Quick Answer, CTA, callout, etc.
                cell = tbl.rows[0].cells[0]
                lines.append("[BOX_START]")
                for p in cell.paragraphs:
                    pt = p.text.strip()
                    if not pt:
                        continue
                    all_bold = all(r.bold for r in p.runs if r.text.strip())
                    pfx = "[BOLD]" if (all_bold and p.runs) else "[P]"
                    linked_pt = _element_text_with_links(p._element, p.part).strip() or pt
                    lines.append(f"  {pfx} {linked_pt}")
                lines.append("[BOX_END]")
            else:
                lines.append(f"[TABLE_START {nrows}x{ncols}]")
                for row in tbl.rows:
                    cells = []
                    for c in row.cells:
                        parts = []
                        for p in c.paragraphs:
                            if p.text.strip():
                                parts.append(p.text.strip())
                            if p._element.findall(".//" + qn("a:blip")):
                                parts.append("[IMAGE_EMBEDDED]")
                        # catch images not inside a paragraph (e.g. drawing directly in cell)
                        if not parts and c._element.findall(".//" + qn("a:blip")):
                            parts.append("[IMAGE_EMBEDDED]")
                        cells.append(" ".join(parts) if parts else "")
                    lines.append("  | " + " | ".join(cells) + " |")
                lines.append("[TABLE_END]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 2: Claude extraction prompt
# ---------------------------------------------------------------------------

_SCHEMA_DESCRIPTION = """
{
  "title": "H1 headline of the post",
  "subtitle": "subtitle if present, else empty string",
  "slug": "url-safe slug from title (lowercase, hyphens)",
  "url": "/slug",
  "author": "author name",
  "authorBio": "author bio paragraph if present, else empty string",
  "publishDate": "publish date as found in document, else empty string",
  "seo": {
    "metaTitle": "SEO title max 65 chars — shorten post title if needed, keep main keyword",
    "metaDescription": "120-155 char description for Google/social previews — use verbatim if present in doc, else write one based on content",
    "metaDescriptionFromDoc": true,
    "targetKeywords": ["3-5 keywords inferred from content"]
  },
  "quickAnswer": [{"headline": "Bold first line (10-20 words).", "body": "Supporting second line (15-25 words)."}],
  "quickAnswerFromDoc": true,
  "heroMedia": {"type": "image or video", "assetUid": "", "sourcePath": "", "url": "", "altText": ""} or null,
  "body": [
    {
      "type": "section",
      "heading": "H2 section heading, empty string for intro content before first H2",
      "subheading": "H3 immediately under this H2 if present, else empty string",
      "level": 2,
      "blocks": [
        {"type": "paragraph", "text": "plain paragraph text"},
        {"type": "paragraph", "runs": [{"text": "bold text", "bold": true}, {"text": " normal "}, {"text": "linked text", "url": "https://example.com"}, {"text": " continuation"}]},
        {"type": "heading", "text": "subheading text", "level": 3},
        {"type": "list", "style": "bullet or numbered", "items": ["item 1", "item 2"]},
        {"type": "table", "headers": ["Column 1", "Column 2"], "rows": [["cell", "cell"], ["cell", "cell"]]},
        {"type": "image", "sourcePath": "image_N.png or empty", "assetUid": "", "altText": "", "url": "if url-based"},
        {"type": "video", "url": "video url", "embedType": "youtube|vimeo|sharepoint|loom|wistia"},
        {"type": "blockquote", "text": "quoted text including attribution (e.g. \"Quote text\" — Author, Source, Year)"},
        {"type": "callout", "label": "bold label text", "text": "callout body text"}
      ]
    }
  ],
  "faq": [{"question": "question ending with ?", "answer": "answer text", "accordionEnabled": true}],
  "postFaqContent": ["paragraph strings that appear AFTER the last FAQ item — empty array if none"],
  "suggestedTaxonomyTerms": ["2-5 relevant blog category/topic term names inferred from content"],
  "cta_list": [{"headline": "CTA headline", "body": "CTA body text", "buttonText": "button label", "buttonUrl": "url or empty"}],
  "internalLinks": ["internal /path urls"],
  "externalLinks": ["https:// external urls"],
  "validationWarnings": ["notes about ambiguous or skipped content"]
}
"""

_EXTRACTION_PROMPT = """\
You are a content extraction specialist. Parse this blog post document and return a single JSON object.

OUTPUT SCHEMA:
{schema}

DOCUMENT:
{content}

EXTRACTION RULES:
- title: first [H1] heading, or the most prominent heading near the top
- author/publishDate: look for "By Name", "Name | Date", or "Name, Title" patterns near the top
- quickAnswer: TWO PATHS — choose based on whether the doc has a Quick Answer callout box. (1) DOC HAS A QUICK ANSWER BOX: If [BOX_START]/[BOX_END] content is labeled "Quick Answer", "Quick Summary", "Short Answer", or contains a bulleted list under such a heading near the top of the doc, extract it directly. Preserve EVERY bullet item exactly as written — do NOT merge, reduce, reorder, or reword them to hit a target count. Map each bullet as {{"headline": "bullet text verbatim", "body": ""}}. The count can be 2, 3, 4, 5, or more — whatever the doc contains. Set quickAnswerFromDoc: true. Do NOT include that box anywhere in the body sections. (2) NO QUICK ANSWER BOX: If no such box exists, synthesize exactly 3 items from the article content — each with "headline" (bold first line, 10-20 words, punchy thesis) and "body" (supporting second line, 15-25 words, elaboration or evidence). Set quickAnswerFromDoc: false. This field is REQUIRED and must have at least 1 item.
- body: map [H2] to section headings. Content before the first [H2] goes in a section with empty heading. [H3] headings NEVER become top-level sections — they must always appear inside the blocks array of their parent [H2] section as {{"type": "heading", "text": "...", "level": 3}}. Only [H2] creates new sections.
- FAQ: a section whose heading contains "FAQ", "Frequently Asked", or "Questions" — or a sequence of bold questions followed by answer paragraphs. Extract as faq array, NOT in body.
- cta_list: collect ALL [BOX] sections that contain a [LINK:] annotation or are action-oriented (e.g. "Explore X", "Learn more", "Get started", "Read the guide") — regardless of their position in the document. Include mid-document CTA boxes, not just end-of-article ones. Each matching box becomes one entry in cta_list. If no CTAs are found, set cta_list to [].
- [BOX] elements that are not Quick Answer, FAQ, or CTA: if the box contains a direct quote or citation (text starts with a quotation mark or contains an attribution like "— Author" or "— Source, Year"), map it as {{"type": "blockquote", "text": "full quote text including attribution"}}. All other non-quote boxes become {{"type": "callout", "label": "bold label text", "text": "callout body text"}}.
- [BLOCKQUOTE] paragraphs are pull-quotes formatted with Word's Quote paragraph style. Map them as {{"type": "blockquote", "text": "full quote text"}}. Also treat any [P] paragraph that opens and closes with quotation marks, or that contains a clear attribution pattern (e.g. "— Author Name" or "— Source, Year"), as a blockquote.
- Inline formatting markers: [B]text[/B] = bold, [I]text[/I] = italic, [BI]text[/BI] = bold+italic. These appear within paragraph text for mixed-format runs. Map each marked span as a separate run with the corresponding bold/italic flags. Example: "[P] See the [B]Strategy Mosaic[/B] approach" → {{"type": "paragraph", "runs": [{{"text": "See the "}}, {{"text": "Strategy Mosaic", "bold": true}}, {{"text": " approach"}}]}}. When a [B] or [I] span also contains a [LINK:anchor|url], combine both: {{"text": "anchor", "bold": true, "url": "https://..."}}.
- [BOLD] paragraphs that appear OUTSIDE a [BOX_START]/[BOX_END] block are paragraphs where ALL text is bold — map them as {{"type": "paragraph", "runs": [{{"text": "paragraph text", "bold": true}}]}}. Do NOT strip the bold or map them as plain {{"type": "paragraph", "text": "..."}}.
- [LIST_NUMBERED] means an ordered/numbered list item. [LIST_BULLET] means an unordered/bullet list item. Group consecutive same-type list items into a single list block with the correct style ("numbered" or "bullet"). Do NOT convert [LIST_NUMBERED] items to bullet style or vice versa. If numbered list items are separated by a paragraph that continues the enumeration (e.g. "Next, consider..." immediately before the next numbered item), keep the paragraph inside the list as part of the previous item's content or as a standalone paragraph within the section — do not break the list numbering.
- [IMAGE_EMBEDDED]: ALWAYS becomes its own standalone image block (type "image", with sourcePath "image_N.png" where N increments from 0, empty assetUid, altText, and url). When [IMAGE_EMBEDDED] appears between paragraphs, SPLIT the content: output all paragraph blocks before the image, then the image block, then new paragraph blocks for the text after the image. Never combine text from before and after an image into the same paragraph block. This split is required even mid-section.
- Videos: URLs containing youtube, youtu.be, vimeo, sharepoint .mp4/.mov/.webm, loom, wistia become video blocks.
- seo.metaTitle: shorten post title to ≤65 chars while keeping the main keyword.
- seo.metaDescription: if a meta description is explicitly written in the document, use it VERBATIM — copy every word exactly as written, including the full text. Set seo.metaDescriptionFromDoc=true. Otherwise write a compelling description under 150 characters — complete sentences only, never truncate mid-word or mid-phrase. Set seo.metaDescriptionFromDoc=false.
- seo.targetKeywords: infer 3-5 keywords from the content.
- table: if the first row of a table functions as a header row (column labels, bold formatting, or clearly distinct from data rows), put it in the "headers" field and data rows in "rows". If all rows are data, leave "headers" absent and put everything in "rows".
- postFaqContent: any paragraphs that appear AFTER the final FAQ question/answer pair in the document — do NOT put these in body sections. Extract as an array of plain strings. Set to [] if nothing follows the FAQ.
- suggestedTaxonomyTerms: analyze the post topic and suggest 2-5 relevant blog category or topic term names (e.g. "Semantic Layer", "Enterprise AI", "Data Governance", "Analytics"). These are used to pre-select taxonomy in Contentstack.
- Strip editorial metadata: "WEB TEAM:", "REVIEWED + OPTIMIZED", "FOR PUBLISH", "SEO: N", schema markup sections.
- Inline links: the document uses [LINK:anchor text|url] markers to indicate hyperlinks. When you see [LINK:some text|https://example.com], map it as a run with a "url" field: {{"text": "some text", "url": "https://example.com"}}. Combine with bold/italic from surrounding context as needed (e.g. {{"text": "bold link", "bold": true, "url": "https://..."}}). The [LINK:] marker replaces the old [URLS:] annotation — do not look for [URLS:] any more.
- internalLinks: collect /path URLs from [LINK:] markers. externalLinks: collect https:// URLs from [LINK:] markers.
- validationWarnings: note anything ambiguous, skipped, or that needs human review.

Return ONLY valid JSON. No markdown fences, no explanation, no extra text.
"""

_SEO_PROMPT = """\
You are an expert in SEO, AEO (AI search optimization), and enterprise B2B SaaS marketing.

Your task is to generate:

1 primary meta description (recommended)
1–2 alternative meta descriptions
SEO + AIO keyword sets (Primary, Secondary, Long-tail, Branded)

INPUT

Page Title:
{title}

Page Type:
blog post

Target Audience:
{target_audience}

Core Message / Content:
{core_message}

INSTRUCTIONS
Meta Description Rules
Length: STRICT maximum 150 characters — write complete, untruncated sentences only. Never end mid-word or mid-phrase. If needed, write a shorter sentence rather than cutting one off.
Include Strategy (or Strategy Mosaic when relevant)
Clearly communicate value + outcome
Focus on:
Trusted data
Governed metrics
Semantic layer
AI-ready foundation
Scalability / consistency
Use strong action verbs:
→ Discover, Learn, See, Explore
Avoid vague buzzwords:
❌ cutting-edge
❌ innovative solution
Make it industry-specific and use-case driven
Optimize for Google + AI search (ChatGPT, Gemini, etc.)
Keyword Rules
Primary Keywords (max 5)
Core, high-intent keywords
Example: retail analytics, semantic layer, enterprise AI analytics
Secondary Keywords (8–12)
Supporting and industry-specific terms
Include use cases (finance, supply chain, merchandising, etc.)
Long-Tail / AIO Keywords (8–12)
Natural language queries
Include formats like:
"how to…"
"why…"
"best way to…"
Reflect real buyer intent
Branded Keywords (3–5)

Always include:

Strategy
Strategy Mosaic
Strategy + [industry/use case]

STYLE GUIDELINES
Tone: Executive, clear, outcome-driven
No fluff or generic marketing language
Emphasize:
Business outcomes (ROI, speed, trust)
Data consistency
AI reliability
Align with Strategy positioning:
Universal Semantic Layer
Trusted, governed data for AI

Return ONLY valid JSON in this exact format. No markdown fences, no explanation:
{{
  "metaDescription": "recommended meta description (140-160 chars)",
  "metaDescriptionAlternatives": ["alternative 1", "alternative 2"],
  "primaryKeywords": ["keyword 1", "keyword 2"],
  "secondaryKeywords": ["keyword 1", "keyword 2"],
  "longTailKeywords": ["natural language query 1", "query 2"],
  "brandedKeywords": ["Strategy", "Strategy Mosaic"]
}}
"""


# ---------------------------------------------------------------------------
# Step 3: Claude call + post-processing
# ---------------------------------------------------------------------------


def _build_core_message(result: dict) -> str:
    """Summarize blog content for the SEO enrichment prompt."""
    parts = []
    quick = result.get("quickAnswer", [])
    if quick:
        qa_texts = []
        for item in quick:
            if isinstance(item, dict):
                qa_texts.append(item.get("headline", "") + " " + item.get("body", ""))
            else:
                qa_texts.append(str(item))
        parts.append(" ".join(qa_texts))
    for section in result.get("body", [])[:2]:
        heading = section.get("heading", "")
        if heading:
            parts.append(heading + ":")
        for block in section.get("blocks", [])[:2]:
            if block.get("type") == "paragraph":
                parts.append(block.get("text", ""))
    return " ".join(parts)[:2000]


def _enrich_seo(result: dict, client, model: str) -> dict:
    """Run the SEO/AEO enrichment prompt and merge results into seo field."""
    logger.info("Running SEO enrichment with Claude...")
    core_message = _build_core_message(result)
    # Infer target audience from author context or default to Strategy's typical reader
    author = result.get("author", "")
    audience = f"enterprise analytics leaders, BI teams, and data decision-makers following {author}" if author else "enterprise analytics leaders and BI decision-makers"

    prompt = (
        _SEO_PROMPT
        .replace("{title}", result.get("title", ""))
        .replace("{target_audience}", audience)
        .replace("{core_message}", core_message)
    )
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        seo_data = json.loads(raw)
    except json.JSONDecodeError:
        result["validationWarnings"].append("SEO enrichment failed to parse — seo fields left as extracted.")
        return result

    seo = result.setdefault("seo", {})
    from_doc = seo.get("metaDescriptionFromDoc", False)
    if from_doc:
        # Doc had an explicit meta description — keep it, surface enrichment version as an alternative
        enriched_version = seo_data.get("metaDescription", "")
        alts = seo_data.get("metaDescriptionAlternatives", [])
        if enriched_version:
            alts = [enriched_version] + alts
        seo["metaDescriptionAlternatives"] = alts
    else:
        # No doc meta description — use the enriched version
        seo["metaDescription"] = seo_data.get("metaDescription", seo.get("metaDescription", ""))
        seo["metaDescriptionAlternatives"] = seo_data.get("metaDescriptionAlternatives", [])
    seo["metaDescriptionAlternatives"] = seo_data.get("metaDescriptionAlternatives", [])
    seo["primaryKeywords"] = seo_data.get("primaryKeywords", [])
    seo["secondaryKeywords"] = seo_data.get("secondaryKeywords", [])
    seo["longTailKeywords"] = seo_data.get("longTailKeywords", [])
    seo["brandedKeywords"] = seo_data.get("brandedKeywords", [])
    # Keep targetKeywords for backwards compat — use primaryKeywords as source
    seo["targetKeywords"] = seo_data.get("primaryKeywords", seo.get("targetKeywords", []))
    result["seo"] = seo
    return result

def parse_with_claude(docx_path: str, config: Optional[dict] = None) -> dict:
    model = "claude-sonnet-4-6"
    if config:
        model = config.get("pipeline", {}).get("claude_model", model)

    client = anthropic.Anthropic()

    logger.info(f"Extracting document structure: {docx_path}")
    content = _extract_document_text(docx_path)

    logger.info(f"Sending to Claude ({model}) for extraction and normalization...")
    prompt = _EXTRACTION_PROMPT.replace("{schema}", _SCHEMA_DESCRIPTION).replace("{content}", content)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip accidental markdown fences
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), asking Claude to repair...")
        fix_response = client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "The JSON you returned has a syntax error and could not be parsed. "
                    "Please return the exact same data as valid JSON, ensuring all special "
                    "characters within string values (quotes, backslashes, newlines) are "
                    "properly escaped. Return only the JSON object, no commentary."
                )},
            ],
        )
        fixed_raw = fix_response.content[0].text.strip()
        fixed_raw = re.sub(r"^```(?:json)?\n?", "", fixed_raw)
        fixed_raw = re.sub(r"\n?```$", "", fixed_raw)
        result = json.loads(fixed_raw)

    # Deterministic fallbacks for slug/url
    if not result.get("slug"):
        result["slug"] = slugify(result.get("title", "untitled"))
    if not result.get("url"):
        result["url"] = f"/{result['slug']}"
    if not result["url"].startswith("/"):
        result["url"] = f"/{result['url']}"

    # Ensure required keys exist
    result.setdefault("validationWarnings", [])
    result.setdefault("body", [])
    result.setdefault("faq", [])
    result.setdefault("cta_list", [])
    result.setdefault("seo", {})
    result.setdefault("internalLinks", [])
    result.setdefault("externalLinks", [])

    # Default publishDate to tomorrow if missing
    if not result.get("publishDate"):
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
        result["publishDate"] = tomorrow
        result["validationWarnings"].append(
            f"publishDate was not found in the document — defaulted to tomorrow ({tomorrow}). Confirm before publishing."
        )

    # Warn if Quick Answer was synthesized (not from doc) so reviewer knows to check it
    if not result.get("quickAnswerFromDoc", True):
        result["validationWarnings"].append(
            "No Quick Answer box found in document — 3 bullets synthesized from article content. "
            "Review before publishing and edit in the Contentstack editor if needed."
        )

    # SEO enrichment — generate meta descriptions, keyword sets
    result = _enrich_seo(result, client, model)

    # Truncate meta description only when AI-generated. Doc-provided descriptions are kept
    # verbatim — flag for human review if over 160 chars.
    seo = result.get("seo", {})
    meta_desc = seo.get("metaDescription", "")
    from_doc = seo.get("metaDescriptionFromDoc", False)
    if len(meta_desc) > 160:
        if from_doc:
            result["validationWarnings"].append(
                f"Meta description from doc is {len(meta_desc)} chars (over 160 — Google may truncate). Kept verbatim; consider shortening before publishing."
            )
        else:
            trimmed = meta_desc[:160]
            for punct in (".", "!", "?"):
                idx = trimmed.rfind(punct)
                if idx > 100:
                    trimmed = trimmed[:idx + 1]
                    break
            else:
                idx = trimmed.rfind(" ")
                if idx > 0:
                    trimmed = trimmed[:idx]
            seo["metaDescription"] = trimmed
            result["validationWarnings"].append(
                f"Meta description was {len(meta_desc)} chars (over 160 limit) — trimmed to {len(trimmed)}. Original: \"{meta_desc}\""
            )
            result["seo"] = seo

    return result


def main(docx_path: str, output_path: Optional[str] = None, config: Optional[dict] = None) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = parse_with_claude(docx_path, config)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Written: {output_path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse a .docx blog to normalized JSON using Claude.",
    )
    parser.add_argument("docx_path", help="Path to .docx file")
    parser.add_argument("--output", "-o", default="output/normalized_blog.json")
    args = parser.parse_args()
    result = main(args.docx_path, args.output)
    print(f"Done. Title: {result.get('title', '(none)')}")
    print(f"  Sections: {len(result.get('body', []))}")
    print(f"  FAQ items: {len(result.get('faq', []))}")
    warnings = result.get("validationWarnings", [])
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}")
