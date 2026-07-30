# Blog Validation Report

## Technical Summary ⚠️

**Status:** WARNINGS — review recommended

| Level | Count |
|---|---|
| ❌ ERROR | 0 |
| ⚠ WARN  | 4 |
| ✅ PASS  | 13 |

## Warnings (review recommended)

### ⚠ Empty headings
Empty heading text found: Section 1

### ⚠ Image asset UIDs
1 image(s) missing assetUid — upload to Contentstack Assets and fill in manually: ['image_0.png']

### ⚠ Field map coverage
config.yaml field_map missing entries for: ['body', 'faq', 'cta']

### ⚠ Parser warnings
7 parser warning(s):
  - No author name or publish date found in the document.
  - The [IMAGE_EMBEDDED] element in the Metadata & Semantic Modeling subsection has no alt text, source path details, or caption provided — altText left empty and sourcePath set to image_0.png for human review.
  - The second callout references a linked article 'How to Choose a Semantic Layer: A Buyer's Guide for Enterprise Teams' but no URL was provided for that link — no buttonUrl captured for that reference.
  - All three domain URLs (strategy.com) are treated as external links since no path-only internal URLs were found in the document.
  - The Short Answer table at the top contained only two sentences so quickAnswer array contains only two items.

## All Checks

| Check | Result | Detail |
|---|---|---|
| Title present | ✅ PASS | Title: "Semantic Layer Architecture for Enterprise AI: The Five Core" |
| URL present | ✅ PASS | URL: /semantic-layer-architecture-for-enterprise-ai-the-five-core-components |
| SEO meta title | ✅ PASS | Meta title: "Semantic Layer Architecture for Enterprise AI: 5 Components" |
| SEO meta description | ✅ PASS | Meta description (160 chars) |
| Target keywords | ✅ PASS | 5 keyword(s): semantic layer architecture, enterprise AI analytics, governed business logic, AI-ready semantic layer, en |
| Quick answer | ✅ PASS | 2 quick answer sentence(s) present. |
| CTA | ✅ PASS | CTA: "Explore Strategy Mosaic" → https://www.strategy.com/software/strategymosaic |
| Single H1 | ✅ PASS | No duplicate H1s detected. |
| Empty headings | ⚠ WARN | Empty heading text found: Section 1 |
| Duplicate headings | ✅ PASS | No duplicate headings. |
| Link format | ✅ PASS | All links appear well-formed. |
| Image asset UIDs | ⚠ WARN | 1 image(s) missing assetUid — upload to Contentstack Assets and fill in manually: ['image_0.png'] |
| FAQ structure | ✅ PASS | 6 FAQ item(s) with question + answer. |
| Contentstack entry wrapper | ✅ PASS | Entry is correctly wrapped in {"entry": {...}}. |
| Entry required fields | ✅ PASS | Required entry fields (title, url) present. |
| Field map coverage | ⚠ WARN | config.yaml field_map missing entries for: ['body', 'faq', 'cta'] |
| Parser warnings | ⚠ WARN | 7 parser warning(s):   - No author name or publish date found in the document.   - The [IMAGE_EMBEDDED] element in the M |