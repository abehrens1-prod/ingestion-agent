"""
rte_builder.py — Build Contentstack JSON RTE node structures from normalized blocks.

Each node has: type, uid (UUID v4), attrs, children.
Imported by map_to_contentstack.py — not called directly.

Formatting nodes (paragraphs, headings, lists, tables, blockquotes — anything with
bold/italic/links/colors) are built by rendering a small HTML fragment and piping it
through the Node serializer in rte_serializer_node/ (Contentstack's own open-source
@contentstack/json-rte-serializer), so the exact node shapes always match what
Contentstack's own editor produces. Structural placeholder nodes (image-pending,
callout) stay hand-built here — they're plain paragraphs, not real RTE formatting.

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


def _uid() -> str:
    return uuid.uuid4().hex  # 32 hex chars, no hyphens — matches CS internal format


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


def _serialize_html(html_fragment: str) -> list:
    """Run one HTML element through the Node RTE serializer; return its doc children.

    One subprocess call per node (paragraph, heading, list, table, blockquote) — a
    typical post makes 20-50 of these, adding a handful of seconds to a pipeline
    that already takes minutes for Claude parsing. Simpler and more reliable than
    keeping a persistent Node process alive for a pipeline that only ever processes
    one blog post at a time.
    """
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


def _runs_to_html(runs: list) -> str:
    """Convert normalized run dicts (text/bold/italic/url) to inline HTML."""
    parts = []
    for run in runs:
        text = run.get("text", "")
        if not text:
            continue
        chunk = _esc(text)
        if run.get("bold"):
            chunk = f"<b>{chunk}</b>"
        if run.get("italic"):
            chunk = f"<i>{chunk}</i>"
        url = run.get("url")
        if url:
            chunk = f'<a href="{_esc(url)}" target="_blank">{chunk}</a>'
        parts.append(chunk)
    return "".join(parts)


def p_node(runs: Optional[list] = None, text: Optional[str] = None) -> dict:
    """Paragraph node. Accepts either a runs list or a plain text string."""
    if runs:
        inner = _runs_to_html(runs)
    elif text is not None:
        inner = _esc(text)
    else:
        inner = ""
    return _serialize_html(f"<p>{inner}</p>")[0]


def heading_node(text: str, level: int = 2) -> dict:
    tag = f"h{max(1, min(6, level))}"
    return _serialize_html(f"<{tag}>{_esc(text)}</{tag}>")[0]


def ul_node(items: list) -> dict:
    lis = "".join(f"<li>{_esc(str(item))}</li>" for item in items)
    return _serialize_html(f"<ul>{lis}</ul>")[0]


def ol_node(items: list) -> dict:
    lis = "".join(f"<li>{_esc(str(item))}</li>" for item in items)
    return _serialize_html(f"<ol>{lis}</ol>")[0]


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
    """Table node. Column widths are the serializer's own default (equal split) —
    the previous content-length-proportional heuristic was hand-rolled logic
    duplicating what Contentstack's own editor already computes; dropped in favor
    of letting the serializer own it, matching every other node type here."""
    thead = ""
    if headers:
        ths = "".join(f"<th><b>{_esc(str(h))}</b></th>" for h in headers)
        thead = f"<thead><tr>{ths}</tr></thead>"
    trs = "".join(
        "<tr>" + "".join(f"<td>{_esc(str(cell)) if cell else ''}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return _serialize_html(f"<table>{thead}<tbody>{trs}</tbody></table>")[0]


def blockquote_node(text: str) -> dict:
    """Two-tone blue blockquote — matches the whitepaper pipeline quote format.

    Renders as a real ``blockquote`` node wrapping a single ``p``. If the text
    carries an em/en/double-hyphen dash attribution ("...quote..." — Name, Title),
    the quote body renders navy (``rgb(0, 61, 91)``) and the attribution renders
    bold medium-blue (``rgb(26, 78, 159)``). A plain pull-quote with no attribution
    is a single navy run. See whitepaper docs/formatting_guide.md §5.8.

    The attribution's color is applied AFTER serializing, not in the HTML fed to the
    serializer: the installed @contentstack/json-rte-serializer (3.1.0) silently drops
    a text node's color style whenever it's combined with bold/italic in the source
    HTML — verified directly against the package (every nesting order tested: span-in-b,
    b-in-span, style on the <b> itself). Found 2026-08-27 because the real output for
    this post's blockquote had the attribution rendering bold but colorless. Only this
    function is affected — no other node type here combines a mark with a color.
    """
    NAVY = "rgb(0, 61, 91)"
    BLUE = "rgb(26, 78, 159)"

    quote, attribution = text, ""
    for sep in (" — ", " – ", " -- "):
        if sep in text:
            quote, attribution = text.rsplit(sep, 1)
            quote = quote.rstrip()
            attribution = attribution.strip()
            break

    inner = f'<span style="color: {NAVY}">{_esc(quote)}</span>'
    if attribution:
        inner += f'<b> — {_esc(attribution)}</b>'

    node = _serialize_html(f"<blockquote><p>{inner}</p></blockquote>")[0]
    if attribution:
        attribution_leaf = node["children"][0]["children"][-1]
        attribution_leaf.setdefault("attrs", {}).setdefault("style", {})["color"] = BLUE
    return node


def callout_node(label: str = "", text: str = "") -> list:
    """Return a list of plain paragraph nodes (avoids the CS blockquote/orange-line rendering).

    Structural placeholder, not article-body formatting — stays hand-built rather
    than round-tripping through the serializer for two inert plain-text paragraphs.
    """
    nodes = []
    if label:
        nodes.append({"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": label, "bold": True}]})
    if text:
        nodes.append({"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": text}]})
    return nodes if nodes else [{"type": "p", "uid": _uid(), "attrs": {}, "children": [{"text": ""}]}]


def _block_to_node(block: dict):
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
