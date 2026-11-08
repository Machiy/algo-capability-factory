"""录制一次真实 DeepSeek 调用（需 .env 中的 LLM_API_KEY）。

    .venv\\Scripts\\python.exe scripts/record_llm.py             # 首次 / 幂等覆盖同键条目
    .venv\\Scripts\\python.exe scripts/record_llm.py --recheck   # 用复测 prompt 新增独立条目

产物脱敏后写入 assets/llm_cassettes/；录制与回放共用
``factory.llm.demo.build_demo_request``，确保命中键一致。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings
from factory.llm.demo import RECHECK_USER_PROMPT, USER_PROMPT, build_demo_request
from factory.llm.openai_compat import OpenAICompatLLM
from factory.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="录制一次真实 DeepSeek 调用")
    parser.add_argument("--recheck", action="store_true",
                        help="用复测 prompt 新增一条录制，不覆盖首次证据")
    args = parser.parse_args()
    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml")
    llm_settings = settings.llm.model_copy(update={
        "cassette": settings.llm.cassette.model_copy(update={"record": True}),
    })
    llm = OpenAICompatLLM(llm_settings, ROOT)
    user_prompt = RECHECK_USER_PROMPT if args.recheck else USER_PROMPT
    response = llm.complete(build_demo_request(llm_settings, user_prompt))
    print(f"[P3] source={response.source} model={response.model} "
          f"tokens={response.usage.total_tokens} recheck={args.recheck}")
    print(f"  响应摘录：{response.raw[:200]}")
    logger.info("录制完成，请用 provider=cassette 验证回放一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
