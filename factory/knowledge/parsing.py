"""源材料的语法层解析：章节、Markdown 表格、pipeline 顺序。

本模块只做切分，不含任何业务映射；业务映射见 ``extractor.py``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
_SEPARATOR_RE = re.compile(r"^[\s\-:|]+$")
_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


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


def parse_sections(text: str) -> list[Section]:
    """按 ``##`` 标题切分，标题之前的引言归入 ``引言``。"""
    lines = text.splitlines()
    sections: list[Section] = []
    current_title = "引言"
    current_lines: list[str] = []
    current_start = 1

    for offset, line in enumerate(lines, start=1):
        match = _SECTION_RE.match(line)
        if match:
            sections.append(Section(current_title, "\n".join(current_lines), current_start))
            current_title = match.group(1).strip()
            current_lines = []
            current_start = offset
        else:
            current_lines.append(line)
    sections.append(Section(current_title, "\n".join(current_lines), current_start))
    return sections


def _split_row(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    stripped = stripped.removeprefix("|")
    stripped = stripped.removesuffix("|")
    return tuple(cell.strip() for cell in stripped.split("|"))


def parse_tables(body: str) -> list[Table]:
    """解析连续的 ``|`` 行块，自动跳过 ``|---|`` 分隔行。"""
    tables: list[Table] = []
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        rows = [_split_row(line) for line in block]
        headers = rows[0]
        data = [
            TableRow(raw=line, cells=cells)
            for line, cells in zip(block[1:], rows[1:])
            if not _SEPARATOR_RE.match(line.strip()) and cells
        ]
        if data:
            tables.append(Table(headers=headers, rows=data))
        block.clear()

    for line in body.splitlines():
        if line.strip().startswith("|"):
            block.append(line)
        else:
            flush()
    flush()
    return tables


def parse_pipeline_order(text: str) -> list[str]:
    """从代码块的 ``A → B → C`` 行提取算子顺序，忽略含 ``↑`` 的注释行。"""
    order: list[str] = []
    for block in _CODE_BLOCK_RE.findall(text):
        for line in block.splitlines():
            if "→" not in line or "↑" in line:
                continue
            order.extend(part.strip() for part in line.split("→") if part.strip())
    return order


__all__ = ["Section", "Table", "TableRow", "parse_pipeline_order", "parse_sections", "parse_tables"]
