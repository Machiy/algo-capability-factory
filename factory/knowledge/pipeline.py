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


def build_knowledge_graph(settings: Settings, root: Path,
                          docs_dir: str | None = None,
                          legacy_dir: str | None = None,
                          prefix: str = "",
                          dataset_profile: dict | None = None) -> KnowledgeGraph:
    """构建知识图谱并产出全部交付物，返回图谱契约供检索器消费。

    ``docs_dir`` / ``legacy_dir`` 覆盖全局路径，用于为不同场景构建独立子图；
    ``prefix`` 给产物加前缀，避免第二个场景覆盖主场景的 JSON / CSV / GraphML；
    ``dataset_profile`` 由 ``verify_*.yaml`` 派生的数据集画像，抽取器据此填
    Dataset 节点，不再把标签名与敏感列写死在代码里。

    共享材料（工程教训库）无论构建哪个子图都会读入：系统级知识不该按场景切分。
    """
    docs = docs_dir or settings.paths.docs
    legacy = settings.paths.legacy if legacy_dir is None else legacy_dir
    sources = read_sources(root, docs, legacy, settings.knowledge.shared_docs)
    graph = MockExtractor(dataset_profile).extract(sources)
    store = KnowledgeGraphStore(graph)
    kg_dir = root / settings.paths.kg
    if prefix:
        exported: dict[str, Path] = {
            "json": store.export_json(kg_dir / f"{prefix}capabilities.json"),
            "csv": store.export_csv(kg_dir / f"{prefix}capabilities.csv"),
            "graphml": store.export_graphml(kg_dir / f"{prefix}graph.graphml"),
            "sqlite": store.persist_sqlite(kg_dir / f"{prefix}kg.db"),
        }
    else:
        exported = store.export_all(settings, root)
    render_html(graph, kg_dir / f"{prefix}kg.html")
    for name, path in exported.items():
        logger.info("产物 %s -> %s", name, path.relative_to(root))
    return graph


__all__ = ["build_knowledge_graph"]
