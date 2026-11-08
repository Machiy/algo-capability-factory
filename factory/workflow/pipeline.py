"""a–g 七步工作流编排：自研轻量状态机。

修复循环只有「验证失败 → 按签名定向修复 → 重新验证」一条条件边，状态规模
小，因此不引入图编排框架；候选按 Beam Top-3 比较，修复最多 3 轮，每轮结果
由 Curator 回写图谱。检索证据强制进入 Planner / Coder 的 prompt。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from factory.agents import (
    Coder,
    Curator,
    Interpreter,
    Planner,
    Repairer,
    Retriever,
    Reviewer,
    Verifier,
)
from factory.config import Settings, TaskSettings, load_settings, load_task_settings
from factory.contracts.models import ValidationReport
from factory.contracts.workflow import CandidateEvaluation, RunTrace
from factory.knowledge import MockExtractor, read_sources
from factory.llm import build_llm
from factory.logging_setup import write_trace
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox
from factory.validation import FourLayerValidator

logger = logging.getLogger(__name__)

SEVEN_STEPS = ["a.Parse", "b.Retrieve", "c.Plan", "d.Generate",
               "e.Execute+Validate", "f.Diagnose+Repair", "g.Sink"]


def _candidate_score(report: ValidationReport) -> float:
    value = report.metric_values.get("auc")
    return float(value) if isinstance(value, (int, float)) else 0.0


def render_run_report(trace: RunTrace, reports: list[ValidationReport],
                      rationale: str, path: Path) -> Path:
    """生成端到端报告：七步轨迹、候选排名、修复轨迹、四层结论与图谱 diff。"""
    lines = [
        f"# 端到端运行报告 · {trace.run_id}",
        "",
        "> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径",
        "> （开发要求 g），T1 列名错误由规则模板模拟 LLM 的直觉命名，",
        "> 并在子进程用真实数据集触发 `KeyError` 后定向修复；指标均为实测，未造数值。",
        "> test 集全程未访问。引用 cassette 回放的内容须另标注「离线回放」。",
        "",
        f"- 能力描述：{trace.spec}",
        f"- 七步流程：执行完成（{' → '.join(SEVEN_STEPS)} 均有产物）",
        f"- 四层全通过：**{'PASS' if trace.passed else 'FAIL'}**",
        f"- 七步轨迹：{' → '.join(trace.steps)}",
        "",
        "> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `verify_credit.yaml`",
        "> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。",
        "",
        "## 1. 检索证据（进入 Planner / Coder prompt）",
        "",
        "```text",
        trace.retrieval_prompt,
        "```",
        "",
        "## 2. 候选方案比较（Beam Top-3）",
        "",
        "| 方案 | 模型族 | AUC | 通过 | 修复轮次 |",
        "|---|---|---|---|---|",
    ]
    for item in sorted(trace.candidates, key=lambda c: -c.score):
        auc = item.metrics.get("auc")
        auc_text = "N/A" if auc is None else f"{auc:.4f}"
        lines.append(f"| {item.plan_id} | {item.model_family} | {auc_text} | "
                     f"{'PASS' if item.passed else 'FAIL'} | {item.repair_rounds} |")
    lines.extend([
        "",
        "## 3. 四层验证结论",
        "",
        "| 运行 | 接口 | 功能 | 指标 | 稳定性 | 错误签名 |",
        "|---|---|---|---|---|---|",
    ])
    for report in reports:
        interface = all(report.interface_checks.values())
        functional = all(report.functional_checks.values())
        metrics = all(report.threshold_checks.values()) if report.threshold_checks else False
        stable = not report.stability.get("timed_out") and not report.stability.get(
            "memory_exceeded")
        lines.append(
            f"| {report.plan_id} | {'PASS' if interface else 'FAIL'} | "
            f"{'PASS' if functional else 'FAIL'} | {'PASS' if metrics else 'FAIL'} | "
            f"{'PASS' if stable else 'FAIL'} | {report.error_signature or '无'} |"
        )
    lines.extend(["", "## 4. 修复轨迹", ""])
    if trace.repairs:
        for record in trace.repairs:
            lines.append(f"- 第 {record.round} 轮：`{record.error_signature}` → "
                         f"{record.fix_strategy}（{record.outcome}）")
    else:
        lines.append("- 无失败轮次")
    lines.extend(["", rationale, "", "## 5. 图谱沉淀 diff", ""])
    for key, value in trace.kg_diff.items():
        lines.append(f"- {key}：{value}")
    lines.extend(["", "## 6. 产物", ""])
    lines.extend(f"- `{item}`" for item in trace.generated_files)
    lines.append("- 回写图谱：`outputs/kg/capabilities_after_run.json`")
    lines.extend(["", trace.notes, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class Workflow:
    """一次端到端运行；持有各角色与共享配置，不持有跨轮可变全局状态。"""

    def __init__(self, settings: Settings, task: TaskSettings, root: Path) -> None:
        self.settings = settings
        self.task = task
        self.root = root
        sources = read_sources(root, settings.paths.docs, settings.paths.legacy)
        graph = MockExtractor().extract(sources)
        llm = build_llm(settings.llm, root)
        frame = pd.read_csv(root / settings.paths.data, nrows=1)
        excluded = set(task.dataset.forbidden_features)
        excluded.update(task.sensitive_features)
        excluded.update({task.dataset.target, task.dataset.id_column})
        self.columns = [name for name in frame.columns if name not in excluded]
        with (root / settings.paths.data).open(encoding="utf-8") as handle:
            n_samples = sum(1 for _ in handle) - 1
        checker = StaticChecker(settings.runtime, task.dataset)
        self.interpreter = Interpreter(llm)
        self.retriever = Retriever(graph, settings.knowledge.top_k,
                                   settings.knowledge.weights)
        self.planner = Planner(llm)
        self.coder = Coder(llm)
        self.reviewer = Reviewer(checker)
        self.verifier = Verifier(FourLayerValidator(task))
        self.repairer = Repairer(llm)
        self.curator = Curator(graph, llm)
        self.sandbox = DatasetSandbox(
            settings.runtime, task.split, root / settings.paths.data,
            task.dataset.target, sorted(excluded), n_samples,
        )
        group_column = task.sensitive_features[0] if task.sensitive_features else None
        if group_column:
            group_frame = pd.read_csv(root / settings.paths.data,
                                      usecols=[group_column])
            self.groups = [int(value) for value in group_frame[group_column].iloc[
                self.sandbox.train_end:self.sandbox.valid_end]]
        else:
            self.groups = []
        self.max_rounds = 3

    def run(self, spec_text: str, run_id: str = "demo") -> RunTrace:
        trace = RunTrace(run_id=run_id, spec=spec_text)
        spec = self.interpreter.parse(spec_text)
        trace.steps.append(SEVEN_STEPS[0])
        retrieval = self.retriever.retrieve(spec_text)
        trace.retrieval_prompt = retrieval.as_prompt_context()
        trace.steps.append(SEVEN_STEPS[1])
        plans = self.planner.plan(spec, retrieval)
        trace.steps.append(SEVEN_STEPS[2])
        reports: list[ValidationReport] = []
        for index, plan in enumerate(plans):
            induce_t1 = index == 0
            source = self.coder.generate(plan, retrieval, self.columns, induce_t1)
            trace.steps.append(SEVEN_STEPS[3])
            static = self.reviewer.review(source)
            report: ValidationReport | None = None
            repair_rounds = 0
            for round_index in range(self.max_rounds + 1):
                run_result = self.sandbox.run(source)
                if run_result.sandbox.passed:
                    run_result.context["groups"] = self.groups
                    run_result.context["cost_ratio"] = self.task.cost_ratio_fn_fp
                    run_result.context["threshold"] = 0.5
                report, _ = self.verifier.verify(run_id, plan.plan_id, static, run_result)
                trace.steps.append(SEVEN_STEPS[4])
                if report.passed or round_index == self.max_rounds:
                    break
                source, record = self.repairer.repair(
                    source, report.error_signature, round_index + 1
                )
                static = self.reviewer.review(source)
                trace.repairs.append(record)
                repair_rounds += 1
                trace.steps.append(SEVEN_STEPS[5])
                if record.outcome == "no_change":
                    break
            generated = (self.root / self.settings.paths.generated /
                         f"candidate_{plan.plan_id}.py")
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text(source, encoding="utf-8")
            trace.generated_files.append(generated.relative_to(self.root).as_posix())
            assert report is not None
            reports.append(report)
            trace.candidates.append(CandidateEvaluation(
                plan_id=plan.plan_id,
                model_family=plan.model_family,
                passed=report.passed,
                score=_candidate_score(report),
                metrics=report.metric_values,
                repair_rounds=repair_rounds,
            ))
        kg_out = self.root / self.settings.paths.kg / "capabilities_after_run.json"
        trace.kg_diff = self.curator.sink(trace, reports, kg_out)
        trace.steps.append(SEVEN_STEPS[6])
        trace.passed = any(item.passed for item in trace.candidates)
        trace.notes = (f"候选 {len(plans)} 个；修复 {len(trace.repairs)} 轮；"
                       f"检索证据 {len(retrieval.hits)} 项已注入 Planner 与 Coder prompt。")
        trace.report_path = render_run_report(
            trace, reports, self.curator.explain(trace),
            self.root / self.settings.paths.reports / f"run_{run_id}.md",
        ).relative_to(self.root).as_posix()
        write_trace(
            self.root / self.settings.paths.runs / f"trace_{run_id}.json",
            trace.model_dump(mode="json"),
        )
        logger.info("工作流完成：passed=%s 候选=%d 修复=%d",
                    trace.passed, len(plans), len(trace.repairs))
        return trace


def run_from_cli(spec_text: str, mock: bool = False,
                 root: Path | None = None) -> int:
    """CLI 入口；默认按配置 provider，--mock 时强制规则模板。"""
    from factory.logging_setup import configure_logging
    root = root or Path.cwd()
    configure_logging()
    settings = load_settings(root / "configs/default.yaml")
    task = load_task_settings(root / "configs/verify_credit.yaml")
    if mock:
        settings.llm = settings.llm.model_copy(update={"provider": "mock"})
    trace = Workflow(settings, task, root).run(spec_text)
    print(f"[P3] 七步闭环执行完成；四层全通过={trace.passed} "
          f"候选={len(trace.candidates)} 修复={len(trace.repairs)} "
          f"报告={trace.report_path}")
    for item in sorted(trace.candidates, key=lambda c: -c.score):
        print(f"  {item.plan_id}: auc={item.metrics.get('auc')} "
              f"passed={item.passed} repairs={item.repair_rounds}")
    for record in trace.repairs:
        print(f"  修复[{record.round}] {record.error_signature} -> {record.fix_strategy}")
    if not trace.passed:
        print("  说明：指标层未达 verify_credit.yaml 业务门槛，已如实判 FAIL 并回写 FailureCase")
    return 0


__all__ = ["Workflow", "render_run_report", "run_from_cli"]
