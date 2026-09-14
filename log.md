# Ingestion Governance Log

Append new records above older records. Entries use
`## [YYYY-MM-DD] <tag> | <summary>` and are newest-first. This log starts on
2026-09-14; it does not backfill earlier work.

## [2026-09-14] decision | Retained the `claude-sonnet-4-6` model pin in all three pipeline configs; the shared-library extraction does not change parser, mapper, validator, RTE, or Claude behavior.

## [2026-09-14] documentation | `Glossary Agent/docs/formatting_guide.md` is a stale Whitepaper `page`/`content_blocks` guide, while the live Glossary mapper targets `asset_page` and emits its `content` field. Treat `docs/glossary_page_spec.md` and the mapper as the current Glossary reference until the guide is replaced.

## [2026-09-14] documentation | `Whitepaper Ingestion Agent/CLAUDE.md` says auto-named outputs are `output/<slug>/`; `scripts/run_pipeline.py` actually uses `output/{YYYY-MM-DD}_{slug}/`. Use the script behavior and existing output tree as authoritative until the command documentation is corrected.

## [2026-09-14] documentation | `field_map` is documented as mapper input, but no mapper consumes it. The Blog orchestrator reads `field_map.body` and the Blog validator checks field-map coverage; uploaders read the content-type UID, not the field map. Keep field-map edits scoped to those current consumers until mapper support is deliberately added.

## [2026-09-14] limitation | The Contentstack proxy has no PUT endpoint: `--entry-uid` updates fail with HTTP 404. The uploader rejects an update before authentication or network access; create a new draft version instead. See `Glossary Agent/docs/session_2026_06_16_mcp_v2_fixes.md`.

## [2026-09-14] extraction | Shared configuration lookup, UTF-8 console setup, Contentstack upload/publish behavior, and schema-discovery behavior now live in `ingestion_common`; pipeline scripts remain compatibility wrappers with explicit project roots. Automatic `vN | <title>` draft-title retries apply across Blog, Whitepaper, and Glossary.
