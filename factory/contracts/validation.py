"""L0 契约：静态检查、沙箱执行、指标定义与数据划分。

四层验证的最终输出复用 ``factory.contracts.models.ValidationReport``，
本文件只补充其输入侧契约；Repairer 依据 ``error_signature`` 定向修复。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StaticCheckResult(_StrictModel):
    """静态检查结论；``checks`` 逐项对应四层验证中的接口规范层。"""

    passed: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    violations: list[str] = Field(default_factory=list)
    source_sha256: str = ""
    error_signature: str | None = None

    def failed_checks(self) -> list[str]:
        return [name for name, ok in self.checks.items() if not ok]


class SandboxResult(_StrictModel):
    """子进程执行结论，含资源与超时证据供报告使用。"""

    passed: bool
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    peak_memory_mb: float | None = None
    memory_limit_applied: bool = False
    timed_out: bool = False
    memory_exceeded: bool = False
    error_signature: str | None = None
    # 推理延迟（毫秒 / 单条），由沙箱子进程按批实测，供资源消耗分析使用
    inference_p50_ms: float | None = None
    inference_p95_ms: float | None = None


class MetricSpec(_StrictModel):
    """``verify_*.yaml`` 的单个指标定义；新任务类型只加配置与插件。"""

    name: str
    direction: str = "maximize"
    threshold: float | None = None
    plugin: str = "sklearn_metrics"

    def passes(self, value: float | None) -> bool:
        if value is None:
            return False
        if self.threshold is None:
            return True
        return value >= self.threshold if self.direction == "maximize" else value <= self.threshold


class SplitSpec(_StrictModel):
    """时间外划分策略；标签为「下月违约」，禁止随机打乱。

    各 ``verify_*.yaml`` 可携带任务专属划分参数（如 ``n_splits``、
    ``train_split``），核心验证器只消费公共字段，因此这里忽略额外键。
    """

    model_config = ConfigDict(extra="ignore")

    strategy: str = "temporal_holdout"
    train_ratio: float = 0.60
    valid_ratio: float = 0.20
    test_ratio: float = 0.20
    stratify: bool = False
    random_state: int = 42
    test_used_once: bool = True

    def ratios_sum_to_one(self) -> bool:
        return abs(self.train_ratio + self.valid_ratio + self.test_ratio - 1.0) < 1e-6


class SplitIndices(_StrictModel):
    """按行序切出的索引集合，三段互不重叠。"""

    train: list[int]
    valid: list[int]
    test: list[int]
    strategy: str


class MetricResult(_StrictModel):
    """单个指标的实测值与门槛判定，供 ValidationReport 与报告模板消费。"""

    name: str
    value: float | None
    direction: str
    threshold: float | None
    passed: bool
    plugin: str


__all__ = [
    "MetricResult",
    "MetricSpec",
    "SandboxResult",
    "SplitIndices",
    "SplitSpec",
    "StaticCheckResult",
]
