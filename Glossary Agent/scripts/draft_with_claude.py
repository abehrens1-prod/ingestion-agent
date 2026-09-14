"""
draft_with_claude.py — Synthesize normalized_glossary.json from a term_queue.json entry
plus input/sources/<slug>/harvested_sources.json.

Same two-call pattern as the Whitepaper agent's parse_with_claude.py: one call to draft
the page content, one to enrich SEO. The core instruction is Frank Volinsky's framing,
verbatim (2026-08-25): "The whole idea is just to capture whichever current content we
have on the website now, sort of aggregate it into one page on that particular topic."
This is consolidation of harvested sources, not net-new invention — see
docs/glossary_page_spec.md, which is read directly into the prompt.

Usage:
    python3 scripts/draft_with_claude.py semantic-layer
    python3 scripts/draft_with_claude.py semantic-layer \
        --term-queue input/term_queue.json --sources-dir input/sources \
        --output output/2026-08-25_semantic-layer/normalized_glossary.json
"""

import re
import json
import sys
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

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import yaml
import anthropic
from slugify import slugify

logger = logging.getLogger(__name__)

_SCHEMA_DESCRIPTION = """
{
  "title": "Page title, e.g. 'What Is a Semantic Layer?'",
  "definition": [
    {
      "boldSentence": "First sentence — the key point, stated boldly. Always ends with a period.",
      "supportingText": "1-2 sentences that expand on the key point with evidence or context."
    }
  ],
  "sections": [
    {
      "heading": "H2 phrased as a question, matching the geoQueryTarget pattern where possible",
      "blocks": [
        {"type": "paragraph", "text": "paragraph text"},
        {"type": "paragraph", "runs": [{"text": "Bold phrase:", "bold": true}, {"text": " rest of sentence"}]},
        {"type": "list", "style": "bullet or numbered", "items": ["item text", "item text"]},
        {"type": "callout", "label": "bold label text", "text": "callout body text"}
      ]
    }
  ],
  "faq": [
    {"question": "question text", "answer": "answer text"}
  ],
  "seo": {
    "metaTitle": "SEO title, max 65 chars",
    "metaDescription": "140-160 char description"
  },
  "provenance": [
    {"section": "matches a section heading, or 'definition' or 'faq'", "sourceType": "live_url|local_doc|wiki_concept|model_generated", "urlOrPath": "source url or path used, empty if model_generated", "title": "source title", "aiGenerated": true}
  ],
  "validationWarnings": ["notes about gaps, thin sourcing, or claims needing verification"]
}
"""

_DRAFT_PROMPT = """\
You are drafting a glossary/concept page for strategy.com (Strategy Software, formerly
MicroStrategy). This page is Narrative-tier content in Strategy's website framework —
its job is to build topical authority and be citable by AI answer engines for a specific
term.

CORE INSTRUCTION (Frank Volinsky, the SEO/GEO lead, verbatim): "The whole idea is just to
capture whichever current content we have on the website now, sort of aggregate it into
one page on that particular topic." This is CONSOLIDATION of the harvested sources below,
not invention. Draw claims, framing, and even phrasing from the harvested sources where
they cover the topic. Only synthesize new connective text where the sources don't already
say it plainly.

TERM: {term}
GEO QUERY TARGET (the direct question this page must answer): {geo_query}
KEYWORD TARGETS: {keyword_targets}

PAGE SPEC (read this carefully — it is the standing framework this page must follow):
{page_spec}

HARVESTED SOURCES (each tagged with its type and title — attribute every section you
draw from a source back to it in the provenance array):
{sources}

INTERNAL LINK CANDIDATES ALREADY SURFACED (weave these into sections/CTAs where relevant;
you do not need to invent additional ones):
{internal_links}

OUTPUT SCHEMA:
{schema}

DRAFTING RULES:

DEFINITION (always required, 3-5 items — modeled on the approved whitepaper "The Brief"
pattern, explicitly designed to be cited by AI search engines):
- Each item: a bold, ~15-20 word factual sentence + 1-2 sentences of supporting context.
- Lead with the harvested source that most directly answers the GEO query target.
- Do not describe what the page is about — state the actual definition/facts.

SECTIONS:
- Phrase H2 headings as direct questions, matching the citation-example pattern from the
  page spec (e.g. "What is a semantic layer?", "Benefits of semantic layers").
- Cover: the core definition/how it works, benefits, and — if the sources support it —
  how this term relates to other Strategy product/architecture concepts.
- Do not fabricate statistics. If a source states a stat you're not fully confident is
  still accurate/citable, include it but add a validationWarnings entry flagging it for
  Frank's SEO/GEO review (this happened with a "38% of analyst time" stat in one source —
  flag it, don't quietly drop or quietly trust it).

FAQ:
- Pull directly from any source that already has an FAQ section — Lauren O'Connor's post
  in this queue's sources has one that's close to publish-ready. Prefer reuse over
  rewriting when the existing Q&A is already clear and accurate.
- Add 1-2 more questions only if there's a clear gap the sources support answering.

PROVENANCE (required — this is not optional metadata, it drives the human review gate):
- One entry per section (plus "definition" and "faq" if populated).
- sourceType + urlOrPath should point at whichever harvested source most directly
  informed that section. Use "model_generated" only for connective/synthesized text with
  no single clear source.
- aiGenerated should be true for essentially everything here — this is a first-cut draft
  that Henry reviews for accuracy and Frank reviews for SEO/GEO before anything publishes.
  Do not set it false just because content closely follows a source; false is reserved for
  content reproduced verbatim from an internal, already-approved source.

SEO:
- metaTitle: include the term, ≤65 chars.
- metaDescription: 140-160 chars, should read like it could satisfy the geoQueryTarget in
  a search snippet.

Return ONLY valid JSON. No markdown fences, no explanation, no extra text.
"""

_SEO_PROMPT = """\
You are an expert in SEO, AEO (AI search optimization), and enterprise B2B SaaS marketing.

Generate keyword sets for this glossary/concept page.

Page Title: {title}
Page Type: glossary / concept page (Narrative tier, GEO Tier 2 — authority builder)
Target Audience: enterprise data/analytics leaders, BI teams, data architects, AI/ML teams
GEO Query Target: {geo_query}
Keyword Targets already assigned: {keyword_targets}
Core Message: {core_message}

Keyword Rules:
- Primary (max 5): should include the assigned keyword targets, not replace them
- Secondary (8-12): supporting and industry-specific terms
- Long-Tail / AIO (8-12): natural language queries ("what is...", "how does...", "why...")
- Branded (3-5): always include Strategy, Strategy Mosaic where relevant

Return ONLY valid JSON in this exact format. No markdown fences, no explanation:
{{
  "metaDescriptionAlternatives": ["alternative 1", "alternative 2"],
  "primaryKeywords": ["keyword 1", "keyword 2"],
  "secondaryKeywords": ["keyword 1", "keyword 2"],
  "longTailKeywords": ["natural language query 1", "query 2"],
  "brandedKeywords": ["Strategy", "Strategy Mosaic"]
}}
"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return raw


def _format_sources(harvested: dict) -> str:
    parts = []
    for s in harvested.get("sources", []):
        if not s.get("hasText"):
            continue
        parts.append(
            f"--- SOURCE [{s['sourceType']}] {s['title']} ({s.get('urlOrPath', '')}) ---\n"
            f"{s['text']}\n"
        )
    if not parts:
        return "(no harvested source text available — draft will need heavier human authorship)"
    return "\n".join(parts)


def _load_related_terms(registry_path: Path, exclude_slug: str) -> list:
    """Pull previously-published terms from glossary_registry.md for related_terms linking."""
    if not registry_path.exists():
        return []
    text = registry_path.read_text(encoding="utf-8")
    related = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Entry UID" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 5:
            continue
        term, url = cols[1], cols[4].strip("`")
        if term and slugify(term) != exclude_slug:
            related.append({"term": term, "url": url})
    return related


def draft(term_record: dict, harvested: dict, page_spec: str, registry_path: Path, locale: Optional[str] = None) -> dict:
    model_config_path = Path("config.yaml")
    model = "claude-sonnet-4-6"
    cfg = {}
    if model_config_path.exists():
        cfg = yaml.safe_load(model_config_path.read_text())
        model = cfg.get("pipeline", {}).get("claude_model", model)

    client = anthropic.Anthropic()

    prompt = (
        _DRAFT_PROMPT
        .replace("{term}", term_record["term"])
        .replace("{geo_query}", term_record.get("geoQueryTarget") or f"What is {term_record['term']}?")
        .replace("{keyword_targets}", ", ".join(term_record.get("keywordTargets", [])) or "(none assigned)")
        .replace("{page_spec}", page_spec)
        .replace("{sources}", _format_sources(harvested))
        .replace("{internal_links}", json.dumps(harvested.get("internalLinkCandidates", {}), indent=2))
        .replace("{schema}", _SCHEMA_DESCRIPTION)
    )

    logger.info(f"Sending to Claude ({model}) for drafting...")
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _strip_fences(response.content[0].text)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), asking Claude to repair...")
        fix_response = client.messages.create(
            model=model,
            max_tokens=8192,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "The JSON you returned has a syntax error and could not be parsed. "
                    "Return the exact same data as valid JSON, ensuring all special "
                    "characters within string values are properly escaped. "
                    "Return only the JSON object, no commentary."
                )},
            ],
        )
        result = json.loads(_strip_fences(fix_response.content[0].text))

    # Fill in fields the model doesn't need to produce
    result["term"] = term_record["term"]
    result["priority"] = term_record.get("priority")
    result["slug"] = term_record["slug"]
    result["url"] = f"/{term_record['slug']}"
    result["geoQueryTarget"] = term_record.get("geoQueryTarget")
    result["keywordTargets"] = term_record.get("keywordTargets", [])
    result.setdefault("validationWarnings", [])
    result.setdefault("faq", [])
    result.setdefault("provenance", [])

    # Locale: explicit --locale wins, else config default, else "en". Never guessed from
    # harvested source content — misdetection is worse than requiring a human to say so.
    result["locale"] = locale or cfg.get("contentstack", {}).get("default_locale", "en")

    result["relatedTerms"] = _load_related_terms(registry_path, term_record["slug"])
    result["internalLinks"] = {
        "toDetail": harvested.get("internalLinkCandidates", {}).get("detail", []),
        "toArrival": harvested.get("internalLinkCandidates", {}).get("arrival", []),
        "inbound": [],
    }

    if len(result["internalLinks"]["toDetail"]) + len(result["internalLinks"]["toArrival"]) < 3:
        result["validationWarnings"].append(
            "Fewer than 3 internal links surfaced from harvesting — Frank's stated minimum "
            "is >=3 in and >=3 out per page. Add more manually before publishing."
        )

    # SEO enrichment
    logger.info("Running SEO enrichment with Claude...")
    definition_text = " ".join(
        f"{d.get('boldSentence', '')} {d.get('supportingText', '')}" for d in result.get("definition", [])[:2]
    )
    seo_response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": _SEO_PROMPT.format(
            title=result.get("title", ""),
            geo_query=result.get("geoQueryTarget", ""),
            keyword_targets=", ".join(result.get("keywordTargets", [])),
            core_message=definition_text[:2000],
        )}],
    )
    try:
        seo_data = json.loads(_strip_fences(seo_response.content[0].text))
    except json.JSONDecodeError:
        result["validationWarnings"].append("SEO enrichment JSON parse failed — seo fields left as drafted.")
        seo_data = {}

    seo = result.setdefault("seo", {})
    seo["metaDescriptionAlternatives"] = seo_data.get("metaDescriptionAlternatives", [])
    seo["primaryKeywords"] = seo_data.get("primaryKeywords", [])
    seo["secondaryKeywords"] = seo_data.get("secondaryKeywords", [])
    seo["longTailKeywords"] = seo_data.get("longTailKeywords", [])
    seo["brandedKeywords"] = seo_data.get("brandedKeywords", [])
    seo["targetKeywords"] = seo_data.get("primaryKeywords") or result.get("keywordTargets", [])
    result["seo"] = seo

    meta_desc = seo.get("metaDescription", "")
    if len(meta_desc) > 160:
        seo["metaDescription"] = meta_desc[:157].rstrip() + "..."
        result["validationWarnings"].append(f"Meta description was {len(meta_desc)} chars — truncated to 160.")

    return result


def main(
    slug: str,
    term_queue_path: str = "input/term_queue.json",
    sources_dir: str = "input/sources",
    page_spec_path: str = "docs/glossary_page_spec.md",
    registry_path: str = "glossary_registry.md",
    output_path: Optional[str] = None,
    locale: Optional[str] = None,
) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    term_queue = json.loads(Path(term_queue_path).read_text())
    term_record = next((t for t in term_queue if t["slug"] == slug), None)
    if term_record is None:
        raise ValueError(f"Slug '{slug}' not found in {term_queue_path}")

    harvested_path = Path(sources_dir) / slug / "harvested_sources.json"
    if not harvested_path.exists():
        raise FileNotFoundError(f"{harvested_path} not found — run harvest_sources.py {slug} first.")
    harvested = json.loads(harvested_path.read_text())

    page_spec = Path(page_spec_path).read_text(encoding="utf-8")

    result = draft(term_record, harvested, page_spec, Path(registry_path), locale=locale)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Written: {output_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Draft normalized_glossary.json from a term and its harvested sources.")
    parser.add_argument("slug", help="Term slug, e.g. semantic-layer")
    parser.add_argument("--term-queue", default="input/term_queue.json")
    parser.add_argument("--sources-dir", default="input/sources")
    parser.add_argument("--page-spec", default="docs/glossary_page_spec.md")
    parser.add_argument("--registry", default="glossary_registry.md")
    parser.add_argument("--output", "-o", default=None)
    parser.add_argument("--locale", default=None, help="Locale code (e.g. es, fr) — defaults to contentstack.default_locale in config.yaml")
    args = parser.parse_args()
    out = args.output or f"output/{__import__('datetime').date.today().isoformat()}_{args.slug}/normalized_glossary.json"
    result = main(args.slug, args.term_queue, args.sources_dir, args.page_spec, args.registry, out, locale=args.locale)
    print(f"Done. Title: {result.get('title', '(none)')}")
    print(f"  Definition bullets: {len(result.get('definition', []))}")
    print(f"  Sections: {len(result.get('sections', []))}")
    print(f"  FAQ: {len(result.get('faq', []))}")
    for w in result.get("validationWarnings", []):
        print(f"  ⚠ {w}")
