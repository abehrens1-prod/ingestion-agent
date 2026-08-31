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

`rte_builder.py` is a helper module, never run directly. `map_to_contentstack.py` calls its per-block builders (`p_node`, `heading_node`, `ul_node`/`ol_node`, `table_node`, `blockquote_node`) via `_block_to_node()` when assembling the `content` field.

**RTE formatting nodes are built via Node (`scripts/rte_serializer_node/`), done 2026-08-27.** Per the 2026-08-26 Contentstack team review, hand-rolling RTE node JSON duplicates Contentstack's own open-source RTE serializer (`@contentstack/json-rte-serializer`, https://github.com/contentstack/json-rte-serializer), which tracks their RTE format changes automatically. It's an NPM module, so it lives as a standalone Node subproject; Python calls it as a subprocess.

- **How it works:** `p_node`, `heading_node`, `ul_node`, `ol_node`, `table_node`, and `blockquote_node` each render a small HTML fragment (e.g. `<p><b>bold</b> text <a href="...">link</a></p>`) and pipe it through `scripts/rte_serializer_node/serialize.js` (`htmlToJson()` + jsdom), one subprocess call per node — a typical post makes 20-50 calls, adding roughly 5 seconds total (verified: `map_to_contentstack.py` ran in ~5.3s against a real post). Structural placeholders (`callout_node`, image-pending nodes) stay hand-built in Python — they're not real RTE formatting, no need to round-trip them.
- **Scope, deliberately**: only the article-body formatting builders moved. FAQ accordion answers, Quick Answer, lead paragraph, and CTA placeholder text in `map_to_contentstack.py` still hand-build their RTE nodes directly — that's Contentstack block *scaffolding* (uids, block types, layout), not rich-text formatting fidelity, so it was left alone as a smaller, safer diff.
- **Verified**: all 39 existing `normalized_blog.json` files in `output/` map successfully with zero errors. One real content post round-tripped through and manually inspected — blockquote two-tone coloring, table headers, bold/italic runs, and links all came out correct.
- **Bug found and fixed 2026-08-27: the installed serializer (`@contentstack/json-rte-serializer` 3.1.0) silently drops a text node's color style whenever it's combined with bold/italic in the source HTML.** Verified directly against the package — every nesting order tried (`<b><span style="color:...">`, `<span><b>`, style on the `<b>` itself, `<strong>` instead of `<b>`) drops the color and keeps only the bold. This was caught because the real IDC Spotlight post's blockquote attribution (bold + blue, per `blockquote_node`'s two-tone spec) was rendering bold but colorless in the actual generated `contentstack_entry.json` — the "came out correct" verification above did not specifically check the attribution segment. Fixed in `blockquote_node` by serializing the attribution's bold mark *without* color in the HTML, then patching `attrs.style.color` onto the resulting text leaf directly in Python afterward — the serializer still does all the structural/uid work, only the color is hand-applied. No other node builder here combines a mark with a color, so no other function is affected. **If a real entry was already uploaded before this fix** (check `output/*/upload_response.json` for entries created on 2026-08-27 before this fix), its blockquote attribution likely rendered without color in Contentstack and should be re-uploaded or manually corrected.
- **One dropped behavior**: table column widths (`colWidths`) used to be computed proportionally to cell-content length; now they're the serializer's own default (equal split). Matches the "stop duplicating Contentstack's logic" principle behind this whole change, but is a visible rendering difference on wide/uneven tables — watch for it in review.
- **Second bug found and fixed 2026-08-27: links lost `target="_blank"`.** `_runs_to_html`'s anchor tag was `<a href="...">` with no `target` attribute, so the serializer never set one — every link in the real output was missing `attrs.target: "_blank"` (present in every hand-built node before this migration). Fixed by adding `target="_blank"` to the source HTML.
- **`build_body()` removed** — it was dead code (the module docstring claimed `map_to_contentstack.py` called it for the whole `body` field, but the actual live code path has always called `_block_to_node()` per-block from `_build_content_blocks()`; that docstring claim was already stale before this change).
- **Internal link UID references — the actual mechanism**, confirmed from the package's own test fixtures (not guessed): feed it an anchor shaped like `<a class="embedded-entry redactor-component block-entry" target="_blank" type="entry" data-sys-entry-uid="bltXXXX" data-sys-content-type-uid="blog_post" data-sys-entry-locale="en-us" sys-style-type="link">text</a>` and it emits a native `{"type": "reference", "attrs": {"entry-uid": ..., "content-type-uid": ..., "display-type": "link", "locale": ...}}` node — a real UID-backed reference, not a hyperlink. A plain `<a href="...">` still works fine for external links or unresolved internal ones. **Not wired in yet** — turning a resolved internal link path into those attributes requires the middleware endpoint (Mikhal, not yet built) to resolve URL → UID + content type; `_runs_to_html()` in `rte_builder.py` only emits plain `<a href>` today.
- **Requires Node + `npm install` in `scripts/rte_serializer_node/`** — if that hasn't been run on a given machine, every mapping call fails immediately with a clear error pointing at the fix.

`config.yaml` is the only configuration surface:
- `contentstack.field_map` — maps normalized field names to Contentstack field UIDs (confirmed from a live exported entry)
- `contentstack.authors` — display name → entry UID lookup; fill from Contentstack CMS → Content → Authors
- `contentstack.taxonomy_uid` / `taxonomy_terms` — taxonomy UID confirmed as `"blog"`, term UIDs still blank
- `api.base_url` — MicroStrategy API proxy (`https://api-stg.microstrategy.com/cs-software`)
- `pipeline.claude_model` — controls which model is used for parsing

**API proxy auth:** All requests to the proxy use the `x-mstr-key` header, sourced from `MSTR_API_KEY` in `.env`. Available content types: `blog_post`, `page`, `cvent_page`.

**Upload pre-flight:** `upload_to_contentstack.py` calls `GET /content_types/{contentType}` before posting to compare payload field names against the live schema and warn on mismatches — useful for catching field UID drift.

**Image uploads via `upload_assets.py`.** `api.assets_url` in `config.yaml` points at the dedicated blog-post assets endpoint Dale (ITS) provided 2026-08-26 (`.../uploadToBlogAssetsFolder`) — POST, multipart with a single `body` field holding the file. Run `python3 scripts/upload_assets.py output/<slug>/ input/blog.docx` to extract embedded docx images and upload them, which patches `assetUid` into `normalized_blog.json` automatically. **The response shape from this endpoint is unverified** — the parser tries `resp_json["uid"]` / `resp_json["asset"]["uid"]`; if a real upload doesn't populate `assetUid`, check the raw response the script prints and adjust the parsing in `upload_assets.py`. If asset upload isn't run, image blocks keep their `sourcePath`/`url` placeholder and empty `assetUid`, and validation will WARN on it — fall back to uploading manually and pasting UIDs into `normalized_blog.json`.

**Fields that do NOT exist on the blog content type:** `authorBio` is on the Author entry in Contentstack, not the blog post — do not attempt to map or upload it. `tags` exists on the schema (system-required, per Dale/ITS — it can't actually be removed from the content type) but is unused for blog posts; the pipeline no longer sends it in the payload at all (previously sent as `[]`, which Contentstack silently ignored — now just omitted).

**Locale.** `map_to_contentstack.py` sets `entry.locale` from `normalized.locale`, which defaults to `contentstack.default_locale` in `config.yaml` (`"en"`) unless overridden with `--locale <code>` on `parse_with_claude.py` / `run_pipeline.py`. Valid codes are in `contentstack.locales` (en, es, fr, de, it, ja, ko, pt, pl, zh, th — from Dale, ITS, 2026-08-26). `upload_to_contentstack.py` passes it as a `?locale=` query param on create/update, per Contentstack's documented CMA contract. **Unverified against a real non-`"en"` upload** — every live entry so far has used `"en"`; the first non-English post through this pipeline should be checked carefully in Contentstack (draft, unpublished) before trusting it.

**CTA section (`cta_section`):** This is a reference to a Promo content type entry in Contentstack, not a structured object. The pipeline extracts CTA content but cannot create or link a Promo entry automatically. After upload, open the draft entry in Contentstack and add the Promo entry UID manually. If a second CTA appears in the doc above the FAQ section, the pipeline may miss or merge it — check `validationWarnings` for any note about a skipped CTA.

**Stale mapping warnings:** After manually editing `normalized_blog.json` and re-running `map_to_contentstack.py`, the `_mapping_warnings` array in `contentstack_entry.json` reflects the original parse and may reference items already resolved. Trust the actual field values over the warning list.

**Known pipeline limitations:**

**Hyperlinks are preserved inline.** The docx walker emits `[LINK:anchor text|url]` markers in the extracted text. Claude maps these to paragraph runs with a `url` field, and `rte_builder.py` converts them to Contentstack anchor nodes (`{"type": "a", "attrs": {"url": ..., "target": "_blank"}}`). Blog posts published before June 2026 are missing hyperlinks in Contentstack — add them manually in the editor if revisiting an older post.

**Numbered sub-sections that are H2 in the source doc** will be mapped as separate H2 sections, not as a numbered list. If the author wants items like "1. The work that's already there / 2. The answer you think... / 3. The assumption..." to appear as a numbered list, they must be formatted as an ordered list in the .docx, not as H2 headings. The pipeline will always follow the source doc structure.

**Bold + numbered framework steps** split across multiple list blocks (e.g. a four-step framework interrupted by an intervening paragraph) will not be automatically merged or renumbered. These must be corrected manually in the Contentstack editor or fixed in the source .docx before re-parsing.

**lead_paragraph contains only the Quick Summary.** Intro paragraphs (all content before the first H2) are placed in the first content block, not in `lead_paragraph`. This is intentional — `lead_paragraph` maps to a visually distinct field in the blog template (gray background), so it should only hold the Quick Summary. Do not put intro paragraphs back into `lead_paragraph`.
