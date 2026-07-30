"""
rte_builder.py — Build Contentstack JSON RTE node structures from normalized blocks.

Each node has: type, uid (UUID v4), attrs, children.
Imported by map_to_contentstack.py — not called directly.

Contentstack JSON RTE spec:
  https://www.contentstack.com/docs/developers/json-rich-text-editor/
"""

import uuid
from typing import Optional


def _uid() -> str:
    return uuid.uuid4().hex  # 32 hex chars, no hyphens — matches CS internal format


def p_node(runs: Optional[list] = None, text: Optional[str] = None) -> dict:
    """Paragraph node. Accepts either a runs list or a plain text string."""
    if runs:
        children = _runs_to_children(runs)
    elif text is not None:
        children = [{"text": text}]
    else:
        children = [{"text": ""}]
    return {"type": "p", "uid": _uid(), "attrs": {}, "children": children}


def heading_node(text: str, level: int = 2) -> dict:
    tag = f"h{max(1, min(6, level))}"
    return {"type": tag, "uid": _uid(), "attrs": {}, "children": [{"text": text}]}


def ul_node(items: list) -> dict:
    return {
        "type": "ul",
        "uid": _uid(),
        "attrs": {},
        "children": [_li_node(item) for item in items],
    }


def ol_node(items: list) -> dict:
    return {
        "type": "ol",
        "uid": _uid(),
        "attrs": {},
        "children": [_li_node(item) for item in items],
    }


def _li_node(text: str) -> dict:
    return {
        "type": "li",
        "uid": _uid(),
        "attrs": {},
        "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": text}]}],
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


def _proportional_col_widths(headers: Optional[list], rows: list, total: int = 200) -> list:
    """Compute column widths proportional to average content length, minimum 40 per column."""
    ncols = len(headers) if headers else (len(rows[0]) if rows else 0)
    if ncols == 0:
        return []
    all_rows = ([headers] if headers else []) + rows
    col_avg_lens = []
    for c in range(ncols):
        texts = [str(row[c]) if c < len(row) and row[c] else "" for row in all_rows]
        avg = sum(len(t) for t in texts) / len(texts) if texts else 10
        col_avg_lens.append(max(avg, 5))
    total_len = sum(col_avg_lens)
    widths = [max(round(total * l / total_len), 40) for l in col_avg_lens]
    # Fix rounding drift so widths always sum to total
    diff = total - sum(widths)
    widths[-1] = max(widths[-1] + diff, 40)
    return widths


def table_node(rows: list, headers: Optional[list] = None) -> dict:
    ncols = len(headers) if headers else (len(rows[0]) if rows else 0)
    nrows = len(rows) + (1 if headers else 0)
    tr_nodes = []
    if headers:
        th_nodes = [
            {
                "type": "th",
                "uid": _uid(),
                "attrs": {"colspan": 1, "rowspan": 1},
                "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": h, "bold": True}]}],
            }
            for h in headers
        ]
        tr_nodes.append({"type": "tr", "uid": _uid(), "attrs": {}, "children": th_nodes})
    for row in rows:
        td_nodes = [
            {
                "type": "td",
                "uid": _uid(),
                "attrs": {"colspan": 1, "rowspan": 1},
                "children": [{"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": str(cell) if cell else ""}]}],
            }
            for cell in row
        ]
        tr_nodes.append({"type": "tr", "uid": _uid(), "attrs": {}, "children": td_nodes})
    return {
        "type": "table",
        "uid": _uid(),
        "attrs": {"rows": nrows, "cols": ncols, "colWidths": _proportional_col_widths(headers, rows)},
        "children": tr_nodes,
    }


def blockquote_node(text: str) -> dict:
    """Two-tone blue blockquote — matches the whitepaper pipeline quote format.

    Renders as a real ``blockquote`` node wrapping a single ``p``. If the text
    carries an em/en/double-hyphen dash attribution ("...quote..." — Name, Title),
    the quote body renders navy (``rgb(0, 61, 91)``) and the attribution renders
    bold medium-blue (``rgb(26, 78, 159)``). A plain pull-quote with no attribution
    is a single navy run. See whitepaper docs/formatting_guide.md §5.8.
    """
    NAVY = {"style": {"color": "rgb(0, 61, 91)"}}
    BLUE = {"style": {"color": "rgb(26, 78, 159)"}}

    quote, attribution = text, ""
    for sep in (" — ", " – ", " -- "):
        if sep in text:
            quote, attribution = text.rsplit(sep, 1)
            quote = quote.rstrip()
            attribution = attribution.strip()
            break

    children = [{"text": quote, "attrs": NAVY}]
    if attribution:
        children.append({"text": f" — {attribution}", "bold": True, "attrs": BLUE})

    return {
        "type": "blockquote",
        "uid": _uid(),
        "attrs": {},
        "children": [
            {"type": "p", "uid": _uid(), "attrs": {}, "children": children}
        ],
    }


def callout_node(label: str = "", text: str = "") -> list:
    """Return a list of plain paragraph nodes (avoids the CS blockquote/orange-line rendering)."""
    nodes = []
    if label:
        nodes.append({"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": label, "bold": True}]})
    if text:
        nodes.append({"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": text}]})
    return nodes if nodes else [{"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": ""}]}]


def _runs_to_children(runs: list) -> list:
    """Convert normalized run dicts to RTE inline child nodes."""
    children = []
    for run in runs:
        run_text = run.get("text", "")
        if not run_text:
            continue
        url = run.get("url")
        if url:
            link_child: dict = {"text": run_text}
            if run.get("bold"):
                link_child["bold"] = True
            if run.get("italic"):
                link_child["italic"] = True
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
            children.append(node)
    return children or [{"text": ""}]


def build_body(sections: list) -> list:
    """Convert normalized body sections array to a flat list of JSON RTE nodes."""
    nodes = []
    for section in sections:
        heading = section.get("heading", "")
        level = section.get("level", 2)
        if heading:
            nodes.append(heading_node(heading, level))
        subheading = section.get("subheading", "")
        if subheading:
            nodes.append(heading_node(subheading, level + 1))
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
            return p_node(runs=runs)
        return p_node(text=text)
    elif btype == "heading":
        return heading_node(block.get("text", ""), block.get("level", 2))
    elif btype == "list":
        items = block.get("items", [])
        style = block.get("style", "bullet")
        if style == "numbered":
            return ol_node(items)
        return ul_node(items)
    elif btype == "table":
        rows = block.get("rows", [])
        headers = block.get("headers")
        return table_node(rows, headers)
    elif btype == "image":
        asset_uid = block.get("assetUid", "")
        if asset_uid:
            return img_node(
                asset_uid=asset_uid,
                alt=block.get("altText", ""),
                source_path=block.get("sourcePath", ""),
                url=block.get("url", ""),
            )
        # No UID yet — render as placeholder paragraphs so the upload succeeds.
        label = block.get("sourcePath") or block.get("altText") or "embedded image"
        return callout_node(label="[IMAGE PLACEHOLDER]", text=f"Upload asset to Contentstack and replace this placeholder — source: {label}")
    elif btype == "video":
        return p_node(text=f"[Video: {block.get('url', '')}]")
    elif btype == "blockquote":
        return blockquote_node(text=block.get("text", ""))
    elif btype == "callout":
        return callout_node(label=block.get("label", ""), text=block.get("text", ""))
    return None


