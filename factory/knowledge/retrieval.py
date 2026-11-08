"""混合检索器：BM25 相关性 + 历史指标 + 证据新鲜度 − 失败惩罚。

相关性打分直接调用 ``rank_bm25.BM25Okapi``，不再自研词元计数；权重来自
``configs/default.yaml``，排序带 node_id 作为次级键，保证同 query 多次调用
结果完全一致，满足「检索 Top-K 稳定可解释」的 M1 验收。
"""

from __future__ import annotations

import logging
import re

from rank_bm25 import BM25Okapi

from factory.contracts.knowledge import (
    Evidence,
    KGNode,
    KnowledgeGraph,
    NodeType,
    RetrievalHit,
    RetrievalResult,
)

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


def _historical_metric(node: KGNode) -> float:
    """历史验证数值越高越值得复用；无指标的节点记 0。"""
    metrics = node.attributes.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        return 0.0
    numbers = [value for value in metrics.values() if isinstance(value, (int, float))]
    return min(1.0, max(numbers)) if numbers else 0.0


def _failure_flag(node: KGNode) -> float:
    if node.node_type is NodeType.FAILURE_CASE:
        return 1.0
    return 1.0 if node.attributes.get("error_signature") else 0.0


class HybridRetriever:
    """检索能力子图，输出可直接注入 Planner / Coder prompt 的契约。"""

    def __init__(self, graph: KnowledgeGraph, top_k: int = 5,
                 weights: dict[str, float] | None = None) -> None:
        self.graph = graph
        self.top_k = top_k
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        limit = top_k if top_k is not None else self.top_k
        tokens = _tokens(query)
        nodes = [node for node in self.graph.nodes
                 if node.node_type is not NodeType.EVIDENCE]
        relevance = _bm25_scores(tokens, [_searchable_text(node) for node in nodes])
        hits: list[RetrievalHit] = []
        for node, constraint in zip(nodes, relevance):
            reasons: dict[str, float] = {
                "constraint_match": constraint,
                "historical_metric": _historical_metric(node),
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
        result = RetrievalResult(
            query=query,
            top_k=limit,
            hits=hits[:limit],
            constraints=self._constraints(limit),
            failure_warnings=self._failure_warnings(limit),
        )
        logger.info("检索 query=%r 命中 %d 项", query, len(result.hits))
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


__all__ = ["HybridRetriever"]
