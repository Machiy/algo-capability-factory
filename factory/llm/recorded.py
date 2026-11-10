"""录制回放 LLM：无 key、断网环境下复现真实 API 的同一输出。

未命中时按 ``on_miss`` 显式报错或回退 MockLLM，绝不静默造假；
返回的 ``source`` 会标明 ``cassette`` 或 ``mock``，供报告标注「离线回放」。
"""

from __future__ import annotations

import logging

from factory.config import LLMSettings
from factory.contracts.llm import Cassette, LLMRequest, LLMResponse, LLMUsage
from factory.llm.base import BaseLLM
from factory.llm.cassette import compute_key

logger = logging.getLogger(__name__)


class CassetteMiss(RuntimeError):
    """cassette 未命中或文件缺失。"""


class RecordedLLM(BaseLLM):
    def __init__(self, cassette: Cassette, settings: LLMSettings,
                 fallback: BaseLLM | None = None) -> None:
        self.cassette = cassette
        self.settings = settings
        self.fallback = fallback

    def complete(self, request: LLMRequest) -> LLMResponse:
        # 认知角色按角色级 key_fields 算键（去掉动态 user），其余角色沿用全局字段
        key_fields = (self.settings.cassette.role_key_fields.get(request.role)
                      or self.settings.cassette.key_fields)
        key = compute_key(request, key_fields)
        entry = self.cassette.find(key)
        if entry is not None:
            response = entry.response
            return LLMResponse(
                raw=str(response.get("raw", "")),
                parsed=dict(response.get("parsed", {})),
                model=entry.model,
                usage=LLMUsage(**response.get("usage", {})),
                source="cassette",
                cached=True,
            )
        if self.settings.cassette.on_miss == "fallback_mock" and self.fallback is not None:
            logger.warning("cassette 未命中 %s，按配置回退规则模板", key)
            return self.fallback.complete(request)
        raise CassetteMiss(
            f"cassette 未命中 key={key}；on_miss=error，拒绝静默编造 LLM 输出"
        )


__all__ = ["CassetteMiss", "RecordedLLM"]
