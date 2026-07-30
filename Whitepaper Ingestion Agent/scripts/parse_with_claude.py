"""
parse_with_claude.py — Extract and normalize a whitepaper (PDF or DOCX) using Claude.

Two-call pattern:
  1. Extraction: structured tagged text → normalized_whitepaper.json
  2. SEO enrichment: title + content → meta descriptions, keyword sets

Key whitepaper differences from blog:
  - "The Brief" is always generated (3-5 bullets, bold first sentence each) — AEO/BLUFF section
  - No author field — corporate document
  - Hero has H1 + optional subtitle + short description
  - Executive Summary is always the first major section
  - Callout boxes: Claude decides based on section density/importance
  - Tables: plain text extraction, no color

Usage:
    python scripts/parse_with_claude.py input/whitepaper.pdf
    python scripts/parse_with_claude.py input/whitepaper.docx --output output/normalized_whitepaper.json
"""

import re
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic
from slugify import slugify

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema and prompts
# ---------------------------------------------------------------------------

_SCHEMA_DESCRIPTION = """
{
  "title": "H1 headline of the whitepaper",
  "subtitle": "subtitle / orange H3 tagline if present, else empty string",
  "slug": "url-safe slug from title (lowercase, hyphens)",
  "url": "/slug",
  "description": "2-3 sentence intro paragraph for the hero section",
  "publishedYear": "year as string, e.g. '2025', or empty string",
  "seo": {
    "metaTitle": "SEO title max 65 chars — shorten whitepaper title if needed",
    "metaDescription": "120-155 char description — use verbatim if present in doc, else write one",
    "metaDescriptionFromDoc": true,
    "targetKeywords": ["3-5 keywords inferred from content"]
  },
  "brief": [
    {
      "boldSentence": "First sentence — the key point, stated boldly. Always ends with a period.",
      "supportingText": "1-2 sentences that expand on the key point with evidence or context."
    }
  ],
  "body": [
    {
      "type": "section",
      "heading": "H2 section heading — empty string for intro content before first H2",
      "subheading": "H3 immediately under this H2 if present, else empty string",
      "level": 2,
      "isCallout": false,
      "calloutRationale": "",
      "blocks": [
        {"type": "paragraph", "text": "paragraph text"},
        {"type": "paragraph", "runs": [{"text": "Bold phrase:", "bold": true}, {"text": " rest of sentence"}]},
        {"type": "heading", "text": "subheading text", "level": 3},
        {"type": "list", "style": "bullet or numbered", "items": [
          "plain text item",
          [{"text": "Bold label:", "bold": true}, {"text": " rest of item text"}]
        ]},
        {"type": "table", "headers": ["Col 1", "Col 2"], "rows": [["cell", "cell"]]},
        {"type": "callout", "label": "bold label text", "text": "callout body text"}
      ]
    }
  ],
  "cta": {"headline": "CTA headline", "body": "CTA body text", "buttonText": "button label", "buttonUrl": ""},
  "internalLinks": ["/path urls"],
  "externalLinks": ["https:// external urls"],
  "validationWarnings": ["notes about ambiguous or skipped content"]
}
"""

_EXTRACTION_PROMPT = """\
You are a content extraction specialist for enterprise technology whitepapers.
Parse this whitepaper and return a single JSON object.

OUTPUT SCHEMA:
{schema}

DOCUMENT:
{content}

EXTRACTION RULES:

TITLE + HERO:
- title: the primary H1 heading — the whitepaper title
- subtitle: an orange/styled H3 tagline beneath the title if present
- description: 2-3 sentence paragraph suitable for the hero section introduction.
  If a clear intro paragraph exists near the top, use it verbatim or lightly edited.
  Otherwise synthesize from the Executive Summary opening.

THE BRIEF (always required — generate if not present in document):
- Generate exactly 3 bullet points (max 5 if the content warrants it).
- Each bullet has a boldSentence (the key insight, ~15-20 words, ends with period)
  and supportingText (1-2 sentences of evidence or context, ~30-50 words).
- These are meant for AEO/AI citation — they should be the most citable, factual claims.
- Draw from the Executive Summary and the most data-rich sections.
- Do NOT repeat the title or describe what the paper is about — give the actual insights.

BODY SECTIONS:
- Map [H2] to section headings. Content before first [H2] goes in a section with empty heading.
- Map [H3] to either section.subheading (if immediately after H2) or heading blocks inside blocks.

NUMBERED HEADINGS (critical — do not drop numbers):
- ALWAYS preserve numbered prefixes in headings EXACTLY as they appear in the source.
- Examples: "1. Hallucination Fire" NOT "Hallucination Fire", "II. The Context Gap" NOT "The Context Gap",
  "A. Executive Summary" NOT "Executive Summary".
- This applies to ALL heading levels (H1, H2, H3) and ALL numbering styles (1., I., i., A., a., etc.).
- Never strip a leading number, roman numeral, or letter prefix from a heading.

BOLD TEXT (critical — preserve inline formatting):
- When a paragraph or list item contains bold text (marked [BOLD] in source), use the runs format.
- For paragraphs with bold: {"type": "paragraph", "runs": [{"text": "Bold phrase:", "bold": true}, {"text": " regular text"}]}
- For list items with bold: items array entry becomes an array of runs instead of a plain string:
  [{"text": "Bold label:", "bold": true}, {"text": " rest of item"}]
- Common pattern: "**Bold term:** Regular explanation" → split into bold run + regular run.
- Only use plain string items when the entire item has no bold/italic formatting.

- Tables: extract as {"type": "table", "headers": [...], "rows": [[...], ...]}
  - First row is headers if the cells look like column labels.
  - ALL cells as plain strings — no color, no styling.
  - Empty cells become empty strings "".
- CALLOUT DECISIONS (isCallout field):
  - Set isCallout: true for sections that are dense with statistics, key findings, or important warnings.
  - Typical callout candidates: sections with multiple statistics, benchmark data, key risk factors.
  - Do NOT set every section as callout — only 1-3 per document maximum.
  - Set calloutRationale to a short phrase explaining why (e.g., "contains benchmark statistics").

CTA:
- Find any action-oriented section near the end (Get Started, Learn More, Request Demo, Contact Us).
- Extract as the cta object. buttonUrl will usually be empty (add manually after upload).
- If no CTA found, set cta to null.

SEO:
- seo.metaTitle: shorten whitepaper title to ≤65 chars, keep main keyword.
- seo.metaDescription: if explicitly written in doc, use verbatim + set metaDescriptionFromDoc=true.
  Otherwise write a compelling 120-155 char description from the content.
- seo.targetKeywords: 3-5 primary keywords from content.

LINKS:
- internalLinks: /path URLs. externalLinks: https:// URLs.

TABLES:
- Never carry over color information (background colors, red/green cells).
- If a table has many merged cells or complex layout, simplify to a flat grid.

VALIDATION:
- validationWarnings: note any ambiguous content, skipped sections, or items needing human review.

Return ONLY valid JSON. No markdown fences, no explanation, no extra text.
"""

_SEO_PROMPT = """\
You are an expert in SEO, AEO (AI search optimization), and enterprise B2B SaaS marketing.

Generate meta descriptions and keyword sets for this whitepaper.

Page Title: {title}
Page Type: whitepaper / research report
Target Audience: enterprise analytics leaders, BI teams, data architects, and IT decision-makers
Core Message: {core_message}

Meta Description Rules:
- Length: 140–160 characters
- Include "Strategy" (or "Strategy Mosaic" when relevant)
- Communicate the whitepaper's core finding or value proposition
- Use strong action verbs: Discover, Learn, See, Explore
- Make it specific to the findings — not generic "learn about X"
- Optimize for Google + AI search (ChatGPT, Gemini, etc.)

Keyword Rules:
- Primary (max 5): core, high-intent keywords
- Secondary (8–12): supporting and industry-specific terms
- Long-Tail / AIO (8–12): natural language queries ("how to...", "why...", "best way to...")
- Branded (3–5): always include Strategy, Strategy Mosaic

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
# Numbered heading repair
# ---------------------------------------------------------------------------

_NUMBERED_PREFIX_RE = re.compile(
    r'^((?:\d+|[IVXivx]+|[A-Za-z])\.\s+)',
)

def _fix_numbered_headings(result: dict, tagged_text: str) -> dict:
    """
    Scan the tagged source text for headings that carry a numbered/lettered prefix
    (e.g. '1. Hallucination Fire', 'II. The Context Gap').  If the same heading
    appears in the extracted JSON WITHOUT that prefix, restore it.
    """
    heading_tag_re = re.compile(r'^\[H\d\]\s*(.+)$', re.MULTILINE)

    # Build a map: bare_lower → full_text (with prefix) from the source
    source_numbered: dict = {}
    for m in heading_tag_re.finditer(tagged_text):
        full = m.group(1).strip()
        pm = _NUMBERED_PREFIX_RE.match(full)
        if pm:
            bare = full[len(pm.group(1)):].strip().lower()
            source_numbered[bare] = full

    if not source_numbered:
        return result

    fixed = 0

    def _try_fix(text: str) -> str:
        nonlocal fixed
        candidate = source_numbered.get(text.strip().lower())
        if candidate and candidate != text.strip():
            fixed += 1
            return candidate
        return text

    for section in result.get("body", []):
        section["heading"] = _try_fix(section.get("heading", ""))
        section["subheading"] = _try_fix(section.get("subheading", ""))
        for block in section.get("blocks", []):
            if block.get("type") == "heading":
                block["text"] = _try_fix(block.get("text", ""))

    if fixed:
        result["validationWarnings"].append(
            f"Restored numbered prefix on {fixed} heading(s) that were stripped during extraction."
        )
    return result


# ---------------------------------------------------------------------------
# SEO enrichment
# ---------------------------------------------------------------------------

def _build_core_message(result: dict) -> str:
    parts = []
    brief = result.get("brief", [])
    for b in brief[:2]:
        sentence = b.get("boldSentence", "")
        support = b.get("supportingText", "")
        if sentence:
            parts.append(sentence)
        if support:
            parts.append(support)
    for section in result.get("body", [])[:2]:
        heading = section.get("heading", "")
        if heading:
            parts.append(heading + ":")
        for block in section.get("blocks", [])[:2]:
            if block.get("type") == "paragraph":
                parts.append(block.get("text", ""))
    return " ".join(parts)[:2000]


def _enrich_seo(result: dict, client, model: str) -> dict:
    logger.info("Running SEO enrichment with Claude...")
    core_message = _build_core_message(result)
    prompt = _SEO_PROMPT.format(
        title=result.get("title", ""),
        core_message=core_message,
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
        result["validationWarnings"].append("SEO enrichment JSON parse failed — seo fields left as extracted.")
        return result

    seo = result.setdefault("seo", {})
    from_doc = seo.get("metaDescriptionFromDoc", False)
    if from_doc:
        enriched = seo_data.get("metaDescription", "")
        alts = seo_data.get("metaDescriptionAlternatives", [])
        seo["metaDescriptionAlternatives"] = ([enriched] + alts) if enriched else alts
    else:
        seo["metaDescription"] = seo_data.get("metaDescription", seo.get("metaDescription", ""))
        seo["metaDescriptionAlternatives"] = seo_data.get("metaDescriptionAlternatives", [])
    seo["primaryKeywords"] = seo_data.get("primaryKeywords", [])
    seo["secondaryKeywords"] = seo_data.get("secondaryKeywords", [])
    seo["longTailKeywords"] = seo_data.get("longTailKeywords", [])
    seo["brandedKeywords"] = seo_data.get("brandedKeywords", [])
    seo["targetKeywords"] = seo_data.get("primaryKeywords", seo.get("targetKeywords", []))
    result["seo"] = seo
    return result


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def parse_with_claude(file_path: str, config: Optional[dict] = None) -> dict:
    model = "claude-sonnet-4-6"
    if config:
        model = config.get("pipeline", {}).get("claude_model", model)

    client = anthropic.Anthropic()

    # Step 1: parse document → tagged text
    logger.info(f"Extracting document: {file_path}")
    from parse_document import extract as extract_document
    content = extract_document(file_path)

    # Step 2: Claude extraction
    logger.info(f"Sending to Claude ({model}) for extraction...")
    prompt = _EXTRACTION_PROMPT.replace("{schema}", _SCHEMA_DESCRIPTION).replace("{content}", content)

    response = client.messages.create(
        model=model,
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), asking Claude to repair...")
        fix_response = client.messages.create(
            model=model,
            max_tokens=16384,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "The JSON you returned has a syntax error and could not be parsed. "
                    "Please return the exact same data as valid JSON, ensuring all special "
                    "characters within string values are properly escaped. "
                    "Return only the JSON object, no commentary."
                )},
            ],
        )
        fixed = fix_response.content[0].text.strip()
        fixed = re.sub(r"^```(?:json)?\n?", "", fixed)
        fixed = re.sub(r"\n?```$", "", fixed)
        result = json.loads(fixed)

    # Restore any numbered heading prefixes Claude dropped
    result = _fix_numbered_headings(result, content)

    # Normalize slug / url
    if not result.get("slug"):
        result["slug"] = slugify(result.get("title", "untitled"))
    if not result.get("url"):
        result["url"] = f"/{result['slug']}"
    if not result["url"].startswith("/"):
        result["url"] = f"/{result['url']}"

    # Ensure required keys exist
    result.setdefault("validationWarnings", [])
    result.setdefault("body", [])
    result.setdefault("brief", [])
    result.setdefault("seo", {})
    result.setdefault("cta", None)
    result.setdefault("internalLinks", [])
    result.setdefault("externalLinks", [])

    # Validate brief count
    brief = result.get("brief", [])
    if len(brief) < 3:
        result["validationWarnings"].append(
            f"The Brief has {len(brief)} bullet(s) — minimum is 3. Review and add more if needed."
        )
    if len(brief) > 5:
        result["validationWarnings"].append(
            f"The Brief has {len(brief)} bullet(s) — maximum is 5. Trim to the most impactful."
        )

    # SEO enrichment
    result = _enrich_seo(result, client, model)

    # Truncate meta description if over limit
    seo = result.get("seo", {})
    meta_desc = seo.get("metaDescription", "")
    if len(meta_desc) > 160:
        truncated = meta_desc[:157].rstrip() + "..."
        seo["metaDescription"] = truncated
        result["validationWarnings"].append(
            f"Meta description was {len(meta_desc)} chars — truncated to 160. Original: \"{meta_desc}\""
        )
        result["seo"] = seo

    return result


def main(file_path: str, output_path: Optional[str] = None, config: Optional[dict] = None) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = parse_with_claude(file_path, config)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Written: {output_path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse a whitepaper PDF or DOCX to normalized JSON using Claude.")
    parser.add_argument("file_path", help="Path to .pdf or .docx whitepaper")
    parser.add_argument("--output", "-o", default="output/normalized_whitepaper.json")
    args = parser.parse_args()
    result = main(args.file_path, args.output)
    print(f"Done. Title: {result.get('title', '(none)')}")
    print(f"  Brief bullets: {len(result.get('brief', []))}")
    print(f"  Sections: {len(result.get('body', []))}")
    warnings = result.get("validationWarnings", [])
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}")
