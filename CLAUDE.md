# CLAUDE.md

This folder groups three sibling content-ingestion pipelines. They follow the same shape — parse source material, map it to a Contentstack entry, validate, optionally upload — while retaining their own scripts, config, and input/output folders. Shared utilities live in `ingestion_common`; this is a repository of related projects, not one merged pipeline.

## Sub-projects

- **[Blog Ingestion Agent/](Blog%20Ingestion%20Agent/CLAUDE.md)** — converts blog `.docx` files into `blog_post` Contentstack entries. Triggered by the `/blog-ingestion` skill (or standalone `/blog-parse`, `/blog-map`, `/blog-validate`, `/blog-upload`).
- **[Whitepaper Ingestion Agent/](Whitepaper%20Ingestion%20Agent/CLAUDE.md)** — converts whitepaper PDFs/DOCX files into `page` Contentstack entries for strategy.com. Triggered by the `/whitepaper-ingestion` skill.
- **[Glossary Agent/](Glossary%20Agent/CLAUDE.md)** — turns approved source material into reviewed `asset_page` glossary drafts for strategy.com.

Each sub-project's own CLAUDE.md is the authoritative reference for its commands, architecture, and known quirks — read that file before working inside it. Note that Claude Code only auto-loads CLAUDE.md files by walking up from the working directory; it does **not** auto-load a subfolder's CLAUDE.md just because a file in that subfolder is open or referenced. Reading the sub-project's CLAUDE.md is a deliberate step, not something the harness does for you.

## Adding a new ingestion pipeline

If a new document type needs the same treatment (parse → map → validate → upload), scaffold it as a sibling folder with its own `scripts/`, `config.yaml`, `input/`, `output/`, `schemas/`, `AGENTS.md`, and `CLAUDE.md`, then add a corresponding skill under `~/.claude/skills/`.

## Shared facts

- All three pipelines use four steps: parse → map → validate → upload. Upload creates a draft only after explicit user confirmation.
- `api.base_url` is exactly `https://api-stg.microstrategy.com/cs-software` in every project `config.yaml`.
- The proxy has no PUT endpoint: an `--entry-uid` update request fails with HTTP 404. Do not promise updates; create a new draft version instead.
- `upload_to_contentstack.py` automatically normalizes titles and applies/retries `vN | <title>` (`v1 |`, `v2 |`, ...) in Blog, Whitepaper, and Glossary. Do not manually prefix or mutate `contentstack_entry.json` titles.
- Each script establishes an explicit `PROJECT_ROOT`, adds its parent repository root to `sys.path`, and imports shared utilities from `ingestion_common`; retain that contract when adding scripts or imports.
- Shared-fact changes must update this AGENTS.md and this CLAUDE.md in the same commit, and `log.md` must record the change.
