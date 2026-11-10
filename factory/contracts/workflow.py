"""L0 契约：工作流轨迹、候选评估、修复记录与数据沙箱结果。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from factory.contracts.intake import IntakeGuidance
from factory.contracts.validation import SandboxResult


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetRunResult(_StrictModel):
    """子进程用真实数据执行生成代码的结果，context 供指标插件消费。"""

    sandbox: SandboxResult
    context: dict[str, Any] = Field(default_factory=dict)


class RepairRecord(_StrictModel):
    round: int
    error_signature: str
    fix_strategy: str
    outcome: str = "repaired"
    # LLM 对失败根因的推理摘要（双轨：确定性补丁保底 + LLM 推理进报告，不冒充补丁）
    llm_reasoning: str = ""


class CandidateEvaluation(_StrictModel):
    plan_id: str
    model_family: str
    passed: bool
    score: float
    metrics: dict[str, float | None] = Field(default_factory=dict)
    repair_rounds: int = 0
    # 与 CandidatePlan.threshold 同型：数值阈值或 cost_optimal 等语义值，
    # 语义值由 pipeline 的 _resolve_threshold 在消费时转成数值
    threshold: float | str = 0.5


class TestEvaluation(_StrictModel):
    """终评结论：最佳候选在 test 段的一次性评估。

    ``consumed`` 为 True 表示 test 段已被本次运行消费；结果只用于报告，
    不参与候选排序与修复决策，避免用未来数据调参。
    """

    plan_id: str = ""
    consumed: bool = False
    metrics: dict[str, float | None] = Field(default_factory=dict)
    note: str = ""


class CollaborationRecord(_StrictModel):
    """角色间的一次协作交互：谁 → 谁、类型、意见。

    ``kind`` 取 ``review_reject`` / ``review_accept`` / ``regenerate``；
    ``comment`` 是 Reviewer 给出的具体意见（拒绝时非空）。用于证明协作不是单向
    流水线，而是「Reviewer 否决 → Coder 带意见重生成」的反馈环。
    """

    round: int
    sender: str
    receiver: str
    kind: str
    comment: str = ""


class RunTrace(_StrictModel):
    """一次 a–g 七步运行的可回放轨迹。

    ``kg_mode`` / ``graph_source`` / ``used_historical_warnings`` 用于证明
    沉淀闭环：本轮是否使用检索、图谱来自源材料还是上一轮回写、是否命中
    历史失败经验。
    """

    run_id: str
    spec: str
    steps: list[str] = Field(default_factory=list)
    retrieval_prompt: str = ""
    # 本次注入 prompt 的系统级教训（跨运行知识），与 failure_warnings 分开留证
    lessons: list[str] = Field(default_factory=list)
    # 入口引导结论：证明「用户输入被体检过」，CLARIFY 也可继续运行
    intake: IntakeGuidance | None = None
    candidates: list[CandidateEvaluation] = Field(default_factory=list)
    repairs: list[RepairRecord] = Field(default_factory=list)
    # 角色间协作轨迹：Reviewer 否决 → Coder 重生成等，与 repairs（修复层）分开留证
    collaborations: list[CollaborationRecord] = Field(default_factory=list)
    kg_diff: dict[str, int] = Field(default_factory=dict)
    # 每个候选的代码来源：llm（通过静态检查后采用）或 template（回退模板）
    code_sources: dict[str, str] = Field(default_factory=dict)
    generated_files: list[str] = Field(default_factory=list)
    report_path: str = ""
    passed: bool = False
    interpreter_source: str = "mock"
    kg_mode: str = "with_kg"
    graph_source: str = "sources"
    used_historical_warnings: bool = False
    test_evaluation: TestEvaluation | None = None
    notes: str = ""


__all__ = [
    "CandidateEvaluation",
    "CollaborationRecord",
    "DatasetRunResult",
    "RepairRecord",
    "RunTrace",
    "TestEvaluation",
]
