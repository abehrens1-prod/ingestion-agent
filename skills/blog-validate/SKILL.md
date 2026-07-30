---
name: blog-validate
description: Validate normalized_blog.json and contentstack_entry.json and return a PASS/WARN/ERROR summary. Args: output directory path.
argument-hint: "<output/dir/>"
---

# Blog Validate

Runs `validate_blog_json.py` to generate `validation_report.md` and surfaces blocking issues.

## Project root

```
/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent/
```

## Steps

**1. Run the validation script:**

```bash
cd "/Users/abehrens/Library/CloudStorage/OneDrive-MicroStrategy,Inc/Desktop/Claude Code/Projects/Ingestion Agents/Blog Ingestion Agent" && python3 scripts/validate_blog_json.py "<OUTPUT_DIR>/normalized_blog.json" "<OUTPUT_DIR>/contentstack_entry.json" 2>&1
```

**2. Read the top section of the report** (the human-readable checklist portion):

```bash
head -80 "<OUTPUT_DIR>/validation_report.md"
```

**3. Count result levels:**

```bash
grep -c " PASS" "<OUTPUT_DIR>/validation_report.md" || echo 0
grep -c " WARN" "<OUTPUT_DIR>/validation_report.md" || echo 0
grep -c " ERROR" "<OUTPUT_DIR>/validation_report.md" || echo 0
```

**4. Extract ERROR and WARN lines specifically:**

```bash
grep " ERROR\| WARN" "<OUTPUT_DIR>/validation_report.md"
```

**5. Return a compact summary** — under 300 words, containing:
- PASS / WARN / ERROR counts
- Full list of ERROR items (these are blocking — must be resolved before upload)
- Full list of WARN items (non-blocking but need human review)
- Full path to the report: `<OUTPUT_DIR>/validation_report.md`

Do NOT include the full report text in your response.
