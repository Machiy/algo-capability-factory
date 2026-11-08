"""L0 契约：AST 静态检查与子进程沙箱执行结果。

P3 的 Repairer 依据 ``error_signature`` 做定向修复，不重写全量代码。
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


__all__ = ["SandboxResult", "StaticCheckResult"]
