"""Pydantic 契约定义（L0）。

所有模块只依赖这里的数据结构：
    CapabilitySpec    Interpreter 输出 → Retriever / Planner 输入
    CandidatePlan     Planner 输出 → Coder 输入
    ValidationReport  Verifier 输出 → Repairer / Curator 输入
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskType(str, Enum):
    """支持的任务类型；新增类型时同步添加 verify_*.yaml。"""

    TABULAR_BINARY = "tabular_binary_classification"
    TABULAR_REGRESSION = "tabular_regression"
    TEXT_CLASSIFICATION = "text_classification"


class _StrictModel(BaseModel):
    """禁止未知字段，防止拼写错误 silently 进入流水线。"""

    model_config = ConfigDict(extra="forbid")


class CapabilitySpec(_StrictModel):
    """结构化后的自然语言能力描述。"""

    spec_id: str = Field(description="能力描述唯一标识")
    description: str = Field(description="用户提交的原始自然语言描述")
    task_type: TaskType = TaskType.TABULAR_BINARY
    inputs: dict[str, str] = Field(default_factory=dict, description="输入字段 → 类型")
    outputs: dict[str, str] = Field(default_factory=dict, description="输出字段 → 类型/取值范围")
    constraints: list[str] = Field(default_factory=list, description="适用条件与业务约束")
    metrics: list[str] = Field(default_factory=list, description="评价指标名")
    cost_ratio_fn_fp: float = Field(default=5.0, gt=0, description="漏报/误报成本比")
    config_path: str = Field(default="configs/verify_credit.yaml")
    source_refs: list[str] = Field(default_factory=list, description="证据来源")


class CandidatePlan(_StrictModel):
    """Beam Search 中的一个候选实现方案。"""

    plan_id: str
    spec_id: str
    model_family: str = Field(description="如 logistic_regression / hist_gradient_boosting")
    operators: list[str] = Field(default_factory=list, description="按 PRECEDES 顺序排列的算子")
    hyperparams: dict[str, Any] = Field(default_factory=dict)
    sampler: str = "none"
    threshold: float | str = 0.5
    rationale: str = Field(default="", description="方案设计依据")
    retrieved_evidence: list[str] = Field(default_factory=list, description="命中的能力节点 id")
    beam_score: float = 0.0
    parent_plan_id: str | None = Field(default=None, description="Beam 扩展来源")


class ValidationReport(_StrictModel):
    """四层统一验证结果，同时也是沉淀回图谱的数据源。"""

    run_id: str
    plan_id: str
    passed: bool
    interface_checks: dict[str, bool] = Field(default_factory=dict)
    functional_checks: dict[str, bool] = Field(default_factory=dict)
    metric_values: dict[str, float | None] = Field(default_factory=dict)
    threshold_checks: dict[str, bool] = Field(default_factory=dict)
    stability: dict[str, Any] = Field(default_factory=dict, description="耗时/内存/方差/依赖")
    error_signature: str | None = Field(default=None, description="用于定向修复的错误签名")
    repair_round: int = Field(default=0, ge=0)
    fix_strategy: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    notes: str = ""

    def failed_checks(self) -> list[str]:
        """返回所有未通过的检查项名称，供 Diagnose 分类。"""
        groups = (
            self.interface_checks,
            self.functional_checks,
            self.threshold_checks,
        )
        return [name for group in groups for name, ok in group.items() if not ok]


__all__ = ["CandidatePlan", "CapabilitySpec", "TaskType", "ValidationReport"]
