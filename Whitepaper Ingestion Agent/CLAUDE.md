# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Takes whitepaper PDFs (or DOCX files) and produces Contentstack-ready JSON entries for strategy.com. Built on the WAT framework (Workflows/Agents/Tools). All scripts run from the project root.

**Before ingesting a new whitepaper, read [`docs/formatting_guide.md`](docs/formatting_guide.md).** It specifies how each PDF element type (headings, callouts, tables, stats, lists, CTA) maps to exact Contentstack block structures, field values, and RTE node types. This is the approved reference derived from the manually created AI Token Cost & Accuracy Benchmark page.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Full pipeline — parse, map, validate, upload
python3 scripts/run_pipeline.py input/whitepaper.pdf --upload

# Full pipeline with publish to staging
python3 scripts/run_pipeline.py input/whitepaper.pdf --upload --publish

# Run steps individually
python3 scripts/parse_with_claude.py input/whitepaper.pdf --output output/normalized.json
python3 scripts/map_to_contentstack.py output/normalized.json --output output/entry.json
python3 scripts/validate_whitepaper_json.py output/normalized.json output/entry.json
python3 scripts/upload_to_contentstack.py output/entry.json

# Update an existing entry (instead of creating a new one)
python3 scripts/upload_to_contentstack.py output/entry.json --entry-uid bltXXXXXXXX

# Dry-run upload (prints payload info without hitting the API)
python3 scripts/upload_to_contentstack.py output/entry.json --dry-run

# Inspect Contentstack schema
python3 scripts/discover_schema.py --type page
```

Output for each run goes to `output/<slug>/` — named automatically from the whitepaper title slug.

## Architecture

### Pipeline (4 steps, orchestrated by `run_pipeline.py`)

```
PDF/DOCX
  → parse_document.py       — pdfplumber or python-docx → tagged plaintext
  → parse_with_claude.py    — Claude API (2 calls) → normalized_whitepaper.json
  → map_to_contentstack.py  — normalized JSON → Contentstack page entry JSON
  → validate_whitepaper_json.py + upload_to_contentstack.py
```

**Step 1 — `parse_document.py`:** Routes by extension. PDF mode uses pdfplumber; headings detected by font size (sizes > `median * 1.3` become headings). Output is tagged plaintext: `[H1]`, `[H2]`, `[P]`, `[BOLD]`, `[LIST]`, `[TABLE_START NxM]`, `[BOX_START/END]`.

**Step 2 — `parse_with_claude.py`:** Two Claude calls — first extracts normalized JSON (title, subtitle, description, The Brief bullets, body sections, tables, CTA, SEO), second enriches SEO (meta descriptions, primary/secondary/long-tail keywords). Uses `claude-sonnet-4-6` with `max_tokens=16384`. The extraction prompt uses `.replace()` not `.format()` because the JSON schema embedded in the prompt contains `{` characters that break Python's `.format()`.

**Step 3 — `map_to_contentstack.py`:** Converts normalized JSON to a Contentstack `page` content type entry. All content goes into `content_blocks` as modular blocks. `rte_builder.py` provides helpers for building JSON RTE node trees. Two UID formats used: `_cs_uid()` = `"cs" + 16 hex chars` for `_metadata.uid`, `_doc_uid()` = 32-char UUID hex for RTE doc/node UIDs.

**Step 4 — `validate_whitepaper_json.py`:** 16 checks against both the normalized JSON and the entry JSON. Outputs `validation_report.md` with a human-review checklist including The Brief bullets, SEO alternatives, and pending items.

### Normalized JSON Schema (intermediate format)

Key fields produced by `parse_with_claude.py`:

```json
{
  "title": "...",
  "subtitle": "...",
  "slug": "url-safe-slug",
  "url": "/slug",
  "description": "hero paragraph",
  "publishedYear": "2025",
  "seo": { "metaTitle": "...", "metaDescription": "...", "targetKeywords": [] },
  "brief": [{ "boldSentence": "...", "supportingText": "..." }],
  "body": [{ "type": "section", "heading": "...", "isCallout": false, "blocks": [] }],
  "cta": { "headline": "...", "body": "...", "buttonText": "...", "buttonUrl": "" },
  "validationWarnings": []
}
```

### Contentstack Entry Structure

Whitepapers use the **`page`** content type (generic — same as all strategy.com pages). Top-level fields: `title`, `url`, `content_blocks`, `seo`, `page_properties`, `resource_data`, `taxonomies`.

`content_blocks` order: hero section → The Brief section → body sections → cta_section block.

Each section block structure:
```
section → columns → mod_column → content → text → text_block (JSON RTE doc)
```

## Contentstack API — Confirmed Valid Enum Values

These were discovered through trial-and-error. Using wrong values causes HTTP 422.

| Field | Valid values |
|---|---|
| `resource_data.type` | `"Blog"`, `"Analyst Report"` (whitepapers) |
| `more_section_options.bg_color` | `"White"` (hero, The Brief, all body sections), `"Brass"` (CTA section only) |
| `more_column_options.two_column_split` | `null` for single-column sections; `"66% / 33%"` confirmed valid for 2-col |
| `more_section_options.add_divider` | `[]` (empty array — `"Bottom"` is invalid) |
| `resource_data.date` | ISO datetime: `"YYYY-01-01T00:00:00.000Z"` (not just a year string) |

**`"Light Gray"` is invalid** as a bg_color. The correct value for a light-gray callout background is unknown — callout sections currently fall back to `"White"`.

## The Brief Section

Every whitepaper must have a "The Brief" — 3–5 bullets, each with `boldSentence` (key insight, ~15–20 words) + `supportingText` (1–2 supporting sentences). Placed directly after the hero section with `bg_color: "White"`. Each bullet renders with an orange left-bar accent via CSS — no special block type needed. These are AEO-optimized — designed to be cited by AI search engines. Claude generates them if not present in the source document.

## Config

`config.yaml` is the single source of truth for the Contentstack content type UID, field map, bg_color values, API base URL, and parser hints (section heading patterns, CTA detection keywords). Read by the mapper and upload scripts at runtime.

## Pending: RTE Serialization to Node

Per the 2026-08-26 Contentstack team review (originally scoped for the sibling Blog Ingestion Agent, applies here too): `rte_builder.py`'s hand-rolled node construction duplicates Contentstack's own open-source RTE serializer, which tracks their RTE format changes automatically (incl. tables, colors) and is where UID-based internal link references will get resolved into RTE nodes: https://github.com/contentstack/json-rte-serializer. It's an NPM module (Python doesn't take NPM), so only the final serialization step should move to a small Node call — the rest of the pipeline stays in Python. Not yet started; blocked on the shared internal-link-resolution middleware endpoint (ITS team building it) and on porting `rte_builder.py` to call the serializer. Do this after the Blog Ingestion Agent's version is proven out — no need to duplicate the work independently.

## Known Quirks

- Claude API call in Step 2 takes ~3 minutes for a 23-page PDF — don't kill the process.
- `max_tokens=16384` is required — 8192 causes JSON truncation on large whitepapers.
- PDF table extraction (pdfplumber) struggles with merged cells and complex layouts; these produce `validationWarnings` in the normalized JSON and pending checklist items in the validation report. They are expected and require human review.
- The `tags` field appears in the entry payload but not in the CS content type schema. The API accepts it anyway — the preflight warning can be ignored.
- Running `run_pipeline.py` end-to-end times out in some tool environments; run steps individually if needed.

## Shared facts

- All three pipelines use four steps: parse → map → validate → upload. Upload creates a draft only after explicit user confirmation.
- `api.base_url` is exactly `https://api-stg.microstrategy.com/cs-software` in every project `config.yaml`.
- The proxy has no PUT endpoint: an `--entry-uid` update request fails with HTTP 404. Do not promise updates; create a new draft version instead.
- `upload_to_contentstack.py` automatically normalizes titles and applies/retries `vN | <title>` (`v1 |`, `v2 |`, ...) in Blog, Whitepaper, and Glossary. Do not manually prefix or mutate `contentstack_entry.json` titles.
- Each script establishes an explicit `PROJECT_ROOT`, adds its parent repository root to `sys.path`, and imports shared utilities from `ingestion_common`; retain that contract when adding scripts or imports.
- Shared-fact changes must update this AGENTS.md and this CLAUDE.md in the same commit, and `log.md` must record the change.
