# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Pipeline

Requires `ANTHROPIC_API_KEY` and `MSTR_API_KEY` in `.env`. Run from this project's root directory:

```bash
# Full pipeline (parse → map → validate)
python3 scripts/run_pipeline.py input/blog.docx

# Full pipeline + upload to Contentstack stage
python3 scripts/run_pipeline.py input/blog.docx --upload

# Full pipeline + upload + publish to stage.strategysoftware.com
python3 scripts/run_pipeline.py input/blog.docx --upload --publish

# Custom output dir
python3 scripts/run_pipeline.py input/blog.docx --output-dir output/my-blog
```

**Individual steps:**

```bash
python3 scripts/parse_with_claude.py input/blog.docx --output output/normalized_blog.json
python3 scripts/map_to_contentstack.py output/normalized_blog.json --output output/contentstack_entry.json
python3 scripts/validate_blog_json.py output/normalized_blog.json output/contentstack_entry.json

# Upload a previously generated entry (with optional --publish, --dry-run)
python3 scripts/upload_to_contentstack.py output/henry-guo-blog-post-2026-05/contentstack_entry.json
```

**Dependencies:** `pip install -r requirements.txt`

## Architecture

Four-step pipeline: `parse_with_claude` → `map_to_contentstack` → `validate_blog_json` → `upload_to_contentstack` (optional). `run_pipeline.py` orchestrates all steps using `importlib.util` dynamic imports — every script is both a standalone CLI tool and an importable module.

**Data flow:**
- `parse_with_claude.py` → `normalized_blog.json` — internal clean format
- `map_to_contentstack.py` → `contentstack_entry.json` — `{"entry": {...}, "_mapping_warnings": [...]}` payload; only the `entry` key is uploaded
- `validate_blog_json.py` → `validation_report.md` — PASS/WARN/ERROR checklist
- `upload_to_contentstack.py` → `upload_response.json` — API response including the created entry UID

**Key design decisions:**

`parse_with_claude.py` has **two Claude API calls** per run: (1) a deterministic docx walker extracts document content as structured plain text using element type tags (`[H1]`, `[H2]`, `[BOLD]`, `[P]`, `[LIST]`, `[BOX_START/END]`, `[TABLE_START/END]`, `[URLS:]`, `[IMAGE_EMBEDDED]`); (2) a primary Claude call returns the complete `normalized_blog.json` — section detection, FAQ/CTA/Quick Answer, SEO field generation, no regex tuning; (3) a second Claude call runs the SEO/AEO enrichment prompt and adds `primaryKeywords`, `secondaryKeywords`, `longTailKeywords`, `brandedKeywords`, and `metaDescriptionAlternatives` to `seo`. If the doc included a meta description, it is kept verbatim and the enrichment version is surfaced as an alternative for human review; if the doc had no meta description, the enrichment version is used.

**publishDate handling:** If `publishDate` is not found in the document, the pipeline defaults it to **tomorrow** (run date + 1 day, ISO 8601) and adds a `validationWarning` flagging it for confirmation. Always verify the date before publishing.

**Meta description handling:** If the doc includes a meta description it is used verbatim (`seo.metaDescriptionFromDoc: true`). If over 160 chars it is auto-truncated and the original is preserved in `validationWarnings`. The SEO enrichment call always generates 1–2 alternatives in `seo.metaDescriptionAlternatives` for the reviewer to compare.

**Validation report structure:** `validation_report.md` now opens with a **"Ready to Post? — Review Checklist"** section containing post details, meta description + alternatives, keyword sets, and a `- [ ]` checklist of pending human actions. This section is designed to be forwarded to the content reviewer before publishing. The technical PASS/WARN/ERROR detail follows below the `---` divider.

`rte_builder.py` is a helper module, never run directly. Exports only `build_body()` (JSON RTE node array). `map_to_contentstack.py` calls it when building the `body` field.

`config.yaml` is the only configuration surface:
- `contentstack.field_map` — maps normalized field names to Contentstack field UIDs (confirmed from a live exported entry)
- `contentstack.authors` — display name → entry UID lookup; fill from Contentstack CMS → Content → Authors
- `contentstack.taxonomy_uid` / `taxonomy_terms` — taxonomy UID confirmed as `"blog"`, term UIDs still blank
- `api.base_url` — MicroStrategy API proxy (`https://api-stg.microstrategy.com/cs-software`)
- `pipeline.claude_model` — controls which model is used for parsing

**API proxy auth:** All requests to the proxy use the `x-mstr-key` header, sourced from `MSTR_API_KEY` in `.env`. Available content types: `blog_post`, `page`, `cvent_page`.

**Upload pre-flight:** `upload_to_contentstack.py` calls `GET /content_types/{contentType}` before posting to compare payload field names against the live schema and warn on mismatches — useful for catching field UID drift.

**Images are never uploaded.** Image blocks carry a `sourcePath` or `url` placeholder and an empty `assetUid`. Validation will WARN on all images missing `assetUid`. Workflow: upload images to Contentstack Assets manually → paste UIDs into `normalized_blog.json` → re-run `map_to_contentstack.py`.

**Fields that do NOT exist on the blog content type:** `authorBio` is on the Author entry in Contentstack, not the blog post — do not attempt to map or upload it. `tags` is also absent from the live schema; Contentstack silently ignores it on upload.

**CTA section (`cta_section`):** This is a reference to a Promo content type entry in Contentstack, not a structured object. The pipeline extracts CTA content but cannot create or link a Promo entry automatically. After upload, open the draft entry in Contentstack and add the Promo entry UID manually. If a second CTA appears in the doc above the FAQ section, the pipeline may miss or merge it — check `validationWarnings` for any note about a skipped CTA.

**Stale mapping warnings:** After manually editing `normalized_blog.json` and re-running `map_to_contentstack.py`, the `_mapping_warnings` array in `contentstack_entry.json` reflects the original parse and may reference items already resolved. Trust the actual field values over the warning list.

**Known pipeline limitations:**

**Hyperlinks are preserved inline.** The docx walker emits `[LINK:anchor text|url]` markers in the extracted text. Claude maps these to paragraph runs with a `url` field, and `rte_builder.py` converts them to Contentstack anchor nodes (`{"type": "a", "attrs": {"url": ..., "target": "_blank"}}`). Any blog post processed before this fix (prior to June 2026) will be missing hyperlinks and must have them added manually in the Contentstack editor.

**Numbered sub-sections that are H2 in the source doc** will be mapped as separate H2 sections, not as a numbered list. If the author wants items like "1. The work that's already there / 2. The answer you think... / 3. The assumption..." to appear as a numbered list, they must be formatted as an ordered list in the .docx, not as H2 headings. The pipeline will always follow the source doc structure.

**Bold + numbered framework steps** split across multiple list blocks (e.g. a four-step framework interrupted by an intervening paragraph) will not be automatically merged or renumbered. These must be corrected manually in the Contentstack editor or fixed in the source .docx before re-parsing.

**lead_paragraph contains only the Quick Summary.** Intro paragraphs (all content before the first H2) are placed in the first content block, not in `lead_paragraph`. This is intentional — `lead_paragraph` maps to a visually distinct field in the blog template (gray background), so it should only hold the Quick Summary. Do not put intro paragraphs back into `lead_paragraph`.
