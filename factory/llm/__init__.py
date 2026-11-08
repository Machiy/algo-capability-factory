"""L2 支撑：LLM 实现工厂，按 ``llm.provider`` 切换三种后端。"""

from __future__ import annotations

from pathlib import Path

from factory.config import LLMSettings
from factory.llm.base import BaseLLM
from factory.llm.cassette import cassette_path, load_cassette
from factory.llm.mock import MockLLM
from factory.llm.openai_compat import MissingCredentialError, OpenAICompatLLM
from factory.llm.recorded import CassetteMiss, RecordedLLM


def build_llm(settings: LLMSettings, root: Path | None = None) -> BaseLLM:
    """构造 LLM 实现；cassette 不存在时明确报错，不假装回放成功。"""
    root = root or Path.cwd()
    if settings.provider == "mock":
        return MockLLM(settings)
    if settings.provider == "openai_compat":
        return OpenAICompatLLM(settings, root)
    if settings.provider == "cassette":
        path = cassette_path(root / settings.cassette.dir, settings.model)
        cassette = load_cassette(path)
        if cassette is None:
            raise CassetteMiss(f"cassette 文件不存在：{path}")
        fallback = (MockLLM(settings)
                    if settings.cassette.on_miss == "fallback_mock" else None)
        return RecordedLLM(cassette, settings, fallback)
    raise ValueError(f"未知 llm.provider：{settings.provider}")


__all__ = [
    "BaseLLM",
    "CassetteMiss",
    "MissingCredentialError",
    "MockLLM",
    "OpenAICompatLLM",
    "RecordedLLM",
    "build_llm",
]
