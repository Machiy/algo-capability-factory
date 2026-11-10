"""图谱合并：材料知识取最新抽取，运行沉淀按 id 叠加。

回写图谱如果整份替代材料抽取结果，会出现两种退化：

1. 材料改了（新增教训、修订约束）却永远进不了图谱，因为之后都从回写文件加载；
2. 每一轮的 ``run.*`` 日志越堆越多，沉淀产物看起来就是一本日志。

合并规则把两类节点分开处理：材料节点一律以本次抽取为准（源材料是唯一事实
来源），运行沉淀（失败案例、教训、能力版本）从旧图谱继承并按 ``node_id`` 去重。
"""

from __future__ import annotations

import logging
import re

from factory.contracts.knowledge import KGNode, KnowledgeGraph, NodeType

logger = logging.getLogger(__name__)

_VERSIONED = re.compile(r"\.v\d+$")


def is_measured_knowledge(node: KGNode) -> bool:
    """判断节点是否属于「运行沉淀」而非材料知识。

    - 失败案例与教训：只在运行中产生；
    - 能力版本（``cap.xxx.v2``）：带 ``run_id`` 或版本后缀；
    - 运行日志（``ValidationRun``）：明确排除，它是日志不是知识。
    """
    if node.node_type in (NodeType.FAILURE_CASE, NodeType.LESSON):
        return True
    if node.node_type is NodeType.VALIDATION_RUN:
        return False
    if node.attributes.get("run_id"):
        return True
    return bool(_VERSIONED.search(node.node_id))


def merge_graphs(measured: KnowledgeGraph, prior: KnowledgeGraph) -> KnowledgeGraph:
    """``measured``（本次材料抽取）为底，叠加 ``prior``（上次回写）中的运行沉淀。"""
    nodes = list(measured.nodes)
    seen = {node.node_id for node in nodes}
    inherited = 0
    for node in prior.nodes:
        if node.node_id in seen or not is_measured_knowledge(node):
            continue
        nodes.append(node)
        seen.add(node.node_id)
        inherited += 1
    edges = list(measured.edges)
    keys = {(edge.source, edge.target, edge.edge_type) for edge in edges}
    for edge in prior.edges:
        key = (edge.source, edge.target, edge.edge_type)
        if key in keys or edge.source not in seen or edge.target not in seen:
            continue
        edges.append(edge)
        keys.add(key)
    merged = KnowledgeGraph(
        nodes=nodes,
        edges=edges,
        source_files=sorted({*measured.source_files, *prior.source_files}),
    )
    merged.validate_references()
    logger.info("图谱合并：材料 %d 节点 + 沉淀继承 %d 节点 = %d 节点",
                len(measured.nodes), inherited, len(nodes))
    return merged


__all__ = ["is_measured_knowledge", "merge_graphs"]
