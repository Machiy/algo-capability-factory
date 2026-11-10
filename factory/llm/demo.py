"""录制与回放共享的示范请求。

命中键由 ``LLMRequest`` 的字段决定，因此录制脚本与回放验收必须使用
完全相同的请求，这里作为单一事实来源。
"""

from __future__ import annotations

from factory.config import LLMSettings
from factory.contracts.llm import LLMRequest

SYSTEM_PROMPT = "你是算法能力工厂的 Interpreter，把自然语言能力描述解析为结构化 JSON。"
USER_PROMPT = "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"
RECHECK_USER_PROMPT = ("复测：确认替换现成库后的实时 LLM 链路可用，"
                       "请把这句能力描述解析为结构化 JSON。")


def build_role_request(settings: LLMSettings, role: str, system: str,
                       user: str) -> LLMRequest:
    """按角色构造录制 / 回放请求，字段口径与 ``build_demo_request`` 完全一致。

    Interpreter 之外的认知角色（Planner / Coder / Repairer / Curator）由
    ``scripts/record_llm.py --role`` 调用，为 B1 的多角色 cassette 录制铺路。
    """
    return LLMRequest(
        role=role,
        system=system,
        user=user,
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        reasoning_effort=settings.reasoning_effort,
        thinking=settings.thinking,
        context_budget_tokens=settings.context_budget_tokens,
    )


def build_demo_request(settings: LLMSettings,
                       user_prompt: str | None = None) -> LLMRequest:
    """构造与 ``scripts/record_llm.py`` 一致的请求，供离线回放验收使用。

    默认使用 ``USER_PROMPT``（首次录制的命中键不变）；传入 ``user_prompt``
    可生成另一条独立录制，用于替换后的实时链路复测。
    """
    return build_role_request(settings, "Interpreter", SYSTEM_PROMPT,
                              user_prompt or USER_PROMPT)


__all__ = ["RECHECK_USER_PROMPT", "SYSTEM_PROMPT", "USER_PROMPT",
           "build_demo_request", "build_role_request"]
