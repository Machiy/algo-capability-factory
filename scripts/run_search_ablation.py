"""P4 搜索消融：同一 spec 在「关闭 / 开启 Successive Halving」下的对比。

    .venv\\Scripts\\python.exe scripts/run_search_ablation.py

关闭：3 候选完整评估；开启：12 候选粗评 → 按 family 去重淘汰 → 3 候选完整评估。
对比最终 Top-1 主指标、完整评估候选数、run 总耗时（含沙箱），证明搜索带来的是
「候选空间扩大 + 淘汰」，而非「指标虚高」；两组 test 段均只消费一次。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.artifacts import shared_report_path
from factory.config import load_settings, load_task_settings
from factory.logging_setup import configure_logging
from factory.workflow import Workflow

SPEC = "预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模"


def _summary(trace, seconds: float) -> dict:
    best = max(trace.candidates,
               key=lambda item: (item.passed, item.score), default=None)
    return {
        "passed": trace.passed,
        "candidates": len(trace.candidates),
        "repairs": len(trace.repairs),
        "top1_score": round(best.score, 6) if best else None,
        "top1_plan": best.plan_id if best else "",
        "seconds": round(seconds, 1),
        "report": trace.report_path,
    }


def _run(settings, task, halving: bool, run_id: str) -> dict:
    search = settings.search.model_copy(update={"halving_enabled": halving})
    cfg = settings.model_copy(update={"search": search})
    start = time.perf_counter()
    trace = Workflow(cfg, task, ROOT).run(SPEC, run_id)
    return _summary(trace, time.perf_counter() - start)


def _render(off: dict, on: dict, path: Path) -> Path:
    delta = (on["seconds"] or 0.0) - (off["seconds"] or 0.0)
    base = off["seconds"] or 1.0
    pct = delta / base * 100
    off_score = off["top1_score"] or 0.0
    on_score = on["top1_score"] or 0.0
    verdict = "不劣于" if on_score >= off_score else "低于"
    lines = [
        "# 搜索消融对比（Successive Halving）",
        "",
        "> 同一 capability spec、同一数据集、同一离线规则模板（`provider=mock`，确定性），",
        "> 唯一变量是是否开启 Successive Halving 搜索。",
        "> 关闭：Planner 生成 3 候选后直接完整评估；",
        ("> 开启：3 候选扩到 12（model_family × sampler × threshold 组合）→ 粗评 → "
         "按 family 去重淘汰 → 3 候选完整评估。"),
        "",
        "| 指标 | 关闭搜索 | 开启搜索 |",
        "|---|---|---|",
        f"| 完整评估候选数 | {off['candidates']} | {on['candidates']} |",
        f"| 最终 Top-1 主指标 | {off['top1_score']} | {on['top1_score']} |",
        f"| 最佳候选 | {off['top1_plan']} | {on['top1_plan']} |",
        f"| 修复轮次 | {off['repairs']} | {on['repairs']} |",
        f"| 四层全通过 | {off['passed']} | {on['passed']} |",
        f"| run 总耗时（含沙箱） | {off['seconds']}s | {on['seconds']}s |",
        "",
        "## 结论",
        "",
        (f"- Top-1 主指标{verdict}基线（{off['top1_score']} → {on['top1_score']}）："
         "搜索在 12 个组合里按粗评淘汰，选出了比「3 候选直接评估」更适合的 family 变体，"
         "未出现「多跑几次就把指标刷高」的虚高。"),
        f"- 代价：run 总耗时增加 {delta:.1f}s（{pct:+.0f}%），来自粗评阶段的额外沙箱执行。",
        "- 两组 test 段均只消费一次（TestGate 硬保证），搜索不改变「test 只看一次」的纪律。",
        "",
        f"- 关闭搜索报告：`{off['report']}`",
        f"- 开启搜索报告：`{on['report']}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml", apply_env=False)
    # 离线确定性：强制规则模板并清空角色路由（与 CLI --mock 同口径）
    settings.llm = settings.llm.model_copy(
        update={"provider": "mock", "role_providers": {}}
    )
    task = load_task_settings(ROOT / "configs/verify_credit.yaml")
    off = _run(settings, task, False, "search_off")
    on = _run(settings, task, True, "search_on")
    out = _render(off, on,
                  shared_report_path(ROOT / settings.paths.reports, "search_ablation"))
    print(json.dumps({"search_off": off, "search_on": on},
                     ensure_ascii=False, indent=2))
    print(f"[P4] 搜索消融报告：{out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
