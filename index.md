# Ingestion Pipeline Index

**Status date:** 2026-09-14

This index tracks saved mapped-entry output directories. It is an inventory of
local artifacts, not a publication record.

## Count method

Counts are reproducible from the repository root with:

```bash
find 'Blog Ingestion Agent/output' 'Whitepaper Ingestion Agent/output' 'Glossary Agent/output' \
  -type f -name contentstack_entry.json -print \
  | sed 's#/contentstack_entry.json$##' \
  | sort -u \
  | wc -l
```

For per-pipeline totals, run the same command against that pipeline's `output`
directory. On 2026-09-14 the total was **52**: 39 Blog, 12 Whitepaper, and 1
Glossary output directory.

## Pipeline status

| Pipeline | Output directories with `contentstack_entry.json` | Detailed registry | Status |
|---|---:|---|---|
| Blog | 39 | None | Mapped-entry inventory exists; registry gap remains. |
| Whitepaper | 12 | [Whitepaper Registry](Whitepaper%20Ingestion%20Agent/whitepaper_registry.md) (11 rows) | One mapped output directory is not represented in the registry. |
| Glossary | 1 | [Glossary Page Registry](Glossary%20Agent/glossary_registry.md) (3 historical draft rows) | One output directory is reused across the recorded draft versions. |

## Detailed records

- [Whitepaper Registry](Whitepaper%20Ingestion%20Agent/whitepaper_registry.md)
- [Glossary Page Registry](Glossary%20Agent/glossary_registry.md)
- [Governance log](log.md)

## Open items and blockers

- **Blog registry gap:** there is no `Blog Ingestion Agent/blog_registry.md` or
  equivalent. Create one before treating the 39 local artifacts as a tracked
  draft inventory.
- **Whitepaper registry coverage:** the local output for
  `2026-06-26_strategy-mosaic-unifying-fragmented-data-intelligent-enterprise-decisions`
  has a mapped entry but no corresponding registry row.
- **Glossary review and asset blockers:** the current glossary draft remains
  pending review; its asset endpoint and promo reference are still unconfirmed.
  See its [validation report](Glossary%20Agent/output/2026-08-25_semantic-layer/validation_report.md).
- **Documentation drift:** the three known code/documentation mismatches are
  recorded in [log.md](log.md); they are not changed as part of this governance
  pass.
- **Contentstack updates:** the proxy has no PUT endpoint. Create a new draft
  version instead of using `--entry-uid`.
