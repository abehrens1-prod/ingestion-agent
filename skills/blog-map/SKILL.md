---
name: blog-map
description: Map normalized_blog.json to contentstack_entry.json using map_to_contentstack.py. Use when re-running the mapping step after editing normalized_blog.json. Args: output directory path (e.g. output/unknown-blog-post-2026-06/).
argument-hint: "<output/dir/>"
---

# Blog Map

Runs `map_to_contentstack.py` to convert `normalized_blog.json` → `contentstack_entry.json`.

## Project root

```
/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
```

## Steps

**1. Run the mapping script:**

```bash
cd "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent" && python3 scripts/map_to_contentstack.py "<OUTPUT_DIR>/normalized_blog.json" --output "<OUTPUT_DIR>/contentstack_entry.json" 2>&1
```

**2. Read ONLY key fields** from the resulting `contentstack_entry.json` (do NOT read or print the full file):

```bash
python3 -c "
import json
d = json.load(open('<OUTPUT_DIR>/contentstack_entry.json'))
entry = d.get('entry', {})
warnings = d.get('_mapping_warnings', [])
print('title:', entry.get('title', ''))
print('url:', entry.get('url', ''))
print('author:', entry.get('author', ''))
print('publish_date:', entry.get('publish_date', ''))
print('warnings_count:', len(warnings))
for w in warnings: print('  WARN:', w)
"
```

**3. Return a compact summary** — under 200 words, containing:
- Entry title and URL slug
- Author field value (UID resolved as `[{uid: blt..., _content_type_uid: blog_author}]` or display name fallback)
- Publish date
- All mapping warnings (full list)

Do NOT dump the full `contentstack_entry.json` into your response.

## Common issues

- **Author display name instead of UID**: means the author isn't in `config.yaml → contentstack.authors`. Ask the user for the UID or add it to config.yaml and re-run.
- **`tags` field warning from pre-flight**: safe to ignore — Contentstack silently drops it.
