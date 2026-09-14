# Session 2026-06-16 — MCP Whitepaper v2 Structural Fixes & Upload

**Why:** Initial v1 upload of the MCP whitepaper had critical rendering issues (no visible text, broken background colors, missing numbered headings, missing bold text). This session diagnosed and fixed all of them, re-extracted the PDF with updated rules, and uploaded a corrected entry.

**How to apply:** These fixes are now baked into the pipeline scripts. All future whitepapers will benefit automatically. Do NOT revert the `section_header` behavior — it is confirmed non-rendering in the current page template.

---

## Contentstack Entries Now in Staging (MCP Whitepaper)

| Title (truncated) | UID | Status |
|---|---|---|
| `...Model Context Protocol` (v1, original) | `blt5719414388bcdaeb` | Broken — all text missing |
| `...Model Context Protocol (v2)` | `blte3c7635620563b8f` | Broken — headers stripped, spacing gaps |
| `...Model Context Protocol (v2 - fixed)` | `blt7c6cc4b708800a64` | **CORRECT** — uploaded 2026-06-16 |

**Action required:** Delete the two broken entries (v1 and v2) from Contentstack editor. Rename "(v2 - fixed)" to the final clean title. The correct entry is `blt7c6cc4b708800a64`.

Full entry title: `Implementing Enterprise AI at Scale: Strategy Mosaic and the Model Context Protocol (v2 - fixed)`
Entry URL: `/software/implementing-enterprise-ai-at-scale-strategy-mosaic-and-the-model-context-protocol`

---

## Problem 1: "Only seeing section headers, no text" (v1)

**Root cause:** Content blocks were structured correctly in the JSON, but something about how `section_header` and `text_block` content was rendered caused only headings to appear without paragraph text in the live page view.

**Diagnosis path:** User screenshots showed section title labels but no paragraph content. The API accepted the payload without error (HTTP 201), so the issue was rendering, not validation.

---

## Problem 2: `section_header` Does Not Render in the Page Template

**Critical discovery:** The `section_header` field on the `section` modular block is accepted by the Contentstack API without error, but the current `strategy.com` page template does **not render its content**. Setting `section_header` to a text or modular block containing RTE nodes causes that content to silently disappear on the live page. It appears to exist in the data but produces only whitespace/gaps in the rendered output.

**Fix applied in `scripts/map_to_contentstack.py`:**
- `section_header` is now always set to `[]` (empty array) for all section types
- All heading nodes (h1, h2, h3, etc.) are prepended to the `text_block` RTE node list so they appear inline with the paragraph content in the column area
- This is the `all_nodes = (section_header_nodes or []) + (rte_nodes or [])` pattern in `_make_section()`

**Do NOT change this back.** If the page template ever gets updated to render `section_header`, the fix would need to be re-evaluated.

---

## Problem 3: Hero and The Brief on Brown/Brass Background

**Root cause:** Initial `bg_color` values were set to `"Gradient Brass & White"` for hero and `"Brass"` for The Brief, matching what appeared in live blog entries. The user confirmed these looked wrong on the whitepaper page — brown/orange background on the opening sections.

**Fix:** Both `_build_hero_section()` and `_build_brief_section()` in `map_to_contentstack.py` now use `bg_color="White"`. All sections default to White.

**Note on config.yaml:** The config still lists these enum values as valid. They are valid (API accepts them), but the design decision is to use White for whitepaper pages. Blog posts may still use Brass/Gradient.

---

## Problem 4: Numbered Subheadings Stripped (e.g., "1. Hallucination Fire")

**Root cause:** pdfplumber strips ordered list item numbers when processing `[LIST]`-tagged content. Items like "1. The Hallucination Amplifier" arrive as just "The Hallucination Amplifier" in the tagged plaintext.

**What was built:** `_fix_numbered_headings()` post-processing function in `scripts/parse_with_claude.py`. It uses regex `_NUMBERED_PREFIX_RE = re.compile(r'^((?:\d+|[IVXivx]+|[A-Za-z])\.\s+)')` to detect numbered prefixes in `[H2]` and `[H3]` tagged headings in the source text, then restores them to headings in the normalized JSON that lost their prefix.

**Limitation:** This fix only works for items tagged `[H2]` or `[H3]` by pdfplumber (i.e., detected as headings by font size). Items that pdfplumber tagged as `[LIST]` items (numbered list items at body font size) cannot be auto-recovered. The "Three Critical Failures" subsection headings (1. The Hallucination Amplifier, 2. The Security Nightmare, 3. The Definition Crisis) fell into this category and still need to be manually added with their numbers in the Contentstack editor.

---

## Problem 5: Bold Inline Text Not Preserved in List Items

**Root cause:** The normalized JSON schema did not define a format for inline bold within list items, so Claude was producing plain strings even when the source had bolded label text (e.g., "**No query volume surprises:** rest of item").

**Fix 1 — `scripts/parse_with_claude.py`:** Updated `_SCHEMA_DESCRIPTION` and `_EXTRACTION_PROMPT` to define the `runs` format for list items:
```json
{"type": "list", "style": "bullet", "items": [
  "plain text item",
  [{"text": "Bold label:", "bold": true}, {"text": " rest of item text"}]
]}
```

**Fix 2 — `scripts/rte_builder.py`:** Updated `_li_node()` to accept either a plain string or a runs array:
```python
def _li_node(item) -> dict:
    if isinstance(item, list):
        children = _runs_to_children(item)
    else:
        children = [{"text": str(item)}]
```

---

## Problem 6: PUT (Update) Endpoint Returns 404

**Discovery:** The MicroStrategy middleware proxy at `https://api-stg.microstrategy.com/cs-software` does not support updating existing entries. Both attempted URLs:
- `{base_url}/entries/{content_type}/{uid}` → 404
- `{base_url}/content_types/{content_type}/entries/{uid}` → 404

Only POST (create) works. The upload script `--entry-uid` flag sends a PUT but it will always fail with 404. There is no programmatic way to update an existing entry through this proxy.

**Workaround:** Create new entries with unique titles (append a version suffix). Have a human delete broken/superseded entries from the Contentstack editor.

---

## v2 Extraction Details

The `output/mcp_normalized_v2.json` was a fresh Claude extraction of `Whitepapers/MCP_AI_Whitepaper.pdf` using the updated rules. Key stats:
- 13 body sections
- 3 Brief bullets
- SEO enriched (meta title, meta description, primary/secondary/long-tail keywords)
- 8 validation warnings (all relate to complex table extraction — expected, needs human review)

The `output/mcp_entry_v2.json` was mapped from that normalized JSON using the corrected `map_to_contentstack.py`:
- 16 total content_blocks: hero + brief + 13 body sections + CTA
- All headings embedded in text_block nodes (not in section_header)
- bg_color = White everywhere
- Bold runs in list items where present
- `section_header: []` on every block

---

## Upload Sequence That Worked

```bash
# Step 1: Remap the normalized JSON with fixed mapper
python3 scripts/map_to_contentstack.py output/mcp_normalized_v2.json --output output/mcp_entry_v2.json

# Step 2: Patch title to avoid uniqueness conflict (done manually in the JSON)
# Title: "...Model Context Protocol (v2 - fixed)"

# Step 3: Upload
python3 scripts/upload_to_contentstack.py output/mcp_entry_v2.json
# → HTTP 201, UID: blt7c6cc4b708800a64
```

First attempt failed with HTTP 422 "title is not unique" because the broken "(v2)" entry already existed. Adding "- fixed" to the title resolved it.

---

## Files Modified in This Session

| File | Change |
|---|---|
| `scripts/map_to_contentstack.py` | `section_header` always `[]`; headings prepended to `text_block`; hero/brief bg_color = White |
| `scripts/parse_with_claude.py` | Added `runs` format to schema; added `_fix_numbered_headings()`; added bold text extraction rules |
| `scripts/rte_builder.py` | `_li_node()` accepts string or runs array |
| `scripts/upload_to_contentstack.py` | Fixed PUT URL format (still 404 — update endpoint not supported) |
| `output/mcp_normalized_v2.json` | Fresh extraction with new rules |
| `output/mcp_entry_v2.json` | Mapped entry, title patched, successfully uploaded |
