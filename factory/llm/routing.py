"""按角色路由的 LLM 组合，让指定角色的输出可来自真实录制。

典型用法：默认 ``MockLLM`` 保证其余角色的确定性与零外部依赖，只让
``Interpreter`` 走 ``cassette``，使「能力理解」这一环由真实 LLM 响应驱动，
而不是全部退回规则模板。
"""

from __future__ import annotations

import logging

from factory.contracts.llm import LLMRequest, LLMResponse
from factory.llm.base import BaseLLM

logger = logging.getLogger(__name__)


class RoutedLLM(BaseLLM):
    """按 ``request.role`` 分发到不同后端；未配置的角色走默认后端。"""

    def __init__(self, routes: dict[str, BaseLLM], default: BaseLLM) -> None:
        self.routes = dict(routes)
        self.default = default

    def complete(self, request: LLMRequest) -> LLMResponse:
        backend = self.routes.get(request.role, self.default)
        response = backend.complete(request)
        logger.debug("角色 %s 由 %s 处理", request.role, type(backend).__name__)
        return response


class SourceRecorder(BaseLLM):
    """记录每个角色本次实际拿到的 ``LLMResponse.source``，供报告如实标注。

    只做观测、不改请求与响应：``deepseek_api`` 表示实时调用，``cassette`` 表示
    离线回放，``mock`` 表示规则模板。报告据此区分「谁是真的模型输出」，
    避免把回放说成实时，也避免把实时调用说成 mock。
    """

    def __init__(self, inner: BaseLLM) -> None:
        self.inner = inner
        self.sources: dict[str, str] = {}

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self.inner.complete(request)
        self.sources[request.role] = response.source
        return response


__all__ = ["RoutedLLM", "SourceRecorder"]
