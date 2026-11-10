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
    """题目六要素 + 运行记录 / 失败案例 / 教训 / 证据，共 10 类节点。

    ``VALIDATION_RUN`` 与 ``LESSON`` 的区别是本项目的核心口径：
    前者是「某次运行发生了什么」（日志，可丢弃、可重跑覆盖），后者是
    「跨运行依然成立的系统级判断」（知识，带根因、处置、预防与置信度）。
    沉淀的价值在后者，前者只用于追溯。
    """

    CAPABILITY = "Capability"
    OPERATOR = "Operator"
    ALGORITHM = "Algorithm"
    METRIC = "Metric"
    DATASET = "Dataset"
    ENVIRONMENT = "Environment"
    VALIDATION_RUN = "ValidationRun"
    FAILURE_CASE = "FailureCase"
    LESSON = "Lesson"
    EVIDENCE = "Evidence"


class LessonScope(str, Enum):
    """教训的适用范围，按「系统层面」而非业务层面划分。

    分类口径决定教训能否迁移：``platform`` / ``runtime`` / ``llm`` 的教训
    与数据集无关，换场景仍然成立；``data`` 的教训只在该数据分布内成立。
    """

    RUNTIME = "runtime"        # 沙箱、超时、内存、确定性
    DATA = "data"              # schema、类别枚举、标签口径、时间泄漏
    LLM = "llm"                # 解析、回放、prompt 输出契约
    VALIDATION = "validation"  # 四层验证自身的语义缺陷
    KNOWLEDGE = "knowledge"    # 抽取、图谱、检索
    PLATFORM = "platform"      # 跨平台、编码、路径与文件名
    WORKFLOW = "workflow"      # 编排、重试、候选比较、报告口径



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


class LessonRecord(_StrictModel):
    """一条系统级教训：可复用、可检索、可判失效的知识单元。

    与 ``ValidationRun`` 的区别是「下次还能用」：日志只说明某次跑了什么，
    教训必须能回答「在什么条件下、会遇到什么现象、为什么、怎么处置、怎么预防」。
    缺了 ``root_cause`` 或 ``action`` 的条目只是记录，不应该进图谱。
    """

    lesson_id: str
    scope: LessonScope
    symptom: str = Field(description="可观测现象：错误签名、报错文本或异常指标")
    root_cause: str = Field(description="系统层根因，不是这一次的输入数据")
    action: str = Field(description="处置动作：改什么、怎么改")
    prevention: str = Field(default="", description="下次怎么提前避免")
    signatures: list[str] = Field(default_factory=list, description="可自动匹配的错误签名")
    applies_to: str = Field(default="", description="适用范围：跨场景通用或限定本任务")
    occurrences: int = Field(default=1, ge=1, description="独立运行中出现次数")
    run_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(default="measured", description="来源：measured / seeded")

    def to_attributes(self) -> dict[str, Any]:
        """转为图谱节点属性；键名与检索、报告的读取口径保持一致。"""
        return {
            "scope": self.scope.value,
            "symptom": self.symptom,
            "root_cause": self.root_cause,
            "action": self.action,
            "prevention": self.prevention,
            "signatures": list(self.signatures),
            "applies_to": self.applies_to,
            "occurrences": self.occurrences,
            "run_ids": list(self.run_ids),
            "confidence": self.confidence,
            "source": self.source,
            "record_kind": "knowledge",
        }

    def one_line(self) -> str:
        """注入 prompt 与报告的单行摘要：现象 → 根因 → 处置。"""
        return (f"[{self.scope.value}] {self.symptom} → 根因：{self.root_cause}"
                f" → 处置：{self.action}（出现 {self.occurrences} 次，"
                f"置信度 {self.confidence:.2f}）")


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
    # 系统级教训：与「某次失败的处置」不同，这里是跨运行稳定成立的知识
    lessons: list[str] = Field(default_factory=list)

    def as_prompt_context(self) -> str:
        """渲染为可直接注入 prompt 的证据文本。"""
        lines = [f"# 检索证据（query={self.query}）"]
        lines.extend(f"- [{hit.score:.3f}] {hit.name} ({hit.node_id})" for hit in self.hits)
        if self.constraints:
            lines.append("## 适用条件")
            lines.extend(f"- {item}" for item in self.constraints)
        if self.lessons:
            lines.append("## 系统级教训（跨运行成立，生成代码必须遵守）")
            lines.extend(f"- {item}" for item in self.lessons)
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
    "LessonRecord",
    "LessonScope",
    "NodeType",
    "RetrievalHit",
    "RetrievalResult",
    "SourceDocument",
]
