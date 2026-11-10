"""P1 编排：源材料 → 抽取 → 引用校验 → 落盘 → 可视化。

本模块只编排契约对象；具体解析、持久化、渲染分别由同层子模块负责。
"""

from __future__ import annotations

import logging
from pathlib import Path

from factory.artifacts import kg_paths
from factory.config import Settings
from factory.contracts.knowledge import KnowledgeGraph
from factory.knowledge.extractor import MockExtractor, read_sources
from factory.knowledge.graph import KnowledgeGraphStore
from factory.knowledge.visualize import render_html

logger = logging.getLogger(__name__)


def build_knowledge_graph(settings: Settings, root: Path,
                          docs_dir: str | None = None,
                          legacy_dir: str | None = None,
                          scene: str = "credit",
                          dataset_profile: dict | None = None) -> KnowledgeGraph:
    """构建知识图谱并产出全部交付物，返回图谱契约供检索器消费。

    ``docs_dir`` / ``legacy_dir`` 覆盖全局路径，用于为不同场景构建独立子图；
    ``scene`` 决定产物前缀（``credit`` / ``text`` / ``repo``），命名规则见
    :mod:`factory.artifacts`，避免第二个场景覆盖主场景的 JSON / CSV / GraphML；
    ``dataset_profile`` 由 ``verify_*.yaml`` 派生的数据集画像，抽取器据此填
    Dataset 节点，不再把标签名与敏感列写死在代码里。

    共享材料（工程教训库）无论构建哪个子图都会读入：系统级知识不该按场景切分。
    """
    docs = docs_dir or settings.paths.docs
    legacy = settings.paths.legacy if legacy_dir is None else legacy_dir
    sources = read_sources(root, docs, legacy, settings.knowledge.shared_docs)
    graph = MockExtractor(dataset_profile).extract(sources)
    store = KnowledgeGraphStore(graph)
    paths = kg_paths(root / settings.paths.kg, scene)
    exported = {
        "json": store.export_json(paths["json"]),
        "csv": store.export_csv(paths["csv"]),
        "graphml": store.export_graphml(paths["graphml"]),
        "sqlite": store.persist_sqlite(paths["db"]),
    }
    render_html(graph, paths["html"])
    for name, path in exported.items():
        logger.info("产物 %s -> %s", name, path.relative_to(root))
    return graph


__all__ = ["build_knowledge_graph"]
