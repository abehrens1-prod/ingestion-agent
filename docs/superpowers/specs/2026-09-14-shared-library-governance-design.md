# Shared Library Extraction and Governance Design

## Goal

Extract the duplicated configuration and Contentstack integration code used by the Blog, Whitepaper, and Glossary ingestion pipelines into a root `ingestion_common` package, while preserving each pipeline's command-line and import contracts.

## Scope

The first pass covers configuration lookup, UTF-8 console setup, Contentstack headers/preflight/upload/publish behavior, schema discovery, project governance files, and the root project index/log. Parsers, mappers, validators, RTE builders, and Claude call behavior remain functionally unchanged apart from adopting the shared console/config helpers.

## Architecture

Each executable script adds the repository root to `sys.path` with `Path(__file__).resolve().parents[2]`. Shared functions receive an explicit project root whenever project-relative `config.yaml` or `.env` lookup is required; they never infer those locations from the shared module's own `__file__`.

The three uploader modules remain thin compatibility wrappers because both Blog and Whitepaper orchestrators import their `upload_entry` functions dynamically. The wrappers preserve their public signatures and select pipeline behavior before delegating to `ingestion_common.contentstack.upload_entry`.

## Upload behavior

- All three pipelines use automatic title versioning on create: normalize a leading `vN |` or legacy Blog `vN --` prefix, then try `v1 |`, `v2 |`, and so on through `v19 |` on title collisions.
- `--entry-uid` remains accepted, but fails before any request with a clear explanation that the proxy has no update endpoint.
- Blog and Glossary retain locale query parameters and locale text in upload output. Whitepaper retains its current no-locale request/output behavior.
- Dry-run stdout remains byte-identical to the baseline for each pipeline and performs no authentication or network access.
- Publish remains an explicit opt-in.

## Console and configuration

Every Python command-line entry point in the three projects calls `enable_utf8()`. `find_config` and `load_config` accept an explicit project root so commands still work from the project directory and from other working directories.

## Governance

The repository root and every pipeline contain standalone `AGENTS.md` and `CLAUDE.md` files. Each pair has an identical `## Shared facts` section documenting the four-step pipeline, API base URL, PUT limitation, title versioning, and shared import contract. The obsolete tracked root `skills/` directory is removed. Live Claude skills are updated separately because they are outside this git repository.

Root `index.md` reports counts based on output directories containing `contentstack_entry.json`; `log.md` is append-only and records decisions and known follow-up work.

## Verification

Unit tests cover shared configuration, UTF-8 setup, dry-run behavior, title-collision retries, legacy-prefix normalization, update rejection, locale handling, schema preflight, and publishing. Integration checks compare baseline and migrated dry-run stdout byte-for-byte, exercise all CLI help paths, verify dynamic uploader imports, compile all Python files, and run schema discovery read-only when credentials are available. No live upload or publish request is made.
