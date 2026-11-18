"""Preserve Markdown code blocks while the document tree is being built.

Code is opaque content: headings, separators, links and datapoints inside it are
characters, not md2ui structure.  This module swaps fenced and genuine indented
blocks for inert sentinels before grouping, then expands those sentinels into
``CODE_BLOCK`` leaves before the final annotation phases begin.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType


class CodeBlockSpec(NamedTuple):
    content: str
    language: str | None
    raw: str


_SENTINEL_FMT = "⟦md2ui-code-{}⟧"
_SENTINEL_RE = re.compile(r"⟦md2ui-code-(\d+)⟧")
_SENTINEL_MARK = "⟦md2ui-code-"
_FENCE_OPEN_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?:(?P<marker>[-+*]|\d+[.)])(?P<marker_space>[ \t]+))?"
    r"(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)\r?\n?$"
)
_INDENTED_CODE_RE = re.compile(
    r"(?P<lead>\A|\n[ \t]*\n)"
    r"(?P<code>(?:(?: {4}|\t)(?=[^\r\n]*\S)[^\r\n]*\r?\n?)+)"
)
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_HTML_COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)


def _language(info: str) -> str | None:
    """Return the deterministic lexer alias from a fence info string."""
    value = info.strip().split(maxsplit=1)[0] if info.strip() else ""
    if value.startswith("{.") and value.endswith("}"):
        value = value[2:-1]
    return value.lower() or None


def _dedent_fence_line(line: str, width: int) -> str:
    """Remove at most the opening fence's continuation width from a body line."""
    count = 0
    while count < width and count < len(line) and line[count] in (" ", "\t"):
        count += 1
    return line[count:]


def _extract_fences(text: str, specs: dict[int, CodeBlockSpec]) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    in_comment = False
    while i < len(lines):
        if in_comment:
            out.append(lines[i])
            in_comment = "-->" not in lines[i]
            i += 1
            continue
        if "<!--" in lines[i] and "-->" not in lines[i].split("<!--", 1)[1]:
            out.append(lines[i])
            in_comment = True
            i += 1
            continue
        opened = _FENCE_OPEN_RE.match(lines[i])
        if opened is None:
            out.append(lines[i])
            i += 1
            continue
        fence = opened.group("fence")
        closing = re.compile(
            rf"^[ \t]*{re.escape(fence[0])}{{{len(fence)},}}[ \t]*\r?\n?$"
        )
        end = i + 1
        while end < len(lines) and closing.match(lines[end]) is None:
            end += 1
        if end == len(lines):
            # An unclosed fence remains ordinary source rather than swallowing
            # the rest of the document into a partially supported construct.
            out.append(lines[i])
            i += 1
            continue
        raw = "".join(lines[i : end + 1])
        prefix = opened.group("indent")
        if opened.group("marker") is not None:
            prefix += opened.group("marker") + opened.group("marker_space")
        body = "".join(
            _dedent_fence_line(line, len(prefix)) for line in lines[i + 1 : end]
        )
        cid = len(specs)
        specs[cid] = CodeBlockSpec(body, _language(opened.group("info")), raw)
        newline = "\n" if raw.endswith(("\n", "\r")) else ""
        out.append(f"{prefix}{_SENTINEL_FMT.format(cid)}{newline}")
        i = end + 1
    return "".join(out)


def _indented_sub(
    match: re.Match[str],
    specs: dict[int, CodeBlockSpec],
    comment_spans: list[tuple[int, int]],
) -> str:
    """Extract a genuine indented block, preserving list-item continuations."""
    if any(start < match.end() and match.start() < end for start, end in comment_spans):
        return match.group(0)
    for line in reversed(match.string[: match.start()].split("\n")):
        if not line.strip() or line[:1] in (" ", "\t"):
            continue
        if _LIST_MARKER_RE.match(line):
            return match.group(0)
        break
    raw_code = match.group("code")
    content = "".join(
        line[1:] if line.startswith("\t") else line[4:]
        for line in raw_code.splitlines(keepends=True)
    )
    cid = len(specs)
    specs[cid] = CodeBlockSpec(content, None, raw_code)
    return match.group("lead") + _SENTINEL_FMT.format(cid) + "\n"


def extract_code_blocks(text: str) -> tuple[str, dict[int, CodeBlockSpec]]:
    """Replace supported code blocks with inert sentinels and return their specs."""
    specs: dict[int, CodeBlockSpec] = {}
    text = _extract_fences(text, specs)
    comment_spans = [match.span() for match in _HTML_COMMENT_RE.finditer(text)]
    text = _INDENTED_CODE_RE.sub(
        lambda match: _indented_sub(match, specs, comment_spans), text
    )
    return text, specs


def _expand_in(
    node: MarkdownGroupNode, specs: dict[int, CodeBlockSpec], ids: IdMint
) -> None:
    whole = _SENTINEL_RE.fullmatch(node.content.strip())
    if whole is not None:
        spec = specs.get(int(whole.group(1)))
        if spec is not None:
            if node.type in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM):
                code = MarkdownGroupNode(
                    type=NodeType.CODE_BLOCK,
                    content=spec.content,
                )
                code.code_language = spec.language
                _inherit_glue(node, [code], ids)
                node.content = ""
                node.children.insert(0, code)
                return
            node.type = NodeType.CODE_BLOCK
            node.content = spec.content
            node.code_language = spec.language
        return
    pieces = _SENTINEL_RE.split(node.content)
    if len(pieces) == 1:
        return
    children: list[MarkdownGroupNode] = []
    for index, piece in enumerate(pieces):
        if index % 2 == 0:
            if piece.strip():
                children.append(
                    MarkdownGroupNode(type=NodeType.TEXT, content=piece.strip())
                )
            continue
        spec = specs.get(int(piece))
        if spec is None:
            children.append(MarkdownGroupNode(type=NodeType.TEXT, content=piece))
            continue
        code = MarkdownGroupNode(type=NodeType.CODE_BLOCK, content=spec.content)
        code.code_language = spec.language
        children.append(code)
    _inherit_glue(node, children, ids)
    if node.type == NodeType.TEXT:
        node.type = NodeType.GROUP
    node.content = ""
    node.children = children + node.children


def expand_code_blocks(
    node: MarkdownGroupNode, specs: dict[int, CodeBlockSpec], ids: IdMint
) -> None:
    """Expand every sentinel under *node* into an opaque code-block leaf."""
    for child in list(node.children):
        expand_code_blocks(child, specs, ids)
    if node.content and _SENTINEL_MARK in node.content:
        _expand_in(node, specs, ids)


def restore_code_blocks(
    node: MarkdownGroupNode, specs: dict[int, CodeBlockSpec]
) -> None:
    """Restore raw Markdown if a sentinel unexpectedly survives expansion."""
    if node.content and _SENTINEL_MARK in node.content:
        node.content = _SENTINEL_RE.sub(
            lambda m: specs.get(
                int(m.group(1)), CodeBlockSpec(m.group(0), None, m.group(0))
            ).raw,
            node.content,
        )
    for child in node.children:
        restore_code_blocks(child, specs)
