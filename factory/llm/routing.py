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


__all__ = ["RoutedLLM"]
