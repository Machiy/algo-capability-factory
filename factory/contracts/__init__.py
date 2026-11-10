"""全系统唯一数据协议：能力描述、候选方案、验证报告、知识图谱、执行结论与 LLM。"""

from factory.contracts.intake import IntakeGuidance, IntakeIssue, IntakeVerdict
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
from factory.contracts.llm import (
    Cassette,
    CassetteEntry,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)
from factory.contracts.models import CandidatePlan, CapabilitySpec, TaskType, ValidationReport
from factory.contracts.validation import (
    MetricResult,
    MetricSpec,
    SandboxResult,
    SplitIndices,
    SplitSpec,
    StaticCheckResult,
)

__all__ = [
    "CandidatePlan",
    "CapabilitySpec",
    "Cassette",
    "CassetteEntry",
    "EdgeType",
    "Evidence",
    "IntakeGuidance",
    "IntakeIssue",
    "IntakeVerdict",
    "KGEdge",
    "KGNode",
    "KnowledgeGraph",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
    "MetricResult",
    "MetricSpec",
    "NodeType",
    "RetrievalHit",
    "RetrievalResult",
    "SandboxResult",
    "SourceDocument",
    "SplitIndices",
    "SplitSpec",
    "StaticCheckResult",
    "TaskType",
    "ValidationReport",
]
