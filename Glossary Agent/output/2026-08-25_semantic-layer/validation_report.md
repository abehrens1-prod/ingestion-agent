# Glossary Page Validation Report

## Ready to Publish? — Review Checklist

**Term:** semantic layer  |  **Priority:** P1
**Title:** What Is a Semantic Layer?
**URL:** /assets/glossary/semantic-layer
**GEO query target:** What is a semantic layer?

### Meta Description

> A semantic layer translates raw data into governed business metrics and definitions, ensuring AI and BI tools compute consistent answers. Learn how it works...
*(159 chars)*

### Keywords

**Primary:** what is a semantic layer, semantic layer, semantic layer definition, semantic layer in data analytics, semantic layer for BI

### Definition block (review before publishing)

1. **A semantic layer is a governed metadata layer that translates raw data into business-meaningful terms, metrics, hierarchies, and definitions.** It sits between raw data sources and the AI or BI tools that consume them, ensuring that calculated metrics, relationships, and business logic are applied consistently — so every downstream tool computes the same answer from the same governed source.
2. **A semantic layer standardizes key business metrics and definitions across teams, ensuring consistent reporting, trusted insights, and more confident decision-making.** That means Finance, Marketing, and Sales calculate 'revenue' or 'active user' the same way every time — no reconciling numbers before a meeting, no conflicting dashboards.
3. **A semantic layer gives AI agents governed business context, ensuring accurate, consistent insights from enterprise data by standardizing definitions for key metrics and entities.** Rather than guessing at business logic from raw tables, AI agents query the same governed definitions people already trust — so an AI-generated answer matches what an analyst would have produced by hand.

### Internal links

**Detail (5):** Retail solutions, Financial Services solutions, Education solutions, Manufacturing solutions, Technology solutions
**Arrival (2):** Strategy Mosaic, Strategy Software
**Inbound (0):** (none)

### Pending Before Publishing

- [ ] URL CHANGE — Frank's feedback moves this page under the 'Asset' page for TOC purposes: /asset/glossary/semantic-layer (was /software/glossary/semantic-layer in the registry). This file's own `url` fie
- [ ] DIAGRAM ASSET SUPPLIED (2026-09-01) — A new Source/Engine/Output diagram was provided (already vendor-neutral, no logo-removal needed) and staged at input/sources/semantic-layer/assets/how-semantic-la
- [ ] STAT FLAG — '38% of analyst time' figure attributed to CIO Dive, 2026 (sourced from The Enterprise Semantic Layer Buyer's Guide). This figure must be independently verified against the original CIO Di
- [ ] STAT FLAG — LLM token cost reduction: The source (Lauren O'Connor's blog) notes this claim was 'truncated at cache time' and cautions against quoting a specific token-savings number. The FAQ answer an
- [ ] INTERNAL LINK REMINDER — The page spec requires at least 3 links in and 3 links out. Outbound links to /software/strategymosaic (Arrival), /software (Arrival), and five industry Detail pages (/softwar
- [ ] TEMPLATE STATUS — Jessica's hybrid Contentstack template (whitepaper + TOC sidebar) was unconfirmed as of 2026-08-25 and remains unconfirmed after this feedback round. This draft targets the known 'pa
- [ ] SCHEMA — No schema type has been confirmed by Frank/Doug/Dale/Jessica. This draft's JSON-LD output defaults to DefinedTerm + FAQPage per the spec's starting-point guidance. Do not treat this as final.
- [ ] RESOURCE_DATA.TYPE — Valid values for a glossary page are unconfirmed. Only 'Blog' and 'Analyst Report' are known-valid today. Flag for Frank before publishing.
- [ ] NEW SECTIONS UNSOURCED — 'What Are the Core Components of a Semantic Layer?' and 'How to Implement a Semantic Layer?' were drafted per Frank's feedback but have no dedicated harvested source behind th

---

## Technical Summary ⚠️

**Status:** WARNINGS

| Level | Count |
|---|---|
| ❌ ERROR | 0 |
| ⚠ WARN  | 2 |
| ✅ PASS  | 18 |

## Warnings (review recommended)

### ⚠ Internal links minimum
only 0 inbound link(s) recorded, need >=3 (this pipeline can't verify inbound links automatically — add manually)

### ⚠ Drafting warnings
16 warning(s):
  - FRANK'S 2026-08-27 FEEDBACK — Applied. See input/sources/semantic-layer/feedback-2026-08-27-frank.md for the full ingested feedback and a section-by-section log of what changed. Raw feedback docx preserved at input/sources/semantic-layer/raw/glossary-mvp-feedback-2026-08-27.docx.
  - URL CHANGE — Frank's feedback moves this page under the 'Asset' page for TOC purposes: /asset/glossary/semantic-layer (was /software/glossary/semantic-layer in the registry). This file's own `url` field stays a per-page suffix (/semantic-layer) — the /asset/glossary prefix now lives in config.yaml's contentstack.url_prefix, which was changed pipeline-wide (affects every glossary term, not just this one) from /software/glossary to /asset/glossary. This depends on the 'Asset' parent page and its TOC existing in Contentstack — needs Jessica/dev confirmation before this is real, not just a config change here. If the URL change was only meant for this one term, url_prefix should be reverted and the prefix instead built per-page.
  - VIDEO ASSET NEEDED — Frank requested a 'Semantic Layer Overview' video under the new lead section, right after the definition box. No video asset exists yet and this pipeline has no video block type — a callout placeholder was inserted in the 'What Is a Semantic Layer?' section. Web team to supply the asset and embed it once Jessica's template supports it.
  - DIAGRAM ASSET SUPPLIED (2026-09-01) — A new Source/Engine/Output diagram was provided (already vendor-neutral, no logo-removal needed) and staged at input/sources/semantic-layer/assets/how-semantic-layer-works.png, referenced by the 'How Does a Semantic Layer Work?' section's image block. Not yet uploaded to Contentstack — config.yaml's api.assets_url is still blank (no confirmed glossary/page assets endpoint from Dale/ITS), so scripts/upload_assets.py can't complete the real upload yet. Run it once that endpoint is confirmed to patch in a real assetUid and get the native asset_page image block instead of a placeholder.
  - STAT FLAG — '38% of analyst time' figure attributed to CIO Dive, 2026 (sourced from The Enterprise Semantic Layer Buyer's Guide). This figure must be independently verified against the original CIO Dive publication before publishing. Frank's 2026-08-27 feedback additionally asks for the Benefits section to cite a named research source (Gartner, Forrester, IDC, or similar) with a working link — no such citation was available to add without fabricating one. If unverifiable, remove the callout block or replace with a verifiable, cited alternative.
  - STAT FLAG — LLM token cost reduction: The source (Lauren O'Connor's blog) notes this claim was 'truncated at cache time' and cautions against quoting a specific token-savings number. The FAQ answer and the 'Why Do AI Agents Need a Semantic Layer?' section describe the mechanism but cite no specific percentage or figure. Do not add a number without sourcing the original post and confirming the exact claim.
  - SECTIONS REMOVED, SPUN OFF — Per Frank's 2026-08-27 feedback, 'What Is a Universal Semantic Layer?' and 'What Is the Difference Between a Semantic Layer and a Data Catalog?' were removed from this page; each should become its own glossary page. 'universal semantic layer' has been added to input/term_queue.json (P2) so the removed content isn't lost — it's the seed source for that future page. 'data catalog ai' was already queued (P2); the removed Data Catalog section here is a useful seed source when that term is drafted.
  - INTERNAL LINK REMINDER — The page spec requires at least 3 links in and 3 links out. Outbound links to /software/strategymosaic (Arrival), /software (Arrival), and five industry Detail pages (/software/solutions/retail, /software/solutions/financial-services, /software/solutions/education, /software/solutions/manufacturing, /software/solutions/technology) are present in the drafted content. Inbound links (3 minimum) must be confirmed and added by the web team when the page is published — this draft cannot verify which existing pages already link here.

## All Checks

| Check | Result | Detail |
|---|---|---|
| Title present | ✅ PASS | Title: "What Is a Semantic Layer?" |
| URL present | ✅ PASS | URL: /semantic-layer |
| Definition | ✅ PASS | 3 definition bullet(s) with boldSentence + supportingText. |
| Body sections | ✅ PASS | 8 section(s), all with headings. |
| Section headings phrased as questions | ✅ PASS | All section headings are questions. |
| SEO meta title | ✅ PASS | "What Is a Semantic Layer? Definition & Benefits" |
| SEO meta description | ✅ PASS | 159 chars |
| Target keywords | ✅ PASS | 2 keyword(s): what is a semantic layer, semantic layer |
| Single H1 | ✅ PASS | Hero title is the only H1; sections are H2. |
| Empty headings | ✅ PASS | No empty headings. |
| FAQ structure | ✅ PASS | 7 FAQ item(s), all complete. |
| Duplicate headings | ✅ PASS | No duplicate section headings. |
| GEO query coverage | ✅ PASS | Core phrase "semantic layer" found in definition or section headings. |
| Internal links minimum | ⚠ WARN | only 0 inbound link(s) recorded, need >=3 (this pipeline can't verify inbound links automatically — add manually) |
| AI-generated content flagged | ✅ PASS | 9 section(s) flagged aiGenerated for human review. |
| Drafting warnings | ⚠ WARN | 16 warning(s):   - FRANK'S 2026-08-27 FEEDBACK — Applied. See input/sources/semantic-layer/feedback-2026-08-27-frank.md for the full ingested feedback and a sec |
| Entry wrapper | ✅ PASS | Entry correctly wrapped. |
| Entry required fields | ✅ PASS | title and url present in entry. |
| JSON-LD present and valid | ✅ PASS | JSON-LD parses (unplaced — no field on asset_page to embed it in yet); DefinedTerm.name="semantic layer", url=https://software.strategy.com/assets/glossary/sema |
| resource_data.type | ✅ PASS | 'Blog' is a confirmed-valid value (though not confirmed specifically for glossary pages). |