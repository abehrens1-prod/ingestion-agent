---
name: blog-parse
description: Parse a .docx blog post into normalized_blog.json using parse_with_claude.py. Use when the user wants to run or re-run just the parse step. Args: path to .docx file (relative to project root or absolute).
argument-hint: "<path/to/blog.docx>"
---

# Blog Parse

Parses a `.docx` file into `normalized_blog.json` via `parse_with_claude.py`.

## Project root

```
/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
```

## Steps

**1. Run the parse script** (cd to project root first):

```bash
cd "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent" && python3 scripts/parse_with_claude.py "<DOCX_PATH>" 2>&1
```

**2. Find the output directory** — it's the most recently modified folder under `output/`:

```bash
ls -td output/*/
```

**3. Read ONLY key fields** from `normalized_blog.json` (do NOT read or print the full file):

```bash
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
print('has_cta:', bool(d.get('cta')))
"
```

**4. Return a compact summary** — under 300 words, containing:
- Output directory path
- Title
- Author (note explicitly if blank or missing)
- Publish date (note if defaulted to today's date)
- Warning count + full warning list
- Body section count, FAQ present (yes/no), CTA present (yes/no)

Do NOT dump the full `normalized_blog.json` into your response.

## Error handling

- If the script fails with a JSON parse error, report the first 500 chars of stderr — do not retry automatically
- If `normalized_blog.json` is not found after the run, report the full script output so the caller can diagnose
