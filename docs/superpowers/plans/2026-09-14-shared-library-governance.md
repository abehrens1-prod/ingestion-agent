# Shared Library Extraction and Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Share the stable config and Contentstack layer across all three ingestion pipelines and add project governance that prevents silent drift.

**Architecture:** A root `ingestion_common` package owns reusable behavior and receives explicit project-root context. Pipeline scripts remain thin wrappers where their callable or CLI surface is externally consumed.

**Tech Stack:** Python 3, unittest, requests, PyYAML, python-dotenv, Markdown, Git

**Spec:** `docs/superpowers/specs/2026-09-14-shared-library-governance-design.md`

## Global Constraints

- Preserve every existing CLI flag and the callable `upload_entry` interface used by the Blog and Whitepaper orchestrators.
- All three pipelines automatically create `vN |` draft titles; accept legacy `vN --` input without nesting prefixes.
- Keep dry-run stdout byte-identical to the captured baseline and make no live write requests during verification.
- `--entry-uid` must fail before network access and name the proxy PUT limitation plus `Glossary Agent/docs/session_2026_06_16_mcp_v2_fixes.md`.
- Project-relative config and `.env` lookup must use an explicit project root, never `ingestion_common.__file__`.
- Do not alter parser, mapper, validator, RTE output, or the `claude-sonnet-4-6` model pin.
- Preserve the existing Whitepaper locale/config and serializer-follow-up edits from commit `6a7b1ff`.
- Commit each task independently; never upload or publish a real Contentstack entry.

---

### Task 1: Shared package and behavior tests

**Files:**
- Create: `ingestion_common/__init__.py`
- Create: `ingestion_common/console.py`
- Create: `ingestion_common/config.py`
- Create: `ingestion_common/contentstack.py`
- Create: `ingestion_common/schema_tools.py`
- Create: `tests/test_console.py`
- Create: `tests/test_config.py`
- Create: `tests/test_contentstack.py`

**Interfaces:**
- `enable_utf8() -> None`
- `find_config(config_path="config.yaml", project_root=None) -> Path`
- `load_config(config_path="config.yaml", project_root=None) -> dict`
- `build_headers(project_root=None) -> dict`
- `preflight_schema_check(base_url, content_type, entry_fields, headers) -> None`
- `upload_entry(..., project_root=None, content_type_uid=None, title_versioning=False, use_locale=False) -> dict`
- `publish_entry(base_url, content_type, entry_uid, headers) -> bool`
- `schema_tools.main(project_root, argv=None) -> int`

- [ ] Write focused tests first and verify they fail because the package is absent.
- [ ] Implement the package from the existing Glossary behavior with the spec's parameters.
- [ ] Run `python3 -m unittest discover -s tests -v` and verify clean output.
- [ ] Commit the shared package and tests.

### Task 2: Migrate upload and schema wrappers

**Files:**
- Modify: `Blog Ingestion Agent/scripts/upload_to_contentstack.py`
- Modify: `Whitepaper Ingestion Agent/scripts/upload_to_contentstack.py`
- Modify: `Glossary Agent/scripts/upload_to_contentstack.py`
- Modify: `Whitepaper Ingestion Agent/scripts/discover_schema.py`
- Modify: `Glossary Agent/scripts/discover_schema.py`
- Create: `tests/test_pipeline_wrappers.py`

**Interfaces:**
- Each uploader continues exporting its existing `upload_entry` signature.
- Each schema wrapper delegates to `schema_tools.main(PROJECT_ROOT)`.

- [ ] Add wrapper integration tests and verify they fail before migration.
- [ ] Replace duplicated implementations with compatibility wrappers; pass automatic title versioning for all three.
- [ ] Compare the three dry-run outputs with `/tmp/*-upload-before.txt` byte-for-byte.
- [ ] Verify Blog and Whitepaper `run_pipeline.py --help` still work.
- [ ] Commit the migrated wrappers.

### Task 3: Migrate config consumers and console entry points

**Files:**
- Modify: `Blog Ingestion Agent/scripts/upload_assets.py`
- Modify: `Glossary Agent/scripts/upload_assets.py`
- Modify: every Python entry point under each project's `scripts/`
- Create: `tests/test_entrypoints.py`

**Interfaces:**
- Asset upload callable and CLI signatures remain unchanged.
- Every entry point can import and call `enable_utf8()` from its project root.

- [ ] Add subprocess/import tests for project-root execution and verify they fail where shared setup is absent.
- [ ] Replace duplicated config functions in both asset uploaders.
- [ ] Replace Blog's inline console shims and add the shared shim to Whitepaper and Glossary entry points.
- [ ] Run the unit suite, compile all Python files, and exercise CLI help commands.
- [ ] Commit the migration.

### Task 4: Governance documents and skill cleanup

**Files:**
- Create: `AGENTS.md`
- Create: `Blog Ingestion Agent/AGENTS.md`
- Create: `Whitepaper Ingestion Agent/AGENTS.md`
- Create: `Glossary Agent/AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `Blog Ingestion Agent/CLAUDE.md`
- Modify: `Whitepaper Ingestion Agent/CLAUDE.md`
- Create: `Glossary Agent/CLAUDE.md`
- Delete: `skills/`
- Modify outside git: `~/.claude/skills/blog-upload/SKILL.md`
- Modify outside git: `~/.claude/skills/blog-ingestion/SKILL.md`

- [ ] Write standalone Codex and Claude guidance with identical shared-facts sections per directory.
- [ ] Document automatic `vN |` behavior and remove manual/unsupported Blog prefix instructions.
- [ ] Remove the obsolete tracked skills directory.
- [ ] Verify shared-facts sections match byte-for-byte within each directory and all documented commands resolve.
- [ ] Commit repository governance changes; record global skill checks separately.

### Task 5: Root index, log, and full verification

**Files:**
- Create: `index.md`
- Create: `log.md`
- Modify: `tests/` only if a failing integration check exposes a defect.

- [ ] Count output directories containing `contentstack_entry.json` and write the dated status index.
- [ ] Seed the append-only log with the extraction, fixes, decisions, known mismatches, and deferred work.
- [ ] Run the complete unit and integration verification suite without live writes.
- [ ] Run `git diff --check` and inspect the final branch diff.
- [ ] Commit the index and log.
