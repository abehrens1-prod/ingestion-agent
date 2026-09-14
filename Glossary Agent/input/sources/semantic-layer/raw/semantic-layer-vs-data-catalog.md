# Semantic Layer vs. Data Catalog for AI: Why Metadata Isn't Meaning

Source: https://www.strategy.com/software/blog/semantic-layer-for-ai-metadata-is-not-meaning
Author: Lauren O'Connor — this is the "Lauren's blog" Henry nominated on the 2026-08-24
call as already defining most of the content needed for the first glossary pages.
Cached: 2026-08-25

## What This Means for Your Enterprise AI Architecture

AI agents are only as reliable as the business logic they run on. If that logic lives
in a label, you have a data dictionary. If it lives in an execution engine, you have a
semantic layer — a meaningfully different AI outcome. Strategy Software builds Strategy
Mosaic as the governed foundation for enterprise AI precisely because metadata, no
matter how rich, is not a substitute for governed meaning.

## Frequently Asked Questions (usable near-verbatim for the glossary FAQ block)

**Q: What is the difference between a semantic layer and a data catalog?**
A: A data catalog describes data. It stores metadata like column names, lineage, and
business definitions. A semantic layer governs data: it encodes business logic and
enforces metric definitions mathematically, so every downstream tool computes the same
answer from the same governed source. The distinction is the difference between telling
an AI what "revenue" means and making the AI compute revenue correctly every time,
without exception.

**Q: Why do AI agents need a semantic layer?**
A: AI agents querying raw data tables lack the business context required to produce
semantically accurate results. Without a governed definition of which revenue
calculation is authoritative, or what qualifies as an active customer, a model produces
results that are computationally valid but semantically incorrect. Strategy Mosaic
exposes governed business semantics to AI agents through Mosaic MCP, so agents operate
on authoritative metrics and defined relationships rather than guessing at business
logic from raw SQL.

**Q: How does a semantic layer reduce LLM token costs?**
A: When an LLM reasons through raw data tables to compute a metric, it consumes API
tokens on SQL generation, schema interpretation, and business logic inference — work
the semantic layer should have already resolved. Routing LLM queries through Strategy
Mosaic reduces that overhead. (Source truncated at cache time — verify exact figure
before quoting a specific token-savings number in the glossary page.)

## Internal links seen on this page

- /strategymosaic (Arrival-tier product page — the primary Detail↔Narrative link
  candidate for this term)

## Why this source matters

This is the source Henry pointed to directly: "The two I was talking to Frank about
was Lauren's blog and Joe Polis blog. Both of them I think already defined most of it.
So just run a couple of ones and I think you just get a pretty solid glossary page."
Its FAQ section is close to publish-ready and should carry the most weight in
draft_with_claude.py's faq[] output for this term.
