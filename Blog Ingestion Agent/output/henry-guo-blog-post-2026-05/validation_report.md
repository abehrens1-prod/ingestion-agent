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
Meta description is 167 chars (recommended ≤160).

### ⚠ CTA completeness
CTA detected but missing: buttonUrl.

### ⚠ Empty headings
Empty heading text found: Section 1

### ⚠ Field map coverage
config.yaml field_map missing entries for: ['body', 'faq', 'cta']

### ⚠ Parser warnings
6 parser warning(s):
  - Two media assets are SharePoint-hosted MP4 video files; access may require authentication. Confirm public embed URLs or replace with accessible CDN links before publishing.
  - The closing paragraph references a 'What's New page' with no URL provided; buttonUrl for CTA is left empty and should be filled in by the web team.
  - No heroMedia was present in the document; the field is set to null.
  - Author bio was not included in the document; authorBio is empty.
  - The [BOLD] 'Image:' labels preceding the SharePoint video URLs appear to label videos, not static images — extracted as video blocks. Human review recommended to confirm asset types.

## All Checks

| Check | Result | Detail |
|---|---|---|
| Title present | ✅ PASS | Title: "May 2026: Consistent Governed Data, Less Compliance Work, an" |
| URL present | ✅ PASS | URL: /may-2026-consistent-governed-data-less-compliance-work-and-actionable-dashboards |
| SEO meta title | ✅ PASS | Meta title: "May 2026: Governed Data, Compliance & Actionable Dashboards" |
| SEO meta description length | ⚠ WARN | Meta description is 167 chars (recommended ≤160). |
| Target keywords | ✅ PASS | 5 keyword(s): Databricks Unity Catalog metadata, GDPR telemetry anonymization, SQL transaction forms, Strategy Mosaic, L |
| Quick answer | ✅ PASS | 3 quick answer sentence(s) present. |
| CTA completeness | ⚠ WARN | CTA detected but missing: buttonUrl. |
| Single H1 | ✅ PASS | No duplicate H1s detected. |
| Empty headings | ⚠ WARN | Empty heading text found: Section 1 |
| Duplicate headings | ✅ PASS | No duplicate headings. |
| Link format | ✅ PASS | All links appear well-formed. |
| Image asset UIDs | ✅ PASS | All images have assetUid (or no images present). |
| FAQ structure | ✅ PASS | 7 FAQ item(s) with question + answer. |
| Contentstack entry wrapper | ✅ PASS | Entry is correctly wrapped in {"entry": {...}}. |
| Entry required fields | ✅ PASS | Required entry fields (title, url) present. |
| Field map coverage | ⚠ WARN | config.yaml field_map missing entries for: ['body', 'faq', 'cta'] |
| Parser warnings | ⚠ WARN | 6 parser warning(s):   - Two media assets are SharePoint-hosted MP4 video files; access may require authentication. Conf |