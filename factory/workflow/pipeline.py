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
from typing import Any, TypedDict

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
    list_templates,
)
from factory.artifacts import kg_stem, report_path, scene_of, trace_path
from factory.config import Settings, TaskSettings, load_settings, load_task_settings
from factory.contracts.intake import IntakeGuidance, IntakeVerdict
from factory.contracts.knowledge import RetrievalResult
from factory.contracts.models import CandidatePlan, CapabilitySpec, ValidationReport
from factory.contracts.validation import StaticCheckResult
from factory.contracts.workflow import (
    CandidateEvaluation,
    CollaborationRecord,
    RunTrace,
    TestEvaluation,
)
from factory.intake import IntakeGuide, SpecRejected, render_guidance
from factory.knowledge import MockExtractor, read_sources
from factory.knowledge.graph import load_graph
from factory.knowledge.merge import merge_graphs
from factory.llm import SourceRecorder, build_llm
from factory.logging_setup import write_trace
from factory.plugins import load_plugins
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox
from factory.validation import (
    SUPPORTED_THRESHOLD_STRATEGIES,
    FourLayerValidator,
    TestGate,
    optimal_threshold,
)

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
    # 一次 execute 里解析出的实际阈值（cost_optimal 会落在某个样本分数上），
    # 供 finalize 记录与终评锁定；不同候选各自独立
    threshold_resolved: float
    last_repair_no_change: bool
    # Reviewer 语义评审：否决时带意见回 generate 重生成，review_rounds 计数防死循环
    review_comment: str
    review_rounds: int
    # 指标层修复已尝试过的算法族，防止「换族→仍不达标→再换回原族」空转
    escalated_families: list[str]


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


SOURCE_LABELS = {
    "deepseek_api": "实时调用",
    "cassette": "离线回放",
    "mock": "规则模板",
}

# 实际改动源码的那条轨：三种修复动作在报告里必须区分，不能都说成「LLM 修好了」
PATCH_SOURCE_LABELS = {
    "deterministic": "确定性补丁（AST 变换）",
    "llm": "LLM 补丁（过静态检查与沙箱复验）",
    "kg_escalation": "图谱方案级修复（按历史高分记录换族重生成）",
    "none": "未改动源码",
}


def _render_llm_sources(sources: dict[str, str]) -> str:
    """把「角色 → 后端」渲染成一行，让实时 / 回放 / 模板一眼可分。"""
    if not sources:
        return "本轮未调用 LLM"
    return "、".join(
        f"{role}={SOURCE_LABELS.get(source, source)}"
        for role, source in sorted(sources.items())
    )


def render_run_report(trace: RunTrace, reports: list[ValidationReport],
                      rationale: str, path: Path, metric_name: str = "auc",
                      task_config: str = "verify_credit.yaml",
                      kg_path: str = "",
                      run_log_path: str = "",
                      text_mode: bool = False) -> Path:
    """生成端到端报告：七步轨迹、候选排名、修复轨迹、四层结论与图谱 diff。"""
    live_roles = sorted(role for role, source in trace.llm_sources.items()
                        if source == "deepseek_api")
    live_llm = (trace.interpreter_source == "deepseek_api" or bool(live_roles)
                or any(source == "llm" for source in trace.code_sources.values()))
    if live_llm:
        header = [
            "> 本报告为真实运行的产物，本次**全链路接入真实 LLM**",
            "> （DeepSeek OpenAI 兼容接口，Interpreter / Planner / Coder / Repairer / Curator 实时调用）。",
            "> LLM 生成代码先过 AST 静态检查才采用；指标均为子进程沙箱在真实数据集上的实测，未造数值。",
        ]
        # 实时与回放混用时不能笼统说「全链路」：按角色列清，谁是真的模型输出一目了然
        others = {role: source for role, source in trace.llm_sources.items()
                  if source != "deepseek_api"}
        if others and live_roles:
            header[1] = (
                f"> 其中实时调用的角色：{'、'.join(live_roles)}；"
                f"其余角色走 cassette 回放或规则模板（{', '.join(f'{r}={s}' for r, s in sorted(others.items()))}）。"
            )
        if not text_mode:
            header.append("> 失败均由真实数据或真实业务门槛产生，未向生成代码人工注入错误。")
    elif trace.interpreter_source == "cassette":
        header = [
            "> 本报告为真实运行的产物。能力理解走 **cassette 离线回放**（真实 DeepSeek 响应），",
            "> 其余角色走 `MockLLM` 规则模板；生成代码在子进程用真实数据集执行，指标均为实测。",
        ]
    else:
        header = [
            "> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径",
            "> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。",
        ]
        if not text_mode:
            header.append("> 失败来自沙箱实测或 `verify_*.yaml` 的真实门槛，"
                          "不向生成代码注入人工错误；修复动作见第 4 节。")
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
        f"- LLM 后端分布：{_render_llm_sources(trace.llm_sources)}",
        f"- 知识图谱：{trace.kg_mode}（图谱来源 {trace.graph_source}）",
        f"- 历史经验实际生效：{'是' if trace.used_historical_warnings else '否'}",
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
        f"## 2. 候选方案比较（主指标 {metric_name} 优先，成本损失收口）",
        "",
        "> 阈值列：配置写策略名（如 `cost_optimal`），实际取值是评估段解析出的数值；两者并列，避免把策略名当成本次生效的阈值。",
        "",
        f"| 方案 | 模型族 | {metric_name} | 阈值（配置 → 实际） | 通过 | 代码来源 | 修复轮次 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in sorted(trace.candidates, key=lambda c: (
            -c.score, -float(c.metrics.get("cost_weighted_loss") or 0.0))):
        value = item.metrics.get(metric_name)
        value_text = "N/A" if value is None else f"{value:.4f}"
        code_source = trace.code_sources.get(item.plan_id, "template")
        configured = (f"{item.threshold:.2f}" if isinstance(item.threshold, (int, float))
                      else str(item.threshold))
        resolved = (f"{item.threshold_resolved:.3f}"
                    if item.threshold_resolved is not None else "N/A")
        lines.append(f"| {item.plan_id} | {item.model_family} | {value_text} | "
                     f"{configured} → {resolved} | "
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
                         f"{record.fix_strategy}（{record.outcome}；补丁来源 "
                         f"{PATCH_SOURCE_LABELS.get(record.patch_source, record.patch_source)}）")
            if record.llm_patch_note:
                # 方案级修复不是 LLM 补丁，报告不能共用「LLM 补丁准入」这个标签
                label = ("方案级修复说明" if record.patch_source == "kg_escalation"
                         else "LLM 补丁准入")
                lines.append(f"  - {label}：{record.llm_patch_note}")
            # 双轨：确定性补丁改源码，推理只解释根因，不冒充补丁
            if record.llm_reasoning:
                lines.append(f"  - 根因说明：{record.llm_reasoning}")
    else:
        lines.append("- 无失败轮次")
    # 评审协作轨迹与修复轨迹分开留证，证明协作不是单向流水线
    if trace.collaborations:
        lines.extend(["", "### 评审协作轨迹（Reviewer → Coder/Executor）", ""])
        for record in trace.collaborations:
            arrow = f"{record.sender} → {record.receiver}"
            if record.kind == "review_reject":
                lines.append(f"- 第 {record.round} 轮：{arrow} 否决——{record.comment}")
            else:
                lines.append(f"- 第 {record.round} 轮：{arrow} 通过")
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
    if kg_path:
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
        # 抽取画像来自 default.yaml：加一种材料只需登记映射，不改抽取器代码
        extraction = settings.knowledge.extraction
        if loaded is None:
            sources = read_sources(root, docs_dir, legacy_dir, shared, extraction)
            graph = MockExtractor(task.dataset_profile, extraction).extract(sources)
            self.graph_source = "sources"
        else:
            # 材料知识以最新抽取为准，运行沉淀（失败案例 / 教训 / 能力版本）叠加其上。
            # 直接整份沿用旧图谱会让新增材料与新增教训规则永远不生效。
            fresh = MockExtractor(task.dataset_profile, extraction).extract(
                read_sources(root, docs_dir, legacy_dir, shared, extraction))
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
        # 观测每个角色实际用的后端（实时 / 回放 / 规则模板），报告据此如实标注；
        # 包装器只记录 response.source，不改变请求与响应
        self.llm_recorder = SourceRecorder(build_llm(settings.llm, root))
        llm = self.llm_recorder
        self.task_type = task.task_type
        self.text_column = task.dataset.text_column
        self.sandbox_mode = ("text" if self.text_column
                             else "regression" if task.task_type == "tabular_regression"
                             else "tabular")
        self.metric_name = task.metrics[0].name if task.metrics else "auc"
        self.metric_direction = task.metrics[0].direction if task.metrics else "maximize"
        self.families = list(task.candidates.model_families)
        # 搜索维度：sampler / threshold 来自 candidates.*，不再硬编码 0.5 / "none"
        self.samplers = list(task.candidates.samplers)
        self.thresholds = list(task.candidates.thresholds)
        # 方案 A1：Successive Halving 搜索开关与预算
        self.search = settings.search
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
        # 保存引用供 LLM 补丁复验使用：补丁与生成代码走同一套 AST 白名单
        self.checker = checker
        self.interpreter = Interpreter(llm, settings.llm)
        self.retriever = Retriever(
            graph, settings.knowledge.top_k, settings.knowledge.weights,
            settings.knowledge.lesson_prompt_limit,
            historical_metric_key=settings.knowledge.retrieval.historical_metric_key,
            invalid_markers=settings.knowledge.retrieval.invalid_markers,
            family_aliases=task.candidates.family_aliases,
        )
        self.planner = Planner(llm, settings.workflow.beam_width)
        self.coder = Coder(llm, checker)
        self.reviewer = Reviewer(checker, llm)
        self.verifier = Verifier(FourLayerValidator(task))
        self.repairer = Repairer(llm, sorted(excluded),
                                 task.dataset.column_aliases)
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
        self.max_review_rounds = settings.workflow.max_review_rounds
        self.determinism_repeat = settings.workflow.determinism_repeat
        self.evaluate_on_test = settings.workflow.evaluate_on_test
        # test 一次性纪律的硬保证：重复消费 test 段即抛 PermissionError，
        # 不再依赖「只在一处调用 segment="test"」的结构约定
        self._test_gate = TestGate(enabled=self.evaluate_on_test)
        self._graph = self._build_graph()

    def _groups_for(self, segment: str) -> list[int]:
        """按评估段取敏感属性分组，供分组公平性指标使用。"""
        if not self.group_column:
            return []
        start, end = self.sandbox.segment_bounds(segment)
        frame = pd.read_csv(self.data_path, usecols=[self.group_column])
        return [int(value) for value in frame[self.group_column].iloc[start:end]]

    def _resolve_threshold(self, threshold: float | str,
                           context: dict[str, Any] | None = None) -> float:
        """把候选阈值解析为数值。

        数值阈值原样使用；``cost_optimal`` 用评估段实测分数按成本比扫最优阈值
        （与 ``metrics.cost_weighted_loss`` 同一口径）。缺评估数据或策略未注册
        时回退 0.5 并记 warning，不静默吞掉，也不伪造一个看起来精确的数字。
        """
        if isinstance(threshold, (int, float)):
            return float(threshold)
        name = str(threshold).strip()
        if name in SUPPORTED_THRESHOLD_STRATEGIES and context:
            return optimal_threshold(context.get("y_true"), context.get("y_score"),
                                     self.task.cost_ratio_fn_fp)
        logger.warning("阈值 %r 无法解析（缺评估段数据或策略未注册），回退 0.5", threshold)
        return 0.5

    def _prepare_metrics_context(self, context: dict[str, Any],
                                 threshold: float | str,
                                 segment: str = "valid") -> float:
        """算指标前统一口径：解析阈值、按阈值派生 y_pred、补齐成本比与分组。

        沙箱返回的 ``y_pred`` 固定按 0.5 派生；若不在此重算，候选的 threshold
        维度（0.30 / cost_optimal）对 F1 与成本加权损失完全不生效，搜索里的阈值
        维度就只是摆设。传入数值阈值时原样使用，不会重选——终评据此锁定为
        valid 段定下的阈值，避免用 test 段调参。
        """
        resolved = self._resolve_threshold(threshold, context)
        context["threshold"] = resolved
        context["cost_ratio"] = self.task.cost_ratio_fn_fp
        context["groups"] = (self.groups if segment == "valid"
                             else self._groups_for(segment))
        if self.sandbox_mode == "tabular":
            scores = context.get("y_score") or []
            if scores:
                context["y_pred"] = [int(value >= resolved) for value in scores]
        return resolved

    def _smoke_score(self, metrics: dict[str, float | None]) -> tuple[float, float]:
        """粗评排序键：主指标优先，同分用成本加权损失（越小越好）做次级。

        只有主指标排不出先后时次级键才生效；但同一模型族的不同阈值 / 采样器
        变体，主指标（AUC）相同而成本损失不同，正是靠这里分出优劣。
        """
        value = metrics.get(self.metric_name)
        if not isinstance(value, (int, float)):
            return (float("-inf"), 0.0)
        primary = float(value) if self.metric_direction != "minimize" else -float(value)
        loss = metrics.get("cost_weighted_loss")
        secondary = -float(loss) if isinstance(loss, (int, float)) else 0.0
        return (primary, secondary)

    def _build_graph(self):
        builder = StateGraph(_GraphState)
        for name, node in (
            ("parse", self._n_parse),
            ("retrieve", self._n_retrieve),
            ("plan_step", self._n_plan),
            ("smoke", self._n_smoke),
            ("generate", self._n_generate),
            ("review", self._n_review),
            ("execute", self._n_execute),
            ("repair", self._n_repair),
            ("finalize", self._n_finalize),
            ("sink", self._n_sink),
        ):
            builder.add_node(name, node)
        builder.set_entry_point("parse")
        builder.add_edge("parse", "retrieve")
        builder.add_edge("retrieve", "plan_step")
        # A1 开启时 plan 后先粗评淘汰，否则直接进入生成
        builder.add_conditional_edges("plan_step", self._after_plan,
                                      {"smoke": "smoke", "generate": "generate"})
        builder.add_edge("smoke", "generate")
        # generate 后先过 Reviewer 语义评审；否决则带意见回 generate，否则执行
        builder.add_edge("generate", "review")
        builder.add_conditional_edges("review", self._after_review,
                                      {"generate": "generate", "execute": "execute"})
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
                                  families=self.families, task_type=self.task_type,
                                  samplers=self.samplers, thresholds=self.thresholds)
        # A1：开启 Successive Halving 时扩候选空间（model_family × sampler × threshold）
        if self.search.halving_enabled:
            plans = self._expand_candidates(plans)
        trace = state["trace"]
        trace.steps.append(SEVEN_STEPS[2])
        return {"plans": plans, "candidate_index": 0, "reports": [], "trace": trace}

    def _after_plan(self, state: _GraphState) -> str:
        """A1 开启时 plan 后先粗评淘汰，否则直接进入生成。"""
        return "smoke" if self.search.halving_enabled else "generate"

    def _expand_candidates(self, base_plans: list[CandidatePlan]) -> list[CandidatePlan]:
        """组合 model_family × sampler × threshold，受 candidate_budget 限制。

        按 (sampler, threshold) 轮询 family，避免嵌套循环让第一个 family 填满预算、
        把后面的 family 挤出候选空间；每个组合得到连续编号的 plan_id（plan.01 …），
        保持产物命名与报告口径不变。
        """
        samplers = self.samplers or ["none"]
        thresholds = self.thresholds or [0.5]
        combos = [(plan, sampler, threshold)
                  for sampler in samplers
                  for threshold in thresholds
                  for plan in base_plans]
        expanded: list[CandidatePlan] = []
        for index, (plan, sampler, threshold) in enumerate(combos, start=1):
            expanded.append(plan.model_copy(update={
                "plan_id": f"plan.{index:02d}",
                "sampler": sampler,
                "threshold": threshold,
            }))
            if len(expanded) >= self.search.candidate_budget:
                return expanded
        return expanded

    def _smoke_one(self, plan: CandidatePlan, retrieval,
                   train_ratio: float) -> tuple[float, float]:
        """单个候选的低成本试跑：渲染代码 → 沙箱 → 复合排序键。"""
        source = self.coder.generate(
            plan, retrieval, self.columns,
            task_type=self.task_type, text_column=self.text_column,
        )
        result = self.sandbox.run(
            source, repeat=self.search.smoke_determinism_repeat,
            train_ratio=train_ratio,
        )
        if not result.sandbox.passed:
            return (float("-inf"), 0.0)
        self._prepare_metrics_context(result.context, plan.threshold)
        metrics = {item.name: item.value
                   for item in self.verifier.validator.evaluate_metrics(result.context)}
        return self._smoke_score(metrics)

    @staticmethod
    def _stratified_survivors(
        scored: list[tuple[CandidatePlan, tuple[float, float]]],
    ) -> list[tuple[CandidatePlan, tuple[float, float]]]:
        """按算法族分层保留前一半变体，返回仍按综合分降序排列的晋级名单。"""
        grouped: dict[str, list[tuple[CandidatePlan, tuple[float, float]]]] = {}
        for plan, score in scored:
            grouped.setdefault(plan.model_family, []).append((plan, score))
        promoted: set[str] = set()
        for items in grouped.values():
            keep = max(1, (len(items) + 1) // 2)
            promoted.update(plan.plan_id for plan, _ in items[:keep])
        return [item for item in scored if item[0].plan_id in promoted]

    def _n_smoke(self, state: _GraphState) -> dict:
        """Successive Halving：逐轮加预算淘汰，而不是只做一次粗评。

        第 1 轮用 ``smoke_train_ratio`` 比例的训练行跑全部扩展候选；晋级者
        每轮把训练预算抬到全量、候选数减半。评估段始终是完整 valid，所以
        不同预算之间只比「用了多少训练资源」，不混入指标口径差异。
        代码只用于排序，后续 generate 会重新生成。
        """
        # 只有一轮时不做低预算（否则「粗评轮数=1」会悄悄降成子采样口径）
        first_ratio = (self.search.smoke_train_ratio
                       if self.search.halving_rounds > 1 else 1.0)
        scored = [(plan, self._smoke_one(plan, state["retrieval"], first_ratio))
                  for plan in state["plans"]]
        scored.sort(key=lambda item: item[1], reverse=True)
        logger.info("粗评第 1 轮（训练预算 %.0f%%）：%d 个候选",
                    first_ratio * 100, len(scored))
        for round_index in range(2, self.search.halving_rounds + 1):
            # 按族分层淘汰：同族只留表现最好的前一半变体，避免强族把弱族整族
            # 挤出候选（那样「多候选比较」就退化成同族内部调参）。
            survivors = self._stratified_survivors(scored)
            scored = [(plan, self._smoke_one(plan, state["retrieval"], 1.0))
                      for plan, _ in survivors]
            scored.sort(key=lambda item: item[1], reverse=True)
            logger.info("粗评第 %d 轮（训练预算 100%%）：%d 个候选",
                        round_index, len(scored))
        # 按 family 去重：同族只保留粗评分最高的变体。变体差异是真实的——阈值与
        # 采样器会改变成本加权损失，复合键因此能在同族内选出更合适的阈值档。
        best_by_family: dict[str, tuple[CandidatePlan, tuple[float, float]]] = {}
        for plan, score in scored:
            if plan.model_family not in best_by_family:
                best_by_family[plan.model_family] = (plan, score)
        deduped = sorted(best_by_family.values(), key=lambda item: item[1], reverse=True)
        keep = max(1, min(len(deduped), self.planner.beam_width))
        # 粗评后按最终排名重编号 plan.01…plan.0N：产物文件名与报告编号不随
        # 扩展候选空间的规模漂移（否则调大 candidate_budget 就会让示例产物改名）
        kept = [plan.model_copy(update={"plan_id": f"plan.{index:02d}"})
                for index, (plan, _) in enumerate(deduped[:keep], start=1)]
        logger.info("粗评淘汰：%d -> %d 候选（按 family 去重后保留 Top-%d，已重编号）",
                    len(state["plans"]), len(kept), self.planner.beam_width)
        return {"plans": kept}

    def _n_generate(self, state: _GraphState) -> dict:
        index = state["candidate_index"]
        plans = state["plans"]
        if not plans:
            # 兜底防线：Planner 已经会在空候选时回退配置，这里避免裸 IndexError
            raise ValueError("Planner 未能产出候选方案；请检查 llm.provider 与 Planner 输出格式")
        plan = plans[index]
        source = self.coder.generate(
            plan, state["retrieval"], self.columns,
            task_type=self.task_type, text_column=self.text_column,
            review_comment=state.get("review_comment", ""),
        )
        trace = state["trace"]
        # 记录代码来源：llm 表示 LLM 代码通过静态检查后采用，template 表示回退
        trace.code_sources[plan.plan_id] = self.coder.last_source
        trace.steps.append(SEVEN_STEPS[3])
        return {
            "plan": plan, "source": source, "static": self.reviewer.review(source),
            "round_index": 0, "repair_rounds": 0, "last_repair_no_change": False,
            "threshold_resolved": 0.5, "escalated_families": [],
            # 评审意见已用于本次生成，清空；review_rounds 保持累计（由 review 节点管理）
            "review_comment": "",
            "trace": trace,
        }

    def _n_review(self, state: _GraphState) -> dict:
        """Reviewer 语义评审：否决则带意见回 generate，上限 max_review_rounds。

        仅对 LLM 生成的代码评审（模板代码是确定性配置，无需语义评审）；评审失败、
        关闭评审或被上限拦截时接受当前代码，不阻塞主流程。
        """
        trace = state["trace"]
        plan = state["plan"]
        rounds = state.get("review_rounds", 0)
        # 关闭语义评审，或代码来自确定性模板：跳过（仍记一轮协作，便于报告展示）
        if (self.max_review_rounds <= 0
                or trace.code_sources.get(plan.plan_id) != "llm"):
            return {"review_rounds": rounds}
        passed, comment = self.reviewer.review_semantics(
            state["source"], state["retrieval"])
        if passed:
            trace.collaborations.append(CollaborationRecord(
                round=rounds + 1, sender="Reviewer", receiver="Executor",
                kind="review_accept",
            ))
            return {"review_rounds": rounds + 1}
        if rounds >= self.max_review_rounds:
            # 超限：接受当前代码并如实记录「已达上限」，不无限协商
            trace.collaborations.append(CollaborationRecord(
                round=rounds + 1, sender="Reviewer", receiver="Coder",
                kind="review_reject",
                comment=f"（已达上限，接受当前代码）{comment}"[:300],
            ))
            return {"review_rounds": rounds + 1}
        trace.collaborations.append(CollaborationRecord(
            round=rounds + 1, sender="Reviewer", receiver="Coder",
            kind="review_reject", comment=comment[:300],
        ))
        return {"review_rounds": rounds + 1, "review_comment": comment}

    def _after_review(self, state: _GraphState) -> str:
        """语义评审否决且未达上限时回 generate 重生成，否则进入执行。"""
        return "generate" if state.get("review_comment") else "execute"

    def _n_execute(self, state: _GraphState) -> dict:
        # repeat>=2 时子进程内二次 fit，产出 repeat_variance 供确定性检查
        run_result = self.sandbox.run(state["source"], repeat=self.determinism_repeat)
        resolved = 0.5
        if run_result.sandbox.passed:
            resolved = self._prepare_metrics_context(
                run_result.context, state["plan"].threshold)
        report, _ = self.verifier.verify(
            state["run_id"], state["plan"].plan_id, state["static"], run_result
        )
        trace = state["trace"]
        trace.steps.append(SEVEN_STEPS[4])
        # 解析后的阈值随状态带到 finalize：终评锁定同一阈值，不在 test 段重选
        return {"report": report, "trace": trace, "threshold_resolved": resolved}

    def _after_execute(self, state: _GraphState) -> str:
        if state["report"].passed or state["round_index"] >= self.max_rounds:
            return "finalize"
        return "repair"

    def _verify_patch(self, source: str) -> tuple[bool, str]:
        """LLM 补丁的准入门槛：静态检查 + 沙箱复验，两者都过才允许采用。

        只验「能不能跑、有没有违反硬约束」，不验指标是否达标——指标达标由
        下一轮正式 ``execute`` 判定，避免在修复环节用 test 段数据调参。
        """
        check = self.checker.check(source)
        if not check.passed:
            return False, "静态检查未通过：" + ",".join(check.failed_checks())
        result = self.sandbox.run(source)
        if not result.sandbox.passed:
            return False, f"沙箱复验失败：{result.sandbox.error_signature}"
        return True, f"静态检查与沙箱复验通过（{result.sandbox.duration_seconds:.1f}s）"

    def _kg_escalation_target(self, plan: CandidatePlan,
                              state: _GraphState) -> str:
        """指标层不达标时，按图谱历史高分记录挑一个还没试过的算法族。

        候选族必须能渲染（注册了模板），且不在本候选已尝试过的族里，避免
        「换族 → 仍不达标 → 换回去」的空转。无图谱（消融组）时推荐列表为空，
        该方法返回空串，修复如实记为 no_change。
        """
        templates = set(list_templates())
        tried = set(state.get("escalated_families") or []) | {plan.model_family}
        for family in state["retrieval"].recommended_families:
            if not family or family in tried:
                continue
            if family in templates or f"{self.task_type}.{family}" in templates:
                return family
        return ""

    def _n_repair(self, state: _GraphState) -> dict:
        source, record = self.repairer.repair(
            state["source"], state["report"].error_signature,
            state["round_index"] + 1, verify=self._verify_patch,
        )
        trace = state["trace"]
        plan = state["plan"]
        extra: dict[str, Any] = {"escalated_families": state.get("escalated_families", [])}
        # 指标层的确定性补丁无法改「模型能力」本身，源码改写也就停在 no_change。
        # 此时用图谱里的历史高分记录做方案级修复：换算法族 + 重新生成源码，
        # 下一轮 execute 用同一套四层验证复验。无图谱证据时不做这一步。
        if (record.patch_source == "none"
                and (record.error_signature or "").startswith("MetricBelowThreshold")):
            target = self._kg_escalation_target(plan, state)
            if target:
                new_plan = plan.model_copy(update={
                    "model_family": target,
                    "rationale": (f"{plan.rationale}；指标层失败后按图谱历史高分记录"
                                  f"从 {plan.model_family} 切换为 {target}"),
                })
                source = self.coder.generate(
                    new_plan, state["retrieval"], self.columns,
                    task_type=self.task_type, text_column=self.text_column,
                )
                record = record.model_copy(update={
                    "outcome": "repaired",
                    "patch_source": "kg_escalation",
                    "fix_strategy": (f"{record.fix_strategy}；按图谱历史分数切换模型族 "
                                     f"{plan.model_family} → {target}"),
                    "llm_patch_note": "方案级修复：重新生成源码，下一轮 execute 复验四层",
                })
                trace.code_sources[new_plan.plan_id] = self.coder.last_source
                # 只有图谱证据真正改变了执行路径时，才声称「历史经验生效」
                trace.used_historical_warnings = True
                extra.update({
                    "plan": new_plan,
                    "static": self.reviewer.review(source),
                    "escalated_families": [
                        *state.get("escalated_families", []), target
                    ],
                })
                logger.info("指标层修复：按图谱历史记录切换模型族 %s → %s",
                            plan.model_family, target)
        trace.repairs.append(record)
        trace.steps.append(SEVEN_STEPS[5])
        return {
            "source": source, "static": self.reviewer.review(source),
            "round_index": state["round_index"] + 1,
            "repair_rounds": state["repair_rounds"] + 1,
            "last_repair_no_change": record.outcome == "no_change",
            "trace": trace,
            **extra,
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
            threshold=plan.threshold,
            # 语义值（cost_optimal）在这里落成实际数值，报告里两者都显示，
            # 便于核对「配置写的策略」与「实际用的阈值」不是同一回事
            threshold_resolved=state.get("threshold_resolved"),
        ))
        reports = [*state["reports"], report]
        # 候选结束：重置语义评审计数，下一个候选从 0 开始
        return {"candidate_index": state["candidate_index"] + 1,
                "reports": reports, "trace": trace,
                "review_rounds": 0, "review_comment": ""}

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
        # 同分时用成本加权损失收口，与粗评层级保持一致的「主指标优先」口径
        best = max(trace.candidates, key=lambda item: (
            item.passed, item.score,
            -float(item.metrics.get("cost_weighted_loss") or 0.0)))
        generated = (self.root / self.settings.paths.generated /
                     self.generated_subdir / f"candidate_{best.plan_id}.py")
        if not generated.is_file():
            return TestEvaluation(plan_id=best.plan_id, consumed=False,
                                 note="最佳候选源码缺失，test 段未消费")
        # test 门禁：真正消费前先过 TestGate，重复访问直接拒绝
        try:
            self._test_gate.consume()
        except PermissionError:
            return TestEvaluation(plan_id=best.plan_id, consumed=False,
                                 note="test 段已被消费过，拒绝重复访问")
        result = self.sandbox.run(generated.read_text(encoding="utf-8"), segment="test")
        if not result.sandbox.passed:
            return TestEvaluation(
                plan_id=best.plan_id, consumed=True,
                note=f"终评执行失败：{result.sandbox.error_signature}",
            )
        # 终评锁定 valid 段定下的阈值：传数值即不再重选，避免用 test 数据挑阈值
        resolved = best.threshold_resolved
        if resolved is None:
            logger.warning("终评候选缺少已解析阈值，按 0.5 评估；不在 test 段重选阈值")
            resolved = 0.5
        self._prepare_metrics_context(result.context, resolved, "test")
        metrics = self.verifier.validator.evaluate_metrics(result.context)
        logger.info("终评（test 段，仅一次）：候选=%s 阈值=%.3f", best.plan_id, resolved)
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
            f"评审协作 {len(trace.collaborations)} 次；"
            f"历史经验实际生效 {'是' if trace.used_historical_warnings else '否'}；"
            f"检索证据 {len(state['retrieval'].hits)} 项已注入 "
            "Planner 与 Coder prompt。"
        )
        rationale = self.curator.explain(
            trace, retrieval=state["retrieval"],
            metric_name=self.metric_name,
            direction=self.metric_direction,
            threshold=self.task.metrics[0].threshold if self.task.metrics else None,
        )
        # 报告渲染前最后一次落定后端分布：覆盖 Curator 在内的全部角色调用
        trace.llm_sources = dict(self.llm_recorder.sources)
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
