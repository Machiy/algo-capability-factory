"""知识图谱可视化：PyVis 生成可直接打开的 ``outputs/kg/kg.html``。

PyVis 为可选依赖；未安装时只记录警告并返回 ``None``，不阻断抽取主流程。
"""

from __future__ import annotations

import logging
from pathlib import Path

from factory.contracts.knowledge import KnowledgeGraph, NodeType

logger = logging.getLogger(__name__)

COLOR_BY_TYPE: dict[NodeType, str] = {
    NodeType.CAPABILITY: "#2E86AB",
    NodeType.OPERATOR: "#A23B72",
    NodeType.ALGORITHM: "#F18F01",
    NodeType.METRIC: "#3B8C3B",
    NodeType.DATASET: "#C73E1D",
    NodeType.ENVIRONMENT: "#6C757D",
    NodeType.VALIDATION_RUN: "#6A4C93",
    NodeType.FAILURE_CASE: "#D7263D",
    # 教训是真正的沉淀产物，用最醒目的颜色与运行日志区分
    NodeType.LESSON: "#F4A259",
    NodeType.EVIDENCE: "#8D99AE",
}


def render_html(graph: KnowledgeGraph, path: Path) -> Path | None:
    """渲染交互式图谱；返回生成路径，PyVis 不可用时返回 ``None``。"""
    try:
        from pyvis.network import Network
    except ImportError:
        logger.warning("pyvis 未安装，跳过 KG 可视化")
        return None

    # in_line 把 JS/CSS 内联进单个 HTML，断网可直接打开，且不会在仓库
    # 根目录生成 pyvis 的 lib/ 资源目录。
    network = Network(height="760px", width="100%", directed=True,
                      cdn_resources="in_line")
    for node in graph.nodes:
        network.add_node(
            node.node_id,
            label=node.name[:36],
            title=f"{node.node_type.value} · {node.name}",
            color=COLOR_BY_TYPE[node.node_type],
            group=node.node_type.value,
        )
    for edge in graph.edges:
        network.add_edge(edge.source, edge.target, label=edge.edge_type.value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(network, "write_html"):
        network.write_html(str(path))
    else:
        network.save_graph(str(path))
    logger.info("图谱可视化已写入 %s", path)
    return path


__all__ = ["render_html"]
