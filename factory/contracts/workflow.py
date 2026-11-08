"""L0 契约：工作流轨迹、候选评估、修复记录与数据沙箱结果。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


class CandidateEvaluation(_StrictModel):
    plan_id: str
    model_family: str
    passed: bool
    score: float
    metrics: dict[str, float | None] = Field(default_factory=dict)
    repair_rounds: int = 0


class RunTrace(_StrictModel):
    """一次 a–g 七步运行的可回放轨迹。"""

    run_id: str
    spec: str
    steps: list[str] = Field(default_factory=list)
    retrieval_prompt: str = ""
    candidates: list[CandidateEvaluation] = Field(default_factory=list)
    repairs: list[RepairRecord] = Field(default_factory=list)
    kg_diff: dict[str, int] = Field(default_factory=dict)
    generated_files: list[str] = Field(default_factory=list)
    report_path: str = ""
    passed: bool = False
    notes: str = ""


__all__ = [
    "CandidateEvaluation",
    "DatasetRunResult",
    "RepairRecord",
    "RunTrace",
]
