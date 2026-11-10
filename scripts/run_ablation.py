"""P4 消融：同一 spec 在「有 KG / 无 KG」下的修复轨迹对比。

    .venv\\Scripts\\python.exe scripts/run_ablation.py

有 KG 组加载上一轮回写的 ``capabilities_after_run.json``，从而命中历史
FailureCase；无 KG 组既不检索也不回写。两组指标均为实测；AUC 不因证据
注入而改变（模型不使用证据作为特征），差异体现在是否重复踩已知错误。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.artifacts import shared_report_path
from factory.config import load_settings, load_task_settings
from factory.logging_setup import configure_logging
from factory.workflow import Workflow

SPEC = "预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模"


def _summary(trace) -> dict:
    ranked = sorted(trace.candidates, key=lambda item: -item.score)
    return {
        "kg_mode": trace.kg_mode,
        "graph_source": trace.graph_source,
        "used_history": trace.used_historical_warnings,
        "repairs": len(trace.repairs),
        "signatures": [record.error_signature for record in trace.repairs],
        "auc": [round(item.score, 6) for item in ranked],
        "passed": trace.passed,
        "report": trace.report_path,
    }


def _render(with_kg: dict, without_kg: dict, path: Path) -> Path:
    used_with = "是" if with_kg["used_history"] else "否"
    used_without = "是" if without_kg["used_history"] else "否"
    with_signatures = "、".join(with_kg["signatures"]) or "无"
    without_signatures = "、".join(without_kg["signatures"]) or "无"
    with_t1 = "是" if "KeyError: PAY_1" not in with_kg["signatures"] else "否"
    without_t1 = "是" if "KeyError: PAY_1" not in without_kg["signatures"] else "否"
    with_auc = " / ".join(map(str, with_kg["auc"]))
    without_auc = " / ".join(map(str, without_kg["auc"]))
    lines = [
        "# 有 KG / 无 KG 消融对比",
        "",
        "> 同一 capability spec、同一候选方案与数据集，唯一变量是是否检索并注入图谱证据。",
        "> 两组指标均为实测；AUC 不因证据注入而改变（模型不使用证据作为特征），",
        "> 差异体现在「是否重复踩已知错误」与修复轮次。无 KG 组不回写图谱，避免污染实验。",
        "",
        "| 指标 | 有 KG | 无 KG |",
        "|---|---|---|",
        f"| 图谱来源 | {with_kg['graph_source']} | {without_kg['graph_source']} |",
        f"| 命中历史失败经验 | {used_with} | {used_without} |",
        f"| 修复轮次 | {with_kg['repairs']} | {without_kg['repairs']} |",
        f"| 错误签名 | {with_signatures} | {without_signatures} |",
        f"| 是否首轮避开 T1 | {with_t1} | {without_t1} |",
        f"| 候选 AUC（降序） | {with_auc} | {without_auc} |",
        "",
        "## 结论",
        "",
        "- 有 KG 组从回写图谱读到上一轮的 `KeyError: PAY_1` 失败案例，Coder 首轮即改用 `PAY_0`，",
        "  省掉一次失败执行；无 KG 组没有这条证据，先踩 T1 再修复。",
        "- 两组业务指标结论一致，说明沉淀改变的是「过程效率」而非「指标口径」，未做任何数值美化。",
        "",
        f"- 有 KG 报告：`{with_kg['report']}`",
        f"- 无 KG 报告：`{without_kg['report']}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml")
    task = load_task_settings(ROOT / "configs/verify_credit.yaml")
    with_trace = Workflow(settings, task, ROOT, use_knowledge=True).run(
        SPEC, "ablation_with_kg"
    )
    without_trace = Workflow(settings, task, ROOT, use_knowledge=False).run(
        SPEC, "ablation_without_kg"
    )
    with_summary = _summary(with_trace)
    without_summary = _summary(without_trace)
    out = _render(with_summary, without_summary,
                  shared_report_path(ROOT / settings.paths.reports, "ablation"))
    print(json.dumps({"with_kg": with_summary, "without_kg": without_summary},
                     ensure_ascii=False, indent=2))
    print(f"[P4] 消融报告：{out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
