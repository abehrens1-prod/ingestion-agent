# Blog Validation Report

## Summary ⚠️

**Status:** WARNINGS — review recommended

| Level | Count |
|---|---|
| ❌ ERROR | 0 |
| ⚠ WARN  | 5 |
| ✅ PASS  | 12 |

## Warnings (review recommended)

### ⚠ SEO meta description length
Meta description is 164 chars (recommended ≤160).

### ⚠ Empty headings
Empty heading text found: Section 1

### ⚠ Image asset UIDs
1 image(s) missing assetUid — upload to Contentstack Assets and fill in manually: ['image_0.png']

### ⚠ Field map coverage
config.yaml field_map missing entries for: ['body', 'faq', 'cta']

### ⚠ Parser warnings
8 parser warning(s):
  - No author name or publish date found in the document.
  - No hero image or video found; heroMedia set to null.
  - The embedded image ([IMAGE_EMBEDDED]) has no alt text or caption in the source document; altText left empty and requires human review.
  - The Metric Editor bullet contained nested sub-bullets (formula examples); these were collapsed into a single list item string for readability. Human review recommended to decide if formula examples should be a separate code block type.
  - No explicit Quick Answer box was present; quickAnswer was written from article content per extraction rules.

## All Checks

| Check | Result | Detail |
|---|---|---|
| Title present | ✅ PASS | Title: "Time Intelligence Metrics in Mosaic: Year-over-Year and Peri" |
| URL present | ✅ PASS | URL: /time-intelligence-metrics-in-mosaic-year-over-year-and-period-to-date-without-the-sql |
| SEO meta title | ✅ PASS | Meta title: "Time Intelligence Metrics in Mosaic: YoY & Period-to-Date" |
| SEO meta description length | ⚠ WARN | Meta description is 164 chars (recommended ≤160). |
| Target keywords | ✅ PASS | 5 keyword(s): time intelligence metrics, Mosaic semantic layer, year-over-year metrics, period-to-date, Mosaic Studio |
| Quick answer | ✅ PASS | 3 quick answer sentence(s) present. |
| CTA | ✅ PASS | CTA: "View Documentation" → https://www2.strategy.com/producthelp/Current/Mosaic/en-us/Content/Create_time_dimension.htm |
| Single H1 | ✅ PASS | No duplicate H1s detected. |
| Empty headings | ⚠ WARN | Empty heading text found: Section 1 |
| Duplicate headings | ✅ PASS | No duplicate headings. |
| Link format | ✅ PASS | All links appear well-formed. |
| Image asset UIDs | ⚠ WARN | 1 image(s) missing assetUid — upload to Contentstack Assets and fill in manually: ['image_0.png'] |
| FAQ structure | ✅ PASS | 5 FAQ item(s) with question + answer. |
| Contentstack entry wrapper | ✅ PASS | Entry is correctly wrapped in {"entry": {...}}. |
| Entry required fields | ✅ PASS | Required entry fields (title, url) present. |
| Field map coverage | ⚠ WARN | config.yaml field_map missing entries for: ['body', 'faq', 'cta'] |
| Parser warnings | ⚠ WARN | 8 parser warning(s):   - No author name or publish date found in the document.   - No hero image or video found; heroMed |