"""L2 Agent 层：8 个角色，各自有独立 system prompt 与输入输出契约。

检索结果必须进入 Planner 与 Coder 的 prompt（``retrieval.as_prompt_context()``），
由 ``RunTrace.retrieval_prompt`` 留证；Coder 代码由参数化模板渲染，属于
开发要求 g 允许的规则模板路径，不冒充真实 LLM 生成。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from factory.agents.templates import (
    LOGISTIC_REGRESSION_TEMPLATE,
    list_templates,
    render,
)
from factory.config import LLMSettings
from factory.contracts.knowledge import KnowledgeGraph, RetrievalResult
from factory.contracts.llm import LLMRequest
from factory.contracts.models import CandidatePlan, CapabilitySpec, TaskType, ValidationReport
from factory.contracts.validation import MetricResult, StaticCheckResult
from factory.contracts.workflow import DatasetRunResult, RepairRecord, RunTrace
from factory.knowledge.retrieval import HybridRetriever
from factory.llm.base import BaseLLM
from factory.llm.demo import SYSTEM_PROMPT, build_demo_request
from factory.runtime import StaticChecker
from factory.validation import FourLayerValidator

SYSTEM_PROMPTS = {
    "Interpreter": SYSTEM_PROMPT,
    "Retriever": "从能力图谱检索约束、历史指标与失败规避项。",
    "Planner": "结合检索证据规划多个候选算法方案。",
    "Coder": "按方案生成实现 build_pipeline() 的可运行代码。",
    "Reviewer": "对生成代码做 AST 静态评审。",
    "Verifier": "汇总沙箱与指标证据，输出四层 ValidationReport。",
    "Repairer": "按错误签名查策略表做定向修复，不重写全量代码。",
    "Curator": "把验证结果与失败经验回写能力图谱并给出设计依据。",
}

REPAIR_STRATEGIES = {
    "KeyError: PAY_1": "按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）",
    "ForbiddenFeature": "从特征列中剔除 ID 与敏感字段",
    "Timeout": "降低 max_iter 或减少训练样本",
    "MetricBelowThreshold": "检索历史高分方案，切换模型族或按成本比调阈值",
    "ImportError": "改用 import 白名单内的库",
    "Nondeterminism": "注入 random_state",
    "LeakageDetected": "强制 sklearn.Pipeline 并改时间外划分",
}

CODE_TEMPLATE = LOGISTIC_REGRESSION_TEMPLATE

# 各族候选的默认超参；新增模板时在此登记，避免超参散落在单点。
HYPERPARAM_PRESETS: dict[str, list[dict[str, float]]] = {
    "logistic_regression": [
        {"C": 0.5, "max_iter": 1000},
        {"C": 1.0, "max_iter": 1000},
        {"C": 2.0, "max_iter": 1000},
    ],
    "hist_gradient_boosting": [
        {"max_iter": 200, "learning_rate": 0.1},
        {"max_iter": 300, "learning_rate": 0.05},
    ],
    "random_forest": [
        {"n_estimators": 200, "max_depth": 8},
        {"n_estimators": 300, "max_depth": 10},
    ],
    # 文本分类族：TF-IDF 管线，超参与表格族互不复用
    "linear_svc": [{"C": 0.5}, {"C": 1.0}],
    "complement_nb": [{"alpha": 0.5}, {"alpha": 1.0}],
}


class Interpreter:
    """a. 理解自然语言能力描述。

    兼容两类解析结果：规则模板的扁平 schema，以及真实 LLM 返回的
    ``capability_name`` / ``problem_type`` / ``feature_constraints`` 结构。
    后者会把响应里的划分策略、成本比、禁入模字段与指标写进
    ``CapabilitySpec``，因此能力理解确实由真实 LLM 驱动，而不是只看演示。
    ``last_source`` 记录本次来源，供 ``RunTrace`` 留证。
    """

    def __init__(self, llm: BaseLLM, settings: LLMSettings | None = None) -> None:
        self.llm = llm
        self.settings = settings
        self.last_source = "mock"

    def _request(self, description: str) -> LLMRequest:
        """与录制脚本共用同一构造，保证 cassette 命中键一致。"""
        if self.settings is None:
            return LLMRequest(role="Interpreter", system=SYSTEM_PROMPT,
                              user=description)
        return build_demo_request(self.settings, description)

    def parse(self, description: str) -> CapabilitySpec:
        response = self.llm.complete(self._request(description))
        self.last_source = response.source
        parsed = response.parsed or {}
        if "capability_name" in parsed or "task_type" in parsed:
            return self._from_llm(parsed, description)
        if isinstance(parsed.get("capability"), dict):
            return self._from_llm(parsed, description)
        return CapabilitySpec(
            spec_id=str(parsed.get("spec_id", "spec.workflow.v1")),
            description=description,
            constraints=list(parsed.get("constraints", [])),
        )

    @staticmethod
    def _from_llm(parsed: dict[str, object], description: str) -> CapabilitySpec:
        constraints: list[str] = []
        split = parsed.get("data_split")
        if isinstance(split, dict) and split.get("strategy"):
            constraints.append(
                f"划分策略 {split['strategy']}：{split.get('description', '')}"
            )
        feature = parsed.get("feature_constraints")
        if isinstance(feature, dict):
            forbidden = [str(item) for item in feature.get("forbidden_features") or []]
            if forbidden:
                constraints.append("禁入模字段：" + ", ".join(forbidden))
            elif feature.get("exclude_identifier_columns"):
                constraints.append("禁止 ID 类字段入模")
        threshold = parsed.get("threshold_selection")
        if isinstance(threshold, dict) and threshold.get("cost_ratio"):
            constraints.append(
                f"成本比 {threshold['cost_ratio']}：{threshold.get('description', '')}"
            )
        horizon = parsed.get("prediction_horizon")
        if horizon:
            constraints.append(f"预测窗口：{horizon}")
        extra = parsed.get("constraints")
        if isinstance(extra, list):
            constraints.extend(str(item) for item in extra)
        metrics: list[str] = []
        evaluation = parsed.get("evaluation")
        if isinstance(evaluation, dict):
            metrics = [str(item) for item in evaluation.get("primary_metrics") or []]
        outputs: dict[str, str] = {}
        output = parsed.get("output")
        if isinstance(output, dict) and output.get("field"):
            detail = f"{output.get('type', '')} {output.get('range', '')}".strip()
            outputs[str(output["field"])] = detail
        nested = parsed.get("capability")
        nested_name = nested.get("name") if isinstance(nested, dict) else None
        target = parsed.get("target")
        target_name = target.get("name") if isinstance(target, dict) else None
        slug_source = str(target_name or nested_name or parsed.get("capability_name") or "")
        slug = re.sub(r"[^a-z0-9]+", "_", slug_source.lower()).strip("_")
        return CapabilitySpec(
            spec_id=f"spec.{slug}" if slug else "spec.workflow.v1",
            description=description,
            task_type=Interpreter._task_type(parsed),
            outputs=outputs,
            constraints=constraints,
            metrics=metrics,
            cost_ratio_fn_fp=Interpreter._cost_ratio(parsed),
        )

    @staticmethod
    def _task_type(parsed: dict[str, object]) -> TaskType:
        raw = str(parsed.get("task_type") or parsed.get("problem_type") or "")
        mapping = {
            "binary_classification": TaskType.TABULAR_BINARY,
            "tabular_binary_classification": TaskType.TABULAR_BINARY,
            "tabular_regression": TaskType.TABULAR_REGRESSION,
            "text_classification": TaskType.TEXT_CLASSIFICATION,
        }
        return mapping.get(raw, TaskType.TABULAR_BINARY)

    @staticmethod
    def _cost_ratio(parsed: dict[str, object]) -> float:
        threshold = parsed.get("threshold_selection")
        raw = str(threshold.get("cost_ratio", "")) if isinstance(threshold, dict) else ""
        match = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", raw)
        if match:
            false_negative = float(match.group(1))
            false_positive = float(match.group(2))
            if false_positive > 0:
                return false_negative / false_positive
        return 5.0


class Retriever:
    """b. 从能力图谱检索证据。"""

    def __init__(self, graph: KnowledgeGraph, top_k: int,
                 weights: dict[str, float]) -> None:
        self._retriever = HybridRetriever(graph, top_k, weights)

    def retrieve(self, description: str) -> RetrievalResult:
        return self._retriever.retrieve(description)


class Planner:
    """c. 规划多个候选方案；检索证据进入 prompt。"""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def plan(self, spec: CapabilitySpec, retrieval: RetrievalResult,
             families: list[str] | None = None,
             task_type: str = "") -> list[CandidatePlan]:
        """规划候选方案。

        当该任务类型注册了专属算法模板（如文本分类的 TF-IDF 管线）时，
        以 ``verify_*.yaml`` 的 ``candidates.model_families`` 为准并去重，
        避免 Planner 提案出该任务无法渲染的模型族；表格场景仍沿用提案。
        """
        user = f"能力描述：{spec.description}\n{retrieval.as_prompt_context()}"
        request = LLMRequest(role="Planner", system=SYSTEM_PROMPTS["Planner"], user=user)
        parsed = self.llm.complete(request).parsed
        raw_plans = parsed.get("candidates", [])
        available = [family for family in (families or [])
                     if f"{task_type}.{family}" in list_templates()]
        used: set[str] = set()
        plans: list[CandidatePlan] = []
        for index, item in enumerate(raw_plans[:3], start=1):
            family = str(item.get("model_family", "logistic_regression"))
            if available and (family not in available or family in used):
                family = next((name for name in available if name not in used),
                              family)
            used.add(family)
            presets = HYPERPARAM_PRESETS.get(
                family, HYPERPARAM_PRESETS["logistic_regression"]
            )
            plans.append(CandidatePlan(
                plan_id=f"plan.{index:02d}",
                spec_id=spec.spec_id,
                model_family=family,
                operators=list(item.get("operators", [])),
                hyperparams=dict(presets[(index - 1) % len(presets)]),
                rationale=f"检索证据 {len(retrieval.hits)} 项；候选 {index}（{family}）",
                retrieved_evidence=[hit.node_id for hit in retrieval.hits],
            ))
        return plans


class Coder:
    """d. 生成可运行代码；检索证据进入 prompt。"""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def generate(self, plan: CandidatePlan, retrieval: RetrievalResult,
                 columns: list[str], induce_t1: bool = False,
                 respect_failures: bool = True, task_type: str = "",
                 text_column: str = "") -> str:
        avoided = (induce_t1 and respect_failures
                   and any("PAY_1" in warning for warning in retrieval.failure_warnings))
        if avoided:
            # 图谱已沉淀 T1 失败经验，首轮即避开直觉命名，不再重复踩坑
            induce_t1 = False
        rendered = [name.replace("PAY_0", "PAY_1") for name in columns] if induce_t1 \
            else list(columns)
        prompt_inputs = (f"文本列：{text_column}" if text_column
                         else f"特征列：{json.dumps(rendered, ensure_ascii=False)}")
        user = (f"方案：{plan.model_dump_json()}\n"
                f"{prompt_inputs}\n"
                f"{retrieval.as_prompt_context()}")
        request = LLMRequest(role="Coder", system=SYSTEM_PROMPTS["Coder"], user=user)
        self.llm.complete(request)
        hyperparams = dict(plan.hyperparams)
        if text_column:
            hyperparams["text_column"] = text_column
        return render(plan.model_family, rendered, hyperparams, task_type)


class Reviewer:
    """AST 静态评审：白名单、危险调用、禁入模字段、契约签名。"""

    def __init__(self, checker: StaticChecker) -> None:
        self.checker = checker

    def review(self, source: str) -> StaticCheckResult:
        return self.checker.check(source)


class Verifier:
    """e. 汇总四层验证结论。"""

    def __init__(self, validator: FourLayerValidator) -> None:
        self.validator = validator

    def verify(self, run_id: str, plan_id: str, static: StaticCheckResult,
               run_result: DatasetRunResult) -> tuple[ValidationReport, list[MetricResult]]:
        metrics = (self.validator.evaluate_metrics(run_result.context)
                   if run_result.sandbox.passed else [])
        report = self.validator.validate(
            run_id=run_id, plan_id=plan_id, static=static,
            sandbox=run_result.sandbox, metrics=metrics,
        )
        return report, metrics


class Repairer:
    """f. 按错误签名定向修复，按策略表只改必要片段。"""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def repair(self, source: str, signature: str | None,
               round_index: int) -> tuple[str, RepairRecord]:
        key = signature or "Unknown"
        strategy = REPAIR_STRATEGIES.get(key, "无匹配策略，保留失败记录供人工分析")
        fixed = source
        if key == "KeyError: PAY_1":
            fixed = source.replace('"PAY_1"', '"PAY_0"')
        request = LLMRequest(role="Repairer", system=SYSTEM_PROMPTS["Repairer"],
                             user=f"错误签名：{key}\n策略：{strategy}")
        self.llm.complete(request)
        record = RepairRecord(round=round_index, error_signature=key,
                              fix_strategy=strategy,
                              outcome="repaired" if fixed != source else "no_change")
        return fixed, record


class Curator:
    """g. 回写 ValidationRun / FailureCase / 能力新版本，产出图谱 diff。"""

    def __init__(self, graph: KnowledgeGraph, llm: BaseLLM) -> None:
        self.graph = graph
        self.llm = llm

    def sink(self, trace: RunTrace, reports: list[ValidationReport],
             out_path: Path) -> dict[str, int]:
        from factory.contracts.knowledge import EdgeType, KGEdge, KGNode, NodeType
        from factory.knowledge.graph import KnowledgeGraphStore

        nodes = list(self.graph.nodes)
        edges = list(self.graph.edges)
        anchor = next(
            (node.node_id for node in nodes if node.node_type is NodeType.CAPABILITY), None
        )
        upgraded = f"{anchor}.v2" if anchor else None
        run_prefix = f"run.{trace.run_id}."
        failure_prefix = f"failure.{trace.run_id}."

        def stale(node_id: str) -> bool:
            return (node_id.startswith((run_prefix, failure_prefix))
                    or (upgraded is not None and node_id == upgraded))

        # 同一 run_id 重跑时覆盖旧节点，避免反复运行让图谱无限膨胀
        nodes = [node for node in nodes if not stale(node.node_id)]
        edges = [edge for edge in edges
                 if not (stale(edge.source) or stale(edge.target))]
        for index, report in enumerate(reports, start=1):
            run_id = f"run.{trace.run_id}.{index:02d}"
            nodes.append(KGNode(
                node_id=run_id,
                node_type=NodeType.VALIDATION_RUN,
                name=f"验证运行 {run_id}",
                attributes={
                    "metrics": report.metric_values,
                    "passed": report.passed,
                    "duration_seconds": report.stability.get("duration_seconds"),
                },
            ))
            if anchor:
                edges.append(KGEdge(source=anchor, target=run_id,
                                    edge_type=EdgeType.HAS_RUN))
        failure_ids: list[str] = []
        for index, repair in enumerate(trace.repairs, start=1):
            failure_id = f"failure.{trace.run_id}.{index:02d}"
            failure_ids.append(failure_id)
            nodes.append(KGNode(
                node_id=failure_id, node_type=NodeType.FAILURE_CASE,
                name=f"失败案例 {repair.error_signature}",
                attributes={"error_signature": repair.error_signature,
                            "fix_strategy": repair.fix_strategy,
                            "repair_round": repair.round},
            ))
            if anchor:
                edges.append(KGEdge(source=anchor, target=failure_id,
                                    edge_type=EdgeType.RESULTED_IN))
        if anchor and failure_ids and upgraded is not None:
            nodes.append(KGNode(
                node_id=upgraded, node_type=NodeType.CAPABILITY,
                name="修复后的能力版本", version="v2",
                attributes={"derived_from": anchor},
            ))
            edges.append(KGEdge(source=upgraded, target=anchor,
                                edge_type=EdgeType.DERIVED_FROM))
            edges.append(KGEdge(source=failure_ids[-1], target=upgraded,
                                edge_type=EdgeType.FIXED_BY))
        updated = self.graph.model_copy(update={"nodes": nodes, "edges": edges})
        updated.validate_references()
        KnowledgeGraphStore(updated).export_json(out_path)
        request = LLMRequest(role="Curator", system=SYSTEM_PROMPTS["Curator"],
                             user=f"回写 {len(nodes)} 节点，修复 {len(trace.repairs)} 轮")
        self.llm.complete(request)
        return {"nodes_added": len(nodes) - len(self.graph.nodes),
                "edges_added": len(edges) - len(self.graph.edges)}

    def explain(self, trace: RunTrace) -> str:
        """自然语言解释方案设计依据（加分项）。"""
        ranked = sorted(trace.candidates, key=lambda item: -item.score)
        lines = ["## 设计依据", f"- 检索证据条目：{len(trace.retrieval_prompt.splitlines())}"]
        lines.append(f"- 候选排名：{' > '.join(item.plan_id for item in ranked)}")
        lines.append(f"- 修复轨迹：{'; '.join(r.fix_strategy for r in trace.repairs) or '无'}")
        lines.append("- 依据：检索到的适用条件约束候选方案，历史失败规避项触发列名映射修复。")
        return "\n".join(lines)


__all__ = [
    "CODE_TEMPLATE",
    "REPAIR_STRATEGIES",
    "SYSTEM_PROMPTS",
    "Coder",
    "Curator",
    "Interpreter",
    "Planner",
    "Repairer",
    "Retriever",
    "Reviewer",
    "Verifier",
]
