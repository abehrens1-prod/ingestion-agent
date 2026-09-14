# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Builds glossary pages for strategy.com as Contentstack `asset_page` entries. Unlike the sibling Blog/Whitepaper agents, there is **no input document** — the input is a term from a queue plus a manifest of already-published Strategy content about that term. Frank Volinsky's framing (2026-08-25): *"The whole idea is just to capture whichever current content we have on the website now, sort of aggregate it into one page on that particular topic."* Consolidation, not net-new writing.

**Read [`docs/glossary_page_spec.md`](docs/glossary_page_spec.md) before doing anything here.** It is the brief that `draft_with_claude.py` and `map_to_contentstack.py` build against (the drafting script literally reads it into the Claude prompt), and it carries the numbered list of open items still unconfirmed with Frank/Jessica/Dale. Don't drift the code away from it silently — change the spec and the code together.

All scripts run from the project root. WAT framework (see the global CLAUDE.md).

## Shared facts

- All three pipelines use four steps: parse → map → validate → upload. Upload creates a draft only after explicit user confirmation.
- `api.base_url` is exactly `https://api-stg.microstrategy.com/cs-software` in every project `config.yaml`.
- The proxy has no PUT endpoint: an `--entry-uid` update request fails with HTTP 404. Do not promise updates; create a new draft version instead.
- `upload_to_contentstack.py` automatically normalizes titles and applies/retries `vN | <title>` (`v1 |`, `v2 |`, ...) in Blog, Whitepaper, and Glossary. Do not manually prefix or mutate `contentstack_entry.json` titles.
- Each script establishes an explicit `PROJECT_ROOT`, adds its parent repository root to `sys.path`, and imports shared utilities from `ingestion_common`; retain that contract when adding scripts or imports.
- Shared-fact changes must update this AGENTS.md and this CLAUDE.md in the same commit, and `log.md` must record the change.

## Commands

```bash
pip install -r requirements.txt
cd scripts/rte_serializer_node && npm install   # Node serializer used by rte_builder.py

# 0. Rebuild the term queue from the Q3 spreadsheet (rarely needed)
python3 scripts/build_term_queue.py

# 1. Assemble cached sources for a term (offline — does NOT fetch URLs)
python3 scripts/harvest_sources.py semantic-layer

# 2. Draft the page (2 Claude calls: content, then SEO enrichment)
python3 scripts/draft_with_claude.py semantic-layer \
    --output output/2026-08-25_semantic-layer/normalized_glossary.json

# 2b. Optional — upload images/videos and patch assetUid back into the normalized JSON
python3 scripts/upload_assets.py input/sources/semantic-layer/assets/ \
    --normalized output/2026-08-25_semantic-layer/normalized_glossary.json

# 3. Map to a Contentstack entry
python3 scripts/map_to_contentstack.py output/2026-08-25_semantic-layer/normalized_glossary.json \
    --output output/2026-08-25_semantic-layer/contentstack_entry.json

# 4. Validate (writes validation_report.md)
python3 scripts/validate_glossary_json.py \
    output/2026-08-25_semantic-layer/normalized_glossary.json \
    output/2026-08-25_semantic-layer/contentstack_entry.json \
    --output output/2026-08-25_semantic-layer/validation_report.md

# 5. Upload as a draft — never --publish (see Review chain)
python3 scripts/upload_to_contentstack.py output/2026-08-25_semantic-layer/contentstack_entry.json --dry-run
python3 scripts/upload_to_contentstack.py output/2026-08-25_semantic-layer/contentstack_entry.json
python3 scripts/upload_to_contentstack.py output/.../contentstack_entry.json --entry-uid bltXXXX  # update existing

# 6. Record the upload in glossary_registry.md
python3 scripts/update_registry.py output/2026-08-25_semantic-layer/

# Inspect Contentstack schema (requires MSTR_API_KEY)
python3 scripts/discover_schema.py --list-types
python3 scripts/discover_schema.py --type asset_page
```

There is **no `run_pipeline.py`** here (the sibling agents have one) — steps are run individually. Output convention is `output/<YYYY-MM-DD>_<slug>/`, created by hand.

## Architecture

```
input/Content needs - Remaining Q3.xlsx
  → build_term_queue.py     → input/term_queue.json           (10 terms; ontology excluded)
input/sources/<slug>/sources.yaml + raw/*.md
  → harvest_sources.py      → input/sources/<slug>/harvested_sources.json
  → draft_with_claude.py    → normalized_glossary.json        (Claude; consolidates sources)
  → map_to_contentstack.py  → contentstack_entry.json         (via rte_builder.py → Node)
  → validate_glossary_json.py + upload_to_contentstack.py + update_registry.py
```

**Sourcing is a manual, interactive step.** `harvest_sources.py` never hits the network. You find candidate pages (WebSearch / `https://software.strategy.com/sitemap.xml`), cache their text into `input/sources/<slug>/raw/*.md`, list them in `sources.yaml`, and the script assembles that into provenance-tagged JSON. A source nominated but not yet located is recorded with empty text and a warning rather than dropped. `sources.yaml` source types: `live_url` (cached snapshot under `raw/`), `local_doc` (.docx/.md/.txt anywhere on disk), `wiki_concept` (Strategy Brain wiki file).

**`draft_with_claude.py`** reads the term queue row, harvested sources, `docs/glossary_page_spec.md`, and `glossary_registry.md` (for `relatedTerms` internal links). Two Claude calls: content draft (`max_tokens=8192`, with a JSON-repair retry call) then SEO enrichment (`max_tokens=1024`). Model comes from `pipeline.claude_model` in config.yaml.

**`map_to_contentstack.py`** targets the **`asset_page`** content type (schema export at `schemas/contentstack_asset_page.schema.json`, confirmed 2026-09-01). Mapping: `page_header.headline` = title, `page_header.subhead` = the term's `geoQueryTarget`, `page_header.brief_content` = the `definition` array as a bulleted list; each section emits a native `section_anchor` block + `divider` + `text`/`image` blocks; FAQ becomes an `accordion` block. Do not revert to the older `page`-content-type hero/section-id workaround described in the spec's history.

**`rte_builder.py`** builds Contentstack JSON RTE nodes. Inline runs (bold/italic/links) are serialized by piping an HTML fragment through `scripts/rte_serializer_node/serialize.js`, which wraps Contentstack's own `@contentstack/json-rte-serializer@3.1.0`. This is a separate copy of the Blog agent's Node boundary, not a shared import — projects here deliberately don't share code. Headings and tables stay hand-built for two reasons: the template's `font-color` swatch attribute has no HTML input the serializer maps to, and serializer 3.1.0 silently drops a run's `style.color` when the run is also bold/italic/underlined (worked around by serializing marks only, then patching color onto the text leaf in Python).

**`validate_glossary_json.py`** runs ~20 checks across both files and writes `validation_report.md`. Glossary-specific ones beyond the sibling agents': section headings phrased as questions, `geoQueryTarget` coverage, internal-link minimums from config, AI-generated-content flagging, JSON-LD parseability.

## Contentstack — confirmed vs. unconfirmed

Confirmed: content type `asset_page`; its `options.url_prefix` is `/assets/` (this pipeline adds `/glossary` as its own grouping segment); the API proxy allowlist now includes `asset_page` (Dale/ITS added it 2026-09-01 after an initial 403). Live URLs on `software.strategy.com` do **not** carry the `/software` segment — hence `api.cms_domain_prefix`; don't strip the whole `url_prefix` when building a canonical URL.

Still unconfirmed, and each one is a live HTTP 422 risk:

| Thing | State |
|---|---|
| `resource_data.type` | Only `"Blog"` and `"Analyst Report"` known valid. Config defaults to `"Blog"` as the closer analog. |
| `text.accent_box` | A real upload with `bg_color: "White"` / `styles: ["Outlined"]` was rejected 422 — both invalid enums for the `accent_box_styles` global field. The mapper no longer sets `accent_box`; callouts render as a bold-lead paragraph. The proxy can't be queried for valid values (`/global_fields/` 404s, that content type 403s). |
| JSON-LD placement | `asset_page` has no `custom_code` block. The computed `DefinedTerm` + `FAQPage` markup is written to a top-level `_schema_markup_unplaced` key in `contentstack_entry.json` so it isn't lost. |
| CTAs | `cta_section` and the in-body `promo` block are *references* to an existing Contentstack `promo` entry, not freeform copy. No promo entries exist for this pipeline yet, so CTAs are omitted with a mapping warning. |
| `api.assets_url` | Blank. No glossary/page assets folder endpoint has been requested from Dale — the Blog agent's confirmed endpoint is for its own blog-assets folder. Ask before a real asset upload. |
| Non-`en` locales | The locale list is copied from the blog folder's confirmed list; not separately confirmed for `asset_page`. Read from `config.yaml`, never hardcode `"en"`. |

## Review chain — never auto-publish

Ash drafts → Henry edits for accuracy ("strategy wording") → Frank reviews for SEO/GEO. Every upload is a draft or `--dry-run`; `--publish` exists on the upload script but is not used here. AI-generated sections must carry `provenance[].aiGenerated = true` so they surface in the validation report's human-review checklist.

## Conventions worth knowing

- `config.yaml` is the single source of truth for content type UID, field map, URLs, model, and internal-link minimums (3 in / 3 out, Frank's verbal standard from 2026-08-24). It's heavily commented with *why* each value is what it is and what's still unconfirmed — read the comments, keep them current when a value gets confirmed.
- `glossary_registry.md` is both the upload log and the `relatedTerms` source for later pages. `update_registry.py` appends rows; only the Status column should ever be hand-edited.
- Ontology is parked (Frank, 2026-08-18) and hard-excluded in `build_term_queue.py` — don't re-add it.
- `input/sources/<slug>/feedback-*.md` holds reviewer feedback on drafted pages. Frank's 2026-08-27 feedback on semantic-layer is the closest thing to an exemplar page structure that exists.
- `docs/formatting_guide.md` and `docs/session_2026_06_16_mcp_v2_fixes.md` are carried over from the Whitepaper agent and are written in whitepaper terms. The formatting guide is still the authoritative color/RTE reference that `rte_builder.py` implements (approved AI Token Cost and Accuracy Benchmark entry, 2026-06-17); the session doc is whitepaper history only.
- `skills/glossary-page/` is empty and there is no `glossary-*` skill under `~/.claude/skills/` — unlike the blog and whitepaper pipelines, this one has no slash-command entry point yet.
- Secrets live in `.env` (`ANTHROPIC_API_KEY`, `MSTR_API_KEY`). The git repo root is the parent `Ingestion Agents/` folder, not this directory.
