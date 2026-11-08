"""LLM 抽象：所有实现共用 ``LLMRequest`` / ``LLMResponse`` 契约。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from factory.contracts.llm import LLMRequest, LLMResponse


class BaseLLM(ABC):
    """一次角色调用；实现可替换，Agent 层不感知具体后端。"""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """返回结构化响应；不得静默伪造来源。"""


__all__ = ["BaseLLM"]
