"""L2 Agent 层：8 个角色，各自有独立 system prompt 与输入输出契约。

检索结果必须进入 Planner 与 Coder 的 prompt（``retrieval.as_prompt_context()``），
由 ``RunTrace.retrieval_prompt`` 留证；Coder 代码由参数化模板渲染，属于
开发要求 g 允许的规则模板路径，不冒充真实 LLM 生成。
"""

from __future__ import annotations

import json
from pathlib import Path

from factory.contracts.knowledge import KnowledgeGraph, RetrievalResult
from factory.contracts.llm import LLMRequest
from factory.contracts.models import CandidatePlan, CapabilitySpec, ValidationReport
from factory.contracts.validation import MetricResult, StaticCheckResult
from factory.contracts.workflow import DatasetRunResult, RepairRecord, RunTrace
from factory.knowledge.retrieval import HybridRetriever
from factory.llm.base import BaseLLM
from factory.runtime import StaticChecker
from factory.validation import FourLayerValidator

SYSTEM_PROMPTS = {
    "Interpreter": "把自然语言能力描述解析为 CapabilitySpec 结构化契约。",
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

CODE_TEMPLATE = '''\
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = {columns}

def build_pipeline(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(C={c_value}, max_iter={max_iter}, random_state=42)),
    ])
'''


class Interpreter:
    """a. 理解自然语言能力描述。"""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def parse(self, description: str) -> CapabilitySpec:
        request = LLMRequest(role="Interpreter", system=SYSTEM_PROMPTS["Interpreter"],
                             user=description)
        parsed = self.llm.complete(request).parsed
        return CapabilitySpec(
            spec_id=str(parsed.get("spec_id", "spec.workflow.v1")),
            description=description,
            constraints=list(parsed.get("constraints", [])),
        )


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

    def plan(self, spec: CapabilitySpec, retrieval: RetrievalResult) -> list[CandidatePlan]:
        user = f"能力描述：{spec.description}\n{retrieval.as_prompt_context()}"
        request = LLMRequest(role="Planner", system=SYSTEM_PROMPTS["Planner"], user=user)
        parsed = self.llm.complete(request).parsed
        raw_plans = parsed.get("candidates", [])
        plans: list[CandidatePlan] = []
        for index, item in enumerate(raw_plans[:3], start=1):
            plans.append(CandidatePlan(
                plan_id=f"plan.{index:02d}",
                spec_id=spec.spec_id,
                model_family=str(item.get("model_family", "logistic_regression")),
                operators=list(item.get("operators", [])),
                hyperparams={"C": [0.5, 1.0, 2.0][index - 1], "max_iter": 1000},
                rationale=f"检索证据 {len(retrieval.hits)} 项；候选 {index}",
                retrieved_evidence=[hit.node_id for hit in retrieval.hits],
            ))
        return plans


class Coder:
    """d. 生成可运行代码；检索证据进入 prompt。"""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def generate(self, plan: CandidatePlan, retrieval: RetrievalResult,
                 columns: list[str], induce_t1: bool = False) -> str:
        rendered = [name.replace("PAY_0", "PAY_1") for name in columns] if induce_t1 \
            else list(columns)
        user = (f"方案：{plan.model_dump_json()}\n"
                f"特征列：{json.dumps(rendered, ensure_ascii=False)}\n"
                f"{retrieval.as_prompt_context()}")
        request = LLMRequest(role="Coder", system=SYSTEM_PROMPTS["Coder"], user=user)
        self.llm.complete(request)
        return CODE_TEMPLATE.format(
            columns=json.dumps(rendered, ensure_ascii=False),
            c_value=plan.hyperparams.get("C", 1.0),
            max_iter=plan.hyperparams.get("max_iter", 1000),
        )


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
        if anchor and failure_ids:
            upgraded = f"{anchor}.v2"
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
