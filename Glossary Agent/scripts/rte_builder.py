"""
rte_builder.py — Build Contentstack JSON RTE node structures from normalized blocks.

Colors and structure match the approved AI Token Cost and Accuracy Benchmark entry
(strategy.com), confirmed 2026-06-17. Each node has: type, uid (UUID hex), attrs, children.

Imported by map_to_contentstack.py — not called directly.

Inline run formatting (bold/italic/links, in `_runs_to_children`) is built by rendering a
small HTML fragment and piping it through the Node serializer in rte_serializer_node/
(Contentstack's own open-source @contentstack/json-rte-serializer) — the same package the
Blog Ingestion Agent depends on (its own separate copy under its own scripts/, per the
"projects don't share code" rule; see that project's CLAUDE.md, 2026-08-27). ITS (Dale)
flagged the real Contentstack RTE serializer as the thing to depend on for anything that
might need to track future format changes — link/mark nesting is exactly that: the part
with real combinatorial complexity (bold+italic+link in any order), where hand-rolling is
most likely to drift from what Contentstack's own editor actually produces.

Headings and tables stay fully hand-built, deliberately, not as leftover scope:
- This template's approved styling uses Contentstack's "font-color" swatch attribute
  (on H3 headings and table header cells) — a distinct thing from a CSS `style.color`.
  Verified against the installed serializer package (grepped its built lib): there is no
  HTML tag or attribute it maps to a `font-color` mark. There's no HTML input that can
  produce it, so these can't go through the serializer at all.
- The installed serializer (3.1.0) also has a separate, confirmed bug: it silently drops
  a run's `style.color` whenever that run is also bold/italic/underlined, in every element
  nesting order tested. Table headers here are bold+white and blockquote labels are
  bold+blue, so both would come out colorless (invisible-on-header-background, in the
  header case) if built via HTML the naive way. `_runs_to_children` works around this by
  serializing the mark (bold/italic/link) only, then patching the run's color directly
  onto the resulting text leaf in Python — the serializer still owns all the structural
  work (uids, node types, link/mark nesting), only the color is hand-applied afterward.

Contentstack JSON RTE spec:
  https://www.contentstack.com/docs/developers/json-rich-text-editor/
"""

import html as html_lib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Optional

_SERIALIZER_SCRIPT = Path(__file__).parent / "rte_serializer_node" / "serialize.js"

# Text colors — used consistently across the entry
BODY_TEXT = "rgb(26, 26, 26)"
HEADING_BLACK = "rgb(0, 0, 0)"
HEADING_ORANGE = "rgb(250, 102, 15)"
HERO_GRAY = "rgb(85, 85, 85)"
TABLE_HEADER_TEXT = "rgb(255, 255, 255)"
TABLE_CELL_TEXT = "rgb(0, 0, 0)"
NAVY_BLUE = "rgb(0, 61, 91)"      # blockquote body text
BLUE_LABEL = "rgb(26, 78, 159)"   # blockquote bold label (stat / key term)


def _uid() -> str:
    return uuid.uuid4().hex  # 32 hex chars, no hyphens — matches CS internal format


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


def _serialize_html(html_fragment: str) -> list:
    """Run one HTML element through the Node RTE serializer; return its doc children."""
    try:
        result = subprocess.run(
            ["node", str(_SERIALIZER_SCRIPT)],
            input=html_fragment,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Node.js not found on PATH — required for RTE serialization. Install Node, "
            "then run `npm install` inside scripts/rte_serializer_node/."
        ) from e
    if result.returncode != 0:
        raise RuntimeError(
            f"rte_serializer_node failed on:\n{html_fragment}\n\nstderr: {result.stderr.strip()}"
        )
    doc = json.loads(result.stdout)
    return doc["children"]


def _run_mark_html(run: dict) -> str:
    """Render a run's bold/italic/link markup only — never color (see module docstring
    for why color is patched on afterward instead of embedded here)."""
    text = run.get("text", "")
    if not text:
        return ""
    chunk = _esc(text)
    if run.get("bold"):
        chunk = f"<b>{chunk}</b>"
    if run.get("italic"):
        chunk = f"<i>{chunk}</i>"
    url = run.get("url")
    if url:
        chunk = f'<a href="{_esc(url)}" target="_blank">{chunk}</a>'
    return chunk


def _patch_color(node: dict, color: str) -> None:
    """Apply a color style onto a serialized leaf — or, for a link node, onto its
    inner text child — working around the serializer's mark+color drop bug."""
    target = node if "text" in node else node["children"][0]
    target.setdefault("attrs", {}).setdefault("style", {})["color"] = color


def _runs_to_children(runs: list, default_color: Optional[str] = None) -> list:
    """Convert normalized run dicts (text/bold/italic/url/color) to RTE inline children."""
    non_empty = [r for r in runs if r.get("text")]
    if not non_empty:
        return [{"text": ""}]
    html_fragment = "".join(_run_mark_html(r) for r in non_empty)
    children = _serialize_html(f"<p>{html_fragment}</p>")[0]["children"]
    for node, run in zip(children, non_empty):
        color = run.get("color") or default_color
        if color:
            _patch_color(node, color)
    return children


def p_node(
    runs: Optional[list] = None,
    text: Optional[str] = None,
    color: Optional[str] = None,
    centered: bool = False,
) -> dict:
    """Paragraph node. Accepts a runs list or a plain text string."""
    node_attrs: dict = {}
    if centered:
        node_attrs = {"style": {"text-align": "center"}, "redactor-attributes": {}}
    if runs:
        children = _runs_to_children(runs, default_color=color)
    elif text is not None:
        run: dict = {"text": text}
        if color:
            run["attrs"] = {"style": {"color": color}}
        children = [run]
    else:
        children = [{"text": ""}]
    return {"type": "p", "uid": _uid(), "attrs": node_attrs, "children": children}


def heading_node(
    text: str,
    level: int = 2,
    color: Optional[str] = None,
    bold: bool = False,
    centered: bool = False,
    font_color: Optional[str] = None,
) -> dict:
    """
    Heading node (h1–h6). Hand-built — see module docstring ("font-color").

    Usage patterns:
      H1 hero title:       color=HEADING_BLACK, centered=True
      H2 section heading:  color=HEADING_BLACK
      H3 subsection:       color=HEADING_ORANGE, bold=True, font_color="#fa660f"
      H3 The Brief label:  font_color="#000000" only (no color, no bold)
      H3 hero subtitle:    color=HEADING_ORANGE, centered=True, font_color="#fa660f"
    """
    tag = f"h{max(1, min(6, level))}"
    run: dict = {"text": text}
    if color:
        run["attrs"] = {"style": {"color": color}}
    if bold:
        run["bold"] = True
    if font_color:
        run["font-color"] = font_color
    children = [run]
    # H3 subsection headings include a trailing space run (matches approved template)
    if level == 3 and (color or bold):
        space: dict = {"text": " "}
        if color:
            space["attrs"] = {"style": {"color": color}}
        if font_color:
            space["font-color"] = font_color
        children.append(space)
    node_attrs: dict = {}
    if centered:
        node_attrs = {"style": {"text-align": "center"}, "redactor-attributes": {}}
    return {"type": tag, "uid": _uid(), "attrs": node_attrs, "children": children}


def ul_node(items: list, text_color: Optional[str] = None) -> dict:
    return {
        "type": "ul",
        "uid": _uid(),
        "attrs": {},
        "children": [_li_node(item, text_color=text_color) for item in items],
    }


def ol_node(items: list, text_color: Optional[str] = None) -> dict:
    return {
        "type": "ol",
        "uid": _uid(),
        "attrs": {},
        "children": [_li_node(item, text_color=text_color) for item in items],
    }


def _li_node(item, text_color: Optional[str] = None) -> dict:
    """item is either a plain string or a list of run dicts (for inline bold)."""
    runs = item if isinstance(item, list) else [{"text": str(item)}]
    children = _runs_to_children(runs, default_color=text_color)
    return {
        "type": "li",
        "uid": _uid(),
        "attrs": {},
        "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": children}],
    }


def img_node(asset_uid: str = "", alt: str = "", source_path: str = "", url: str = "") -> dict:
    attrs: dict = {"alt": alt or ""}
    if asset_uid:
        attrs["asset-uid"] = asset_uid
        attrs["asset-type"] = "image"
    elif url:
        attrs["src"] = url
        attrs["data-source-url"] = url
    elif source_path:
        attrs["data-source-path"] = source_path
        attrs["data-needs-upload"] = "true"
    return {"type": "img", "uid": _uid(), "attrs": attrs, "children": [{"text": ""}]}


def video_node(asset_uid: str = "", source_path: str = "", url: str = "") -> dict:
    """Embedded video node — same 'img' node shape Contentstack uses for any embedded
    asset, with asset-type: "video" instead of "image". UNCONFIRMED against a real
    Contentstack upload (no video has been uploaded through this pipeline yet) — verify
    this shape renders correctly the first time a video asset_uid is used for real, the
    same way every other unconfirmed shape in this pipeline gets verified before trust.
    """
    attrs: dict = {}
    if asset_uid:
        attrs["asset-uid"] = asset_uid
        attrs["asset-type"] = "video"
    elif url:
        attrs["src"] = url
        attrs["data-source-url"] = url
    elif source_path:
        attrs["data-source-path"] = source_path
        attrs["data-needs-upload"] = "true"
    return {"type": "img", "uid": _uid(), "attrs": attrs, "children": [{"text": ""}]}


def table_node(rows: list, headers: Optional[list] = None) -> dict:
    """
    Table with thead/tbody structure. Header cells: white text, bold. Hand-built — see
    module docstring ("font-color" and the mark+color drop bug both apply to headers).
    colWidths: 250px per column (matches approved entry — also the serializer's own
    default equal-split for a column count with no explicit widths, confirmed by testing
    the installed package directly, so this stays consistent even if headers ever move
    through it in the future).
    """
    ncols = len(headers) if headers else (len(rows[0]) if rows else 0)
    nrows = len(rows) + (1 if headers else 0)

    thead_rows = []
    if headers:
        th_nodes = []
        for h in headers:
            header_run: dict = {
                "text": str(h),
                "attrs": {"style": {"color": TABLE_HEADER_TEXT}},
                "bold": True,
                "font-color": "#000000",
            }
            space_run: dict = {
                "text": " ",
                "attrs": {"style": {"color": TABLE_HEADER_TEXT}},
                "font-color": "#000000",
            }
            th_nodes.append({
                "type": "th",
                "uid": _uid(),
                "attrs": {},
                "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": [header_run, space_run]}],
            })
        thead_rows.append({"type": "tr", "uid": _uid(), "attrs": {}, "children": th_nodes})

    tbody_rows = []
    for row in rows:
        td_nodes = []
        for cell in row:
            cell_run: dict = {
                "text": str(cell) if cell else "",
                "attrs": {"style": {"color": TABLE_CELL_TEXT}},
            }
            td_nodes.append({
                "type": "td",
                "uid": _uid(),
                "attrs": {},
                "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": [cell_run]}],
            })
        tbody_rows.append({"type": "tr", "uid": _uid(), "attrs": {}, "children": td_nodes})

    children = []
    if thead_rows:
        children.append({"type": "thead", "uid": _uid(), "attrs": {}, "children": thead_rows})
    if tbody_rows:
        children.append({"type": "tbody", "uid": _uid(), "attrs": {}, "children": tbody_rows})

    return {
        "type": "table",
        "uid": _uid(),
        "attrs": {"rows": nrows, "cols": ncols, "colWidths": [250] * ncols},
        "children": children,
    }


def blockquote_node(label: str = "", text: str = "") -> dict:
    """Blockquote node for pull-quotes and callout emphasis.

    Label (bold stat or key term): medium blue (BLUE_LABEL).
    Body text: navy blue (NAVY_BLUE).
    """
    runs: list = []
    if label:
        runs.append({"text": label, "bold": True, "color": BLUE_LABEL})
        if text:
            runs.append({"text": " " + text, "color": NAVY_BLUE})
    elif text:
        runs.append({"text": text, "color": NAVY_BLUE})

    children_in_p = _runs_to_children(runs) if runs else [{"text": ""}]
    return {
        "type": "blockquote",
        "uid": _uid(),
        "attrs": {},
        "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": children_in_p}],
    }


def callout_node(label: str = "", text: str = "") -> list:
    """Callout rendered as a blockquote for visual pull-quote emphasis."""
    return [blockquote_node(label=label, text=text)]


def _block_to_node(block: dict) -> Optional[dict]:
    btype = block.get("type", "")
    if btype == "paragraph":
        runs = block.get("runs")
        text = block.get("text", "")
        if runs:
            return p_node(runs=runs, color=BODY_TEXT)
        return p_node(text=text, color=BODY_TEXT)
    elif btype == "heading":
        level = block.get("level", 2)
        text = block.get("text", "")
        if level <= 2:
            return heading_node(text, level, color=HEADING_BLACK)
        return heading_node(text, level, color=HEADING_ORANGE, bold=True, font_color="#fa660f")
    elif btype == "list":
        items = block.get("items", [])
        style = block.get("style", "bullet")
        if style == "numbered":
            return ol_node(items, text_color=BODY_TEXT)
        return ul_node(items, text_color=BODY_TEXT)
    elif btype == "table":
        return table_node(block.get("rows", []), block.get("headers"))
    elif btype == "image":
        asset_uid = block.get("assetUid", "")
        if asset_uid:
            return img_node(
                asset_uid=asset_uid,
                alt=block.get("altText", ""),
                source_path=block.get("sourcePath", ""),
                url=block.get("url", ""),
            )
        label = block.get("sourcePath") or block.get("altText") or "embedded image"
        return callout_node(
            label="[IMAGE PLACEHOLDER]",
            text=f"Upload asset to Contentstack and replace this placeholder — source: {label}",
        )
    elif btype == "video":
        return p_node(text=f"[Video: {block.get('url', '')}]", color=BODY_TEXT)
    elif btype == "callout":
        return callout_node(label=block.get("label", ""), text=block.get("text", ""))
    return None
