"""P1 编排：源材料 → 抽取 → 引用校验 → 落盘 → 可视化。

本模块只编排契约对象；具体解析、持久化、渲染分别由同层子模块负责。
"""

from __future__ import annotations

import logging
from pathlib import Path

from factory.config import Settings
from factory.contracts.knowledge import KnowledgeGraph
from factory.knowledge.extractor import MockExtractor, read_sources
from factory.knowledge.graph import KnowledgeGraphStore
from factory.knowledge.visualize import render_html

logger = logging.getLogger(__name__)


def build_knowledge_graph(settings: Settings, root: Path) -> KnowledgeGraph:
    """构建知识图谱并产出全部交付物，返回图谱契约供检索器消费。"""
    sources = read_sources(root, settings.paths.docs, settings.paths.legacy)
    graph = MockExtractor().extract(sources)
    store = KnowledgeGraphStore(graph)
    exported = store.export_all(settings, root)
    render_html(graph, root / settings.paths.kg / "kg.html")
    for name, path in exported.items():
        logger.info("产物 %s -> %s", name, path.relative_to(root))
    return graph


__all__ = ["build_knowledge_graph"]
