"""L0 契约：能力知识图谱 schema。

知识层、Agent 层、验证层只通过本文件的数据类交互；NetworkX / SQLite 的
序列化细节不属于契约，见 ``factory/knowledge/graph.py``。节点采用属性图
模型：``node_type`` 区分 9 类节点，``attributes`` 承载各类专有属性。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    """禁止未知字段，防止拼写错误静默进入图谱。"""

    model_config = ConfigDict(extra="forbid")


class NodeType(str, Enum):
    """题目六要素 + 历史验证结果 / 失败案例 / 证据，共 9 类节点。"""

    CAPABILITY = "Capability"
    OPERATOR = "Operator"
    ALGORITHM = "Algorithm"
    METRIC = "Metric"
    DATASET = "Dataset"
    ENVIRONMENT = "Environment"
    VALIDATION_RUN = "ValidationRun"
    FAILURE_CASE = "FailureCase"
    EVIDENCE = "Evidence"


class EdgeType(str, Enum):
    """关系类型，共 13 类；PLAN / README 与本枚举使用同一口径。

    测试断言至少覆盖 12 类，实际枚举 13 类，不为了凑数字丢弃语义。
    """

    REQUIRES = "REQUIRES"
    USES = "USES"
    EVALUATED_BY = "EVALUATED_BY"
    APPLIES_TO = "APPLIES_TO"
    DEPENDS_ON = "DEPENDS_ON"
    EVIDENCED_BY = "EVIDENCED_BY"
    PRECEDES = "PRECEDES"
    HAS_RUN = "HAS_RUN"
    RESULTED_IN = "RESULTED_IN"
    FIXED_BY = "FIXED_BY"
    DERIVED_FROM = "DERIVED_FROM"
    TRANSFERABLE_TO = "TRANSFERABLE_TO"
    SIMILAR_TO = "SIMILAR_TO"


class Evidence(_StrictModel):
    """可回溯的原文证据；``sha256`` 对 ``excerpt`` 计算，测试会重算校验。"""

    path: str = Field(description="相对仓库根目录的源文件路径")
    excerpt: str = Field(description="触发该节点的原文片段")
    sha256: str = Field(description="excerpt 的 SHA-256")
    doc_type: str = Field(description="材料类型：业务文档 / 专家经验 / 实验记录 / 测试报告等")


class SourceDocument(_StrictModel):
    """抽取器输入：一份已读入内存的源材料。"""

    path: str
    doc_type: str
    content: str
    sha256: str = Field(description="整份文件的 SHA-256")


class KGNode(_StrictModel):
    """属性图节点；``attributes`` 承载 9 类节点各自的专有属性。"""

    node_id: str
    node_type: NodeType
    name: str
    version: str = "v1"
    task_type: str = "tabular_binary_classification"
    status: str = "active"
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)


class KGEdge(_StrictModel):
    """有向边；``source`` / ``target`` 必须指向已存在的 ``KGNode.node_id``。"""

    source: str
    target: str
    edge_type: EdgeType
    attributes: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraph(_StrictModel):
    """抽取与回写的唯一载体；P4 的 Curator 也回写为本类型。"""

    nodes: list[KGNode] = Field(default_factory=list)
    edges: list[KGEdge] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    built_at: datetime = Field(default_factory=datetime.now)

    def node_index(self) -> dict[str, KGNode]:
        """按 id 建索引，供检索器与图存储复用。"""
        return {node.node_id: node for node in self.nodes}

    def by_type(self, node_type: NodeType) -> list[KGNode]:
        """按节点类型筛选。"""
        return [node for node in self.nodes if node.node_type is node_type]

    def edges_of(self, edge_type: EdgeType) -> list[KGEdge]:
        """按关系类型筛选。"""
        return [edge for edge in self.edges if edge.edge_type is edge_type]

    def validate_references(self) -> None:
        """校验边的端点与节点 id 唯一性，防止脏数据进入 GraphML。"""
        index = self.node_index()
        if len(index) != len(self.nodes):
            raise ValueError("存在重复的 node_id")
        for edge in self.edges:
            if edge.source not in index or edge.target not in index:
                raise ValueError(f"边端点不存在：{edge.source} -> {edge.target}")


class RetrievalHit(_StrictModel):
    """单个命中项，``reasons`` 保留打分分项以便解释排序。"""

    node_id: str
    name: str
    score: float
    reasons: dict[str, float] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)


class RetrievalResult(_StrictModel):
    """检索结果契约。

    规则要求检索结果必须进入 Planner 与 Coder 的 prompt，因此本类型同时
    携带 ``constraints`` 与 ``failure_warnings``，并提供统一的渲染入口，
    避免各 Agent 自行拼装导致证据丢失。
    """

    query: str
    top_k: int
    hits: list[RetrievalHit] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    failure_warnings: list[str] = Field(default_factory=list)

    def as_prompt_context(self) -> str:
        """渲染为可直接注入 prompt 的证据文本。"""
        lines = [f"# 检索证据（query={self.query}）"]
        lines.extend(f"- [{hit.score:.3f}] {hit.name} ({hit.node_id})" for hit in self.hits)
        if self.constraints:
            lines.append("## 适用条件")
            lines.extend(f"- {item}" for item in self.constraints)
        if self.failure_warnings:
            lines.append("## 历史失败规避项")
            lines.extend(f"- {item}" for item in self.failure_warnings)
        return "\n".join(lines)


__all__ = [
    "EdgeType",
    "Evidence",
    "KGEdge",
    "KGNode",
    "KnowledgeGraph",
    "NodeType",
    "RetrievalHit",
    "RetrievalResult",
    "SourceDocument",
]
