"""录制一次真实 DeepSeek 调用（需 .env 中的 LLM_API_KEY）。

    .venv\\Scripts\\python.exe scripts/record_llm.py                      # 首次 / 幂等覆盖同键条目
    .venv\\Scripts\\python.exe scripts/record_llm.py --recheck            # 用复测 prompt 新增独立条目
    .venv\\Scripts\\python.exe scripts/record_llm.py --role planner       # 按认知角色录制（B1 铺路）

产物脱敏后写入 assets/llm_cassettes/；录制与回放共用
``factory.llm.demo.build_demo_request`` / ``build_role_request``，确保命中键一致。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.agents.roles import SYSTEM_PROMPTS
from factory.config import load_settings
from factory.contracts.llm import LLMRequest
from factory.llm.demo import (
    RECHECK_USER_PROMPT,
    USER_PROMPT,
    build_demo_request,
    build_role_request,
)
from factory.llm.openai_compat import OpenAICompatLLM
from factory.logging_setup import configure_logging

logger = logging.getLogger(__name__)

# 各认知角色的示例输入，用于按角色录制一条代表性请求。
# 注意：这只是「录制能力」的参数化；运行时稳定命中依赖 B1 的键策略设计，
# 因为认知角色的 user prompt 含动态检索证据，键含完整 prompt 无法稳定命中。
_ROLE_USER_PROMPTS: dict[str, str] = {
    "Planner": (
        "能力描述：预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。\n"
        "# 检索证据（query=预测信用卡客户下月违约概率）\n"
        "- [0.500] 时间外划分 (cap.risk_policy.C4)\n"
        "## 适用条件\n- 必须时间外划分\n"
        "## 历史失败规避项\n- KeyError: PAY_1 → 列名映射为 PAY_0"
    ),
    "Coder": (
        "方案：{\"plan_id\":\"plan.01\",\"model_family\":\"logistic_regression\"}\n"
        "特征列：[\"LIMIT_BAL\", \"PAY_0\", \"BILL_AMT1\"]\n"
        "# 检索证据（query=预测信用卡客户下月违约概率）\n"
        "- [0.500] 时间外划分 (cap.risk_policy.C4)"
    ),
    "Repairer": ("错误签名：KeyError: PAY_1\n"
                 "策略：按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）"),
    "Curator": "回写 112 节点（教训 13 条），修复 1 轮",
}

_KNOWN_ROLES = ["interpreter", "planner", "coder", "repairer", "curator"]


def _build_request(role: str, llm_settings, recheck: bool) -> LLMRequest:
    """按角色构造请求；interpreter 走既有 demo 请求，其余角色走 build_role_request。"""
    if role == "interpreter":
        user_prompt = RECHECK_USER_PROMPT if recheck else USER_PROMPT
        return build_demo_request(llm_settings, user_prompt)
    title = role.title()  # planner -> Planner
    return build_role_request(llm_settings, title, SYSTEM_PROMPTS[title],
                              _ROLE_USER_PROMPTS[title])


def main() -> int:
    parser = argparse.ArgumentParser(description="录制一次真实 DeepSeek 调用")
    parser.add_argument("--recheck", action="store_true",
                        help="用复测 prompt 新增一条录制，不覆盖首次证据（仅 interpreter）")
    parser.add_argument("--role", choices=_KNOWN_ROLES, default="interpreter",
                        help="要录制的认知角色（interpreter 之外供 B1 多角色录制）")
    args = parser.parse_args()
    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml", apply_env=True)
    llm_settings = settings.llm.model_copy(update={
        "cassette": settings.llm.cassette.model_copy(update={"record": True}),
    })
    llm = OpenAICompatLLM(llm_settings, ROOT)
    request = _build_request(args.role, llm_settings, args.recheck)
    response = llm.complete(request)
    print(f"[P3] source={response.source} model={response.model} role={request.role} "
          f"tokens={response.usage.total_tokens} recheck={args.recheck}")
    print(f"  响应摘录：{response.raw[:200]}")
    logger.info("录制完成，请用 provider=cassette 验证回放一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
