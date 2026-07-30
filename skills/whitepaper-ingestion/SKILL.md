---
name: whitepaper-ingestion
description: Run the full whitepaper ingestion pipeline when a PDF (or DOCX) whitepaper needs to be converted into a Contentstack-ready JSON entry for strategy.com. Use this skill whenever the user drops a new PDF into the input folder, says they want to ingest a whitepaper, mentions running the whitepaper pipeline, wants to process a PDF for Contentstack, wants to create a whitepaper page, or is working in the Whitepaper Ingestion Agent project. Always use this skill for any whitepaper ingestion or processing task — even if the user just says "process the whitepaper", "run the pipeline", or "ingest this PDF."
---

# Whitepaper Ingestion — Orchestrator

Coordinates the full whitepaper ingestion pipeline using subagents for heavy steps. The orchestrator stays lean; each step runs in its own context so large JSON files never accumulate here.

**Sub-skills (standalone use):** No standalone sub-skills — run this orchestrator for the full pipeline.

## Project root

```
/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent/
```

Before Phase 1, read this project's own `CLAUDE.md` (in the project root above) — it is the authoritative reference for this pipeline's commands, architecture, and known quirks, and is not auto-loaded just because a skill in this folder is running.

## Formatting reference

Before reviewing or debugging any generated JSON, read:

```
docs/formatting_guide.md
```

This documents all color values, block structures, section patterns, and the pre-upload validation checklist. Consult it whenever validating a `contentstack_entry.json`, debugging rendering issues, or confirming field values.

---

## Phase 1 — Identify the input file

Run these directly (no subagent needed):

```bash
ls "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent/input/"*.pdf "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent/input/"*.docx 2>/dev/null
```

```bash
python3 -c "
import glob, os
base = '/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent'
for f in sorted(glob.glob(base + '/output/*/*.pdf') + glob.glob(base + '/output/*/*.docx')):
    print(f'  [processed] {os.path.basename(f)}  →  {os.path.dirname(f)}/')
"
```

The `input/` folder is the inbox — any file still there is unprocessed. Files copied to `output/*/` after upload are done.

- One unprocessed file → proceed automatically
- Multiple unprocessed → show list, ask which one
- `input/` empty → confirm with user before re-running anything

**Ask the user now** for the desired URL slug if they haven't provided it. The slug determines the page URL (`/software/<slug>`) and must be approved by the content team — the pipeline auto-generates a slug from the title, but the URL must be reviewed and confirmed before upload.

---

## Phase 2 — Parse and normalize with Claude (subagent)

Spawn an Agent with the prompt below. Fill in `<INPUT_PATH>` with the actual file path. This step makes two Claude API calls and takes ~3 minutes for a typical PDF — don't kill the process.

```
You are running the parse step for the whitepaper ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent/

Task: Parse and normalize the whitepaper into normalized_whitepaper.json.

Input file: <INPUT_PATH>

Steps:
1. cd to the project root and run:
   python3 scripts/parse_with_claude.py "<INPUT_PATH>" 2>&1

   This will take ~3 minutes. Do not kill it early.
   The script defaults to output/normalized_whitepaper.json — that's expected.

2. Move the output to a dated subdirectory based on today's date + slug:
   python3 -c "
   import json, os, shutil
   from datetime import date
   base = '/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent'
   src = base + '/output/normalized_whitepaper.json'
   d = json.load(open(src))
   slug = d.get('slug', 'whitepaper')
   today = date.today().strftime('%Y-%m-%d')
   out_dir = f'{base}/output/{today}_{slug}'
   os.makedirs(out_dir, exist_ok=True)
   shutil.move(src, out_dir + '/normalized_whitepaper.json')
   print('output_dir:', out_dir)
   "

3. Read ONLY these specific fields from the moved normalized_whitepaper.json:
   python3 -c "
   import json, glob, os
   base = '/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent'
   dirs = sorted(glob.glob(base + '/output/*/'), key=os.path.getmtime, reverse=True)
   out_dir = dirs[0].rstrip('/')
   print('output_dir:', out_dir)
   d = json.load(open(out_dir + '/normalized_whitepaper.json'))
   print('title:', d.get('title', ''))
   print('subtitle:', d.get('subtitle', ''))
   print('slug:', d.get('slug', ''))
   print('url:', d.get('url', ''))
   print('published_year:', d.get('publishedYear', ''))
   print('description_chars:', len(d.get('description', '')))
   brief = d.get('brief', [])
   print('brief_bullets:', len(brief))
   for i, b in enumerate(brief):
       print(f'  {i+1}. {repr(b.get(\"boldSentence\", \"\")[:80])}')
   body = d.get('body', [])
   print('body_sections:', len(body))
   for i, s in enumerate(body):
       print(f'  Section {i}: heading={repr(s.get(\"heading\",\"\")[:60])} blocks={len(s.get(\"blocks\",[]))}')
   cta = d.get('cta')
   print('has_cta:', bool(cta))
   if cta: print('  cta_headline:', repr(cta.get('headline','')[:60]))
   warnings = d.get('validationWarnings', [])
   print('warnings_count:', len(warnings))
   for w in warnings: print('  WARN:', w)
   seo = d.get('seo', {})
   print('seo_meta_title:', repr(seo.get('metaTitle','')[:70]))
   print('seo_meta_desc_chars:', len(seo.get('metaDescription','')))
   print('seo_keywords:', seo.get('targetKeywords', [])[:5])
   "

4. Return a compact summary under 400 words:
   - Output directory path (the dated subdirectory)
   - Title, subtitle, auto-generated slug and URL
   - Published year
   - Description character count
   - Brief bullet count + each boldSentence preview
   - Body section count + list of all section headings
   - CTA present (yes/no), headline if present
   - Warning count + full warning list
   - SEO: meta title, meta description char count, target keywords
   Do NOT include the full JSON.
```

**Extract from the result:** output directory, auto-generated slug/URL, brief count, section headings, warning list.

---

## Phase 3 — Review normalized output (inline)

Do this inline — no subagent needed.

**3a. Check the Brief (required — every whitepaper must have one):**

The Brief must have 3–5 bullets, each with a `boldSentence` (~15–20 words, key insight) and `supportingText` (1–2 supporting sentences). If the brief is missing or has fewer than 3 bullets, the pipeline will generate them — review them for accuracy.

```bash
python3 -c "
import json
d = json.load(open('<OUTPUT_DIR>/normalized_whitepaper.json'))
brief = d.get('brief', [])
print(f'Brief bullets: {len(brief)}')
for i, b in enumerate(brief, 1):
    print(f'\n{i}. BOLD: {b.get(\"boldSentence\",\"\")}')
    print(f'   SUPPORT: {b.get(\"supportingText\",\"\")}')
"
```

If any bullet reads poorly or is inaccurate, edit `normalized_whitepaper.json` directly with the Edit tool before mapping.

**3b. Check section structure:**

```bash
python3 -c "
import json
d = json.load(open('<OUTPUT_DIR>/normalized_whitepaper.json'))
for i, s in enumerate(d.get('body', [])):
    blocks = s.get('blocks', [])
    block_types = [b.get('type','?') for b in blocks]
    print(f'Section {i}: level={s.get(\"level\",\"?\")} heading={repr(s.get(\"heading\",\"\")[:60])}')
    print(f'  blocks({len(blocks)}): {block_types[:8]}')
"
```

Look for:
- Sections with 0 blocks (empty — may need manual content)
- Numbered section headings that had their numbers stripped (e.g. "Token Cost" instead of "1. Token Cost") — fix with Edit tool if found
- Any H1 sections in the body (only one H1 is valid — it should be the title)

**3c. URL slug review:**

The pipeline auto-generates a slug from the title. Check whether it's clean and matches what the team wants for the live URL:

```
/software/<slug>
```

If the slug needs to change, edit `normalized_whitepaper.json` → update both `slug` and `url` fields.

---

## Phase 4 — Map to Contentstack (subagent)

Spawn an Agent with the prompt below. Fill in `<OUTPUT_DIR>`.

```
You are running the map step for the whitepaper ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent/

Output directory: <OUTPUT_DIR>

Task: Map normalized_whitepaper.json to contentstack_entry.json.

Steps:
1. cd to the project root and run:
   python3 scripts/map_to_contentstack.py "<OUTPUT_DIR>/normalized_whitepaper.json" --output "<OUTPUT_DIR>/contentstack_entry.json" 2>&1

2. Read ONLY these fields from contentstack_entry.json (do not read or print the full file):
   python3 -c "
   import json
   d = json.load(open('<OUTPUT_DIR>/contentstack_entry.json'))
   entry = d.get('entry', {})
   warnings = d.get('_mapping_warnings', [])
   blocks = entry.get('content_blocks', [])
   print('title:', entry.get('title', ''))
   print('url:', entry.get('url', ''))
   print('content_blocks:', len(blocks))
   for b in blocks:
       sec = b.get('section', {})
       sid = sec.get('section_id', '?')
       bg = sec.get('more_section_options', {}).get('bg_color', '?')
       ncols = len(sec.get('columns', []))
       print(f'  [{sid[:40]}] bg={bg} cols={ncols}')
   print('resource_type:', entry.get('resource_data', {}).get('type', ''))
   print('resource_date:', entry.get('resource_data', {}).get('date', ''))
   print('warnings_count:', len(warnings))
   for w in warnings: print('  WARN:', w)
   "

3. Return a compact summary under 300 words:
   - Title and URL slug
   - Total content_blocks count
   - List of all section IDs with bg_color and column count
   - resource_data.type and date
   - All mapping warnings (full list)
   Do NOT include the full entry JSON.
```

---

## Phase 5 — Validate (inline)

Run validation directly — it's fast and produces a readable report:

```bash
cd "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent" && python3 scripts/validate_whitepaper_json.py "<OUTPUT_DIR>/normalized_whitepaper.json" "<OUTPUT_DIR>/contentstack_entry.json" 2>&1 | tail -5
```

Then read the top of the validation report:

```bash
head -60 "<OUTPUT_DIR>/validation_report.md"
```

Triage results:
- **ERRORs** — blocking; fix before upload. Most common: missing URL, brief empty, invalid section structure
- **WARNs** — non-blocking but review; most common: table extraction issues (complex merged cells from PDFs — expected; require human review in Contentstack editor)

---

## Phase 6 — Pre-upload preview and confirm

Run this inline to generate the pre-upload preview:

```bash
python3 -c "
import json
norm = json.load(open('<OUTPUT_DIR>/normalized_whitepaper.json'))
cs = json.load(open('<OUTPUT_DIR>/contentstack_entry.json'))
entry = cs.get('entry', {})
blocks = entry.get('content_blocks', [])

print('=== PRE-UPLOAD PREVIEW ===')
print(f'Title:        {entry.get(\"title\",\"\")}')
print(f'URL:          {entry.get(\"url\",\"\")}')
print(f'Year:         {norm.get(\"publishedYear\",\"\")}')
print(f'Brief:        {len(norm.get(\"brief\",[]))} bullets')
print(f'Body:         {len(norm.get(\"body\",[]))} sections')
print(f'Blocks:       {len(blocks)} content_blocks')
print()

# Check hero structure
hero = next((b[\"section\"] for b in blocks if b.get(\"section\",{}).get(\"section_id\")==\"hero\"), None)
if hero:
    brief_col = hero.get('columns',[{}])[0].get('mod_column',{}) if hero.get('columns') else {}
    has_box = bool(brief_col.get('accent_box_options'))
    lhw = hero.get('limit_header_width')
    print(f'Hero:         limit_header_width={lhw}  The Brief accent_box={\"✓\" if has_box else \"✗ MISSING\"}')

# Check bg_colors
cta_sec = next((b[\"section\"] for b in blocks if b.get(\"section\",{}).get(\"section_id\")==\"cta\"), None)
if cta_sec:
    print(f'CTA section:  bg={cta_sec.get(\"more_section_options\",{}).get(\"bg_color\")}  (should be Brass)')

body_bgs = set()
for b in blocks:
    sec = b.get('section',{})
    if sec.get('section_id') not in ('hero','cta'):
        body_bgs.add(sec.get('more_section_options',{}).get('bg_color'))
if body_bgs:
    print(f'Body bg_colors: {body_bgs}  (should all be White)')

print()
seo = norm.get('seo',{})
meta_desc = seo.get('metaDescription','')
print(f'Meta desc ({len(meta_desc)} chars): {meta_desc}')
alts = seo.get('metaDescriptionAlternatives',[])
for i,a in enumerate(alts,1): print(f'  Alt {i}: {a}')
print()
warnings = cs.get('_mapping_warnings',[])
print(f'Mapping warnings ({len(warnings)}):')
for w in warnings: print(f'  • {w}')
"
```

Present the full preview to the user, then confirm:
1. "Is the URL slug correct?" — this is the final URL on strategy.com; it cannot be changed post-publish without a redirect
2. "Ready to upload as a draft?"

**Do not proceed to Phase 7 until the user explicitly confirms both.**

---

## Phase 7 — Upload (subagent)

Spawn an Agent with the prompt below. Fill in `<OUTPUT_DIR>`.

```
You are running the upload step for the whitepaper ingestion pipeline.

Project root: /Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent/

Output directory: <OUTPUT_DIR>

Task: Upload contentstack_entry.json to Contentstack as a draft.

Steps:
1. cd to the project root and run:
   python3 scripts/upload_to_contentstack.py "<OUTPUT_DIR>/contentstack_entry.json" 2>&1

   Note: The upload script automatically handles title uniqueness by prepending "v1 | ", "v2 | ", etc.
   if an entry with the same title already exists. This is expected behavior — the versioned title
   is only a draft label; the content team renames the final entry in the Contentstack editor.

2. Read upload_response.json for just the entry UID:
   python3 -c "
   import json
   d = json.load(open('<OUTPUT_DIR>/upload_response.json'))
   entry = d.get('entry', d)
   print('uid:', entry.get('uid','(not found)'))
   print('title:', entry.get('title','')[:80])
   print('http_status: from upload script output above')
   "

3. Return a compact summary under 200 words:
   - Final versioned title uploaded (e.g. "v1 | Whitepaper Title")
   - Entry UID (blt...)
   - HTTP status (201 = success)
   - If failed: first 400 chars of the error response
   Do NOT print the full upload_response.json.

4. Include this post-upload checklist in your summary:
   Manual steps before publishing:
   • Rename the entry in Contentstack editor (remove "v1 | " prefix — give it the clean final title)
   • Set the URL slug if it differs from what was in the JSON (editor allows override)
   • Assign taxonomies in the Contentstack editor
   • Add a promo/thumbnail image if required
   • Review any table content that had extraction warnings (complex merged cells need manual fix)
   • Verify The Brief bullets are accurate and compelling
   • Review meta description — alternatives are in the validation report
   • Publish to stage to verify rendering: https://stage.strategysoftware.com
```

**Important — PUT endpoint is broken:** The MicroStrategy API proxy does not support updating existing entries (PUT returns 404). If you need to fix a previously uploaded entry, create a new one (the upload script handles this automatically with version prefixing) and delete the old broken entry from the Contentstack editor.

---

## Phase 7.5 — Move input file to output directory (inline)

After a successful upload, move the source PDF/DOCX from `input/` into the output directory so it's archived alongside the pipeline artifacts:

```bash
mv "<INPUT_PATH>" "<OUTPUT_DIR>/<FILENAME>"
```

For example:
```bash
mv "/path/to/input/Bridging_the_Data_Gap_for_AI_Readiness.pdf" \
   "/path/to/output/2026-06-18_bridging-the-data-gap-for-ai-readiness/Bridging_the_Data_Gap_for_AI_Readiness.pdf"
```

This keeps `input/` as a clean inbox — only unprocessed files remain there. Files in `output/*/` are fully processed.

Then update the whitepaper registry:

```bash
cd "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Whitepaper Ingestion Agent" && python3 scripts/update_registry.py "<OUTPUT_DIR>" 2>&1
```

This appends a new row to `whitepaper_registry.md` at the project root with the title, URL, UID, and output directory. Duplicate UIDs are ignored automatically.

---

## Phase 8 — Final summary

Print a concise summary to the user:

```
✓ Whitepaper ingested successfully

Title: <versioned title>
Entry UID: <uid>
URL: <url>
Output: <output_dir>/
Source PDF: moved from input/ → <output_dir>/

Manual steps before publishing:
• Rename entry in Contentstack editor (remove "v1 | " prefix)
• Set URL slug if different from auto-generated
• Assign taxonomies
• Review The Brief: <N> bullets
• Review meta description (alternatives in validation_report.md)
• Fix any table extraction warnings manually in the CS editor
• Publish to stage and verify: https://stage.strategysoftware.com
```

---

## Known quirks

| Issue | Detail |
|---|---|
| Parse takes ~3 minutes | Two Claude API calls for a typical PDF. Don't kill the process — 8192 token limit causes truncation, pipeline uses 16384. |
| PUT endpoint 404 | The API proxy only supports POST. Updates require creating a new entry and deleting the old one. Upload script handles uniqueness via "v1 | " prefix. |
| `section_header` does not render | The strategy.com page template ignores `section_header` content — the mapper sets it to `[]` always and puts all heading nodes into `text_block`. Do not revert this. |
| PDF table extraction | pdfplumber struggles with merged cells. Tables with complex layouts produce validation WARNs — these are expected and need manual review in the Contentstack editor. |
| Numbered headings stripped | pdfplumber strips list item numbers. The pipeline attempts to recover them via regex on H2/H3 tagged headings. Items tagged as `[LIST]` (body font size) cannot be auto-recovered — fix manually. |
| `tags` field schema warning | Safe to ignore — Contentstack accepts the field even though it's not in the schema. |
| bg_color "Light Gray" is invalid | Use "White" for all non-CTA sections. The only valid colors are "White" (body/hero/brief) and "Brass" (CTA only). |
| Callout blocks → blockquote | Normalized JSON `callout` blocks render as `blockquote` nodes, not styled paragraphs. Bold labels use medium blue (`rgb(26, 78, 159)`); body text uses navy blue (`rgb(0, 61, 91)`). See formatting_guide.md §5.8. |
| Title uniqueness | Contentstack requires unique titles per content type. Upload script auto-increments version prefix. Final title is set manually in the editor. |

## Running individual steps

If the full pipeline times out, run steps individually from the project root:

```bash
# Step 1: Parse
python3 scripts/parse_with_claude.py input/whitepaper.pdf

# Step 2: Map
python3 scripts/map_to_contentstack.py output/<slug>/normalized_whitepaper.json

# Step 3: Validate
python3 scripts/validate_whitepaper_json.py output/<slug>/normalized_whitepaper.json output/<slug>/contentstack_entry.json

# Step 4: Upload
python3 scripts/upload_to_contentstack.py output/<slug>/contentstack_entry.json
```
