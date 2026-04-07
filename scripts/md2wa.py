#!/usr/bin/env python3
"""md2wa.py — Convert Markdown to WhatsApp formatting.

Based on conversion rules from https://github.com/drsound/markdown-to-whatsapp
Ported to Python using mistune for AST-based parsing.

Usage:
    python md2wa.py < input.md          # stdin → stdout
    python md2wa.py input.md            # file  → stdout
    python md2wa.py --clip              # clipboard → clipboard
    python md2wa.py input.md --clip     # file  → clipboard
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys

import mistune

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEADER_EMOJIS = {1: "📌", 2: "🟠", 3: "🟡", 4: "🟢", 5: "🔵", 6: "⚫️"}

WA_ESCAPE = {"*": "∗", "_": "＿", "~": "∼", "`": "ˋ"}

# ---------------------------------------------------------------------------
# Block-level rendering
# ---------------------------------------------------------------------------


def render_blocks(nodes: list[dict]) -> str:
    parts = []
    for node in nodes:
        rendered = render_block(node)
        if rendered is not None:
            parts.append(rendered)
    return "\n\n".join(parts)


def render_block(node: dict) -> str | None:
    t = node["type"]

    if t == "paragraph":
        return render_inline(node.get("children", []))

    if t == "heading":
        level = node.get("attrs", {}).get("level", 1)
        emoji = HEADER_EMOJIS.get(level, "⚫️")
        content = render_inline_for_header(node.get("children", []))
        return f"*{emoji} {content}*"

    if t == "block_code":
        code = node.get("raw", "")
        # Strip single trailing newline that mistune adds
        if code.endswith("\n"):
            code = code[:-1]
        return f"```{code}```"

    if t == "list":
        return render_list(node)

    if t == "block_quote":
        return render_blockquote(node)

    if t == "thematic_break":
        return "───────────────"

    if t == "table":
        return render_table(node)

    if t in ("blank_line", "newline"):
        return None

    if t in ("block_html", "html"):
        return node.get("raw", node.get("text", ""))

    # Fallback for unknown block types
    raw = node.get("raw", node.get("text"))
    return raw if raw else None


# ---------------------------------------------------------------------------
# Inline rendering
# ---------------------------------------------------------------------------


def render_inline(nodes: list[dict]) -> str:
    if not nodes:
        return ""

    parts: list[str] = []
    for i, node in enumerate(nodes):
        t = node["type"]
        children = node.get("children", [])

        prev_node = nodes[i - 1] if i > 0 else None
        next_node = nodes[i + 1] if i < len(nodes) - 1 else None
        partial = _is_partial_word(prev_node, next_node)

        if t == "strong":
            if partial:
                parts.append(render_plain(children))
            elif (
                len(children) == 1 and children[0]["type"] == "emphasis"
            ):
                inner = render_inline(children[0].get("children", []))
                parts.append(f"*_{inner}_*")
            else:
                parts.append(f"*{render_inline(children)}*")

        elif t == "emphasis":
            if partial:
                parts.append(render_plain(children))
            elif (
                len(children) == 1 and children[0]["type"] == "strong"
            ):
                inner = render_inline(children[0].get("children", []))
                parts.append(f"_*{inner}*_")
            else:
                parts.append(f"_{render_inline(children)}_")

        elif t == "strikethrough":
            if partial:
                parts.append(render_plain(children))
            else:
                parts.append(f"~{render_inline(children)}~")

        elif t == "codespan":
            parts.append(f"`{node.get('raw', '')}`")

        elif t == "link":
            text = render_inline(children)
            url = node.get("attrs", {}).get("url", "")
            parts.append(f"{text} ({url})")

        elif t == "image":
            alt = render_plain(children) if children else node.get("attrs", {}).get("alt", "")
            url = node.get("attrs", {}).get("url", "")
            parts.append(f"[{alt}: {url}]")

        elif t == "text":
            parts.append(_unescape(node.get("raw", "")))

        elif t == "softbreak":
            parts.append("\n")

        elif t == "linebreak":
            parts.append("\n")

        elif t == "escape":
            char = node.get("raw", "")
            parts.append(WA_ESCAPE.get(char, char))

        elif t in ("block_text",):
            # Wrapper node inside list items — recurse into children
            parts.append(render_inline(children))

        else:
            parts.append(node.get("raw", node.get("text", "")))

    return "".join(parts)


def render_inline_for_header(nodes: list[dict]) -> str:
    """Render inline for headers — bold stripped (header is already bold)."""
    if not nodes:
        return ""

    parts: list[str] = []
    for node in nodes:
        t = node["type"]
        children = node.get("children", [])

        if t == "strong":
            parts.append(render_inline_for_header(children))
        elif t == "emphasis":
            parts.append(f"_{render_inline_for_header(children)}_")
        elif t == "strikethrough":
            parts.append(f"~{render_inline_for_header(children)}~")
        elif t == "codespan":
            parts.append(f"`{node.get('raw', '')}`")
        elif t == "link":
            text = render_inline_for_header(children)
            url = node.get("attrs", {}).get("url", "")
            parts.append(f"{text} ({url})")
        elif t == "text":
            parts.append(_unescape(node.get("raw", "")))
        else:
            parts.append(node.get("raw", node.get("text", "")))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def render_list(node: dict, depth: int = 0) -> str:
    ordered = node.get("attrs", {}).get("ordered", False)
    start = node.get("attrs", {}).get("start", 1) or 1
    items = node.get("children", [])
    lines: list[str] = []

    for idx, item in enumerate(items):
        children = item.get("children", [])
        is_task = item["type"] == "task_list_item"

        # Determine prefix
        if ordered:
            prefix = f"{start + idx}."
        elif is_task:
            checked = item.get("attrs", {}).get("checked", False)
            prefix = "☑" if checked else "☐"
        else:
            if depth == 0:
                prefix = "*"
            else:
                prefix = "* " + "◦ " * depth
                prefix = prefix.rstrip()

        # Separate text content from nested lists
        text_parts: list[str] = []
        nested_lists: list[dict] = []
        for child in children:
            if child["type"] == "list":
                nested_lists.append(child)
            elif child["type"] in ("block_text", "paragraph"):
                rendered = render_inline(child.get("children", []))
                if rendered:
                    text_parts.append(rendered)
            else:
                rendered = render_block(child)
                if rendered:
                    text_parts.append(rendered)

        content = " ".join(text_parts).replace("\n", " ").strip()
        lines.append(f"{prefix} {content}")

        for nested in nested_lists:
            lines.append(render_list(nested, depth + 1))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------


def render_blockquote(node: dict) -> str:
    lines: list[str] = []
    for child in node.get("children", []):
        if child["type"] == "block_quote":
            nested = render_blockquote(child)
            lines.extend("> " + line for line in nested.split("\n"))
        else:
            content = render_block(child)
            if content:
                lines.extend("> " + line for line in content.split("\n"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tables — rendered as bulleted lists (WhatsApp-friendly)
# ---------------------------------------------------------------------------


def render_table(node: dict) -> str:
    headers: list[str] = []
    rows: list[list[str]] = []

    for child in node.get("children", []):
        if child["type"] == "table_head":
            for cell in child.get("children", []):
                headers.append(render_inline(cell.get("children", [])))
        elif child["type"] == "table_body":
            for row_node in child.get("children", []):
                cells = []
                for cell in row_node.get("children", []):
                    cells.append(render_inline(cell.get("children", [])))
                rows.append(cells)

    if not headers:
        return ""

    # Detect key-value tables (2 columns)
    if len(headers) == 2 and _is_kv_table(headers):
        return _render_kv_table(rows)

    lines: list[str] = []
    for row in rows:
        for i, cell in enumerate(row):
            header = headers[i] if i < len(headers) else f"Column {i + 1}"
            if i == 0:
                lines.append(f"* *{header}:* {cell}")
            else:
                lines.append(f"* ◦ _{header}:_ {cell}")

    return "\n".join(lines)


_KV_KEYWORDS = {
    "attribute", "value", "key", "parameter", "property", "field",
    "description", "setting", "option", "name", "detail", "spec",
    "specification", "metric", "measure", "item",
}


def _is_kv_table(headers: list[str]) -> bool:
    return all(
        any(kw in h.lower() for kw in _KV_KEYWORDS)
        for h in headers
    )


def _render_kv_table(rows: list[list[str]]) -> str:
    lines = []
    for row in rows:
        if len(row) >= 2:
            lines.append(f"* *{row[0]}:* {row[1]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plain-text rendering (no formatting markers)
# ---------------------------------------------------------------------------


def render_plain(nodes: list[dict]) -> str:
    if not nodes:
        return ""

    parts: list[str] = []
    for node in nodes:
        t = node["type"]
        children = node.get("children", [])

        if t in ("strong", "emphasis", "strikethrough"):
            parts.append(render_plain(children))
        elif t == "codespan":
            parts.append(node.get("raw", ""))
        elif t == "link":
            text = render_plain(children)
            url = node.get("attrs", {}).get("url", "")
            parts.append(f"{text} ({url})")
        elif t == "text":
            parts.append(_unescape(node.get("raw", "")))
        elif t == "block_text":
            parts.append(render_plain(children))
        else:
            parts.append(node.get("raw", node.get("text", "")))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_partial_word(prev: dict | None, nxt: dict | None) -> bool:
    """WhatsApp ignores formatting that's mid-word."""
    if prev and prev.get("type") == "text":
        raw = prev.get("raw", "")
        if raw and not re.search(r"\s$", raw):
            return True
    if nxt and nxt.get("type") == "text":
        raw = nxt.get("raw", "")
        if raw and not re.search(r"^\s", raw):
            return True
    return False


def _unescape(text: str) -> str:
    return html.unescape(text) if text else ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def convert(markdown_text: str) -> str:
    """Convert markdown string to WhatsApp-formatted string."""
    if not markdown_text.strip():
        return ""

    md = mistune.create_markdown(
        renderer="ast",
        plugins=["strikethrough", "table", "task_lists"],
    )
    ast = md(markdown_text)
    return render_blocks(ast).strip()


def main() -> None:
    # Ensure UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Convert Markdown to WhatsApp format"
    )
    parser.add_argument(
        "file", nargs="?", help="Markdown file (default: stdin, or clipboard with --clip)"
    )
    parser.add_argument(
        "--clip", action="store_true",
        help="Copy output to clipboard (reads from clipboard if no file/stdin)",
    )
    args = parser.parse_args()

    # Read input
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    elif args.clip:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-c", "Get-Clipboard -Raw"],
            capture_output=True, encoding="utf-8", check=True,
        )
        text = result.stdout
    else:
        parser.error("Provide a file, pipe stdin, or use --clip")
        return

    output = convert(text)

    if args.clip:
        # Write to temp file to avoid Windows encoding issues with emoji
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8", delete=False
        )
        try:
            tmp.write(output)
            tmp.close()
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-c",
                    f"Get-Content -Raw -Encoding UTF8 '{tmp.name}' | Set-Clipboard",
                ],
                check=True,
            )
            print(f"✅ Copied to clipboard ({len(output)} chars)")
        finally:
            os.unlink(tmp.name)
    else:
        print(output)


if __name__ == "__main__":
    main()
