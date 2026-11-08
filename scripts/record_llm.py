"""录制一次真实 DeepSeek 调用（P3 尾执行，需 .env 中的 LLM_API_KEY）。

    .venv\\Scripts\\python.exe scripts/record_llm.py

只录 ``Interpreter`` 与 ``Coder`` 两环即可满足任务 1「可调用的 LLM 接口」；
产物脱敏后写入 assets/llm_cassettes/，报告须标注「离线回放」。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings
from factory.contracts.llm import LLMRequest
from factory.llm.openai_compat import OpenAICompatLLM
from factory.logging_setup import configure_logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是算法能力工厂的 Interpreter，把自然语言能力描述解析为结构化 JSON。"
USER_PROMPT = "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"


def main() -> int:
    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml")
    llm_settings = settings.llm.model_copy(update={
        "cassette": settings.llm.cassette.model_copy(update={"record": True}),
    })
    llm = OpenAICompatLLM(llm_settings, ROOT)
    request = LLMRequest(
        role="Interpreter",
        system=SYSTEM_PROMPT,
        user=USER_PROMPT,
        model=llm_settings.model,
        temperature=llm_settings.temperature,
        max_tokens=llm_settings.max_tokens,
        reasoning_effort=llm_settings.reasoning_effort,
        thinking=llm_settings.thinking,
        context_budget_tokens=llm_settings.context_budget_tokens,
    )
    response = llm.complete(request)
    print(f"[P3] source={response.source} model={response.model} "
          f"tokens={response.usage.total_tokens}")
    print(f"  响应摘录：{response.raw[:200]}")
    logger.info("录制完成，请用 provider=cassette 验证回放一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
