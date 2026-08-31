# Blog Ingestion Agent

A local Python pipeline that converts blog Word documents (`.docx`) into Contentstack-compatible JSON entry files for human review before upload.

**What it does:** parse + normalize (Claude) → map → validate  
**What it does NOT do:** upload to Contentstack, publish, or upload assets

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Anthropic API key (required — Claude handles all parsing and normalization):

```bash
export ANTHROPIC_API_KEY=your_key_here
```

**Dependencies:** `python-docx`, `pyyaml`, `jsonschema`, `python-slugify`, `anthropic`

---

## Running the Pipeline

Drop a `.docx` blog file into `input/`, then run from this project's root directory:

```bash
python3 scripts/run_pipeline.py input/blog.docx
```

**Custom output directory:**
```bash
python3 scripts/run_pipeline.py input/blog.docx --output-dir output/my-blog
```

### Output files

| File | Description |
|---|---|
| `output/normalized_blog.json` | Clean internal structured format |
| `output/contentstack_entry.json` | Contentstack-compatible `{"entry": {...}}` payload |
| `output/validation_report.md` | PASS / WARN / ERROR check results |

---

## Running Individual Steps

Each script is independently runnable:

```bash
# Parse + normalize only (Claude)
python3 scripts/parse_with_claude.py input/blog.docx --output output/normalized_blog.json

# Map only (after editing normalized JSON manually)
python3 scripts/map_to_contentstack.py output/normalized_blog.json --output output/contentstack_entry.json

# Validate only
python3 scripts/validate_blog_json.py output/normalized_blog.json output/contentstack_entry.json
```

---

## Configuring Field Mappings (`config.yaml`)

The `field_map` in `config.yaml` maps internal normalized field names to your actual Contentstack field UIDs. Update these to match your content type schema:

```yaml
contentstack:
  content_type_uid: "blog_post"
  field_map:
    title: "title"
    url: "url"
    body: "rich_text_body"   # ← change to your actual UID if different
    faq: "faq_items"
    cta: "call_to_action"
  body_field_type: "json_rte"
```

Set `claude_model` in `config.yaml` to change which Claude model is used for parsing:

```yaml
pipeline:
  claude_model: "claude-sonnet-4-6"
```

---

## Normalized JSON Format

`normalized_blog.json` is the internal clean format produced by Claude. Key fields:

```json
{
  "title": "...",
  "subtitle": "...",
  "slug": "my-blog-post",
  "url": "/my-blog-post",
  "author": "Jane Smith",
  "publishDate": "May 2026",
  "seo": {
    "metaTitle": "...",
    "metaDescription": "...",
    "targetKeywords": []
  },
  "quickAnswer": ["Sentence 1.", "Sentence 2.", "Sentence 3."],
  "heroMedia": { "type": "image", "assetUid": "", "sourcePath": "image_0.png" },
  "body": [
    {
      "type": "section",
      "heading": "Section Title",
      "level": 2,
      "blocks": [
        { "type": "paragraph", "text": "..." },
        { "type": "list", "style": "bullet", "items": ["..."] },
        { "type": "table", "rows": [["Col A", "Col B"]] },
        { "type": "image", "sourcePath": "image_0.png", "assetUid": "", "altText": "" },
        { "type": "video", "url": "https://...", "embedType": "youtube" },
        { "type": "callout", "label": "The Risk:", "text": "..." }
      ]
    }
  ],
  "faq": [{ "question": "...", "answer": "...", "accordionEnabled": true }],
  "cta": { "headline": "...", "body": "...", "buttonText": "Read the Guide", "buttonUrl": "https://..." },
  "validationWarnings": []
}
```

---

## Manual Review Workflow

1. Run the pipeline
2. Review `output/validation_report.md` and `output/normalized_blog.json`
3. Edit `output/normalized_blog.json` directly to fix any issues:
   - Add `assetUid` values once images are uploaded to Contentstack Assets
   - Adjust any fields Claude got wrong
4. Re-run from the mapping step: `python3 scripts/map_to_contentstack.py output/normalized_blog.json`
5. When satisfied, upload `output/contentstack_entry.json` via Contentstack's UI or API

---

## Image Handling

Images are **not uploaded** by this pipeline:

- Embedded Word images → `{"type": "image", "sourcePath": "image_N.png", "assetUid": ""}` placeholder
- URL image references → `{"type": "image", "url": "...", "assetUid": ""}`
- Validation report flags all images with empty `assetUid`

**After uploading images to Contentstack Assets manually:**
1. Open `output/normalized_blog.json`
2. Set `assetUid` on each image block
3. Re-run: `python3 scripts/map_to_contentstack.py output/normalized_blog.json`

---

## What's Not Included

| Feature | Why excluded |
|---|---|
| Contentstack API upload | Requires env credentials; excluded to prevent accidental publishes |
| Asset upload (images/videos) | Requires Contentstack Management Token and binary upload |
| PDF parsing | Out of scope |
| Scheduled publishing | Use Contentstack's built-in scheduler |

---

## Known Limitations

- **Embedded Word images** are not extracted as files — only metadata is captured. Upload separately.
- **SharePoint/OneDrive video URLs** are captured as plain-text references and render as `[Video: ...]` in the body.
- **Text boxes, SmartArt, WordArt** in Word are not accessible via python-docx and are silently skipped.
