"""L2 支撑：LLM 实现工厂，按 ``llm.provider`` 与 ``llm.role_providers`` 组装。"""

from __future__ import annotations

import logging
from pathlib import Path

from factory.config import LLMSettings
from factory.llm.base import BaseLLM
from factory.llm.cassette import cassette_path, load_cassette
from factory.llm.mock import MockLLM
from factory.llm.openai_compat import MissingCredentialError, OpenAICompatLLM
from factory.llm.recorded import CassetteMiss, RecordedLLM
from factory.llm.routing import RoutedLLM, SourceRecorder

logger = logging.getLogger(__name__)


def _build_single(settings: LLMSettings, provider: str, root: Path) -> BaseLLM:
    if provider == "mock":
        return MockLLM(settings)
    if provider == "openai_compat":
        return OpenAICompatLLM(settings, root)
    if provider == "cassette":
        path = cassette_path(root / settings.cassette.dir, settings.model)
        cassette = load_cassette(path)
        if cassette is None:
            raise CassetteMiss(f"cassette 文件不存在：{path}")
        fallback = (MockLLM(settings)
                    if settings.cassette.on_miss == "fallback_mock" else None)
        return RecordedLLM(cassette, settings, fallback)
    raise ValueError(f"未知 llm.provider：{provider}")


def build_llm(settings: LLMSettings, root: Path | None = None) -> BaseLLM:
    """构造 LLM；``role_providers`` 里不可用的后端按角色显式回退默认后端。

    回退会记录 warning，且 ``LLMResponse.source`` 仍如实标注实际来源，
    不会把回退结果冒充成真实调用。
    """
    root = root or Path.cwd()
    default = _build_single(settings, settings.provider, root)
    routes: dict[str, BaseLLM] = {}
    for role, provider in settings.role_providers.items():
        if provider == settings.provider:
            continue
        try:
            routes[role] = _build_single(settings, provider, root)
        except (CassetteMiss, MissingCredentialError) as error:
            logger.warning("角色 %s 的 %s 后端不可用（%s），回退默认 %s",
                           role, provider, error, settings.provider)
    if not routes:
        return default
    logger.info("角色路由：%s", sorted(routes))
    return RoutedLLM(routes, default)


__all__ = [
    "BaseLLM",
    "CassetteMiss",
    "MissingCredentialError",
    "MockLLM",
    "OpenAICompatLLM",
    "RecordedLLM",
    "RoutedLLM",
    "SourceRecorder",
    "build_llm",
]
