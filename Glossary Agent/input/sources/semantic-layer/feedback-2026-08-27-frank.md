# Feedback: Frank Volinsky — Glossary MVP review (2026-08-27)

**Raw file:** `raw/glossary-mvp-feedback-2026-08-27.docx` (verbatim, do not modify)
**Author (docx metadata):** Volinsky, Frank — last touched by Guo, Henry
**Page reviewed:** https://preview.strategysoftware.com/software/glossary/semantic-layer
**Applies to:** `output/2026-08-25_semantic-layer/normalized_glossary.json`
**Disposition:** Applied to the normalized JSON on 2026-08-27 — see `## Applied` below.
Contentstack entry regenerated but **not re-uploaded** (pending Ash's go-ahead; would
overwrite the live draft entry `bltdee2c01c6be4fb28`).

## General

- Page must live under the "Asset" page for TOC purposes: URL becomes
  `/asset/glossary/semantic-layer` (was `/software/glossary/semantic-layer` per the
  registry / `/semantic-layer` in the normalized JSON's `url` field). This is an IA
  change, not just a content edit — depends on the "Asset" parent page and its TOC
  existing in Contentstack. **Open — needs Jessica/dev confirmation.**
- Add stats and links to external research sources (Gartner, Forrester, IDC, or similar)
  under the Benefits section. **Open — no real citation available; did not fabricate
  one.** The existing unverified "38% of analyst time" / CIO Dive stat still needs
  independent verification or removal (see `validationWarnings` in the normalized JSON).
- Add internal links. Already had 5 Detail + 2 Arrival outbound links (meets Frank's
  3-in/3-out standard per `docs/glossary_page_spec.md`) — no change needed here beyond
  what the new sections below naturally add.

## Definition box

- Bullet 1: keep as-is.
- Bullets 2 & 3: replaced verbatim with Frank's suggested text:
  1. "A semantic layer standardizes key business metrics and definitions across teams,
     ensuring consistent reporting, trusted insights, and more confident
     decision-making."
  2. "A semantic layer gives AI agents governed business context, ensuring accurate,
     consistent insights from enterprise data by standardizing definitions for key
     metrics and entities."
- Bullets 4 & 5 (the two Strategy/Mosaic-specific ones): removed from the definition box
  per "keep this vendor-neutral until the bottom of the page." Reused verbatim in the
  new "Why Choose Strategy for Your Semantic Layer?" section at the bottom instead of
  being discarded.
- Added a new lead section ("What Is a Semantic Layer?", first section in the body,
  right under the definition box) with one expanding paragraph, per Frank's "one
  paragraph before the next section" note.
- Video ("Semantic Layer Overview") requested in that same spot. **Open — no video
  asset exists yet; the pipeline also has no video block type.** Flagged as a callout
  placeholder + a `validationWarnings` entry for the web team.

## How Does a Semantic Layer Work?

- Diagram requested after the first paragraph:
  `https://images.contentstack.io/v3/assets/bltb564490bc5201f31/blt5ca592cf75efe727/69dfa905b01d6b75ab546998/diagram-semantic-layer.svg`
  — **with the Mosaic logo removed.** The pipeline has no image block type and can't
  edit the SVG. Flagged as a callout placeholder (with the asset URL and the
  logo-removal requirement) + a `validationWarnings` entry.

## What Is a Universal Semantic Layer?

- **Removed entirely** — Frank wants this spun off into its own glossary page.
- The removed section text was preserved (not deleted from history) — it's the seed
  content for a future "universal semantic layer" page. Added `universal semantic
  layer` to `input/term_queue.json` (P2) so it isn't lost as a to-do.

## What Are the Benefits of a Semantic Layer?

- Kept, per Frank's note to get real citations for the "Supporting data" callout —
  still open, see General above.

## What Is the Difference Between a Semantic Layer and a Data Catalog?

- **Removed entirely** — same reasoning, own glossary page. `input/term_queue.json`
  already has a related term queued (`data catalog ai`, P2) — no new entry needed, but
  worth noting this section's text (data catalog vs. semantic layer framing) is a good
  seed source when that term gets drafted.

## NEW: What Are the Core Components of a Semantic Layer?

- New section, drafted from scratch (no direct harvested source — marked
  `model_generated` in provenance, flagged for Henry's accuracy review same as
  everything else AI-generated). Ends with a tie-in sentence into the AI agents section
  below it, per Frank's instruction.

## Why Do AI Agents Need a Semantic Layer?

- Removed the "Strategy's position" callout from this section — moved to the new "Why
  Choose Strategy" section at the bottom, same reasoning as the definition bullets.

## Which Industries Benefit From a Semantic Layer?

- No changes — Frank said "section looks good."

## NEW: How to Implement a Semantic Layer?

- New section, drafted from scratch (general implementation best practices — not a
  specific/statistical claim, so no external citation needed). Marked
  `model_generated` in provenance.

## NEW: Why Choose Strategy for Your Semantic Layer?

- New closing section combining: the two Strategy/Mosaic bullets removed from the
  definition box, and the "Strategy's position" callout removed from the AI agents
  section. All three pieces are pre-existing approved copy, not new claims — this
  section is a reassembly, not net-new generation.

## FAQ

- Removed: "What is the difference between a semantic layer and a data catalog?" and
  "What is a universal semantic layer?" (their sections no longer exist on this page).
- Added: FAQ entries for the three new sections (core components, implementation, why
  choose Strategy).
- Kept as-is: "What is a semantic layer?", "Why do AI agents need a semantic layer?",
  "How does a semantic layer reduce LLM token costs?", "How long has Strategy been
  building a semantic layer?"

## Applied

All of the above is reflected in `output/2026-08-25_semantic-layer/normalized_glossary.json`
as of 2026-08-27. `map_to_contentstack.py` and `validate_glossary_json.py` were re-run
against the updated JSON to regenerate `contentstack_entry.json` and
`validation_report.md`. Re-upload to Contentstack was **not** run — that would update
the live draft entry and needs an explicit go-ahead first (see
`docs/glossary_page_spec.md`'s review chain: Ash → Henry → Frank, never auto-publish).

## Still open (needs Frank / Jessica / dev, not resolvable from this pipeline alone)

1. `/asset/glossary/semantic-layer` URL + Asset-page TOC integration.
2. Real external citations (Gartner/Forrester/IDC) for the Benefits section.
3. Semantic Layer Overview video asset.
4. Diagram asset with the Mosaic logo removed.
5. Jessica's hybrid Contentstack template — still unconfirmed (see
   `docs/glossary_page_spec.md` open items; unchanged by this feedback round).
