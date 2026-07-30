---
name: blog-ingestion
description: Run the full blog ingestion pipeline when a new .docx blog post arrives in the input folder and needs to be converted into a Contentstack-ready JSON entry. Use this skill whenever the user drops a new blog .docx into the input folder, says they want to ingest a blog post, mentions running the blog pipeline, wants to process a docx for Contentstack, or is working in the Blog Ingestion Agent project and needs to prepare a new blog entry. Always use this skill for any blog ingestion task — even if the user just says "process the blog" or "run the pipeline."
---

# Blog Ingestion — Orchestrator

Coordinates the full blog ingestion pipeline using isolated subagents for each heavy step. The orchestrator stays lean; each step runs in its own context so large JSON files never accumulate here.

**Sub-skills (standalone use):** `/blog-parse`, `/blog-map`, `/blog-validate`, `/blog-upload`

## Project root

```
/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
```

Before Phase 1, read this project's own `CLAUDE.md` (in the project root above) — it is the authoritative reference for this pipeline's commands, architecture, and known quirks, and is not auto-loaded just because a skill in this folder is running.

## Contentstack formatting reference

Before reviewing or debugging any generated JSON, read the formatting guide:

```
schemas/contentstack_formatting_guide.md
```

This file documents:
- All 6 content block types: `text`, `section_anchor`, `image`, `video`, `accordion`, `promo` (inline)
- A **block selection guide** — when to use each of the 6 block types, how to compose them per post based on source doc content and editorial judgment (no fixed post templates; blocks are chosen per-post)
- RTE node types: `p`, `h3` (Quick Answer/Short Answer label), `h4` (sub-section headers), `hr`, `ul`/`li`, `ol`/`li`, `table`/`tbody`/`tr`/`td`, soft line break
- Inline text attributes: `bold`, `italic`, `underline`, orange callout (`rgb(233,112,50)` + `font-color: "#fa660f"`)
- Hyperlink rules: external links use `target: "_blank"`, internal links omit it
- Quick Answer label variants: `"Quick Answer"` (product) / `"Short Answer"` (thought leadership); summary text color differs by type
- Top-level fields: `lead_paragraph` (always empty), `resource_data`, SEO fields, taxonomy term UIDs
- What the pipeline cannot auto-populate (author UIDs, image/video/promo refs, thumbnail)

Consult it whenever:
- Validating a `contentstack_entry.json` against the live schema
- Debugging why a block renders incorrectly
- Deciding how to map a doc element to the correct block type
- Determining whether a post should use inline promos or a top-level `cta_section`
- Confirming display properties for images, video, or promo blocks

---

## What the pipeline produces

- **Quick Answer block** — two paths depending on the source doc:
  - **Doc has a Quick Answer callout with bullets** → preserve those bullets exactly as written. Do not merge, reorder, or reduce them. If the parser merged items due to a schema limit (warning: "4 bullet items; schema allows 3 — fourth bullet merged"), that merge must be undone in Phase 3c before mapping.
  - **Doc has no Quick Answer callout** → a 3-bullet structure is synthesized from the article content. Review the synthesized bullets for accuracy before proceeding to mapping.

  The Quick Answer block is placed as the **first content block** (before the intro paragraphs). `lead_paragraph` is intentionally left empty. Always verify the Quick Answer appears correctly before publishing.
- **Hyperlinks** — inline hyperlinks from the .docx are preserved as `[LINK:anchor text|url]` markers during extraction and converted to Contentstack anchor nodes (`{"type": "a", "attrs": {"url": ..., "target": "_blank"}}`) in the JSON RTE. Any blog processed before June 2026 will be missing hyperlinks — add them manually in the Contentstack editor.
- **Table header rows** — if the first row of a table functions as a header, it goes into `headers` and renders with bold text (`th` cells) in Contentstack.
- **Post-FAQ paragraphs** — any paragraphs after the last FAQ item are extracted into `postFaqContent` and placed after the FAQ accordion, not before it.
- **Taxonomy — content-matched, not blindly applied** — `config.yaml → contentstack.taxonomy_terms` is a *catalog* of terms with known UIDs, not a fixed set to stamp on every post. `map_to_contentstack.py` cross-matches each post's AI-generated `suggestedTaxonomyTerms` (from parsing) against that catalog (case-insensitive substring match) and only applies terms that match — e.g. a post suggesting "Analytics Consolidation" will pick up the catalog's "Analytics" term, but won't get unrelated catalog terms like "Mosaic" or "Product Updates" just because they happen to be configured. Suggested terms with no catalog match are surfaced in `_mapping_warnings` for manual review — either add the term's UID to the catalog if it's a real gap, or apply it manually in the CS editor for a one-off case. (Fixed 2026-07-20 — previously the pipeline applied every catalog term to every post regardless of relevance.)

  **Available taxonomy terms (Contentstack):**
  - Mosaic
  - Semantic Layer
  - Data Fabric
  - AI Trends
  - Analytics
  - Business Intelligence
  - Product Updates
  - Thought Leadership
  - World
  - Customer Stories
  - Partner Network
  - Retail
  - Healthcare
  - Financial Services

  **How to recommend:** Match to article content. Thought Leadership fits strategic/opinion pieces. AI Trends fits AI adoption/strategy articles. Analytics/Business Intelligence fit how-to or technical content. Product Updates for feature announcements. Industry terms (Retail, Healthcare, Financial Services) for vertical-specific posts. Mosaic/Semantic Layer/Data Fabric for product-adjacent technical posts. Recommend 2–3 terms max.
- **Meta description** — targeted at 150 characters, complete sentences only, no "..." truncation. If the doc includes a meta description it is used verbatim; the SEO enrichment call always generates 1–2 alternatives in `seo.metaDescriptionAlternatives` for comparison.
- **URL slug** — the entry URL must be `/blog/<slug>` with **no `/software` prefix**. `config.yaml → contentstack.url_prefix` is set to `/blog` for this. If a mapped entry ever comes back with `/software/blog/...`, fix `url_prefix` to `/blog` and re-run `/blog-map`. Never publish an entry whose URL starts with `/software`.

---

## Phase 1 — Identify the input file

Run these two commands directly (no subagent needed):

```bash
ls "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/input/"*.docx 2>/dev/null
```

```bash
python3 -c "
import glob, os
base = '/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent'
for f in sorted(glob.glob(base + '/output/*/*.docx')):
    print(f'  [processed] {os.path.basename(f)}  →  {os.path.dirname(f)}/')
"
```

The `input/` folder is the inbox — any `.docx` still there is unprocessed. Files that have been moved to `output/*/` after upload are done.

- One unprocessed `.docx` → proceed automatically
- Multiple unprocessed → show list, ask the user which one
- `input/` empty → confirm with the user before re-running anything

**Ask the user now** for author name if they haven't provided it — it avoids a patch step after parse.

**Never ask about publish date.** Standing convention: always default to tomorrow (run date + 1 day, ISO 8601) and proceed without confirming. See Phase 3 for how to apply this after parse.

---

## Phase 2 — Parse (subagent)

Spawn an Agent with the prompt below. Fill in `<DOCX_PATH>` with the actual path.

```
You are running the blog-parse step for the blog ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/

Task: Parse this .docx file into normalized_blog.json.

Docx path: <DOCX_PATH>

Steps:
1. cd to the project root and run:
   python3 scripts/parse_with_claude.py "<DOCX_PATH>" 2>&1

2. Find the output directory (most recently modified under output/):
   ls -td output/*/

3. Read ONLY these specific fields from normalized_blog.json (do not read or print the full file):
   python3 -c "
   import json
   d = json.load(open('<OUTPUT_DIR>/normalized_blog.json'))
   print('title:', d.get('title', ''))
   print('author:', d.get('author', ''))
   print('publishDate:', d.get('publishDate', ''))
   print('warnings_count:', len(d.get('validationWarnings', [])))
   for w in d.get('validationWarnings', []): print('  WARN:', w)
   print('body_sections:', len(d.get('body', [])))
   print('has_faq:', bool(d.get('faq')))
   print('has_quick_answer:', bool(d.get('quickAnswer')))
   print('has_post_faq_content:', bool(d.get('postFaqContent')))
   print('has_cta:', bool(d.get('cta_list')))
   suggested = d.get('suggestedTaxonomyTerms') or []
   print('suggested_taxonomy_terms:', ', '.join(suggested) if suggested else '(none)')
   "

4. Return a compact summary under 300 words:
   - Output directory path
   - Title
   - Author (explicitly note if blank/missing)
   - Publish date (note if missing, non-ISO, or not equal to tomorrow's date)
   - Warning count + full warning list
   - Body section count, FAQ present, Quick Answer present, post-FAQ content present, CTA present
   - Suggested taxonomy terms (if any)
   Do NOT include the full JSON.
```

**Extract from the result:** output directory path, author (blank?), publishDate (missing/non-ISO/wrong?), warning list.

---

## Phase 3 — Patch author / date if missing

If the author came back blank:
- Ask the user for the author name (if not already provided)
- Use the Edit tool to patch `<OUTPUT_DIR>/normalized_blog.json`: find `"author": ""` and replace with the correct name
- No subagent needed — this is a single Edit call

**Publish date — never ask the user.** Always default to tomorrow (today's date + 1 day, ISO 8601 `YYYY-MM-DD`). This is a standing convention, not a per-run decision:
- If `publishDate` is missing, blank, or not in ISO format (e.g. a doc heading like `"July 2026"` bled into the field) — patch it to tomorrow's date with the Edit tool.
- If the doc explicitly provided a specific, unambiguous ISO date that differs from tomorrow, keep it verbatim — that's a real doc-provided value, not something to override.
- Only surface the date in your summary/preview to the user for their awareness — don't phrase it as a question.

---

## Phase 3b — Header structure check (ALWAYS run before mapping)

**Do this inline — no subagent needed.** Run this command directly:

```bash
python3 -c "
import json
d = json.load(open('<OUTPUT_DIR>/normalized_blog.json'))
for i, s in enumerate(d.get('body', [])):
    print(f'Section {i}: L{s.get(\"level\",2)} heading={repr(s.get(\"heading\",\"\")[:70])} blocks={len(s.get(\"blocks\",[]))}')
"
```

Review the output and ask: **do any H2 sections look like subheadings of the section immediately before them?** Signs of this:
- Very short section (1-3 blocks)
- Heading sounds like a sub-item, not a standalone topic ("The work that's already there", "Step 1: ...", "Why X", "How Y")
- The parent H2 has minimal content of its own (1 block) and these H2s follow in sequence

**If yes — fix it before mapping via JSON injection:**

```bash
python3 -c "
import json
from pathlib import Path
p = Path('<OUTPUT_DIR>/normalized_blog.json')
d = json.load(open(p))
body = d['body']

# Example: sections 3, 4, 5 are subheadings of section 2
# Adjust indices to match the actual structure
parent_idx = 2
sub_indices = [3, 4, 5]

parent = body[parent_idx]
for idx in sub_indices:
    sub = body[idx]
    parent['blocks'].append({'type': 'heading', 'text': sub['heading'], 'level': 3})
    parent['blocks'].extend(sub['blocks'])

# Remove merged sections (iterate in reverse to preserve indices)
for idx in sorted(sub_indices, reverse=True):
    body.pop(idx)

d['body'] = body
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)
print('Done. Sections remaining:', len(d['body']))
for i, s in enumerate(d['body']):
    print(f'  {i}: {repr(s[\"heading\"][:60])} — {len(s[\"blocks\"])} blocks')
"
```

**Numbered headers:** If the source doc has numbered headings (e.g. "1. The work that's already there", "2. The answer you think you're supposed to give"), check whether the number was preserved in the extracted heading text. If it was stripped by the parser or lost during H2→H3 restructuring, add it back manually in the JSON patch — set `"text": "1. The work that's already there"` explicitly. Do not rely on Contentstack or the template to supply numbering. This applies to H2 and H3 headings alike.

The same approach applies to **any other JSON-fixable issue** before mapping: reordering blocks, correcting list styles, merging split list blocks, adding missing blockquote type, etc. Always prefer a JSON patch here over a manual Contentstack editor fix.

---

## Phase 3c — Quick Answer review (ALWAYS run before mapping)

**Do this inline — no subagent needed.** Run this command directly:

```bash
python3 -c "
import json
d = json.load(open('<OUTPUT_DIR>/normalized_blog.json'))
qa = d.get('quickAnswer') or []
print(f'quickAnswer bullet count: {len(qa)}')
for i, item in enumerate(qa):
    if isinstance(item, dict):
        print(f'  {i+1}. {repr(item.get(\"headline\",\"\")[:80])}')
        if item.get('body'): print(f'     {repr(item[\"body\"][:80])}')
    else:
        print(f'  {i+1}. {repr(str(item)[:80])}')
for w in d.get('validationWarnings', []):
    if 'quick answer' in w.lower() or 'bullet' in w.lower() or 'merged' in w.lower():
        print(f'  WARN: {w}')
"
```

**Decision logic:**

- **Merge warning present** (e.g. "4 bullet items; schema allows 3 — fourth bullet merged into third") → the parser collapsed original doc bullets to fit an artificial limit. Restore all bullets from the doc using a JSON patch before mapping. The schema limit is a pipeline artifact, not a Contentstack constraint.
- **No merge warning, bullets look doc-sourced** → preserve as-is. Do not restructure.
- **Bullets look synthesized** (generic, no merge warning, doc had no callout) → review them for accuracy. If they don't read well, manually edit the `quickAnswer` items in `normalized_blog.json` before mapping.

**To restore merged bullets**, edit `normalized_blog.json` directly using the Edit tool — add the missing item back to the `quickAnswer` array with its `headline` and `body` fields matching what the doc said.

---

## Phase 4 — Map (subagent)

Spawn an Agent with the prompt below. Fill in `<OUTPUT_DIR>`.

```
You are running the blog-map step for the blog ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
Output directory: <OUTPUT_DIR>

Task: Map normalized_blog.json to contentstack_entry.json.

Steps:
1. cd to the project root and run:
   python3 scripts/map_to_contentstack.py "<OUTPUT_DIR>/normalized_blog.json" --output "<OUTPUT_DIR>/contentstack_entry.json" 2>&1

2. Read ONLY these fields from contentstack_entry.json (do not read or print the full file):
   python3 -c "
   import json
   d = json.load(open('<OUTPUT_DIR>/contentstack_entry.json'))
   entry = d.get('entry', {})
   warnings = d.get('_mapping_warnings', [])
   print('title:', entry.get('title', ''))
   print('url:', entry.get('url', ''))
   print('author:', entry.get('author', ''))
   print('publish_date:', entry.get('publish_date', ''))
   print('content_blocks:', len(entry.get('content', [])))
   print('warnings_count:', len(warnings))
   for w in warnings: print('  WARN:', w)
   "

3. Return a compact summary under 200 words:
   - Title and URL slug
   - Author field value (UID resolved or display name fallback — note which)
   - Publish date
   - Content block count
   - All mapping warnings (full list — note any suggested taxonomy terms)
   Do NOT include the full entry JSON.
```

---

## Phase 5 — Validate (subagent)

Spawn an Agent with the prompt below. Fill in `<OUTPUT_DIR>`.

```
You are running the blog-validate step for the blog ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
Output directory: <OUTPUT_DIR>

Task: Validate the pipeline output.

Steps:
1. cd to the project root and run:
   python3 scripts/validate_blog_json.py "<OUTPUT_DIR>/normalized_blog.json" "<OUTPUT_DIR>/contentstack_entry.json" 2>&1

2. Read the first 80 lines of validation_report.md:
   head -80 "<OUTPUT_DIR>/validation_report.md"

3. Count result levels:
   grep -c " PASS" "<OUTPUT_DIR>/validation_report.md" || echo 0
   grep -c " WARN" "<OUTPUT_DIR>/validation_report.md" || echo 0
   grep -c " ERROR" "<OUTPUT_DIR>/validation_report.md" || echo 0

4. Return a compact summary under 300 words:
   - PASS / WARN / ERROR counts
   - All ERROR items (blocking — must resolve before upload)
   - All WARN items (non-blocking but surfaced for review)
   - Full path to the report
   Do NOT include the full report text.
```

---

## Phase 6 — Structured preview and confirm

Run this command directly (no subagent) to generate the pre-upload preview:

```bash
python3 -c "
import json
norm = json.load(open('<OUTPUT_DIR>/normalized_blog.json'))
cs = json.load(open('<OUTPUT_DIR>/contentstack_entry.json'))
entry = cs.get('entry', {})

# Quick Answer check — first content block should be h3 label + ul
content = entry.get('content', [])
qa_ok = False
qa_bullet_count = 0
if content:
    b0_children = content[0].get('text', {}).get('text_content', {}).get('children', [])
    if b0_children and b0_children[0].get('type') == 'h3':
        label_text = (b0_children[0].get('children') or [{}])[0].get('text', '')
        if label_text.strip() in ('Quick Answer', 'Short Answer'):
            qa_ok = True
            if len(b0_children) > 1:
                qa_bullet_count = len(b0_children[1].get('children', []))

print('=== PRE-UPLOAD PREVIEW ===')
print(f'Title:         {entry.get(\"title\",\"\")}')
print(f'URL:           {entry.get(\"url\",\"\")}')
print(f'Author:        {entry.get(\"author\",\"(missing)\")}')
print(f'Publish date:  {entry.get(\"publish_date\",\"(missing)\")}')
print()
print(f'Quick Answer: {\"✓ present (\" + str(qa_bullet_count) + \" bullets)\" if qa_ok else \"✗ MISSING or not first content block (h3 label expected)\"}')
print(f'Content blocks: {len(entry.get(\"content\",[]))}')
faq = norm.get('faq',[])
print(f'FAQ items:     {len(faq)}')
images = [b for s in norm.get('body',[]) for b in s.get('blocks',[]) if b.get('type')==\"image\"]
missing_uid = [i for i in images if not i.get('assetUid')]
print(f'Images:        {len(images)} total, {len(missing_uid)} missing assetUid')
print(f'CTA:           {\"present\" if norm.get(\"cta_list\") else \"none\"}')
print()
meta = norm.get('seo',{}).get('metaDescription','')
print(f'Meta desc ({len(meta)} chars): {meta}')
alts = norm.get('seo',{}).get('metaDescriptionAlternatives',[])
for i,a in enumerate(alts,1): print(f'  Alt {i}: {a}')
print()
warnings = cs.get('_mapping_warnings',[])
print(f'Mapping warnings ({len(warnings)}):')
for w in warnings: print(f'  • {w}')
"
```

Present the full preview output to the user, then ask only: "Ready to upload as a draft?"

**Title prefix — do not ask, apply automatically:** Every uploaded title is prefixed with a version tag, `v1 -- `, `v2 -- `, etc. Start at `v1 --` unless a prior version of this same post already exists in Contentstack, in which case increment (`v2 --`, `v3 --`...). This is a standing convention — never ask the user about it, just apply it. See [[feedback_upload_versioning]].

Do not proceed to Phase 7 until the user explicitly confirms the upload itself.

---

## Phase 7 — Upload (subagent)

Spawn an Agent with the prompt below. Fill in `<OUTPUT_DIR>` and `<VERSION_PREFIX>` (default `v1 -- `; increment to `v2 -- `, `v3 -- `... only if a prior version of this post already exists in Contentstack — see [[feedback_upload_versioning]]).

```
You are running the blog-upload step for the blog ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
Output directory: <OUTPUT_DIR>
Title prefix: <VERSION_PREFIX>

Task: Upload contentstack_entry.json to Contentstack as a draft.

Steps:
1. Read only enough of contentstack_entry.json to find the entry.title line.
   Use the Edit tool to prepend "<VERSION_PREFIX>" to the title string inside the "entry" object only
   (there may be a second title occurrence elsewhere in the file — leave it alone).
   Skip this step only if the title already starts with a "vN -- " prefix.

2. cd to the project root and run:
   python3 scripts/upload_to_contentstack.py "<OUTPUT_DIR>/contentstack_entry.json" 2>&1

3. If the upload fails with HTTP 422 "title is not unique": increment the version
   (v1 → v2, v2 → v3, etc.), re-apply the Edit to bump the prefix, and retry the upload.

4. Return a compact summary under 200 words:
   - Final title uploaded (including version prefix)
   - Entry UID (blt...)
   - HTTP status
   - If failed: first 400 chars of the error response
   Do NOT print the full upload_response.json.

5. Include this post-upload checklist:
   Manual steps before publishing:
   • Set author in Contentstack editor (if not auto-linked via UID)
   • Link Promo entry UID to cta_section field
   • Upload hero image and inline images to CS Assets → paste UIDs into normalized_blog.json → re-run /blog-map
   • Verify publish date
   • Check mapping warnings for AI-suggested taxonomy terms → add manually in CS editor, or populate config.yaml → contentstack.taxonomy_terms with term UIDs to auto-apply on future runs
```

---

## Phase 7b — Move source file to output directory

Run this directly after a successful upload (entry UID returned). Do NOT run if the upload failed.

```bash
mv "<DOCX_PATH>" "<OUTPUT_DIR>/"
```

This moves the `.docx` out of `input/` and into the output directory alongside the pipeline artifacts (`normalized_blog.json`, `contentstack_entry.json`, `validation_report.md`, `upload_response.json`). An empty `input/` folder means all files for the day are done.

No `_source.txt` file is needed — the presence of the `.docx` in the output directory is the completion marker.

---

## Phase 8 — Final summary

Print a concise summary to the user:

```
✓ Blog ingested successfully

Title: <title>
Entry UID: <uid>
Output: <output_dir>/
Source file moved: input/<filename>.docx → <output_dir>/

Manual steps before publishing:
• Author: <name> — confirm in Contentstack editor
• Link Promo entry UID to cta_section
• Upload images → paste UIDs → re-run /blog-map
• Verify publish date: <date>
• Taxonomy: <suggested terms from AI> — add manually or populate config.yaml to auto-apply
```

---

## Known pipeline limitations

These are structural constraints — flag them to the user and note they require manual fixes in the Contentstack editor or changes to the source .docx before re-parsing:

| Limitation | Detail |
|---|---|
| Numbered sub-sections formatted as H2 | The pipeline maps H2 headings as section anchors, not numbered list items. If the source doc uses H2 headings for steps like "1. Start with inventory", they'll appear as section headers. Fix: restructure the .docx to use an ordered list instead of H2 headings. |
| Framework steps split across list blocks | Bold/numbered items interrupted by intervening paragraphs won't be auto-merged or renumbered. Fix manually in the CS editor or restructure the .docx. |
| CTA section requires manual Promo entry | The pipeline captures CTA content into `cta_list` (headline, button text) but cannot create or link a Promo entry — the API proxy only permits `blog_post`, `page`, and `cvent_page`. After upload, create a Promo entry manually in Contentstack using the extracted `cta_list` content, then link the Promo UID to the `cta_section` field on the blog draft. |
| Orange styling is template CSS | Orange headers, orange "Quick Answer" label, orange numbered list labels — these come from the blog template CSS applied at publish time. They will not be visible in the Contentstack editor draft preview; check stage.strategysoftware.com after publishing. |

---

## Common issues

| Issue | Fix |
|---|---|
| Author blank after parse | Patch `normalized_blog.json` → re-run map subagent |
| HTTP 422 "title is not unique" | Increment the version prefix (`v1 --` → `v2 --`...) and re-upload — see [[feedback_upload_versioning]] |
| Image WARNs | Upload images to CS Assets, paste UIDs into `normalized_blog.json`, re-run map subagent |
| JSON truncation during parse | `parse_with_claude.py` has built-in repair retry; if both calls fail, report the error |
| CTA missing Promo UID | Create a Promo entry in Contentstack using the `cta_list` headline + button text from `normalized_blog.json`, then link the Promo UID to `cta_section` in the blog draft. Button URL is often missing from the doc — ask the content author. |
| `tags` field schema warning | Safe to ignore — Contentstack silently drops it |
| Stale mapping warnings | Trust the actual field values in the entry, not the `_mapping_warnings` list |
| Relevant taxonomy term didn't auto-apply | The mapper only applies a catalog term when it matches one of the post's AI-suggested terms — check the mapping warning listing "Suggested taxonomy terms with no configured match." If the term is genuinely relevant, get its UID from Contentstack and add it to `config.yaml → contentstack.taxonomy_terms`, then re-run `/blog-map`. |
| Meta description ends in "..." | Re-parse the doc — pipeline now targets 150 chars with complete sentences and no truncation marker |
| Post-FAQ paragraphs placed before FAQ | Re-parse the doc — pipeline now extracts `postFaqContent` and places it after the FAQ accordion |
| Quick Answer not at top of page | The Quick Answer is the first content block (not in `lead_paragraph`). If it's missing, check whether `quickAnswer` is populated in `normalized_blog.json` — if empty, re-parse. If present but not appearing, re-run the map step. |
| Quick Answer bullets merged or reduced | If the parse warning mentions "4 bullet items; schema allows 3 — merged", restore all original bullets via JSON patch in Phase 3c before mapping. Preserve doc bullets exactly — count and text. |
| Quick Answer synthesized but reads poorly | Edit the `quickAnswer` items directly in `normalized_blog.json` before mapping. Three bullets is the target for synthesized answers, but accuracy matters more than count. |
| H4 feature headers not orange / missing | Pipeline now generates a two-h4 pair per H3 heading (empty spacer h4 + content h4, both with `font-color: "#fa660f"`). Each H3 starts its own `text` content block. If a post was processed before this fix (pre-June 2026), re-run `/blog-map` to regenerate. |
| Videos missing from content blocks | Video blocks require manual Contentstack asset UIDs — the pipeline skips them. After upload, open the entry in CS editor and insert video blocks between the relevant feature text blocks. |
| Images missing from content blocks | Images only become standalone content blocks when `assetUid` is populated in `normalized_blog.json`. Upload images to CS Assets → paste UIDs → re-run `/blog-map`. Until then, the image slot is absent from the entry (not a placeholder). |
| Wrong/irrelevant taxonomy terms applied | Fixed 2026-07-20 — the pipeline used to apply every catalog term in `config.yaml → contentstack.taxonomy_terms` to every post. It now only applies terms that match the post's AI-suggested topics (`_map_taxonomy` in `map_to_contentstack.py`). `config.yaml` currently has confirmed UIDs for: `product_updates`, `mosaic`, `semantic_layer`, `ai_trends`, `analytics`, `business_intelligence`. To add more terms to the catalog, get the UID from Contentstack (taxonomy slug, e.g. `thought_leadership`) and add it to config — it will only apply to posts whose suggested terms match it. |
