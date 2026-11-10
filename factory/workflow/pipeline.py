"""a–g 七步工作流编排：LangGraph StateGraph。

用现成图框架的「节点 + 条件边」表达修复循环与候选循环，不再自研状态机：
``execute`` 后按四层结论分支到 ``repair`` 或 ``finalize``，``repair`` 后按
是否无可行动作分支回 ``execute`` 或直接收尾，``finalize`` 后决定是否进入
下一个候选。输出仍是 ``RunTrace`` 契约，七步顺序、修复轮次与产物保持不变。
检索证据强制进入 Planner / Coder 的 prompt。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TypedDict

import pandas as pd
from langgraph.graph import END, StateGraph

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
from factory.artifacts import kg_stem, report_path, scene_of, trace_path
from factory.config import Settings, TaskSettings, load_settings, load_task_settings
from factory.contracts.intake import IntakeGuidance, IntakeVerdict
from factory.contracts.knowledge import RetrievalResult
from factory.contracts.models import CandidatePlan, CapabilitySpec, ValidationReport
from factory.contracts.validation import StaticCheckResult
from factory.contracts.workflow import CandidateEvaluation, RunTrace, TestEvaluation
from factory.intake import IntakeGuide, SpecRejected, render_guidance
from factory.knowledge import MockExtractor, read_sources
from factory.knowledge.graph import load_graph
from factory.knowledge.merge import merge_graphs
from factory.llm import build_llm
from factory.logging_setup import write_trace
from factory.plugins import load_plugins
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox
from factory.validation import FourLayerValidator

logger = logging.getLogger(__name__)

# run_id 同时用于文件名与图谱节点 id：限死字符集并禁止「..」，杜绝路径穿越
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

SEVEN_STEPS = ["a.Parse", "b.Retrieve", "c.Plan", "d.Generate",
               "e.Execute+Validate", "f.Diagnose+Repair", "g.Sink"]

# 入口体检结论在报告里的可读名称（REJECT 仅出现在 --force 强制放行的运行里）
INTAKE_LABELS = {
    IntakeVerdict.OK: "OK（要素齐全）",
    IntakeVerdict.CLARIFY: "CLARIFY（可继续，缺失要素已提示）",
    IntakeVerdict.REJECT: "REJECT（不可执行，已 --force 强制放行）",
}


class _GraphState(TypedDict, total=False):
    """LangGraph 状态：全部为契约对象或标量，不引入跨轮隐式全局状态。"""

    spec_text: str
    run_id: str
    trace: RunTrace
    guidance: IntakeGuidance
    spec: CapabilitySpec
    retrieval: RetrievalResult
    plans: list[CandidatePlan]
    plan: CandidatePlan
    candidate_index: int
    round_index: int
    repair_rounds: int
    source: str
    static: StaticCheckResult
    report: ValidationReport
    reports: list[ValidationReport]
    last_repair_no_change: bool


def _candidate_score(report: ValidationReport, metric_name: str = "auc",
                     direction: str = "maximize") -> float:
    """按任务主指标给候选打分，统一成「越大越好」便于排序。

    RMSE 这类 ``direction: minimize`` 的指标取负号；指标算不出时退化为 0，
    不伪造数值（原始值仍保留在 ``metrics`` 里）。
    """
    value = report.metric_values.get(metric_name)
    if not isinstance(value, (int, float)):
        return 0.0
    return float(value) if direction != "minimize" else -float(value)


def render_intake_section(guidance: IntakeGuidance | None) -> list[str]:
    """报告第 0 节：入口体检结论，证明用户输入被引导过而非直接灌进流水线。"""
    if guidance is None:
        return []
    elements = "、".join(guidance.matched_elements) or "无"
    missing = "、".join(guidance.missing_elements) or "无"
    lines = [
        "## 0. 输入引导（入口体检）",
        "",
        f"- 结论：**{INTAKE_LABELS[guidance.verdict]}**，要素完备度 {guidance.score:.2f}",
        f"- 已表达要素：{elements}",
        f"- 缺失要素：{missing}",
    ]
    for issue in guidance.issues:
        hint = f"（建议：{issue.hint}）" if issue.hint else ""
        lines.append(f"- 问题 `{issue.code}`：{issue.message}{hint}")
    if guidance.suggestion:
        lines.append(f"- 引导建议：{guidance.suggestion}")
    lines.append("")
    return lines


KG_DIFF_LABELS = {
    "nodes_added": "新增节点",
    "edges_added": "新增边",
    "runs_recorded": "运行记录 ValidationRun（本次留痕，可随重跑覆盖）",
    "failures_merged": "失败案例证据合并（独立 run 数累加）",
    "lessons_promoted": "本次提升为教训（跨运行知识）",
    "lessons_total": "图谱内教训总数",
}


def render_kg_diff(diff: dict[str, int]) -> list[str]:
    """把图谱 diff 分成「知识」与「运行记录」两类，避免把日志当成沉淀成果。"""
    if not diff:
        return ["- 消融对照组不回写图谱（避免污染实验口径）"]
    lines = ["> 运行记录只用于追溯、可被重跑覆盖；教训跨运行成立，随证据累积置信度。", ""]
    for key, value in diff.items():
        lines.append(f"- {KG_DIFF_LABELS.get(key, key)}：{value}")
    return lines


def render_run_report(trace: RunTrace, reports: list[ValidationReport],
                      rationale: str, path: Path, metric_name: str = "auc",
                      task_config: str = "verify_credit.yaml",
                      kg_path: str = "outputs/kg/credit_kg_after_run.json",
                      run_log_path: str = "",
                      text_mode: bool = False) -> Path:
    """生成端到端报告：七步轨迹、候选排名、修复轨迹、四层结论与图谱 diff。"""
    live_llm = (trace.interpreter_source == "deepseek_api"
                or any(source == "llm" for source in trace.code_sources.values()))
    if live_llm:
        header = [
            "> 本报告为真实运行的产物，本次**全链路接入真实 LLM**",
            "> （DeepSeek OpenAI 兼容接口，Interpreter / Planner / Coder / Repairer / Curator 实时调用）。",
            "> LLM 生成代码先过 AST 静态检查才采用；指标均为子进程沙箱在真实数据集上的实测，未造数值。",
        ]
        if not text_mode:
            header.append("> T1 列名错误由 LLM 生成代码按直觉写成 `PAY_1`，"
                          "在子进程用真实数据集触发 `KeyError` 后定向修复。")
    else:
        header = [
            "> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径",
            "> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。",
        ]
        if not text_mode:
            header.append("> T1 列名错误由规则模板模拟 LLM 的直觉命名，"
                          "并在子进程用真实数据集触发 `KeyError` 后定向修复。")
    test_eval = trace.test_evaluation
    if test_eval is not None and test_eval.consumed:
        header.append("> test 段仅在候选比较结束后对最佳候选评估一次，"
                      "不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。")
    else:
        header.append("> test 段本轮未消费。引用 cassette 回放的内容须另标注「离线回放」。")
    lines = [
        f"# 端到端运行报告 · {trace.run_id}",
        "",
        *header,
        "",
        f"- 能力描述：{trace.spec}",
        f"- 能力理解来源：{trace.interpreter_source}",
        f"- 知识图谱：{trace.kg_mode}（图谱来源 {trace.graph_source}）",
        f"- 历史失败经验命中：{'是' if trace.used_historical_warnings else '否'}",
        f"- 七步流程：执行完成（{' → '.join(SEVEN_STEPS)} 均有产物）",
        f"- 四层全通过：**{'PASS' if trace.passed else 'FAIL'}**",
        f"- 七步轨迹：{' → '.join(trace.steps)}",
        "",
        f"> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `{task_config}`",
        "> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。",
        "",
        *render_intake_section(trace.intake),
        f"## 1. 检索证据（进入 Planner / Coder prompt，含 {len(trace.lessons)} 条系统级教训）",
        "",
        "```text",
        trace.retrieval_prompt,
        "```",
        "",
        f"## 2. 候选方案比较（Beam Top-3，主指标 {metric_name}）",
        "",
        f"| 方案 | 模型族 | {metric_name} | 通过 | 代码来源 | 修复轮次 |",
        "|---|---|---|---|---|---|",
    ]
    for item in sorted(trace.candidates, key=lambda c: -c.score):
        value = item.metrics.get(metric_name)
        value_text = "N/A" if value is None else f"{value:.4f}"
        code_source = trace.code_sources.get(item.plan_id, "template")
        lines.append(f"| {item.plan_id} | {item.model_family} | {value_text} | "
                     f"{'PASS' if item.passed else 'FAIL'} | {code_source} | "
                     f"{item.repair_rounds} |")
    lines.extend([
        "",
        "## 3. 四层验证结论",
        "",
        "| 运行 | 接口 | 功能 | 指标 | 稳定性 | 确定性 Δ | 错误签名 |",
        "|---|---|---|---|---|---|---|",
    ])
    for report in reports:
        interface = all(report.interface_checks.values())
        functional = all(report.functional_checks.values())
        metrics = all(report.threshold_checks.values()) if report.threshold_checks else False
        stable = not report.stability.get("timed_out") and not report.stability.get(
            "memory_exceeded")
        # 确定性证据来自沙箱重复 fit 的实测差值；None 表示本轮未测
        variance = report.stability.get("repeat_variance")
        variance_text = "未测" if variance is None else f"{float(variance):.2e}"
        lines.append(
            f"| {report.plan_id} | {'PASS' if interface else 'FAIL'} | "
            f"{'PASS' if functional else 'FAIL'} | {'PASS' if metrics else 'FAIL'} | "
            f"{'PASS' if stable else 'FAIL'} | {variance_text} | "
            f"{report.error_signature or '无'} |"
        )
    lines.extend(["", "## 4. 修复轨迹", ""])
    if trace.repairs:
        for record in trace.repairs:
            lines.append(f"- 第 {record.round} 轮：`{record.error_signature}` → "
                         f"{record.fix_strategy}（{record.outcome}）")
    else:
        lines.append("- 无失败轮次")
    lines.extend(["", rationale, "", "## 5. 终评（test 段，仅一次）", ""])
    if test_eval is None:
        lines.append("- 本轮未启用终评（`workflow.evaluate_on_test=false`）")
    elif not test_eval.consumed:
        lines.append(f"- 未消费 test 段：{test_eval.note}")
    else:
        lines.append(f"- 终评候选：`{test_eval.plan_id}`；{test_eval.note}")
        lines.extend(["", "| 指标 | test 实测 |", "|---|---|"])
        for name, value in test_eval.metrics.items():
            value_text = "N/A" if value is None else f"{value:.4f}"
            lines.append(f"| {name} | {value_text} |")
    lines.extend(["", "## 6. 图谱沉淀（知识 vs 运行记录）", ""])
    lines.extend(render_kg_diff(trace.kg_diff))
    if run_log_path:
        lines.extend(["", f"- 运行日志另存：`{run_log_path}`（仅追溯，不参与检索）"])
    lines.extend(["", "## 7. 产物", ""])
    lines.extend(f"- `{item}`" for item in trace.generated_files)
    lines.append(f"- 回写图谱（知识）：`{kg_path}`")
    lines.extend(["", trace.notes, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class Workflow:
    """一次端到端运行；LangGraph 图在初始化时编译，节点复用已构造的角色。"""

    def __init__(self, settings: Settings, task: TaskSettings, root: Path,
                 use_knowledge: bool = True,
                 task_config: str = "configs/verify_credit.yaml",
                 kg_filename: str = "",
                 generated_subdir: str = "") -> None:
        self.settings = settings
        self.task = task
        self.root = root
        self.use_knowledge = use_knowledge
        self.task_config = task_config
        # 外部插件目录扫描：新增模板 / 指标只需放一个 .py，不改包内文件
        load_plugins(root)
        # 场景取自 verify_<scope>.yaml；所有产物命名统一走 factory.artifacts
        self.scope = scene_of(task_config)
        # 不同场景各自沉淀到独立图谱文件，避免跨场景指标混进同一份统计
        self.kg_filename = kg_filename or f"{kg_stem(self.scope, 'after_run')}.json"
        # 不同场景的生成代码分目录存放，避免后跑的覆盖先跑的
        self.generated_subdir = generated_subdir or self.scope
        after_run = root / settings.paths.kg / self.kg_filename
        loaded = load_graph(after_run) if use_knowledge else None
        # 场景自带能力材料时抽自己的子图，避免把其他领域的约束注入 prompt；
        # 共享材料（工程教训库）无论哪个场景都读，系统级知识不按场景切分
        docs_dir = task.knowledge.docs or settings.paths.docs
        legacy_dir = (task.knowledge.legacy if task.knowledge.docs
                      else settings.paths.legacy)
        shared = task.knowledge.shared or settings.knowledge.shared_docs
        if loaded is None:
            sources = read_sources(root, docs_dir, legacy_dir, shared)
            graph = MockExtractor(task.dataset_profile).extract(sources)
            self.graph_source = "sources"
        else:
            # 材料知识以最新抽取为准，运行沉淀（失败案例 / 教训 / 能力版本）叠加其上。
            # 直接整份沿用旧图谱会让新增材料与新增教训规则永远不生效。
            fresh = MockExtractor(task.dataset_profile).extract(
                read_sources(root, docs_dir, legacy_dir, shared))
            graph = merge_graphs(fresh, loaded)
            self.graph_source = "sources+after_run"
            logger.info("加载上一轮回写图谱：%s（%d 节点），与材料抽取合并",
                        after_run, len(loaded.nodes))
        # 入口引导：描述不可执行时先追问 / 给示例，不把噪声直接灌进七步闭环。
        # 判据来自两个 yaml 的 intake 段，本类只负责编排。
        self.intake = IntakeGuide(
            settings.intake, task.intake,
            configs_dir=root / "configs",
            task_config=task_config,
            graph_path=after_run,
        )
        llm = build_llm(settings.llm, root)
        self.task_type = task.task_type
        self.text_column = task.dataset.text_column
        self.sandbox_mode = ("text" if self.text_column
                             else "regression" if task.task_type == "tabular_regression"
                             else "tabular")
        self.metric_name = task.metrics[0].name if task.metrics else "auc"
        self.metric_direction = task.metrics[0].direction if task.metrics else "maximize"
        self.families = list(task.candidates.model_families)
        excluded = set(task.dataset.forbidden_features)
        excluded.update(task.sensitive_features)
        excluded.update({task.dataset.target, task.dataset.id_column})
        excluded.discard("")
        # 任务自带数据集路径时优先用它，否则回落到全局 paths.data
        data_path = root / (task.dataset.path or settings.paths.data)
        frame = pd.read_csv(data_path, nrows=1)
        # 文本任务不按表格列选特征，改由模板声明的 TEXT_COLUMN 驱动
        self.columns = [] if self.text_column else [
            name for name in frame.columns if name not in excluded
        ]
        with data_path.open(encoding="utf-8") as handle:
            n_samples = sum(1 for _ in handle) - 1
        checker = StaticChecker(settings.runtime, task.dataset)
        self.interpreter = Interpreter(llm, settings.llm)
        self.retriever = Retriever(graph, settings.knowledge.top_k,
                                   settings.knowledge.weights,
                                   settings.knowledge.lesson_prompt_limit)
        self.planner = Planner(llm, settings.workflow.beam_width)
        self.coder = Coder(llm, checker)
        self.reviewer = Reviewer(checker)
        self.verifier = Verifier(FourLayerValidator(task))
        self.repairer = Repairer(llm)
        self.curator = Curator(graph, llm,
                               settings.knowledge.lesson_promote_threshold)
        self.sandbox = DatasetSandbox(
            settings.runtime, task.split, data_path,
            task.dataset.target, sorted(excluded), n_samples,
            text_column=self.text_column, mode=self.sandbox_mode,
        )
        self.data_path = data_path
        self.group_column = (task.sensitive_features[0]
                             if task.sensitive_features else "")
        self.groups = self._groups_for("valid")
        # 修复轮次、确定性重复次数与终评开关均来自 workflow 配置段
        self.max_rounds = settings.workflow.max_repair_rounds
        self.determinism_repeat = settings.workflow.determinism_repeat
        self.evaluate_on_test = settings.workflow.evaluate_on_test
        self._graph = self._build_graph()

    def _groups_for(self, segment: str) -> list[int]:
        """按评估段取敏感属性分组，供分组公平性指标使用。"""
        if not self.group_column:
            return []
        start, end = self.sandbox.segment_bounds(segment)
        frame = pd.read_csv(self.data_path, usecols=[self.group_column])
        return [int(value) for value in frame[self.group_column].iloc[start:end]]

    def _build_graph(self):
        builder = StateGraph(_GraphState)
        for name, node in (
            ("parse", self._n_parse),
            ("retrieve", self._n_retrieve),
            ("plan_step", self._n_plan),
            ("generate", self._n_generate),
            ("execute", self._n_execute),
            ("repair", self._n_repair),
            ("finalize", self._n_finalize),
            ("sink", self._n_sink),
        ):
            builder.add_node(name, node)
        builder.set_entry_point("parse")
        builder.add_edge("parse", "retrieve")
        builder.add_edge("retrieve", "plan_step")
        builder.add_edge("plan_step", "generate")
        builder.add_edge("generate", "execute")
        builder.add_conditional_edges("execute", self._after_execute,
                                      {"repair": "repair", "finalize": "finalize"})
        builder.add_conditional_edges("repair", self._after_repair,
                                      {"execute": "execute", "finalize": "finalize"})
        builder.add_conditional_edges("finalize", self._after_finalize,
                                      {"generate": "generate", "sink": "sink"})
        builder.add_edge("sink", END)
        return builder.compile()

    def _n_parse(self, state: _GraphState) -> dict:
        spec = self.interpreter.parse(state["spec_text"])
        trace = RunTrace(run_id=state["run_id"], spec=state["spec_text"],
                         interpreter_source=self.interpreter.last_source,
                         intake=state.get("guidance"))
        trace.steps.append(SEVEN_STEPS[0])
        return {"spec": spec, "trace": trace}

    def _n_retrieve(self, state: _GraphState) -> dict:
        if self.use_knowledge:
            retrieval = self.retriever.retrieve(state["spec_text"])
        else:
            # 消融对照组：不检索、不注入任何证据
            retrieval = RetrievalResult(query=state["spec_text"], top_k=0)
        trace = state["trace"]
        trace.retrieval_prompt = retrieval.as_prompt_context()
        trace.lessons = list(retrieval.lessons)
        trace.kg_mode = "with_kg" if self.use_knowledge else "without_kg"
        trace.graph_source = self.graph_source
        trace.steps.append(SEVEN_STEPS[1])
        return {"retrieval": retrieval, "trace": trace}

    def _n_plan(self, state: _GraphState) -> dict:
        plans = self.planner.plan(state["spec"], state["retrieval"],
                                  families=self.families, task_type=self.task_type)
        trace = state["trace"]
        trace.steps.append(SEVEN_STEPS[2])
        return {"plans": plans, "candidate_index": 0, "reports": [], "trace": trace}

    def _n_generate(self, state: _GraphState) -> dict:
        index = state["candidate_index"]
        plans = state["plans"]
        if not plans:
            # 兜底防线：Planner 已经会在空候选时回退配置，这里避免裸 IndexError
            raise ValueError("Planner 未能产出候选方案；请检查 llm.provider 与 Planner 输出格式")
        plan = plans[index]
        source = self.coder.generate(
            plan, state["retrieval"], self.columns, index == 0,
            task_type=self.task_type, text_column=self.text_column,
        )
        trace = state["trace"]
        # T1 列名经验只对表格场景有意义，文本场景不据此声称命中历史经验
        trace.used_historical_warnings = (not self.text_column) and any(
            "PAY_1" in warning for warning in state["retrieval"].failure_warnings
        )
        # 记录代码来源：llm 表示 LLM 代码通过静态检查后采用，template 表示回退
        trace.code_sources[plan.plan_id] = self.coder.last_source
        trace.steps.append(SEVEN_STEPS[3])
        return {
            "plan": plan, "source": source, "static": self.reviewer.review(source),
            "round_index": 0, "repair_rounds": 0, "last_repair_no_change": False,
            "trace": trace,
        }

    def _n_execute(self, state: _GraphState) -> dict:
        # repeat>=2 时子进程内二次 fit，产出 repeat_variance 供确定性检查
        run_result = self.sandbox.run(state["source"], repeat=self.determinism_repeat)
        if run_result.sandbox.passed:
            run_result.context["groups"] = self.groups
            run_result.context["cost_ratio"] = self.task.cost_ratio_fn_fp
            run_result.context["threshold"] = 0.5
        report, _ = self.verifier.verify(
            state["run_id"], state["plan"].plan_id, state["static"], run_result
        )
        trace = state["trace"]
        trace.steps.append(SEVEN_STEPS[4])
        return {"report": report, "trace": trace}

    def _after_execute(self, state: _GraphState) -> str:
        if state["report"].passed or state["round_index"] >= self.max_rounds:
            return "finalize"
        return "repair"

    def _n_repair(self, state: _GraphState) -> dict:
        source, record = self.repairer.repair(
            state["source"], state["report"].error_signature, state["round_index"] + 1
        )
        trace = state["trace"]
        trace.repairs.append(record)
        trace.steps.append(SEVEN_STEPS[5])
        return {
            "source": source, "static": self.reviewer.review(source),
            "round_index": state["round_index"] + 1,
            "repair_rounds": state["repair_rounds"] + 1,
            "last_repair_no_change": record.outcome == "no_change",
            "trace": trace,
        }

    def _after_repair(self, state: _GraphState) -> str:
        return "finalize" if state["last_repair_no_change"] else "execute"

    def _n_finalize(self, state: _GraphState) -> dict:
        plan, report = state["plan"], state["report"]
        generated = (self.root / self.settings.paths.generated /
                     self.generated_subdir / f"candidate_{plan.plan_id}.py")
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text(state["source"], encoding="utf-8")
        trace = state["trace"]
        trace.generated_files.append(generated.relative_to(self.root).as_posix())
        trace.candidates.append(CandidateEvaluation(
            plan_id=plan.plan_id,
            model_family=plan.model_family,
            passed=report.passed,
            score=_candidate_score(report, self.metric_name, self.metric_direction),
            metrics=report.metric_values,
            repair_rounds=state["repair_rounds"],
        ))
        reports = [*state["reports"], report]
        return {"candidate_index": state["candidate_index"] + 1,
                "reports": reports, "trace": trace}

    def _after_finalize(self, state: _GraphState) -> str:
        return ("generate" if state["candidate_index"] < len(state["plans"])
                else "sink")

    def _finalize_on_test(self, trace: RunTrace) -> TestEvaluation:
        """终评：最佳候选在 test 段只跑一次，结果仅入报告。

        纪律：先按 valid 指标选出最佳候选，再消费 test；test 指标不参与
        ``score`` 计算，也不触发新的修复轮次，避免用未来数据调参。
        """
        if not trace.candidates:
            return TestEvaluation(consumed=False, note="无可评估候选，test 段未消费")
        best = max(trace.candidates, key=lambda item: (item.passed, item.score))
        generated = (self.root / self.settings.paths.generated /
                     self.generated_subdir / f"candidate_{best.plan_id}.py")
        if not generated.is_file():
            return TestEvaluation(plan_id=best.plan_id, consumed=False,
                                 note="最佳候选源码缺失，test 段未消费")
        result = self.sandbox.run(generated.read_text(encoding="utf-8"), segment="test")
        if not result.sandbox.passed:
            return TestEvaluation(
                plan_id=best.plan_id, consumed=True,
                note=f"终评执行失败：{result.sandbox.error_signature}",
            )
        context = dict(result.context)
        context["groups"] = self._groups_for("test")
        context["cost_ratio"] = self.task.cost_ratio_fn_fp
        context["threshold"] = 0.5
        metrics = self.verifier.validator.evaluate_metrics(context)
        logger.info("终评（test 段，仅一次）：候选=%s", best.plan_id)
        return TestEvaluation(
            plan_id=best.plan_id, consumed=True,
            metrics={item.name: item.value for item in metrics},
            note="test 段本次一次性消费，未参与候选排序与修复决策",
        )

    def _n_sink(self, state: _GraphState) -> dict:
        trace = state["trace"]
        run_log_path = ""
        if self.use_knowledge:
            kg_out = self.root / self.settings.paths.kg / self.kg_filename
            trace.kg_diff = self.curator.sink(trace, state["reports"], kg_out)
            if self.curator.last_run_log_path is not None:
                run_log_path = self.curator.last_run_log_path.relative_to(
                    self.root).as_posix()
        else:
            # 消融对照组不回写，避免污染实验
            trace.kg_diff = {}
        trace.steps.append(SEVEN_STEPS[6])
        trace.passed = any(item.passed for item in trace.candidates)
        if self.evaluate_on_test:
            trace.test_evaluation = self._finalize_on_test(trace)
        trace.notes = (
            f"模式 {trace.kg_mode}（图谱来源 {trace.graph_source}）；"
            f"候选 {len(state['plans'])} 个；修复 {len(trace.repairs)} 轮；"
            f"历史失败经验命中 {'是' if trace.used_historical_warnings else '否'}；"
            f"检索证据 {len(state['retrieval'].hits)} 项已注入 "
            "Planner 与 Coder prompt。"
        )
        rationale = self.curator.explain(
            trace, retrieval=state["retrieval"],
            metric_name=self.metric_name,
            direction=self.metric_direction,
            threshold=self.task.metrics[0].threshold if self.task.metrics else None,
        )
        trace.report_path = render_run_report(
            trace, state["reports"], rationale,
            report_path(self.root / self.settings.paths.reports, self.scope, trace.run_id),
            metric_name=self.metric_name,
            task_config=Path(self.task_config).name,
            kg_path=f"{self.settings.paths.kg}/{self.kg_filename}",
            run_log_path=run_log_path,
            text_mode=bool(self.text_column),
        ).relative_to(self.root).as_posix()
        write_trace(
            trace_path(self.root / self.settings.paths.runs, self.scope, trace.run_id),
            trace.model_dump(mode="json"),
        )
        logger.info("工作流完成：passed=%s 候选=%d 修复=%d",
                    trace.passed, len(state["plans"]), len(trace.repairs))
        return {"trace": trace}

    def run(self, spec_text: str, run_id: str = "demo",
            force: bool = False) -> RunTrace:
        """用 LangGraph 执行七步，返回与旧状态机完全一致的 RunTrace。

        ``run_id`` 会拼进 ``run_<id>.md`` / ``trace_<id>.json`` 与图谱节点 id，
        因此入口处强制校验字符集，避免从 API 传参造成路径穿越。

        ``force=False`` 时先做入口体检：REJECT 的描述抛 ``SpecRejected``（附
        引导内容），CLARIFY 记 warning 但继续——用户对自己的描述有最终决定权，
        引导只负责把明显不可执行的输入挡在闭环之外。
        """
        if not _RUN_ID_PATTERN.match(run_id) or ".." in run_id:
            raise ValueError(
                f"run_id 只允许字母、数字、点、下划线与连字符（不得含 ..），"
                f"长度 1–64：{run_id!r}"
            )
        guidance = self.intake.review(spec_text)
        if guidance.verdict is IntakeVerdict.REJECT and not force:
            logger.warning("输入被入口引导拦下：%s",
                           "；".join(item.code for item in guidance.issues))
            raise SpecRejected(guidance)
        if guidance.verdict is IntakeVerdict.CLARIFY:
            logger.warning("输入引导：%s",
                           "；".join(item.message for item in guidance.issues))
        final = self._graph.invoke(
            {"spec_text": spec_text, "run_id": run_id, "guidance": guidance},
            config={"recursion_limit": 100},
        )
        return final["trace"]


def run_from_cli(spec_text: str, mock: bool = False,
                 root: Path | None = None,
                 task_config: str = "configs/verify_credit.yaml",
                 run_id: str = "demo",
                 kg_filename: str = "",
                 generated_subdir: str = "",
                 force: bool = False) -> int:
    """CLI 入口；默认按配置 provider，--mock 时强制规则模板。

    ``task_config`` 决定任务类型与指标门槛——换场景只换 yaml，不改代码。
    ``force=True`` 跳过入口引导的拦截，用于用户确认自己的描述没问题时。
    退出码：0 正常、2 运行前检查失败、3 输入被引导拦下。
    """
    from factory.logging_setup import configure_logging
    root = root or Path.cwd()
    configure_logging()
    # --mock 时不读 .env，保证离线路径确定；不带 --mock 才让 .env 里的
    # LLM_PROVIDER / LLM_MODEL 等真正生效（此前这些变量写了也没人读）
    settings = load_settings(root / "configs/default.yaml", apply_env=not mock)
    task = load_task_settings(root / task_config)
    if mock:
        # --mock 表示全链路规则模板，按角色路由也一并关闭
        settings.llm = settings.llm.model_copy(
            update={"provider": "mock", "role_providers": {}}
        )
    workflow = Workflow(settings, task, root, task_config=task_config,
                        kg_filename=kg_filename,
                        generated_subdir=generated_subdir)
    try:
        trace = workflow.run(spec_text, run_id, force=force)
    except SpecRejected as exc:
        # 输入不可执行：打印引导后退出，不消耗一次七步闭环
        logger.error("输入被入口引导拦下：%s", len(exc.guidance.issues))
        print(render_guidance(exc.guidance))
        return 3
    except (FileNotFoundError, ValueError) as exc:
        # 数据缺失 / 配置非法 / 标识不合法属于使用问题：给出可读原因并返回非 0
        logger.error("运行前检查失败：%s", exc)
        print(f"错误：{exc}")
        return 2
    if trace.intake is not None and trace.intake.verdict is IntakeVerdict.CLARIFY:
        # 已在入口放过，这里把「补什么会更稳」留一份痕迹
        print(render_guidance(trace.intake))
    print(f"[P3] 七步闭环执行完成；四层全通过={trace.passed} "
          f"理解来源={trace.interpreter_source} "
          f"候选={len(trace.candidates)} 修复={len(trace.repairs)} "
          f"报告={trace.report_path}")
    for item in sorted(trace.candidates, key=lambda c: -c.score):
        print(f"  {item.plan_id}: {workflow.metric_name}={item.metrics.get(workflow.metric_name)} "
              f"passed={item.passed} repairs={item.repair_rounds}")
    for record in trace.repairs:
        print(f"  修复[{record.round}] {record.error_signature} -> {record.fix_strategy}")
    if not trace.passed:
        print(f"  说明：指标层未达 {Path(task_config).name} 业务门槛，"
              "已如实判 FAIL 并回写 FailureCase")
    return 0


__all__ = ["Workflow", "render_intake_section", "render_kg_diff",
           "render_run_report", "run_from_cli"]
