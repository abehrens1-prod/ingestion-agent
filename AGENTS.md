# AGENTS.md

This repository contains the Blog Ingestion Agent, Whitepaper Ingestion Agent, and Glossary Agent. Work from the relevant project directory, read that project's `AGENTS.md` and `CLAUDE.md`, and keep project-specific configuration and output isolated. Shared Python behavior belongs in `ingestion_common`.

## Projects

- `Blog Ingestion Agent/` converts blog DOCX files to `blog_post` drafts.
- `Whitepaper Ingestion Agent/` converts PDF/DOCX whitepapers to `page` drafts.
- `Glossary Agent/` builds reviewed glossary `asset_page` drafts from approved sources.

## Shared facts

- All three pipelines use four steps: parse → map → validate → upload. Upload creates a draft only after explicit user confirmation.
- `api.base_url` is exactly `https://api-stg.microstrategy.com/cs-software` in every project `config.yaml`.
- The proxy has no PUT endpoint: an `--entry-uid` update request fails with HTTP 404. Do not promise updates; create a new draft version instead.
- `upload_to_contentstack.py` automatically normalizes titles and applies/retries `vN | <title>` (`v1 |`, `v2 |`, ...) in Blog, Whitepaper, and Glossary. Do not manually prefix or mutate `contentstack_entry.json` titles.
- Each script establishes an explicit `PROJECT_ROOT`, adds its parent repository root to `sys.path`, and imports shared utilities from `ingestion_common`; retain that contract when adding scripts or imports.
- Shared-fact changes must update this AGENTS.md and this CLAUDE.md in the same commit, and `log.md` must record the change.
