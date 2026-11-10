"""L0 契约：用户输入引导（Intake Guidance）。

用户提交的自然语言描述不一定可执行：可能过短、跑题，或者缺「目标 / 数据 /
指标 / 约束」中的关键要素。入口层先用 ``IntakeGuide`` 做一次规则体检，把结论
固化成 ``IntakeGuidance``：

    OK       要素齐全，直接进七步闭环
    CLARIFY  可继续，但缺要素：给出追问与示例，结论写入 ``RunTrace.intake``
    REJECT   明显不可执行（空白 / 乱码 / 跑题）：拦在闭环之前，附可复制的示例

契约只承载数据与渲染，判定逻辑在 ``factory/intake/guard.py``，规则来自
``configs/default.yaml`` 与各任务 ``verify_*.yaml`` 的 ``intake`` 段——换场景
只改 yaml，不改这里。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntakeVerdict(str, Enum):
    """输入体检结论。"""

    OK = "ok"
    CLARIFY = "clarify"
    REJECT = "reject"


class IntakeIssue(_StrictModel):
    """一条具体问题：`code` 供程序判定，`message` / `hint` 给人看。"""

    code: str = Field(description="问题代码，如 too_short / off_topic / task_mismatch")
    message: str = Field(description="问题说明")
    hint: str = Field(default="", description="怎么改")


class IntakeGuidance(_StrictModel):
    """一次输入体检的完整结论，同时用于终端提示、API 响应与运行轨迹留证。"""

    verdict: IntakeVerdict = IntakeVerdict.OK
    score: float = Field(default=1.0, ge=0.0, le=1.0, description="要素完备度")
    scenario: str = Field(default="", description="当前任务场景名")
    matched_elements: list[str] = Field(default_factory=list, description="已表达要素")
    missing_elements: list[str] = Field(default_factory=list, description="缺失要素")
    issues: list[IntakeIssue] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list, description="针对性追问")
    examples: list[str] = Field(default_factory=list, description="可直接复制的合格描述")
    elements: list[str] = Field(default_factory=list, description="期望要素清单")
    suggestion: str = Field(default="", description="一句话建议，如切换场景的命令")

    @property
    def accepted(self) -> bool:
        return self.verdict is not IntakeVerdict.REJECT


__all__ = ["IntakeGuidance", "IntakeIssue", "IntakeVerdict"]
