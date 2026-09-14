# Final review fix report — 2026-09-14

## Important: title version normalizer

- Root cause: `ingestion_common.contentstack._post_versioned_entry` removed every trailing parenthetical after stripping a `vN |` or legacy `vN --` prefix.
- Fix: its suffix cleanup now matches only a parenthetical version marker beginning with `v` and digits, with an optional `- ...` note. Legitimate title content remains intact.
- Regression coverage proves:
  - `Understanding Business Intelligence (BI)` becomes `v1 | Understanding Business Intelligence (BI)`.
  - `v3 -- Analytics (Part 2)` becomes `v1 | Analytics (Part 2)`.
  - `Semantic Layer (v2 - fixed)` becomes `v1 | Semantic Layer`.

## Minor: `--entry-uid` CLI help

- Retained `--entry-uid` in Blog, Whitepaper, and Glossary uploader wrappers.
- Help now says that the proxy does not support updates and the flag fails before network access.
- A wrapper CLI-help test exercises all three `main(["--help"])` paths. Existing tests also verify an `entry_uid` is rejected before any HTTP call.

## TDD and verification evidence

- RED: focused title regression tests failed for `(BI)` and `(Part 2)` before the regex change; the recognized `(v2 - fixed)` case passed as the existing cleanup contract.
- RED: the new three-wrapper CLI-help test failed before its help text was changed.
- GREEN: focused title and help tests passed after the minimal changes.
- Full suite: `python3 -m unittest discover -s tests -p 'test_*.py'` — 32 tests passed.
- Compile check: `python3 -m compileall -q ingestion_common 'Blog Ingestion Agent/scripts' 'Whitepaper Ingestion Agent/scripts' 'Glossary Agent/scripts'` — passed.
- Dry-run parity: `test_dry_run_preserves_output_and_skips_authentication_and_http` passed; it asserts byte-for-byte dry-run stdout and no authentication or HTTP. No live writes were made.
- Diff hygiene: `git diff --check` passed.
