"""P4 消融：同一 spec 在「有 KG / 无 KG」下的修复轨迹对比。

    .venv\\Scripts\\python.exe scripts/run_ablation.py

有 KG 组加载上一轮回写的 ``*_after_run.json``，从而拿到历史实验记录里的
「主指标更高」的算法族；无 KG 组既不检索也不回写。两组指标均为实测，
差异体现在「指标层失败后能否按历史证据换族修复」，而不是把某个候选的
分数算得更高。
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
        "actions": [record.patch_source for record in trace.repairs],
        "passed_count": sum(1 for item in trace.candidates if item.passed),
        "candidates": len(trace.candidates),
        "auc": [round(item.score, 6) for item in ranked],
        "passed": trace.passed,
        "report": trace.report_path,
    }


def _render(with_kg: dict, without_kg: dict, path: Path) -> Path:
    used_with = "是" if with_kg["used_history"] else "否"
    used_without = "是" if without_kg["used_history"] else "否"
    with_signatures = "、".join(with_kg["signatures"]) or "无"
    without_signatures = "、".join(without_kg["signatures"]) or "无"
    with_actions = "、".join(with_kg["actions"]) or "无"
    without_actions = "、".join(without_kg["actions"]) or "无"
    with_auc = " / ".join(map(str, with_kg["auc"]))
    without_auc = " / ".join(map(str, without_kg["auc"]))
    lines = [
        "# 有 KG / 无 KG 消融对比",
        "",
        "> 同一 capability spec、同一候选方案与数据集，唯一变量是是否检索并注入图谱证据。",
        "> 两组指标均为实测；模型、特征与数据完全相同，主指标不因证据注入而改变。",
        "> 差异体现在「指标层失败后，能否按图谱里的历史高分记录换族修复」。",
        "> 无 KG 组不回写图谱，避免污染实验。",
        "",
        "| 指标 | 有 KG | 无 KG |",
        "|---|---|---|",
        f"| 图谱来源 | {with_kg['graph_source']} | {without_kg['graph_source']} |",
        f"| 历史经验实际生效 | {used_with} | {used_without} |",
        f"| 修复轮次 | {with_kg['repairs']} | {without_kg['repairs']} |",
        f"| 修复动作 | {with_actions} | {without_actions} |",
        f"| 错误签名 | {with_signatures} | {without_signatures} |",
        (f"| 四层通过的候选数 | {with_kg['passed_count']}/{with_kg['candidates']} | "
         f"{without_kg['passed_count']}/{without_kg['candidates']} |"),
        f"| 候选 AUC（降序） | {with_auc} | {without_auc} |",
        "",
        "## 结论",
        "",
        "- 有 KG 组从历史实验记录里拿到「主指标更高的算法族」排序，指标层失败后按该排序",
        "  换族重生成并复验，把原本不达标的候选救回；无 KG 组没有这条证据，指标层失败只能",
        "  如实记为 `no_change`，候选维持 FAIL。",
        "- 两组 AUC 的绝对值由模型与数据决定，不因证据注入而变化；沉淀改变的是「修复是否",
        "  有据可依」与「候选通过率」，未做任何数值美化。",
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
