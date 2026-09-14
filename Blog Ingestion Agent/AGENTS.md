# AGENTS.md

Run commands from this directory. The Blog Ingestion Agent converts a blog DOCX into a reviewed `blog_post` Contentstack draft. It requires `ANTHROPIC_API_KEY` and `MSTR_API_KEY` in `.env`.

```bash
python3 scripts/run_pipeline.py input/blog.docx
python3 scripts/run_pipeline.py input/blog.docx --upload
python3 scripts/validate_blog_json.py output/normalized_blog.json output/contentstack_entry.json
```

Read `CLAUDE.md` for the full mapping, review, asset-upload, and publishing guidance. Do not publish without the user's explicit request.

## Shared facts

- All three pipelines use four steps: parse → map → validate → upload. Upload creates a draft only after explicit user confirmation.
- `api.base_url` is exactly `https://api-stg.microstrategy.com/cs-software` in every project `config.yaml`.
- The proxy has no PUT endpoint: an `--entry-uid` update request fails with HTTP 404. Do not promise updates; create a new draft version instead.
- `upload_to_contentstack.py` automatically normalizes titles and applies/retries `vN | <title>` (`v1 |`, `v2 |`, ...) in Blog, Whitepaper, and Glossary. Do not manually prefix or mutate `contentstack_entry.json` titles.
- Each script establishes an explicit `PROJECT_ROOT`, adds its parent repository root to `sys.path`, and imports shared utilities from `ingestion_common`; retain that contract when adding scripts or imports.
- Shared-fact changes must update this AGENTS.md and this CLAUDE.md in the same commit, and `log.md` must record the change.
