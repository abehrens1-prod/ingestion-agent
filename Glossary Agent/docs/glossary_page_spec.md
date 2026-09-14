# Glossary Page Spec

What a glossary page has to be, distilled from Frank Volinsky's Web & Digital Experience
operating plan (2026-08-20), the template launch deck (2026-08-25), and three Fireflies
calls (2026-08-10, 2026-08-18, 2026-08-24/25). This is the brief `draft_with_claude.py`
and `map_to_contentstack.py` build against. Update it as Frank/Jessica confirm the open
items below — do not silently drift the code away from what's written here.

## What a glossary page is

Frank, verbatim, 2026-08-25: *"The whole idea is just to capture whichever current
content we have on the website now, sort of aggregate it into one page on that
particular topic."*

**This is consolidation, not net-new writing.** The job is to find what Strategy has
already published about a term — across blogs, product pages, whitepapers — and
reshape it into one canonical page. Net-new generation is the fallback when nothing
existing covers a subtopic, not the default.

## Where it sits in the framework

Glossary pages are the **Narrative** template (GEO Tier 2, "Authority builders"),
alongside Blog, Whitepapers, and Reports. Framework classification: "Universal."

Citation-example pattern (from the deck): direct question framing —
"What is a semantic layer?", "What is AI governance?", "Benefits of semantic layers",
"Common AI governance challenges." Section headings should follow this pattern, matching
each term's `geoQueryTarget`.

Page-type hierarchy: Narrative (build authority) → Detail (answer questions) → Arrival
(define solutions) → Proofs (build trust) → Spotlight (generate pipeline), with Hubs
connecting everything.

## Internal linking — not optional

From the deck's priority matrix:

- Detail↔Narrative: **Critical**, both directions
- Narrative→Arrival: **High**

Frank's stated numeric standard (2026-08-24 call): **at least 3 links in and 3 links out**
per page.

## Structure

Frank's framework deck ("slide 4") turned out to be the tier/purpose/citation-example
table, not a section-by-section page template — there is no literal layout spec in that
deck. What we know instead:

- Same shared template as blog and whitepaper pages — Frank: *"That template is being
  used for blogs, white papers and the glossary pages... you can leave some of the
  sections out if you need to. Don't feel like you have to follow it word for word, but
  as much as possible."*
- **CONFIRMED 2026-09-01:** Jessica's template shipped as its own Contentstack content
  type, `asset_page` (schema export saved at
  `schemas/contentstack_asset_page.schema.json`) — not literally a hybrid of the `page`
  content type as first described, but the same intent: a native `page_header` group for
  the hero/"Brief," native `section_anchor` blocks for the TOC, plus `text`/`image`/
  `video`/`accordion`/`divider`/`promo` content blocks. This is now the standard —
  `scripts/map_to_contentstack.py` targets it directly. Do not revert to the old
  `page`-based hero/section-id workaround described below; it's kept here only as
  history.

Before 2026-09-01, this pipeline targeted the known `page` content type using the
whitepaper's **"The Brief"** hero pattern for the definition block and **`section_anchor`**
blocks per H2 (lifted from the blog mapper) as a TOC stand-in. Both were explicitly
provisional and are now replaced by `asset_page`'s native fields for the same purposes.

Two things `asset_page` does *not* have that the old mapper relied on:
- **No `custom_code` block** — nowhere to embed JSON-LD (see "Schema markup" below).
- **CTA is reference-only** — `cta_section` and the in-body `promo` block both reference
  an existing Contentstack `promo` entry, not freeform RTE copy. This pipeline has no
  promo entries to reference yet, so CTAs are currently omitted with a mapping warning
  instead of guessed. Once real promo entry UIDs exist (Jessica/Dale), wire them in.

## Schema markup / AI-LLM visibility

Frank is running a separate backend schema workstream with Doug, Dale and Jessica — "to
help support our AI and LLM visibility." **No schema type has been decided.** This
pipeline still computes `DefinedTerm` + `FAQPage` JSON-LD as a starting point, not a
confirmed spec, but as of the `asset_page` switch (2026-09-01) **there is no confirmed
place to put it** — `asset_page` has no `custom_code` block. `map_to_contentstack.py`
writes the computed JSON-LD to a top-level `_schema_markup_unplaced` key in
`contentstack_entry.json` so it isn't lost, pending a placement decision from
Frank/Doug/Dale/Jessica. `resource_data.type` is also still unconfirmed for a glossary
page (only `"Blog"` and `"Analyst Report"` are known-valid today).

## Term selection & prioritization

Source: `Content needs - Remaining Q3.xlsx` (the closest artifact found to the "Q3
Content Strategy doc" the operating plan references — that doc itself wasn't found on
disk). Nine glossary rows, all assigned to Ash, each with a `Keyword/phrase target` and
a `GEO query target` column already filled in. SEMrush keyword-gap tracking (43 keywords
vs. a fixed competitor set, AtScale named specifically) is the upstream logic that
produced this list — not something this pipeline re-derives.

**Ontology is on hold** — Frank explicitly parked it 2026-08-18. Don't add it to the
queue even though it appears elsewhere in wiki notes as a candidate term.

## Review chain

Ash drafts first cut → Henry edits for "strategy wording" (accuracy) → Frank reviews for
SEO/GEO. **Never auto-publish.** Every upload in this pipeline is `--dry-run` or a draft
entry, never `--publish`. AI-generated sections must be flagged (`provenance[].aiGenerated
= true`) so they surface in the human-review checklist.

## Open items (see plan's "Open items to close with Frank / Jessica")

1. ~~Jessica's hybrid template — content type/fields, once confirmed~~ — **CLOSED
   2026-09-01.** Shipped as the `asset_page` content type; see "Structure" above.
2. ~~Frank's exemplar glossary page~~ — no separate exemplar arrived, but Frank sent
   direct structural/content feedback on the drafted semantic-layer page on 2026-08-27
   (`input/sources/semantic-layer/feedback-2026-08-27-frank.md`), which now serves as
   the closest thing to a reference. Still watch for a literal exemplar if one shows up.
3. The literal Narrative section structure — Frank's 2026-08-27 feedback gives a
   concrete section-by-section shape for this one term (definition → intro paragraph +
   video → how it works + diagram → benefits → core components → why AI agents need it
   → industries → how to implement → why choose Strategy → FAQ). Treat this as a strong
   signal for the template, not yet a confirmed universal structure — re-verify against
   the next term drafted.
4. Valid `resource_data.type` for a glossary page
5. Schema markup type (`DefinedTerm` vs `Article` vs `FAQPage`) **and** — new as of the
   `asset_page` switch — where it even goes, since there's no `custom_code` block on
   this content type. See "Schema markup" above.
6. The "four live framework pages" the wiki mentions — count and URLs unconfirmed
7. ~~`contentstack.url_prefix`~~ — **CLOSED 2026-09-01.** `asset_page`'s own
   `options.url_prefix` is confirmed `/assets/` in the schema export; config now uses
   `/assets/glossary`.
8. **NEW (2026-09-01):** CTA entries — `cta_section` and the in-body `promo` block both
   need a real Contentstack `promo` entry to reference. No promo entries exist yet for
   this pipeline to point to; CTAs are omitted with a mapping warning until Jessica/Dale
   provide one (or a set, per Arrival-tier target).
9. ~~`page_header.subhead` mapping~~ — **CLOSED 2026-09-14.** Ash's call: `subhead` uses
   the definition block's first item's `boldSentence` (falling back to `geoQueryTarget`
   only if there's no definition item), not `geoQueryTarget` directly as originally
   mapped.
10. ~~`scripts/upload_to_contentstack.py` blocked with HTTP 403~~ — **CLOSED 2026-09-01.**
    The MicroStrategy API proxy's allowlist didn't include `asset_page` at first; Dale/ITS
    added it same-day.
11. **NEW (2026-09-01):** `text.accent_box` (references global field `accent_box_styles`)
    — a real upload with `bg_color: "White"`, `styles: ["Outlined"]` (copied from the old
    `page`-mapper's hero accent box) was rejected: HTTP 422, both values invalid enum
    members. That old shape was apparently specific to whatever global field the `page`
    type's hero used, not `accent_box_styles`. The API proxy can't be queried for the
    real enum values either (`/global_fields/` 404s; `content_types/accent_box_styles` is
    403 — same allowlist gap `asset_page` itself had, item #10). `map_to_contentstack.py`
    no longer sets `accent_box` on callout blocks — they're a plain bold-lead paragraph
    instead until Dale/Jessica can confirm valid values.
12. **NEW (2026-09-14) — Video workflow, confirmed with Ash:** Every on-site video is its
    own Contentstack `video`-content-type entry wrapping a YouTube/Wistia/Wistia-Channel
    link — that entry's own Entry ID (from its "Entry Information" panel, e.g.
    `bltfb3d9af8e01be23d`) is distinct from the video host's own ID (e.g. a Wistia ID like
    `4axrx3zvc9`). `map_to_contentstack.py`'s video block needs the **Entry ID** (field
    `contentstackUid` in `normalized_glossary.json`) to build a native `video` content
    block — the host ID alone can't be substituted. **The `video` content type is fully
    blocked from this pipeline's API proxy** (`content_types/video` returns 403 "not
    permitted through this middleware"; `entries/video/*` 404s even for real entries) —
    there is no read, list, or create access to it at all, so an Entry ID can never be
    looked up or verified programmatically and a new video entry can never be created by
    this pipeline. **Process rule: before drafting/mapping a section that should include a
    video, ask Ash for the Entry ID rather than defaulting straight to the
    `[VIDEO PLACEHOLDER]` fallback** — only fall back if Ash confirms no entry exists yet.
    Default-assume the source is Wistia (Ash: "90% of the time it'll be a Wistia video")
    and only confirm otherwise if something (e.g. a youtube.com link) suggests it isn't.
