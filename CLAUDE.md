# CLAUDE.md

This folder groups two sibling content-ingestion pipelines. Both follow the WAT framework (see the global CLAUDE.md) and the same shape — parse a source document with Claude, map it to a Contentstack entry, validate, optionally upload — but they are independent projects with their own scripts, config, and input/output folders. Neither shares code with the other; this is an organizational grouping, not a merged codebase.

## Sub-projects

- **[Blog Ingestion Agent/](Blog%20Ingestion%20Agent/CLAUDE.md)** — converts blog `.docx` files into `blog_post` Contentstack entries. Triggered by the `/blog-ingestion` skill (or standalone `/blog-parse`, `/blog-map`, `/blog-validate`, `/blog-upload`).
- **[Whitepaper Ingestion Agent/](Whitepaper%20Ingestion%20Agent/CLAUDE.md)** — converts whitepaper PDFs/DOCX files into `page` Contentstack entries for strategy.com. Triggered by the `/whitepaper-ingestion` skill.

Each sub-project's own CLAUDE.md is the authoritative reference for its commands, architecture, and known quirks — read that file before working inside either one. Note that Claude Code only auto-loads CLAUDE.md files by walking up from the working directory; it does **not** auto-load a subfolder's CLAUDE.md just because a file in that subfolder is open or referenced. Reading the sub-project's CLAUDE.md is a deliberate step, not something the harness does for you — both ingestion skills include an explicit instruction to read it before their first phase runs.

## Adding a new ingestion pipeline

If a third document type needs the same treatment (parse → map → validate → upload), scaffold it as a new sibling folder here with its own `scripts/`, `config.yaml`, `input/`, `output/`, `schemas/`, and `CLAUDE.md`, then add a corresponding skill under `~/.claude/skills/` following the pattern of the existing two.
