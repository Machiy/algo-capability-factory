"""L2 Agent 层：8 个角色，各自有独立 system prompt 与输入输出契约。

检索结果必须进入 Planner 与 Coder 的 prompt（``retrieval.as_prompt_context()``），
由 ``RunTrace.retrieval_prompt`` 留证。

Coder 有两条路径：真实 LLM（``source != "mock"``）返回的代码先过 AST 静态
检查，通过才采用；解析失败或检查不过则回退参数化模板，并把原因写进 trace。
``MockLLM`` 只作契约示例，固定走模板——模板输出不会冒充模型生成，回退路径
本身才是可靠性设计。
"""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path

from factory.agents.templates import list_templates, render
from factory.config import LLMSettings
from factory.contracts.knowledge import KGNode, KnowledgeGraph, RetrievalResult
from factory.contracts.llm import LLMRequest
from factory.contracts.models import CandidatePlan, CapabilitySpec, TaskType, ValidationReport
from factory.contracts.validation import MetricResult, StaticCheckResult
from factory.contracts.workflow import DatasetRunResult, RepairRecord, RunTrace
from factory.knowledge.lessons import confidence_for, promote_failures
from factory.knowledge.retrieval import HybridRetriever
from factory.llm.base import BaseLLM
from factory.llm.demo import SYSTEM_PROMPT, build_demo_request
from factory.runtime import StaticChecker
from factory.validation import FourLayerValidator

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "Interpreter": SYSTEM_PROMPT,
    "Retriever": "从能力图谱检索约束、历史指标与失败规避项。",
    "Planner": (
        "结合检索证据规划多个候选算法方案。只输出 JSON，不要输出解释文字："
        '{"candidates": [{"model_family": "logistic_regression", '
        '"operators": ["Imputer", "Scaler"]}]}'
    ),
    "Coder": (
        "按方案生成可运行的 Python 源码，只输出代码，不要解释。硬性要求：\n"
        "1) 定义模块级常量 FEATURE_COLUMNS，值为特征列名列表，必须与用户消息给出的"
        "特征列一致，不得包含 ID、标签列或敏感字段；若用户消息给的是文本列，"
        "则改为定义 TEXT_COLUMN = \"<列名>\"；\n"
        "2) 定义 def build_pipeline(config): 返回 sklearn.pipeline.Pipeline；\n"
        "3) 必须使用方案中的 model_family 对应的算法；\n"
        "4) 缺失值处理、缩放、编码、采样全部放进 Pipeline，不得在 Pipeline 外 fit；\n"
        "5) 只 import 白名单内的库（numpy / pandas / sklearn / imblearn / math / typing）。"
    ),
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

# 接受 random_state 的 sklearn 随机估计器：确定性修复据此判断该给哪个类注入。
# 这是算法库的已知事实（哪些估计器有随机性），不是业务列名或指标阈值。
_RANDOM_STATE_ESTIMATORS = frozenset({
    "LogisticRegression",
    "LinearSVC",
    "RandomForestClassifier",
    "RandomForestRegressor",
    "ExtraTreesClassifier",
    "ExtraTreesRegressor",
    "HistGradientBoostingClassifier",
    "HistGradientBoostingRegressor",
    "GradientBoostingClassifier",
    "GradientBoostingRegressor",
    "Ridge",
    "SGDClassifier",
    "SGDRegressor",
    "MLPClassifier",
    "MLPRegressor",
})


def _replace_range(source: str, start_line: int, start_col: int,
                   end_line: int, end_col: int, new_text: str) -> str:
    """按 AST 节点位置（1-based 行列）用新文本替换源码片段。"""
    lines = source.splitlines()
    first = start_line - 1
    last = end_line - 1
    if first == last:
        line = lines[first]
        lines[first] = line[:start_col] + new_text + line[end_col:]
    else:
        prefix = lines[first][:start_col]
        suffix = lines[last][end_col:]
        lines[first] = prefix + new_text
        lines[first + 1:last + 1] = [suffix] if suffix else []
    return "\n".join(lines)


def _render_column_list(elts: list[ast.expr]) -> str:
    """把列名列表元素渲染回源码字面量；非字符串元素退回 ast.unparse。"""
    parts = []
    for el in elts:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            parts.append(json.dumps(el.value, ensure_ascii=False))
        else:
            parts.append(ast.unparse(el))
    return "[" + ", ".join(parts) + "]"


def _repair_forbidden_feature(source: str, forbidden: set[str]) -> str:
    """从 FEATURE_COLUMNS 剔除禁入模字段（ID / 标签 / 敏感字段）。

    定向修复而非重写全量：只改 FEATURE_COLUMNS 赋值里的列表字面量，
    其余代码原样保留。``forbidden`` 由任务配置派生，不在修复逻辑里写死列名。
    """
    if not forbidden:
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    edits: list[tuple[int, int, int, int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign)
                and isinstance(node.value, (ast.List, ast.Tuple))):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "FEATURE_COLUMNS"
                   for t in node.targets):
            continue
        kept = [el for el in node.value.elts
                if not (isinstance(el, ast.Constant) and el.value in forbidden)]
        if len(kept) == len(node.value.elts):
            continue
        edits.append((node.value.lineno, node.value.col_offset,
                      node.value.end_lineno, node.value.end_col_offset,
                      _render_column_list(kept)))
    for start_line, start_col, end_line, end_col, text in reversed(edits):
        source = _replace_range(source, start_line, start_col,
                                end_line, end_col, text)
    return source


def _repair_nondeterminism(source: str) -> str:
    """给缺 random_state 的随机估计器实例化注入 random_state=42。

    消除同一子进程内二次 fit 的输出差异；已有 random_state 的调用不动，
    不重复注入。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    edits: list[tuple[int, int, int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if name not in _RANDOM_STATE_ESTIMATORS:
            continue
        if any(kw.arg == "random_state" for kw in node.keywords):
            continue
        new_call = ast.Call(
            func=node.func,
            args=list(node.args),
            keywords=[*node.keywords,
                      ast.keyword(arg="random_state", value=ast.Constant(value=42))],
        )
        edits.append((node.lineno, node.col_offset, node.end_lineno,
                      node.end_col_offset, ast.unparse(new_call)))
    for start_line, start_col, end_line, end_col, text in reversed(edits):
        source = _replace_range(source, start_line, start_col,
                                end_line, end_col, text)
    return source

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
    # 回归族：同样是全部署在 sklearn.Pipeline 内
    "ridge": [{"alpha": 1.0}, {"alpha": 5.0}],
    "hist_gradient_boosting_regressor": [
        {"max_iter": 200, "learning_rate": 0.1},
        {"max_iter": 400, "learning_rate": 0.05},
    ],
    "random_forest_regressor": [
        {"n_estimators": 200, "max_depth": 12},
        {"n_estimators": 300, "max_depth": 16},
    ],
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
                 weights: dict[str, float], lesson_limit: int = 5) -> None:
        self._retriever = HybridRetriever(graph, top_k, weights, lesson_limit)

    def retrieve(self, description: str) -> RetrievalResult:
        return self._retriever.retrieve(description)


class Planner:
    """c. 规划多个候选方案；检索证据进入 prompt。"""

    def __init__(self, llm: BaseLLM, beam_width: int = 3) -> None:
        self.llm = llm
        # 候选宽度来自 configs/default.yaml 的 workflow.beam_width，不在代码里写死
        self.beam_width = beam_width

    def plan(self, spec: CapabilitySpec, retrieval: RetrievalResult,
             families: list[str] | None = None,
             task_type: str = "",
             samplers: list[str] | None = None,
             thresholds: list[float] | None = None) -> list[CandidatePlan]:
        """规划候选方案。

        当该任务类型注册了专属算法模板（如文本分类的 TF-IDF 管线）时，
        以 ``verify_*.yaml`` 的 ``candidates.model_families`` 为准并去重，
        避免 Planner 提案出该任务无法渲染的模型族；表格场景仍沿用提案。

        ``samplers`` / ``thresholds`` 来自 ``candidates.*`` 维度，按候选序号循环
        取值写入 ``CandidatePlan``，替换硬编码的 ``sampler="none"`` / ``threshold=0.5``；
        缺省时退回默认值，保证旧调用（仅传 families）行为不变。
        """
        user = f"能力描述：{spec.description}\n{retrieval.as_prompt_context()}"
        request = LLMRequest(role="Planner", system=SYSTEM_PROMPTS["Planner"],
                             user=user, scene=task_type)
        parsed = self.llm.complete(request).parsed
        raw_plans = parsed.get("candidates", [])
        sampler_cycle = list(samplers or ["none"])
        threshold_cycle = list(thresholds or [0.5])
        # 模板有两种注册写法：任务专属的 ``<task_type>.<family>``（文本 / 回归）
        # 与通用表格的裸 ``<family>``，两者都算已注册，否则裁剪会静默失效
        templated = set(list_templates())
        available = [
            family for family in (families or [])
            if family in templated or f"{task_type}.{family}" in templated
        ]
        used: set[str] = set()
        plans: list[CandidatePlan] = []

        def _add(family: str, operators: list[str], rationale: str) -> None:
            if not family or family in used:
                return
            used.add(family)
            index = len(plans) + 1
            presets = HYPERPARAM_PRESETS.get(
                family, HYPERPARAM_PRESETS["logistic_regression"]
            )
            plans.append(CandidatePlan(
                plan_id=f"plan.{index:02d}",
                spec_id=spec.spec_id,
                model_family=family,
                operators=list(operators),
                hyperparams=dict(presets[(index - 1) % len(presets)]),
                sampler=sampler_cycle[(index - 1) % len(sampler_cycle)],
                threshold=threshold_cycle[(index - 1) % len(threshold_cycle)],
                rationale=rationale,
                retrieved_evidence=[hit.node_id for hit in retrieval.hits],
            ))

        # 先按算法族去重再截断：直接切前 N 条会出现「同族候选占满宽度、
        # 后续可用族被丢弃」，去重后 Top-N 才真的代表 N 种算法。
        for item in raw_plans:
            if len(plans) >= self.beam_width:
                break
            if not isinstance(item, dict):
                continue
            family = str(item.get("model_family", "logistic_regression"))
            if available and (family not in available or family in used):
                family = next((name for name in available if name not in used), "")
            operators = item.get("operators")
            _add(family,
                 operators if isinstance(operators, list) else [],
                 f"检索证据 {len(retrieval.hits)} 项；候选 {len(plans) + 1}（{family}）")

        if not plans:
            # 真实模型的输出未必符合契约（漏字段、纯自然语言）。这里按任务
            # 配置的算法族兜底，宁可降级为模板候选，也不让闭环在 generate
            # 节点以 IndexError 崩掉。
            fallback = available[: self.beam_width] or ["logistic_regression"]
            logger.warning("Planner 未返回有效候选（parsed keys=%s），按配置兜底：%s",
                           sorted(parsed), fallback)
            for family in fallback:
                _add(family, [], f"Planner 未返回候选，按配置兜底（{family}）")
        return plans


_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def _extract_code(response) -> str:
    """从 LLM 响应取代码：优先结构化字段，其次 markdown 代码块或裸代码。"""
    parsed = response.parsed if isinstance(response.parsed, dict) else {}
    code = parsed.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    match = _CODE_FENCE_RE.search(response.raw or "")
    if match:
        return match.group(1).strip()
    raw = (response.raw or "").strip()
    return raw if "def build_pipeline" in raw else ""


class Coder:
    """d. 生成可运行代码；检索证据进入 prompt。

    真实 LLM 返回的代码先过 AST 静态检查，通过才采用；解析失败或检查不过
    就回退参数化模板。``last_source`` / ``last_reject_reason`` 记录本次走了
    哪条路径，由工作流写进 ``RunTrace.code_sources``，不靠文档自述。
    """

    def __init__(self, llm: BaseLLM, checker: StaticChecker | None = None) -> None:
        self.llm = llm
        self.checker = checker
        self.last_source = "template"
        self.last_reject_reason = ""

    def _reject_reason(self, source: str, text_column: str) -> str:
        """LLM 代码能否采用；返回空串表示可用，否则给出拒收原因。"""
        if "def build_pipeline" not in source:
            return "缺少 build_pipeline 契约"
        if not text_column and "FEATURE_COLUMNS" not in source:
            return "缺少 FEATURE_COLUMNS"
        if self.checker is not None:
            result = self.checker.check(source)
            if not result.passed:
                return "静态检查未通过：" + ",".join(result.failed_checks())
        return ""

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
        request = LLMRequest(role="Coder", system=SYSTEM_PROMPTS["Coder"],
                             user=user, scene=task_type)
        response = self.llm.complete(request)
        hyperparams = dict(plan.hyperparams)
        if text_column:
            hyperparams["text_column"] = text_column
        # sampler 维度渲染：smote → SMOTE 采样步骤，class_weight → 模型参数，
        # none 不渲染（模板据此决定是否插入采样 / 类别权重）
        if plan.sampler and plan.sampler != "none":
            hyperparams["sampler"] = plan.sampler
        template = render(plan.model_family, rendered, hyperparams, task_type)
        self.last_source = "template"
        self.last_reject_reason = ""
        if response.source == "mock":
            # 规则模板输出只作契约示例，不冒充模型生成
            self.last_reject_reason = "MockLLM 输出仅作契约示例"
            return template
        candidate = _extract_code(response)
        if not candidate:
            self.last_reject_reason = "响应中没有可解析的代码"
            return template
        reason = self._reject_reason(candidate, text_column)
        if reason:
            self.last_reject_reason = reason
            logger.warning("LLM 代码未采用（%s），回退模板", reason)
            return template
        self.last_source = "llm"
        logger.info("采用 LLM 生成代码：候选 %s", plan.plan_id)
        return candidate


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
        # 重复 fit 的差值由沙箱实测，直接喂给「功能正确性 - 确定性」检查
        report = self.validator.validate(
            run_id=run_id, plan_id=plan_id, static=static,
            sandbox=run_result.sandbox, metrics=metrics,
            repeat_variance=run_result.context.get("repeat_variance"),
        )
        return report, metrics


class Repairer:
    """f. 按错误签名定向修复，按策略表只改必要片段。

    补丁是确定性的源码变换（不调用 LLM）：列名映射、剔除禁入模字段、
    注入 random_state。``forbidden`` 来自任务配置派生，避免把字段名写死在
    修复逻辑里；未提供时退化为不剔除（防御性，不误删）。
    """

    def __init__(self, llm: BaseLLM, forbidden: list[str] | None = None) -> None:
        self.llm = llm
        self.forbidden = set(forbidden or [])

    def repair(self, source: str, signature: str | None,
               round_index: int) -> tuple[str, RepairRecord]:
        key = signature or "Unknown"
        strategy = REPAIR_STRATEGIES.get(key, "无匹配策略，保留失败记录供人工分析")
        fixed = source
        if key == "KeyError: PAY_1":
            fixed = source.replace('"PAY_1"', '"PAY_0"')
        elif key in ("ForbiddenFeature", "LeakageDetected"):
            fixed = _repair_forbidden_feature(source, self.forbidden)
        elif key == "Nondeterminism":
            fixed = _repair_nondeterminism(source)
        request = LLMRequest(role="Repairer", system=SYSTEM_PROMPTS["Repairer"],
                             user=f"错误签名：{key}\n策略：{strategy}")
        self.llm.complete(request)
        record = RepairRecord(round=round_index, error_signature=key,
                              fix_strategy=strategy,
                              outcome="repaired" if fixed != source else "no_change")
        return fixed, record


def _run_ids_of(node: KGNode) -> list[str]:
    """失败案例的证据 run 列表；兼容早期只写了单个 ``run_id`` 的节点。"""
    runs = [str(item) for item in node.attributes.get("run_ids") or []]
    single = node.attributes.get("run_id")
    if single and str(single) not in runs:
        runs.append(str(single))
    return runs


def _accumulate_failure(node: KGNode, run_id: str, fix: str) -> KGNode:
    """累加失败案例的独立 run 数；同一 run 重跑视为同一条证据。"""
    attributes = dict(node.attributes)
    runs = _run_ids_of(node)
    if run_id not in runs:
        runs.append(run_id)
    attributes["run_ids"] = runs
    attributes["occurrences"] = len(runs)
    if fix and not attributes.get("fix_strategy"):
        attributes["fix_strategy"] = fix
    return node.model_copy(update={"attributes": attributes})


def _refresh_lesson(node: KGNode, observed: dict[str, int]) -> KGNode:
    """已沉淀的教训随新证据更新次数与置信度，而不是产生同义新节点。"""
    signatures = [str(item) for item in node.attributes.get("signatures") or []]
    occurrences = int(node.attributes.get("occurrences") or 1)
    seen = max([observed.get(signature, 0) for signature in signatures] or [0])
    if seen <= occurrences:
        return node
    attributes = {**node.attributes, "occurrences": seen,
                  "confidence": confidence_for(seen)}
    return node.model_copy(update={"attributes": attributes})


class Curator:
    """g. 沉淀：运行日志留痕，教训与能力版本才是可复用知识。

    分工明确——``ValidationRun`` 记录「某次跑了什么」，同一 run 重跑覆盖；
    失败案例按错误签名累积**独立 run 数**，达到阈值后提升为 ``Lesson``；
    能力版本只记录「因为哪条教训、修了哪些签名」，避免空壳版本节点。
    """

    def __init__(self, graph: KnowledgeGraph, llm: BaseLLM,
                 lesson_threshold: int = 2) -> None:
        self.graph = graph
        self.llm = llm
        self.lesson_threshold = lesson_threshold
        # 运行日志（ValidationRun）单独落盘，交付图谱只保留知识节点
        self.last_run_log_path: Path | None = None

    def sink(self, trace: RunTrace, reports: list[ValidationReport],
             out_path: Path) -> dict[str, int]:
        from factory.contracts.knowledge import EdgeType, KGEdge, KGNode, NodeType
        from factory.knowledge.graph import KnowledgeGraphStore

        nodes = list(self.graph.nodes)
        edges = list(self.graph.edges)
        anchor = next(
            (node.node_id for node in nodes if node.node_type is NodeType.CAPABILITY), None
        )
        run_prefix = f"run.{trace.run_id}."

        # 失败案例按签名累积「独立 run 数」：同一 run 重跑不重复计数，保证幂等，
        # 也就不会让一次偶发失败凭重跑次数变成「知识」
        failure_by_signature = {
            str(node.attributes.get("error_signature")): node
            for node in nodes if node.node_type is NodeType.FAILURE_CASE
        }
        merged = 0
        for repair in trace.repairs:
            node = failure_by_signature.get(repair.error_signature)
            if node is None:
                continue
            updated = _accumulate_failure(node, trace.run_id, repair.fix_strategy)
            if updated.attributes != node.attributes:
                nodes = [updated if item.node_id == node.node_id else item
                         for item in nodes]
                failure_by_signature[repair.error_signature] = updated
                merged += 1
        new_signatures = {repair.error_signature for repair in trace.repairs} - set(
            failure_by_signature
        )

        # 只有出现新失败签名才升版本：没有新经验时保留既有版本节点，
        # 同一 run_id 重跑也不会反复 +1，保证产物可复现
        upgraded = None
        next_version = 0
        if anchor and new_signatures:
            prefix = f"{anchor}.v"
            same_run = {node.node_id for node in nodes
                        if node.attributes.get("run_id") == trace.run_id}
            nodes = [node for node in nodes if node.node_id not in same_run]
            edges = [edge for edge in edges
                     if edge.source not in same_run and edge.target not in same_run]
            versions = [int(node.node_id[len(prefix):]) for node in nodes
                        if node.node_id.startswith(prefix)
                        and node.node_id[len(prefix):].isdigit()]
            next_version = (max(versions) if versions else 1) + 1
            upgraded = f"{prefix}{next_version}"

        def stale(node_id: str) -> bool:
            # 只覆盖本 run 的验证运行节点；失败案例按签名复用，跨 run 保留经验
            return node_id.startswith(run_prefix)

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
            known = failure_by_signature.get(repair.error_signature)
            if known is not None:
                failure_ids.append(known.node_id)
                continue
            failure_id = f"failure.{trace.run_id}.{index:02d}"
            failure_ids.append(failure_id)
            node = KGNode(
                node_id=failure_id, node_type=NodeType.FAILURE_CASE,
                name=f"失败案例 {repair.error_signature}",
                attributes={"error_signature": repair.error_signature,
                            "fix_strategy": repair.fix_strategy,
                            "repair_round": repair.round,
                            "run_id": trace.run_id,
                            "run_ids": [trace.run_id],
                            "occurrences": 1},
            )
            failure_by_signature[repair.error_signature] = node
            nodes.append(node)
            if anchor:
                edges.append(KGEdge(source=anchor, target=failure_id,
                                    edge_type=EdgeType.RESULTED_IN))
        # 教训优先于版本：先把累积够次数的失败案例提升为系统级知识，
        # 版本节点再引用这些教训，形成「现象 → 教训 → 修复」的可追溯链路
        interim = self.graph.model_copy(update={"nodes": nodes, "edges": edges})
        records, lesson_nodes, lesson_edges = promote_failures(interim,
                                                               self.lesson_threshold)
        nodes.extend(lesson_nodes)
        edges.extend(lesson_edges)
        observed = {
            str(node.attributes.get("error_signature")):
                int(node.attributes.get("occurrences") or 1)
            for node in nodes if node.node_type is NodeType.FAILURE_CASE
        }
        nodes = [_refresh_lesson(node, observed) if node.node_type is NodeType.LESSON
                 else node for node in nodes]

        if anchor and failure_ids and upgraded is not None:
            # 上一版本：v2 指向原始能力，v3 起指向前一版，形成版本链
            previous = (f"{anchor}.v{next_version - 1}"
                        if next_version > 2 else anchor)
            fixed = sorted(str(item) for item in new_signatures)
            related = [node.node_id for node in nodes
                       if node.node_type is NodeType.LESSON
                       and set(node.attributes.get("signatures") or []) & set(fixed)]
            nodes.append(KGNode(
                node_id=upgraded, node_type=NodeType.CAPABILITY,
                name=f"修复后的能力版本（{'、'.join(fixed)}）",
                version=f"v{next_version}",
                attributes={"derived_from": previous,
                            "run_id": trace.run_id,
                            "repair_rounds": len(trace.repairs),
                            "fixed_signatures": fixed,
                            "lesson_ids": related},
            ))
            edges.append(KGEdge(source=upgraded, target=previous,
                                edge_type=EdgeType.DERIVED_FROM))
            edges.append(KGEdge(source=failure_ids[-1], target=upgraded,
                                edge_type=EdgeType.FIXED_BY))
        updated = self.graph.model_copy(update={"nodes": nodes, "edges": edges})
        updated.validate_references()
        lessons_total = sum(1 for node in nodes if node.node_type is NodeType.LESSON)
        # 交付图谱只留知识：本轮产生的运行日志另存一个文件，避免「一打开沉淀
        # 产物全是 run.xxx」。材料里的历史实验记录属于证据型知识，仍留在图谱中。
        log_ids = {f"{run_prefix}{index:02d}" for index in range(1, len(reports) + 1)}
        knowledge_nodes = [node for node in nodes if node.node_id not in log_ids]
        knowledge_ids = {node.node_id for node in knowledge_nodes}
        knowledge_edges = [edge for edge in edges
                           if edge.source in knowledge_ids and edge.target in knowledge_ids]
        KnowledgeGraphStore(KnowledgeGraph(
            nodes=knowledge_nodes, edges=knowledge_edges,
            source_files=list(updated.source_files),
        )).export_json(out_path)
        self.last_run_log_path = out_path.with_name(f"{out_path.stem}_runs.json")
        KnowledgeGraphStore(KnowledgeGraph(
            nodes=[node for node in nodes if node.node_id in log_ids],
        )).export_json(self.last_run_log_path)
        request = LLMRequest(
            role="Curator", system=SYSTEM_PROMPTS["Curator"],
            user=(f"回写 {len(nodes)} 节点（教训 {lessons_total} 条），"
                  f"修复 {len(trace.repairs)} 轮"),
        )
        self.llm.complete(request)
        return {"nodes_added": len(nodes) - len(self.graph.nodes),
                "edges_added": len(edges) - len(self.graph.edges),
                "runs_recorded": len(reports),
                "failures_merged": merged,
                "lessons_promoted": len(records),
                "lessons_total": lessons_total}

    def explain(self, trace: RunTrace, *, retrieval: RetrievalResult | None = None,
                metric_name: str = "auc", direction: str = "maximize",
                threshold: float | None = None) -> str:
        """生成可回溯的设计依据：判据 → 证据 → 候选比较 → 排除原因 → 修复。

        早期版本是四行固定话术，连「为什么排除某个候选」都答不出来。这里把
        检索命中的节点 id、任务门槛、每个候选的实测指标与失败签名组织成因果链；
        纯确定性拼接，不调用 LLM，保证离线可复现、每句结论都能按节点 id 回溯。
        """
        ranked = sorted(trace.candidates, key=lambda item: -item.score)
        best = ranked[0] if ranked else None
        hits = retrieval.hits if retrieval else []
        constraints = retrieval.constraints if retrieval else []
        lessons = retrieval.lessons if retrieval else []
        gate = f"门槛 {threshold}" if threshold is not None else "门槛由任务配置给出"
        lines = [
            "## 设计依据",
            "",
            (f"- 评价口径：主指标 `{metric_name}`（{direction}，{gate}）；"
             "候选在 valid 段实测后统一打分排名，test 段只在比较结束后消费一次。"),
        ]
        evidence = "、".join(hit.node_id for hit in hits[:5]) or "无"
        lines.append(
            f"- 检索证据：命中 {len(hits)} 项（{evidence}），适用条件 {len(constraints)} 条、"
            f"系统级教训 {len(lessons)} 条已注入 Planner / Coder 的 prompt。")
        if constraints:
            lines.append("- 硬约束：" + "；".join(str(item)[:70] for item in constraints[:3]))
        if ranked:
            lines.append("- 候选实测比较：")
            for item in ranked:
                value = item.metrics.get(metric_name)
                value_text = "N/A" if value is None else f"{value:.4f}"
                lines.append(
                    f"  - `{item.plan_id}`（{item.model_family}）：{metric_name}={value_text} "
                    f"{'PASS' if item.passed else 'FAIL'}，修复 {item.repair_rounds} 轮")
        failed = [item.plan_id for item in ranked if not item.passed]
        if best is not None:
            reason = (f"主指标实测 {best.score:.4f} 排名第一且四层验证通过"
                      if best.passed else "本轮无候选通过全部四层，如实判 FAIL")
            excluded = (f"；未选 {', '.join(failed)}，因其未通过指标 / 四层门槛" if failed
                        else "；全部候选通过门槛，按主指标择优")
            lines.append(f"- 选择 `{best.plan_id}` 的依据：{reason}{excluded}。")
        if trace.repairs:
            lines.append("- 失败与定向修复：" + "；".join(
                f"`{item.error_signature}` → {item.fix_strategy}（{item.outcome}）"
                for item in trace.repairs))
            lines.append("- 这些签名已回写 `FailureCase`；同一签名在独立运行中出现达阈值后"
                         "提升为 `Lesson`，下一轮由检索注入 prompt。")
        else:
            lines.append("- 本轮未触发失败签名，无需定向修复。")
        lines.append("- 上述依据均可用节点 id 在图谱 / 报告中回溯，不含事后编造的数值。")
        return "\n".join(lines)


__all__ = [
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
