"""录制与回放共享的示范请求。

命中键由 ``LLMRequest`` 的字段决定，因此录制脚本与回放验收必须使用
完全相同的请求，这里作为单一事实来源。
"""

from __future__ import annotations

from factory.config import LLMSettings
from factory.contracts.llm import LLMRequest

SYSTEM_PROMPT = "你是算法能力工厂的 Interpreter，把自然语言能力描述解析为结构化 JSON。"
USER_PROMPT = "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"


def build_demo_request(settings: LLMSettings) -> LLMRequest:
    """构造与 ``scripts/record_llm.py`` 一致的请求，供离线回放验收使用。"""
    return LLMRequest(
        role="Interpreter",
        system=SYSTEM_PROMPT,
        user=USER_PROMPT,
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        reasoning_effort=settings.reasoning_effort,
        thinking=settings.thinking,
        context_budget_tokens=settings.context_budget_tokens,
    )


__all__ = ["SYSTEM_PROMPT", "USER_PROMPT", "build_demo_request"]
