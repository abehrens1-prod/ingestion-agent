---
name: blog-upload
description: Upload contentstack_entry.json to Contentstack as a draft. Args: output directory path. Optional: --prefix "DRAFT -- " to prepend to the entry title (use when an entry with the same title already exists).
argument-hint: "<output/dir/> [--prefix 'DRAFT -- ']"
---

# Blog Upload

Uploads `contentstack_entry.json` to Contentstack via the MicroStrategy API proxy.

## Project root

```
/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
```

## Steps

**1. If a title prefix was specified** (`--prefix`), patch it into `contentstack_entry.json`:
- Read only the `entry.title` line to find the current title
- Use the Edit tool to prepend the prefix to the title string **inside the `"entry"` object only** (there may be a second title occurrence in `_mapping_warnings` — leave that one alone)
- Do NOT re-read the full file

**2. Run the upload script:**

```bash
cd "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent" && python3 scripts/upload_to_contentstack.py "<OUTPUT_DIR>/contentstack_entry.json" 2>&1
```

**3. Return a compact summary** — under 200 words, containing:
- Final title uploaded
- Entry UID (e.g. `blta89db3ea9085efff`)
- HTTP status (201 = created draft)
- If failed: first 400 chars of the error response

Do NOT print the full `upload_response.json`.

**4. Include this post-upload checklist** in your response:
```
Manual steps before publishing:
• Set author in Contentstack editor (if not auto-linked via UID)
• Link Promo entry UID to cta_section field
• Upload hero image and any inline images to CS Assets → paste UIDs into normalized_blog.json → re-run /blog-map
• Verify publish date
• Add taxonomy terms if needed
```

## Common issues

| Issue | Fix |
|---|---|
| HTTP 422 "title is not unique" | An entry with this title already exists. Re-run with `--prefix "DRAFT -- "` |
| HTTP 404 on PUT | Proxy only supports POST (create). Delete the old draft in Contentstack UI, then re-upload |
| `MSTR_API_KEY` not set | Add `MSTR_API_KEY=<key>` to `.env` in the project root |
