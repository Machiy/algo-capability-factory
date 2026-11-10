"""L0 契约：LLM 请求、响应与录制回放。

``source`` 用于区分规则模板、真实 API、离线回放与测试夹具，避免把回放
结果说成实时调用；cassette 中绝不出现 header、endpoint 或凭据。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMRequest(_StrictModel):
    """一次角色调用；所有影响输出的参数都参与 cassette 命中键。

    ``scene`` 承载任务类型（tabular_binary_classification / tabular_regression /
    text_classification），用于让认知角色的 cassette 键区分场景——Coder / Planner
    的响应依赖场景，跨场景错配会产生错误代码。
    """

    role: str
    system: str
    user: str
    scene: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 8192
    reasoning_effort: str = "high"
    thinking: str = "enabled"
    context_budget_tokens: int = 32000


class LLMUsage(_StrictModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(_StrictModel):
    raw: str
    parsed: dict[str, Any] = Field(default_factory=dict)
    model: str = ""
    usage: LLMUsage = Field(default_factory=LLMUsage)
    source: str = "mock"
    cached: bool = False


class CassetteEntry(_StrictModel):
    """一条脱敏后的请求/响应；不含 header、完整 endpoint、key/token。

    ``recorded_at`` 为该条自己的录制时刻；旧版 cassette 无此字段时为空串，
    保持向后兼容。
    """

    key: str
    role: str
    prompt_sha256: str
    request: dict[str, Any]
    response: dict[str, Any]
    model: str
    recorded_at: str = ""


class Cassette(_StrictModel):
    """录制文件契约。

    ``source`` 取 ``deepseek_api``（真实录制）或 ``test_fixture``（测试夹具），
    报告与 README 据此标注「离线回放」，不冒充实时调用。``recorded_at`` 是
    **首次**录制时间，后续新增条目的时间由各 ``CassetteEntry.recorded_at`` 记录。
    """

    cassette_version: int = 1
    provider: str = "deepseek"
    model: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    source: str = "deepseek_api"
    recorded_at: str = ""
    entries: list[CassetteEntry] = Field(default_factory=list)

    def find(self, key: str) -> CassetteEntry | None:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None


__all__ = [
    "Cassette",
    "CassetteEntry",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
]
