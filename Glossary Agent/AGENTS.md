# AGENTS.md

Run commands from this directory. The Glossary Agent consolidates approved Strategy material into reviewed `asset_page` glossary drafts; it does not auto-publish. Read `docs/glossary_page_spec.md` before changing source, mapping, or review behavior.

```bash
python3 scripts/harvest_sources.py semantic-layer
python3 scripts/draft_with_claude.py semantic-layer
python3 scripts/map_to_contentstack.py output/semantic-layer/normalized_glossary.json --output output/semantic-layer/contentstack_entry.json
python3 scripts/validate_glossary_json.py output/semantic-layer/normalized_glossary.json output/semantic-layer/contentstack_entry.json
```

Use `upload_to_contentstack.py` only after human review and explicit confirmation.

## Shared facts

- All three pipelines use four steps: parse → map → validate → upload. Upload creates a draft only after explicit user confirmation.
- `api.base_url` is exactly `https://api-stg.microstrategy.com/cs-software` in every project `config.yaml`.
- The proxy has no PUT endpoint: an `--entry-uid` update request fails with HTTP 404. Do not promise updates; create a new draft version instead.
- `upload_to_contentstack.py` automatically normalizes titles and applies/retries `vN | <title>` (`v1 |`, `v2 |`, ...) in Blog, Whitepaper, and Glossary. Do not manually prefix or mutate `contentstack_entry.json` titles.
- Each script establishes an explicit `PROJECT_ROOT`, adds its parent repository root to `sys.path`, and imports shared utilities from `ingestion_common`; retain that contract when adding scripts or imports.
- Shared-fact changes must update this AGENTS.md and this CLAUDE.md in the same commit, and `log.md` must record the change.
