"""
rte_builder.py — Build Contentstack JSON RTE node structures from normalized blocks.

Colors and structure match the approved AI Token Cost and Accuracy Benchmark entry
(strategy.com), confirmed 2026-06-17. Each node has: type, uid (UUID hex), attrs, children.

Imported by map_to_contentstack.py — not called directly.
"""

import uuid
from typing import Optional

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
    Heading node (h1–h6).

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
    if isinstance(item, list):
        children = _runs_to_children(item, default_color=text_color)
    else:
        run: dict = {"text": str(item)}
        if text_color:
            run["attrs"] = {"style": {"color": text_color}}
        children = [run]
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


def table_node(rows: list, headers: Optional[list] = None) -> dict:
    """
    Table with thead/tbody structure. Header cells: white text, bold.
    colWidths: 250px per column (matches approved entry).
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
    children_in_p: list = []
    if label:
        children_in_p.append({"text": label, "bold": True, "attrs": {"style": {"color": BLUE_LABEL}}})
        if text:
            children_in_p.append({"text": " " + text, "attrs": {"style": {"color": NAVY_BLUE}}})
    elif text:
        children_in_p.append({"text": text, "attrs": {"style": {"color": NAVY_BLUE}}})
    else:
        children_in_p = [{"text": ""}]
    return {
        "type": "blockquote",
        "uid": _uid(),
        "attrs": {},
        "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": children_in_p}],
    }


def callout_node(label: str = "", text: str = "") -> list:
    """Callout rendered as a blockquote for visual pull-quote emphasis."""
    return [blockquote_node(label=label, text=text)]


def _runs_to_children(runs: list, default_color: Optional[str] = None) -> list:
    """Convert normalized run dicts to RTE inline child nodes."""
    children = []
    for run in runs:
        run_text = run.get("text", "")
        if not run_text:
            continue
        color = run.get("color") or default_color
        url = run.get("url")
        if url:
            link_child: dict = {"text": run_text}
            if run.get("bold"):
                link_child["bold"] = True
            if run.get("italic"):
                link_child["italic"] = True
            if color:
                link_child["attrs"] = {"style": {"color": color}}
            children.append({
                "type": "a",
                "uid": _uid(),
                "attrs": {"url": url, "target": "_blank"},
                "children": [link_child],
            })
        else:
            node: dict = {"text": run_text}
            if run.get("bold"):
                node["bold"] = True
            if run.get("italic"):
                node["italic"] = True
            if color:
                node["attrs"] = {"style": {"color": color}}
            children.append(node)
    return children or [{"text": ""}]


def build_body(sections: list) -> list:
    """Convert normalized body sections array to a flat list of RTE nodes (utility function)."""
    nodes = []
    for section in sections:
        heading = section.get("heading", "")
        level = section.get("level", 2)
        if heading:
            nodes.append(heading_node(heading, level, color=HEADING_BLACK))
        subheading = section.get("subheading", "")
        if subheading:
            nodes.append(heading_node(
                subheading, level + 1,
                color=HEADING_ORANGE, bold=True, font_color="#fa660f",
            ))
        for block in section.get("blocks", []):
            node = _block_to_node(block)
            if node is None:
                continue
            if isinstance(node, list):
                nodes.extend(node)
            else:
                nodes.append(node)
    return nodes


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
