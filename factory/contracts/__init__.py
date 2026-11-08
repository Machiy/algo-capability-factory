"""全系统唯一数据协议：能力描述、候选方案、验证报告、知识图谱与执行结论。"""

from factory.contracts.knowledge import (
    EdgeType,
    Evidence,
    KGEdge,
    KGNode,
    KnowledgeGraph,
    NodeType,
    RetrievalHit,
    RetrievalResult,
    SourceDocument,
)
from factory.contracts.models import CandidatePlan, CapabilitySpec, TaskType, ValidationReport
from factory.contracts.validation import SandboxResult, StaticCheckResult

__all__ = [
    "CandidatePlan",
    "CapabilitySpec",
    "EdgeType",
    "Evidence",
    "KGEdge",
    "KGNode",
    "KnowledgeGraph",
    "NodeType",
    "RetrievalHit",
    "RetrievalResult",
    "SandboxResult",
    "SourceDocument",
    "StaticCheckResult",
    "TaskType",
    "ValidationReport",
]
