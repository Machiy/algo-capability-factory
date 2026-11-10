"""能力版本谱系：按能力列出 v1→vN 链、查看单个版本、对比两版差异。

Curator 只在出现新错误签名时生成 ``cap.xxx.vN`` 节点并连 ``DERIVED_FROM``
（见 ``factory/agents/roles.py``）。本模块补上「读」的一侧，让版本管理不只是
写进图谱：可以回答「这个能力有哪些版本」「v2 因哪些失败签名升版」「v1/v2
差在哪」。回滚仍不做——切换证据源会改变已验证的选型行为，留作后续方向。
"""

from __future__ import annotations

import re

from factory.contracts.knowledge import KGNode, KnowledgeGraph, NodeType

_VERSION_SUFFIX = re.compile(r"\.v(\d+)$")


def base_capability_id(node_id: str) -> str:
    """``cap.data_dictionary.T1.v2`` → ``cap.data_dictionary.T1``。"""
    return _VERSION_SUFFIX.sub("", node_id)


def version_number(node_id: str) -> int:
    """版本节点的序号；基础节点视为 v1。"""
    match = _VERSION_SUFFIX.search(node_id)
    return int(match.group(1)) if match else 1


def is_version_node(node: KGNode) -> bool:
    return bool(_VERSION_SUFFIX.search(node.node_id))


def list_versions(graph: KnowledgeGraph) -> dict[str, list[KGNode]]:
    """返回「有版本演进」的能力 → 按版本号升序排列的节点链。"""
    groups: dict[str, list[KGNode]] = {}
    for node in graph.by_type(NodeType.CAPABILITY):
        groups.setdefault(base_capability_id(node.node_id), []).append(node)
    return {
        base: sorted(nodes, key=lambda item: version_number(item.node_id))
        for base, nodes in sorted(groups.items())
        if any(is_version_node(node) for node in nodes)
    }


def show_version(graph: KnowledgeGraph, capability_id: str,
                 version: str = "") -> list[KGNode]:
    """取某个能力的全部版本，或指定 ``vN`` 的单个版本。"""
    nodes = list_versions(graph).get(capability_id, [])
    if not version:
        return nodes
    target = version if version.startswith("v") else f"v{version}"
    return [node for node in nodes
            if f"v{version_number(node.node_id)}" == target or node.node_id == version]


def version_diff(graph: KnowledgeGraph, capability_id: str,
                 from_version: str, to_version: str) -> dict[str, dict]:
    """对比两个版本的属性：逐键给出旧值 / 新值，另列修复签名与教训来源。"""
    nodes = {f"v{version_number(node.node_id)}": node
             for node in list_versions(graph).get(capability_id, [])}
    old = nodes.get(from_version if from_version.startswith("v") else f"v{from_version}")
    new = nodes.get(to_version if to_version.startswith("v") else f"v{to_version}")
    if old is None or new is None:
        raise KeyError(f"版本不存在：{capability_id} {from_version} → {to_version}")
    keys = sorted(set(old.attributes) | set(new.attributes))
    return {
        key: {"from": old.attributes.get(key), "to": new.attributes.get(key)}
        for key in keys
        if old.attributes.get(key) != new.attributes.get(key)
    }


__all__ = [
    "base_capability_id",
    "is_version_node",
    "list_versions",
    "show_version",
    "version_diff",
    "version_number",
]
