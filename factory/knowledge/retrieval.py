"""混合检索器：BM25 相关性 + 历史指标 + 证据新鲜度 − 失败惩罚。

相关性打分直接调用 ``rank_bm25.BM25Okapi``，不再自研词元计数；权重来自
``configs/default.yaml``，排序带 node_id 作为次级键，保证同 query 多次调用
结果完全一致，满足「检索 Top-K 稳定可解释」的 M1 验收。
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import ClassVar

from rank_bm25 import BM25Okapi

from factory.contracts.knowledge import (
    EdgeType,
    Evidence,
    KGNode,
    KnowledgeGraph,
    NodeType,
    RetrievalHit,
    RetrievalResult,
)
from factory.knowledge.lessons import rank_lessons

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]+|[\u4e00-\u9fff]{2,}")
DEFAULT_WEIGHTS: dict[str, float] = {
    "constraint_match": 0.40,
    "historical_metric": 0.30,
    "evidence_freshness": 0.15,
    "failure_penalty": 0.15,
}


def _tokens(query: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(query)}


def _searchable_text(node: KGNode) -> str:
    parts = [node.name, node.node_type.value]
    parts.extend(str(value) for value in node.attributes.values())
    return " ".join(parts).lower()


def _bm25_scores(query_tokens: set[str], texts: list[str]) -> list[float]:
    """用现成 BM25 计算相关性，并归一化到 [0, 1] 以匹配配置权重口径。"""
    corpus = [_TOKEN_RE.findall(text) for text in texts]
    if not query_tokens or not any(corpus):
        return [0.0] * len(texts)
    raw = BM25Okapi(corpus).get_scores(sorted(query_tokens))
    peak = float(max(raw)) if len(raw) else 0.0
    if peak <= 0:
        return [0.0] * len(texts)
    return [min(1.0, max(0.0, float(score) / peak)) for score in raw]


def _historical_metric(node: KGNode, key: str) -> float:
    """只取配置指定的主指标列，避免把耗时 / 样本量当成绩效信号。

    材料里的实验记录同时带头指标、KS、成本损失与耗时（还有「编号」这类
    负数），若对所有数值取最大值，任何带数字的节点都会拿到同一个满分，
    该分项就退化成常数。这里只认 ``historical_metric_key`` 那一列。
    """
    metrics = node.attributes.get("metrics")
    if not isinstance(metrics, dict):
        return 0.0
    value = metrics.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0.0
    return min(1.0, max(0.0, float(value)))


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", text.lower())


def _failure_flag(node: KGNode) -> float:
    if node.node_type is NodeType.FAILURE_CASE:
        return 1.0
    return 1.0 if node.attributes.get("error_signature") else 0.0


def _is_runtime_log(node: KGNode) -> bool:
    """判断是否「本轮运行日志」。

    材料里的历史实验记录同样带 ``metrics``，但那是有价值的证据型知识（历史
    实测指标），必须继续参与检索；回写的运行节点带 ``run_id``，只是日志。
    """
    return (node.node_type is NodeType.VALIDATION_RUN
            and bool(node.attributes.get("run_id")))


class HybridRetriever:
    """检索能力子图，输出可直接注入 Planner / Coder prompt 的契约。"""

    def __init__(self, graph: KnowledgeGraph, top_k: int = 5,
                 weights: dict[str, float] | None = None,
                 lesson_limit: int = 5,
                 historical_metric_key: str = "验证集 AUC",
                 invalid_markers: list[str] | None = None,
                 family_aliases: dict[str, list[str]] | None = None) -> None:
        self.graph = graph
        self.top_k = top_k
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.lesson_limit = lesson_limit
        # 历史证据口径与「作废记录」标记都来自配置：换场景 / 换指标列名不改代码
        self.historical_metric_key = historical_metric_key
        self.invalid_markers = list(invalid_markers or [])
        self.family_aliases = dict(family_aliases or {})

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        limit = top_k if top_k is not None else self.top_k
        tokens = _tokens(query)
        # 证据原文只是节点的支撑材料；本轮运行日志只说明这次跑了什么，
        # 两者都不是知识，不占用 prompt 名额
        nodes = [node for node in self.graph.nodes
                 if node.node_type is not NodeType.EVIDENCE
                 and not _is_runtime_log(node)]
        relevance = _bm25_scores(tokens, [_searchable_text(node) for node in nodes])
        hits: list[RetrievalHit] = []
        for node, constraint in zip(nodes, relevance):
            reasons: dict[str, float] = {
                "constraint_match": constraint,
                "historical_metric": _historical_metric(node, self.historical_metric_key),
                "evidence_freshness": min(1.0, len(node.evidence) / 2),
                "failure_penalty": _failure_flag(node),
            }
            score = (
                self.weights["constraint_match"] * reasons["constraint_match"]
                + self.weights["historical_metric"] * reasons["historical_metric"]
                + self.weights["evidence_freshness"] * reasons["evidence_freshness"]
                - self.weights["failure_penalty"] * reasons["failure_penalty"]
            )
            evidence: list[Evidence] = list(node.evidence[:2])
            hits.append(RetrievalHit(node_id=node.node_id, name=node.name,
                                     score=round(score, 6), reasons=reasons,
                                     evidence=evidence))
        hits.sort(key=lambda hit: (-hit.score, hit.node_id))
        # 图邻域扩展：受限多跳 BFS（深度≤2）从 Top-K 种子召回 BM25 没直接
        # 命中的节点，并记录显式路径，弥补 BM25 只认词面的局限（如命中「阈值」
        # 节点后连带召回 EVALUATED_BY 的指标节点）。
        expansion = self._expand({hit.node_id for hit in hits[:limit]})
        node_by_id = {node.node_id: node for node in self.graph.nodes}
        hit_ids = {hit.node_id for hit in hits}
        for hit in hits:
            found = expansion.get(hit.node_id)
            if found:
                weight, paths = found
                hit.reasons["graph_neighbor"] = weight
                hit.score = round(hit.score + self._NEIGHBOR_BONUS * weight, 6)
                hit.paths = paths
        # 召回的新节点（不在原 BM25 命中里）作为低分命中追加；证据与运行日志
        # 仍被排除，不因图邻域召回而重新进入 prompt
        for node_id, (weight, paths) in expansion.items():
            if node_id in hit_ids:
                continue
            node = node_by_id.get(node_id)
            if node is None or node.node_type is NodeType.EVIDENCE or _is_runtime_log(node):
                continue
            hits.append(RetrievalHit(
                node_id=node_id, name=node.name,
                score=round(self._NEIGHBOR_BONUS * weight, 6),
                reasons={"graph_neighbor": weight},
                evidence=list(node.evidence[:2]), paths=paths,
            ))
        hits.sort(key=lambda hit: (-hit.score, hit.node_id))
        result = RetrievalResult(
            query=query,
            top_k=limit,
            hits=hits[:limit],
            constraints=self._constraints(limit),
            failure_warnings=self._failure_warnings(limit),
            lessons=self._lessons(self.lesson_limit),
            recommended_families=self._recommended_families(limit),
        )
        logger.info("检索 query=%r 命中 %d 项", query, len(result.hits))
        return result

    # 邻域加分的上限：相关性仍是主项，图结构只做同分段的排序微调
    _NEIGHBOR_BONUS: ClassVar[float] = 0.10

    # 不同关系对「相关」的贡献不同：证据节点不参与打分，故不计权重
    _EDGE_WEIGHTS: ClassVar[dict[EdgeType, float]] = {
        EdgeType.EVALUATED_BY: 1.0,
        EdgeType.USES: 1.0,
        EdgeType.REQUIRES: 0.8,
        EdgeType.DERIVED_FROM: 0.8,
        EdgeType.HAS_RUN: 0.8,
        EdgeType.RESULTED_IN: 0.8,
        EdgeType.FIXED_BY: 0.8,
        EdgeType.SIMILAR_TO: 0.6,
        EdgeType.PRECEDES: 0.6,
        EdgeType.TRANSFERABLE_TO: 0.6,
        EdgeType.APPLIES_TO: 0.4,
        EdgeType.DEPENDS_ON: 0.2,
        EdgeType.EVIDENCED_BY: 0.0,
    }

    # 多跳扩展的深度衰减：一跳满权重，二跳折半
    _DEPTH_DECAY: ClassVar[float] = 0.5

    def _expand(self, seeds: set[str],
                max_depth: int = 2) -> dict[str, tuple[float, list[str]]]:
        """受限多跳 BFS：从种子节点按边类型衰减召回可达节点并记录显式路径。

        返回 ``{node_id: (weight, paths)}``；``weight`` 是「路径边权连乘 × 深度
        衰减」的最大值，``paths`` 是对应的「源 --EDGE--> 目标」链。图结构加分因此
        可回溯到具体边，而非只有一个不可解释的数值；种子节点本身不返回。
        """
        adjacency: dict[str, list[tuple[str, EdgeType, float]]] = defaultdict(list)
        for edge in self.graph.edges:
            edge_weight = self._EDGE_WEIGHTS.get(edge.edge_type, 0.0)
            if edge_weight <= 0:
                continue
            adjacency[edge.source].append((edge.target, edge.edge_type, edge_weight))
            adjacency[edge.target].append((edge.source, edge.edge_type, edge_weight))

        result: dict[str, tuple[float, list[str]]] = {}
        frontier: dict[str, tuple[float, list[str]]] = {
            node_id: (1.0, []) for node_id in seeds
        }
        visited: set[str] = set(seeds)
        for depth in range(1, max_depth + 1):
            next_frontier: dict[str, tuple[float, list[str]]] = {}
            for current, (acc_weight, path) in frontier.items():
                for neighbor, edge_type, edge_weight in adjacency.get(current, []):
                    if neighbor in visited:
                        continue
                    weight = acc_weight * edge_weight * self._DEPTH_DECAY ** (depth - 1)
                    new_path = [*path, f"{current} --{edge_type.value}--> {neighbor}"]
                    if (neighbor not in next_frontier
                            or weight > next_frontier[neighbor][0]):
                        next_frontier[neighbor] = (weight, new_path)
            for node_id, (weight, path) in next_frontier.items():
                visited.add(node_id)
                result[node_id] = (weight, path)
            frontier = next_frontier
        return result

    def _constraints(self, limit: int) -> list[str]:
        """汇总适用条件，供 Planner 生成候选方案时遵守。"""
        items: list[str] = []
        for node in self.graph.nodes:
            if node.node_type is not NodeType.CAPABILITY:
                continue
            section = str(node.attributes.get("section", ""))
            if "适用条件" not in section and "约束" not in section:
                continue
            detail = node.attributes.get("说明") or node.attributes.get("约束")
            if detail:
                items.append(f"{node.name}：{detail}")
        return items[:limit]

    def _lessons(self, limit: int) -> list[str]:
        """系统级教训：跨运行成立的知识，全部注入 prompt 供生成代码遵守。

        与 ``failure_warnings`` 的区别：后者是「某次怎么失败的」，前者是
        「这类失败为什么发生、以后怎么不犯」，因此排序只按可信度与出现次数，
        不做 query 相关性过滤——通用教训不因这次提问没提到就不适用。
        """
        if limit <= 0:
            return []
        return [record.one_line() for record in rank_lessons(self.graph, limit=limit)]

    def _failure_warnings(self, limit: int) -> list[str]:
        """汇总历史失败规避项，本项目实测回写的经验优先于材料里的种子案例。"""
        measured: list[str] = []
        seeded: list[str] = []
        for node in self.graph.by_type(NodeType.FAILURE_CASE):
            signature = node.attributes.get("error_signature")
            fix = (node.attributes.get("fix_strategy")
                   or node.attributes.get("修复策略")
                   or node.attributes.get("定向修复")
                   or node.attributes.get("description"))
            if not (signature or fix):
                continue
            text = f"{signature or '未知签名'} → {fix}"
            if node.node_id.startswith("failure."):
                measured.append(text)
            else:
                seeded.append(text)
        merged: list[str] = []
        for text in measured + seeded:
            if text not in merged:
                merged.append(text)
        return merged[:limit]

    def _recommended_families(self, limit: int) -> list[str]:
        """从历史实验记录里提炼「值得优先复用的算法族」。

        只认配置指定的主指标列（``historical_metric_key``），并剔除结论里
        带作废标记的记录（如随机划分造成的虚高指标）。模型名 → 算法族的映射
        来自任务配置的 ``candidates.family_aliases``，检索器不认识具体业务命名。
        """
        scored: list[tuple[float, str]] = []
        for node in self.graph.nodes:
            if node.node_type not in (NodeType.VALIDATION_RUN, NodeType.CAPABILITY):
                continue
            value = _historical_metric(node, self.historical_metric_key)
            if value <= 0:
                continue
            text = f"{node.name} {node.attributes.get('结论', '')}"
            if any(marker and marker in text for marker in self.invalid_markers):
                continue
            model_name = str(node.attributes.get("模型") or node.name)
            family = self._match_family(model_name)
            if family:
                scored.append((value, family))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ordered: list[str] = []
        for _, family in scored:
            if family not in ordered:
                ordered.append(family)
        return ordered[:limit]

    def _match_family(self, model_name: str) -> str:
        """把人类可读的模型名映射回可渲染的算法族；无法映射返回空串。"""
        normalized = _normalized(model_name)
        if not normalized:
            return ""
        for family, aliases in self.family_aliases.items():
            tokens = [family, *aliases]
            if any(token and _normalized(str(token)) in normalized for token in tokens):
                return family
        return ""


__all__ = ["HybridRetriever"]
