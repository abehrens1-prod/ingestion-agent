# Whitepaper Formatting → Contentstack Implementation Guide
## Reference: AI Token Cost and Accuracy Benchmark (strategy.com)

**Source PDF:** `Whitepapers/AI Token Efficiency Whitepaper POSTED.pdf`  
**Purpose:** Exact JSON structures, colors, and dimensions for every element type. The JSON blocks below are annotated with `// design spec` comments — these are documentation notes, not valid JSON syntax.

> **Updated 2026-06-17** from the approved Contentstack entry JSON. The color values, dimensions, and structural patterns all derive from the live approved page.

---

## 1. Color + Design Quick Reference

| Element | Color | Hex | Notes |
|---|---|---|---|
| H1 title | `rgb(0, 0, 0)` | `#000000` | Black. Hero section_header. Centered. |
| H2 section heading | `rgb(0, 0, 0)` | `#000000` | Black. Banner mod_column. |
| H3 subsection heading | `rgb(250, 102, 15)` | `#fa660f` | **Orange. Always bold. Trailing space run.** |
| H3 hero subtitle | `rgb(250, 102, 15)` | `#fa660f` | Orange. Centered. |
| H3 "The Brief" label | via `font-color: "#000000"` | `#000000` | Black. No `attrs.style.color`. |
| Hero description (P) | `rgb(85, 85, 85)` | `#555555` | Medium gray. Centered. |
| Body paragraph text | `rgb(26, 26, 26)` | `#1a1a1a` | Near-black. All body content. |
| The Brief bullet text | _(no color styling)_ | inherited | Plain — no attrs on runs. |
| Table header (th) | `rgb(255, 255, 255)` | `#ffffff` | White text, dark bg, bold. |
| Table cell: error | `rgb(183, 28, 28)` | `#b71c1c` | Dark red, bold. Wrong/incorrect values. |
| Table cell: correct | `rgb(27, 107, 46)` | `#1b6b2e` | Dark green, bold. Correct values. |
| Table cell: default | `rgb(0, 0, 0)` | `#000000` | Black. Regular data cells. |
| Post-table note | `rgb(198, 93, 0)` | `#c65d00` | Dark orange. Context/warning text below tables. |
| Blockquote body text | `rgb(0, 61, 91)` | `#003d5b` | **Navy blue.** Callout blocks render as blockquote. |
| Blockquote bold label | `rgb(26, 78, 159)` | `#1a4e9f` | **Medium blue, bold.** Stat or key-term label inside blockquote. |
| Divider | `colorOrange` | _(CS token)_ | Not an RGB — string enum value. |
| Accent box outline | `outlineColorOrange` | _(CS token)_ | String enum in `outline_styles`. |

---

## 2. Page-Level Fields

| Field | Value | Notes |
|---|---|---|
| `title` | Full whitepaper title | From PDF cover page |
| `url` | `/software/<slug>` | **Approved short slug only** — do not auto-generate |
| `resource_data.type` | `"Analyst Report"` | All whitepapers |
| `resource_data.date` | `"YYYY-01-01T00:00:00.000Z"` | Year from copyright; always Jan 1 |
| `seo.metaTitle` | ~60 chars | Short version of title |
| `seo.metaDescription` | 130–155 chars | Pipeline generates; human reviews |
| `taxonomies` | Set by content team | Leave empty from pipeline |

---

## 3. Content Blocks Order

```
1. Hero section       — bg: "White", padding: "Default"
                        section_header: H1 + H3 subtitle + P (centered)
                        columns: The Brief mod_column (orange outlined box)
2. Body sections × N  — bg: "White", padding: "Short"
                        banner col: H2 + orange divider + intro paragraphs
                        subsection cols: one per H3 (orange, bold)
3. CTA section        — bg: "Brass" (orange background), padding: "Default"
```

The Brief is **inside the hero section** as a mod_column — not a separate section.

---

## 4. Common Section Options

These apply to every section.

```json
{
  "columns_per_row": 1,                    // always 1 — columns stack vertically
  "column_alignment": "Center, Top",
  "section_footer": [],
  "limit_header_width": null,              // null for all body sections; hero uses "75%" (see 5.1)
  "limit_footer_width": null,
  "more_column_options": {
    "column_spacing": "Default",
    "one_column_limit_width": "75%",       // content limited to 75% of page width
    "two_column_split": null,              // always null — single column layout
    "reverse_column_order_mobile": false,
    "accent_box_stretch": false
  },
  "more_section_options": {
    "text_color": "Dark",
    "padding": "Short bottom only",        // DEFAULT for all body sections
    "add_divider": [],                     // always empty array
    "bg_color": "White",                   // "White" everywhere except CTA ("Brass")
    "bg_custom_color": "",
    "bg_image": null,
    "mobile_bg_image": null,
    "parallax_bg": false,
    "bg_video_id": ""
  }
}
```

---

## 5. Block-by-Block Structures

### 5.1 Hero Section

Two parts: (a) centered title in `section_header`, (b) The Brief in `columns`.

```json
{
  "section": {
    "section_id": "hero",
    "section_header": [{
      "text": {
        // NOTE: hero section_header uses "text_content" key, NOT "text_block"
        // This is the ONLY place in the entire entry that uses text_content.
        "text_content": {
          "type": "doc",
          "_version": 98,
          "attrs": {},
          "children": [
            {
              "type": "h1",
              "attrs": {"style": {"text-align": "center"}, "redactor-attributes": {}},
              // H1: black (#000000), centered
              "children": [{"text": "Whitepaper Title Here", "attrs": {"style": {"color": "rgb(0, 0, 0)"}}}]
            },
            {
              "type": "h3",
              "attrs": {"style": {"text-align": "center"}, "redactor-attributes": {}},
              // H3 subtitle: orange (#fa660f), centered — smaller than H1, appears below it
              "children": [{"text": "Subtitle: Evaluating X Against Y", "attrs": {"style": {"color": "rgb(250, 102, 15)"}}, "font-color": "#fa660f"}]
            },
            {
              "type": "p",
              "attrs": {"style": {"text-align": "center"}, "redactor-attributes": {}},
              // Description: medium gray (#555555), centered — smallest text in hero block
              "children": [{"text": "Concise descriptor line here.", "attrs": {"style": {"color": "rgb(85, 85, 85)"}}}]
            }
          ]
        }
      }
    }],
    "columns": [ /* The Brief — see 5.2 */ ],
    "columns_per_row": 1,
    "column_alignment": "Center, Top",
    // HERO ONLY: limit_header_width constrains the section_header title block to 75% width.
    // Without this, the H1/H3/P title renders at full page width and bleeds outside the content column.
    // All body sections leave limit_header_width as null (they have no section_header content).
    "limit_header_width": "75%",
    "limit_footer_width": null,
    "more_column_options": {"one_column_limit_width": "75%", "two_column_split": null, "column_spacing": "Default"},
    "more_section_options": {"bg_color": "White", "padding": "Default", "add_divider": [], "text_color": "Dark"}
  }
}
```

**`limit_header_width` rule:** `"75%"` on the hero section only. This is what keeps the centered title block within the same width as the rest of the article. Body sections use `null` — they have no `section_header` content, so the setting has no effect.

---

### 5.2 The Brief (mod_column inside hero)

A single mod_column in the hero's `columns` array. Renders as an orange-outlined white box.

```json
{
  "mod_column": {
    "column_name": "The Brief",
    "accent_box_options": [{
      // Visual: thin orange border (#fa660f) outline, white fill, medium width
      // "Medium" = roughly 60% of column width (not full-width, not narrow)
      "size": "Medium",
      "styles": ["Outlined"],              // border style — no background fill
      "outline_styles": [
        "outlineThin",                     // thin border (1px approx)
        "outlineColorOrange"               // color: #fa660f = rgb(250,102,15)
      ],
      "flag": "",
      "align": null,
      "bg_color": "White",                 // white interior
      "bg_custom_color": "",
      "bg_image": null,
      "text_color": null,
      "add_link": []
    }],
    "content": [{
      "text": {
        "text_block": {                    // uses text_block (not text_content)
          "type": "doc",
          "_version": 98,
          "attrs": {},
          "children": [
            {
              "type": "h3",
              "attrs": {},
              // The Brief label: black via font-color attribute (NOT attrs.style.color)
              "children": [{"text": "The Brief", "font-color": "#000000"}]
            },
            {
              "type": "ul",
              "attrs": {},
              // 3–5 bullet items — NO color styling on runs (inherits from box CSS)
              "children": [
                {
                  "type": "li",
                  "attrs": {},
                  "children": [{
                    "type": "p",
                    "attrs": {},
                    "children": [
                      {"text": "Bold insight sentence here (~15–20 words).", "bold": true},
                      {"text": " Supporting sentence with evidence and context."}
                      // Note: no attrs.style.color on these runs — Brief inherits CSS defaults
                    ]
                  }]
                }
              ]
            }
          ]
        }
      }
    }]
  }
}
```

---

### 5.3 Body Section Structure

Each top-level section = one `section` block. Multiple mod_columns stack vertically (`columns_per_row: 1`).

```json
{
  "section": {
    "section_id": "section-1-token-cost",  // slug of heading; prefix "section-" if starts with digit
    "section_header": [],                  // always empty for body sections
    "columns": [

      // ── Column 1: "banner" ─────────────────────────────────────────
      // Contains: H2 heading (its own text_block) + orange divider + intro text_block
      {
        "mod_column": {
          "column_name": "banner",
          "accent_box_options": [],
          "content": [

            // H2 in its own text_block — black (#000000)
            {
              "text": {
                "text_block": {
                  "type": "doc", "_version": 98, "attrs": {},
                  "children": [{
                    "type": "h2",
                    "attrs": {},
                    // H2: black (#000000), no bold, no center
                    "children": [{"text": "1. Section Title Here", "attrs": {"style": {"color": "rgb(0, 0, 0)"}}}]
                  }]
                }
              }
            },

            // Orange divider — always between H2 and intro text
            {
              "divider": {
                "style": "thin",           // thin line (1px approx)
                "spacing": "12",           // 12px top and bottom padding
                "custom_spacing": null,
                "color": "colorOrange",    // orange: #fa660f (CS enum token, not RGB)
                "opacity": "1",
                "width": "100"             // 100% of column width
              }
            },

            // Intro paragraph(s) in their own text_block — near-black (#1a1a1a)
            {
              "text": {
                "text_block": {
                  "type": "doc", "_version": 98, "attrs": {},
                  "children": [{
                    "type": "p",
                    "attrs": {},
                    // Body text: near-black rgb(26,26,26) = #1a1a1a
                    "children": [{"text": "Intro paragraph text.", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}}]
                  }]
                }
              }
            }

          ]
        }
      },

      // ── Columns 2…N: one per H3 subsection ─────────────────────────
      {
        "mod_column": {
          "column_name": "1.1 Subsection Name",  // use subsection heading text
          "accent_box_options": [],
          "content": [{
            "text": {
              "text_block": {
                "type": "doc", "_version": 98, "attrs": {},
                "children": [
                  {
                    "type": "h3",
                    "attrs": {},
                    // H3 subsection: orange (#fa660f), ALWAYS bold, trailing space run
                    "children": [
                      {"text": "1.1  Subsection Title", "attrs": {"style": {"color": "rgb(250, 102, 15)"}}, "bold": true, "font-color": "#fa660f"},
                      {"text": " ", "attrs": {"style": {"color": "rgb(250, 102, 15)"}}, "font-color": "#fa660f"}
                    ]
                  },
                  {
                    "type": "p",
                    "attrs": {},
                    // Body paragraph: near-black rgb(26,26,26) = #1a1a1a
                    "children": [{"text": "Subsection body paragraph.", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}}]
                  }
                ]
              }
            }
          }]
        }
      }

    ],
    "columns_per_row": 1,
    "column_alignment": "Center, Top",
    "more_column_options": {"one_column_limit_width": "75%", "two_column_split": null, "column_spacing": "Default"},
    // DEFAULT padding for all body sections is "Short bottom only" (editorial decision, MCP whitepaper)
    "more_section_options": {"bg_color": "White", "padding": "Short bottom only", "add_divider": [], "text_color": "Dark"}
  }
}
```

**Banner pattern — two cases:**

**Case A — section has intro paragraphs before the first H3:**
```
banner: [H2 text_block] → [divider] → [intro paragraphs text_block]
sub col 1: H3 + content
sub col 2: H3 + content ...
```

**Case B — section jumps straight to H3 subsections (no intro text):**
The first subsection's H3+content is merged into the banner intro. Remaining subsections stay as separate mod_columns. This prevents a visually thin banner with only H2+divider and nothing below it.
```
banner: [H2 text_block] → [divider] → [H3(first sub) + content text_block]
sub col 1: H3 (second sub) + content
sub col 2: H3 (third sub) + content ...
```

**Padding defaults:**
- `"Default"` — hero, CTA only
- `"Short bottom only"` — **all body sections** (pipeline default, confirmed from final published entry)
- `"Short"` — editorial override for sections that need more breathing room below

---

### 5.4 Tables

Tables sit inside a subsection mod_column's `text_block`, or inline in the banner intro.

```json
{
  "type": "table",
  // colWidths: 250px per column, fixed regardless of column count
  "attrs": {"rows": 4, "cols": 4, "colWidths": [250, 250, 250, 250]},
  "children": [
    {
      "type": "thead",
      "attrs": {},
      "children": [{
        "type": "tr", "attrs": {},
        "children": [{
          "type": "th", "attrs": {},
          "children": [{
            "type": "p", "attrs": {},
            "children": [
              // th text: white (#ffffff), bold. font-color "#000000" is a CS quirk — keep it.
              {"text": "Column Header", "attrs": {"style": {"color": "rgb(255, 255, 255)"}}, "bold": true, "font-color": "#000000"},
              {"text": " ", "attrs": {"style": {"color": "rgb(255, 255, 255)"}}, "font-color": "#000000"}
            ]
          }]
        }]
      }]
    },
    {
      "type": "tbody",
      "attrs": {},
      "children": [
        {
          "type": "tr", "attrs": {},
          "children": [
            {
              "type": "td", "attrs": {},
              // Row label cell: black (#000000), left-aligned
              "children": [{"type": "p", "attrs": {}, "children": [{"text": "Row label", "attrs": {"style": {"color": "rgb(0, 0, 0)"}}}]}]
            },
            {
              "type": "td", "attrs": {},
              // Error/wrong result: dark red (#b71c1c), bold, center-aligned
              "children": [{"type": "p", "attrs": {"style": {"text-align": "center"}}, "children": [{"text": "Wrong value", "attrs": {"style": {"color": "rgb(183, 28, 28)"}}, "bold": true}]}]
            },
            {
              "type": "td", "attrs": {},
              // Correct result: dark green (#1b6b2e), bold, center-aligned
              "children": [{"type": "p", "attrs": {"style": {"text-align": "center"}}, "children": [{"text": "Correct value", "attrs": {"style": {"color": "rgb(27, 107, 46)"}}, "bold": true}]}]
            }
          ]
        }
      ]
    }
  ]
}
```

**Table rules:**
- `colWidths`: always `[250, 250, ...]` — 250px per column, never vary this
- Header row: `thead` wrapper → `tr` → `th` nodes with white text + bold + trailing space run
- Data rows: `tbody` wrapper → `tr` → `td` nodes
- Post-table context notes: use `rgb(198, 93, 0)` (#c65d00) dark orange on the paragraph below the table

---

### 5.5 Bulleted and Numbered Lists

```json
{
  "type": "ul",   // or "ol" for numbered
  "attrs": {},
  "children": [
    {
      "type": "li", "attrs": {},
      "children": [{
        "type": "p", "attrs": {},
        "children": [
          // Bold label: same near-black color as body text, bold true
          {"text": "Bold label:", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}, "bold": true},
          // Rest of item: same color, no bold
          {"text": " Rest of list item text.", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}}
        ]
      }]
    },
    {
      "type": "li", "attrs": {},
      "children": [{
        "type": "p", "attrs": {},
        // Plain item: near-black, no bold
        "children": [{"text": "Plain list item.", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}}]
      }]
    }
  ]
}
```

**Exception:** List items inside The Brief have **no color attrs** — runs are plain `{"text": "...", "bold": true}` with no `attrs.style.color`.

---

### 5.6 Inline Bold (mid-paragraph)

```json
{
  "type": "p", "attrs": {},
  "children": [
    // All runs in a paragraph share the same color. Only "bold" differs.
    {"text": "Normal text before — ", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}},
    {"text": "bold phrase here", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}, "bold": true},
    {"text": " — continuing normally.", "attrs": {"style": {"color": "rgb(26, 26, 26)"}}}
  ]
}
```

---

### 5.7 CTA Section

```json
{
  "section": {
    "section_id": "cta",
    "section_header": [],
    "columns": [{
      "mod_column": {
        "column_name": "cta",
        "accent_box_options": [],
        "content": [{
          "text": {
            "text_block": {
              "type": "doc", "_version": 98, "attrs": {},
              "children": [
                // CTA text has no explicit color styling — inherits from "Brass" section CSS
                {"type": "h2", "attrs": {}, "children": [{"text": "CTA Headline Here"}]},
                {"type": "p", "attrs": {}, "children": [{"text": "CTA body text."}]}
              ]
            }
          }
        }]
      }
    }],
    "columns_per_row": 1,
    "column_alignment": "Center, Top",
    "more_column_options": {"one_column_limit_width": "75%", "two_column_split": null, "column_spacing": "Default"},
    // "Brass" = the ONLY section that is not White — renders as orange/gold background
    "more_section_options": {"bg_color": "Brass", "padding": "Default", "add_divider": [], "text_color": "Dark"}
  }
}
```

---

### 5.8 Blockquote and HR (Callout Blocks → Blockquote)

Callout blocks from the normalized JSON (pull-quotes, highlighted statements, stat call-outs) are rendered as `blockquote` nodes. The blockquote provides visual separation from body text and renders with a left-border accent in the page template.

```json
{
  "type": "blockquote",
  "uid": "<32-hex>",
  "attrs": {},
  "children": [
    {
      "type": "p",
      "uid": "<32-hex>",
      "attrs": {},
      "children": [
        // If callout has a label: medium blue bold label + navy blue body
        {"text": "45.5% of organizations lack enterprise-wide governance.", "bold": true, "attrs": {"style": {"color": "rgb(26, 78, 159)"}}},
        {"text": " Supporting context sentence.", "attrs": {"style": {"color": "rgb(0, 61, 91)"}}}
        // If no label: navy blue plain run only
        // {"text": "Pull-quote or key insight.", "attrs": {"style": {"color": "rgb(0, 61, 91)"}}}
      ]
    }
  ]
}
```

**Color rules for blockquotes:**
- Bold label (stat, key term): `rgb(26, 78, 159)` medium blue (`#1a4e9f`)
- Body text: `rgb(0, 61, 91)` navy blue (`#003d5b`)
- Plain callout (no label): navy blue only

These two blues create a two-tone effect that distinguishes blockquotes from orange-accented headings and near-black body paragraphs.
```

**HR node** — used as a visual divider within a text block (separate from the orange section-level divider block):

```json
{
  "type": "hr",
  "uid": "<32-hex>",
  "attrs": {},
  "children": [{"text": ""}]
}
```

HR sits inside a `text_block` doc's `children` array. Use after a closing section or before a conclusion paragraph when visual breathing room is needed within a single mod_column.

---

### 5.9 FAQ Accordion Block

When a whitepaper has a section with heading `"FAQ"` (case-insensitive), the mapper automatically converts it to an `accordion` content block instead of a regular `section` block. The accordion sits at the top level of `content_blocks`, alongside other section blocks.

The normalized JSON must have alternating Q/A paragraph blocks:
- **Q block:** `{"type": "paragraph", "runs": [{"text": "Q: Question?", "bold": true}]}`
- **A block:** `{"type": "paragraph", "text": "A: Answer text."}`

The mapper strips the `Q: ` / `A: ` prefixes automatically.

```json
{
  "accordion": {
    "accordion_item": [
      {
        "title": "Question text (Q: prefix stripped)",
        "_metadata": {"uid": "cs<16-hex>"},
        "content": {
          "type": "doc",
          "attrs": {},
          "uid": "<32-hex>",
          "children": [
            {
              "type": "p",
              "attrs": {},
              "uid": "<32-hex>",
              "children": [{"text": "Answer text (A: prefix stripped)."}]
            }
          ],
          "_version": 1
        }
      }
    ],
    "_metadata": {"uid": "cs<16-hex>"},
    "accordion_options": "closed"
  }
}
```

- `accordion_options`: `"closed"` — all items collapsed by default
- Answer content is plain `p` nodes — no headings inside accordion answers
- The `accordion` block type is confirmed working in the blog content type; same structure applies here

---

### 5.10 H4 Headings (Sub-Subsection Level)

H4 is used when a section has named sub-features or sub-steps below the H3 level. Each H4 uses two nodes: an empty spacer h4 + the content h4. Both carry `font-color: "#fa660f"` (orange).

```json
{"type": "h4", "uid": "<32-hex>", "attrs": {}, "children": [{"text": "", "font-color": "#fa660f"}]},
{"type": "h4", "uid": "<32-hex>", "attrs": {}, "children": [{"text": "Sub-Section Header", "font-color": "#fa660f"}]}
```

- Use only when the source doc has clear named sub-items below an H3 (e.g. a list of named features or steps)
- Do NOT use H4 for ordinary bold emphasis — use an inline bold run in a `p` node instead
- H4 always appears at the start of a new content block, not inline in a larger text block

---

### 5.11 Image Blocks

Images sit as standalone content blocks within a mod_column's `content` array — they are NOT inline RTE nodes inside a `text_block`.

```json
{
  "image": {
    "reference": {},
    "_metadata": {"uid": "cs<16-hex>"},
    "caption": "",
    "limit_width": null,
    "alignment": "Center",
    "rounded_corners": "Medium",
    "drop_shadow": "None",
    "outline": false,
    "link": []
  }
}
```

**Display properties:**

| Property | Options | Default |
|---|---|---|
| `alignment` | `"Left"`, `"Center"`, `"Right"` | `"Center"` |
| `rounded_corners` | `"None"`, `"Small"`, `"Medium"`, `"Large"` | `"Medium"` |
| `drop_shadow` | `"None"`, `"Light"`, `"Medium"`, `"Heavy"` | `"None"` |
| `outline` | `true` / `false` | `false` |
| `limit_width` | `null` (full) or number in px (e.g. `500`) | `null` |

- `reference` must be populated with a Contentstack asset object after the image is uploaded to CS Assets — the pipeline cannot auto-populate this
- When no asset UID is available yet, leave `reference: {}` — validation will WARN but not block upload
- `link` is empty array unless the image should be hyperlinked

---

## 6. What to Drop from the PDF

| PDF Element | Action |
|---|---|
| Table of Contents | Drop entirely |
| Page numbers | Drop |
| "WHITEPAPER" cover label | Drop |
| Cover background image | Drop |
| Footer / copyright / address | Drop |
| Section separator lines | Drop — divider blocks handle visual separation |
| Raw URLs without context | Keep only if cited as a source reference |

---

## 7. section_id Naming Rules

| Rule | Example |
|---|---|
| Lowercase, alphanumeric, hyphens only | ✓ `section-1-token-cost` |
| Cannot start with a digit | ✗ `1-token-cost` → ✓ `section-1-token-cost` |
| No spaces or special characters | ✗ `section 1: token cost` → ✓ `section-1-token-cost` |
| Unique within the entry | Derive from section heading text |
| Fixed IDs for structural blocks | `hero` and `cta` always stay constant |

---

## 8. Output Folder Convention

Each whitepaper gets its own folder: `output/{YYYY-MM-DD}_{slug}/` where the date is when the pipeline was run.

```
output/
  2026-06-17_ai-token-cost-and-accuracy-benchmark/
    AI Token Efficiency Whitepaper POSTED.pdf   ← original source document
    normalized_whitepaper.json                  ← Claude extraction output
    contentstack_entry.json                     ← Contentstack-ready payload
    validation_report.md                        ← review checklist
```

---

## 9. Pre-Upload Validation Checklist

- [ ] URL slug approved by team (not auto-generated)
- [ ] Hero `section_header` has H1 (black, centered) + H3 (orange #fa660f, centered) + P (gray #555555, centered)
- [ ] Hero uses `text_content` key (not `text_block`) in section_header
- [ ] The Brief is a mod_column inside hero (NOT a separate section)
- [ ] The Brief accent box: `size: "Medium"`, `outline_styles: ["outlineThin", "outlineColorOrange"]`
- [ ] The Brief heading is H3 with `font-color: "#000000"` (not attrs.style.color)
- [ ] The Brief has 3–5 `ul` list items (not separate paragraphs)
- [ ] The Brief bullet runs have NO color styling (no attrs.style.color)
- [ ] Every body section banner: H2 (black) → orange divider → intro content (near-black)
- [ ] Sections with NO intro text: first H3 subsection merged into banner (Case B pattern)
- [ ] Sections WITH intro text: subsections stay as separate mod_columns (Case A pattern)
- [ ] Every H3 subsection: `rgb(250,102,15)` orange, `bold: true`, `font-color: "#fa660f"`, trailing space run
- [ ] All body paragraph runs: `rgb(26,26,26)` color
- [ ] All numbered headings preserved with numbers intact
- [ ] All `section_id` values: no digit at start, hyphens only
- [ ] All `bg_color` = `"White"` except CTA (`"Brass"`)
- [ ] Hero `limit_header_width` = `"75%"` — all other sections `null`
- [ ] All body section `padding` = `"Short bottom only"` (pipeline default)
- [ ] Hero and CTA `padding` = `"Default"`
- [ ] `add_divider: []` on every section
- [ ] `two_column_split: null` on every column
- [ ] `columns_per_row: 1` on every section
- [ ] `one_column_limit_width: "75%"` on every section
- [ ] Tables: `colWidths: [250, 250, ...]`, thead/tbody, white header text
- [ ] `resource_data.type` = `"Analyst Report"`
- [ ] `resource_data.date` = `"YYYY-01-01T00:00:00.000Z"`

---

*Reference: Approved Contentstack JSON — MCP Whitepaper (blte263a2900285495f) + Token Benchmark*  
*Updated: 2026-06-17*
