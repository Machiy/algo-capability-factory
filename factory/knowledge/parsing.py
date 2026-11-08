"""源材料的语法层解析：用 ``markdown-it-py`` 识别章节、表格与代码块。

现成解析器负责 Markdown 结构切分；本模块只保留「原文行 → 证据摘录」的
薄适配，不含任何业务映射（业务映射见 ``extractor.py``）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt

_MD = MarkdownIt("commonmark").enable("table")
_SEPARATOR_RE = re.compile(r"^[\s\-:|]+$")


@dataclass(frozen=True)
class Section:
    """一个二级标题及其正文。"""

    title: str
    body: str
    start_line: int


@dataclass(frozen=True)
class TableRow:
    """一行表格；``raw`` 保留原文，用作证据摘录。"""

    raw: str
    cells: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    """一张 Markdown 表格。"""

    headers: tuple[str, ...] = field(default_factory=tuple)
    rows: list[TableRow] = field(default_factory=list)


def _split_row(line: str) -> tuple[str, ...]:
    stripped = line.strip().removeprefix("|").removesuffix("|")
    return tuple(cell.strip() for cell in stripped.split("|"))


def parse_sections(text: str) -> list[Section]:
    """按 ``##`` 标题切分，标题之前的引言归入「引言」。"""
    lines = text.splitlines()
    tokens = _MD.parse(text)
    headings: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h2" and token.map:
            title = tokens[index + 1].content if index + 1 < len(tokens) else ""
            headings.append((token.map[0], title))
    sections: list[Section] = []
    if headings:
        first_line = headings[0][0]
        sections.append(Section("引言", "\n".join(lines[:first_line]), 1))
    for index, (start, title) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        sections.append(Section(title, "\n".join(lines[start + 1:end]), start + 1))
    if not headings:
        sections.append(Section("引言", text, 1))
    return sections


def parse_tables(body: str) -> list[Table]:
    """解析 markdown-it 识别出的 table 块，保留原始行作为证据摘录。"""
    lines = body.splitlines()
    tables: list[Table] = []
    for token in _MD.parse(body):
        if token.type != "table_open" or not token.map:
            continue
        start, end = token.map
        block = lines[start:end]
        if not block:
            continue
        rows = [_split_row(line) for line in block]
        headers = rows[0]
        data = [
            TableRow(raw=line, cells=cells)
            for line, cells in zip(block[1:], rows[1:])
            if not _SEPARATOR_RE.match(line.strip()) and cells
        ]
        if data:
            tables.append(Table(headers=headers, rows=data))
    return tables


def parse_pipeline_order(text: str) -> list[str]:
    """从 fence / code_block 的 ``A → B → C`` 行提取算子顺序，忽略 ``↑`` 注释行。"""
    order: list[str] = []
    for token in _MD.parse(text):
        if token.type not in ("fence", "code_block"):
            continue
        for line in token.content.splitlines():
            if "→" not in line or "↑" in line:
                continue
            order.extend(part.strip() for part in line.split("→") if part.strip())
    return order


__all__ = ["Section", "Table", "TableRow", "parse_pipeline_order", "parse_sections", "parse_tables"]
