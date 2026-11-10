"""P3 工作流测试：检索证据进 prompt、真实数据陷阱触发、定向修复与图谱回写。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factory.agents import Coder, Curator, Planner, Repairer, Reviewer
from factory.config import load_settings, load_task_settings
from factory.contracts.knowledge import KGNode, NodeType, RetrievalHit, RetrievalResult
from factory.contracts.llm import LLMRequest, LLMResponse
from factory.contracts.models import CandidatePlan, ValidationReport
from factory.contracts.workflow import RunTrace
from factory.knowledge import MockExtractor, read_sources
from factory.knowledge.graph import KnowledgeGraphStore, load_graph
from factory.knowledge.retrieval import HybridRetriever
from factory.llm import MockLLM
from factory.llm.base import BaseLLM
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox
from factory.workflow.pipeline import SEVEN_STEPS

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"
TASK_CONFIG = ROOT / "configs/verify_credit.yaml"
COLUMNS = ["LIMIT_BAL", "PAY_0", "PAY_2", "BILL_AMT1", "PAY_AMT1"]


class RecordingLLM(BaseLLM):
    """记录请求，同时委托 MockLLM 给出确定性响应。"""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self._delegate = MockLLM()

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return self._delegate.complete(request)


def _retrieval(failure_warnings: list[str] | None = None) -> RetrievalResult:
    return RetrievalResult(
        query="预测信用卡客户下月违约概率",
        top_k=5,
        hits=[RetrievalHit(node_id="cap.risk_policy.C4", name="时间外划分", score=0.5)],
        constraints=["必须时间外划分"],
        failure_warnings=(failure_warnings if failure_warnings is not None
                          else ["KeyError: PAY_1 → 列名映射为 PAY_0"]),
    )


def _plan() -> CandidatePlan:
    return CandidatePlan(plan_id="plan.test", spec_id="spec.test",
                         model_family="logistic_regression", hyperparams={"C": 1.0})


class PromptInjectionTests(unittest.TestCase):
    def test_planner_receives_retrieval_evidence(self) -> None:
        from factory.agents import Interpreter
        llm = RecordingLLM()
        spec = Interpreter(llm).parse("预测信用卡客户下月违约概率")
        Planner(llm).plan(spec, _retrieval())
        user = llm.requests[-1].user
        self.assertIn("检索证据", user)
        self.assertIn("必须时间外划分", user)
        self.assertIn("历史失败规避项", user)

    def test_coder_receives_retrieval_evidence(self) -> None:
        llm = RecordingLLM()
        Coder(llm).generate(_plan(), _retrieval(), COLUMNS)
        user = llm.requests[-1].user
        self.assertIn("检索证据", user)
        self.assertIn("KeyError: PAY_1", user)

    def test_generated_code_passes_static_check(self) -> None:
        settings = load_settings(CONFIG)
        task = load_task_settings(TASK_CONFIG)
        source = Coder(MockLLM()).generate(_plan(), _retrieval(), COLUMNS)
        result = StaticChecker(settings.runtime, task.dataset).check(source)
        self.assertTrue(result.passed, result.violations)


class RepairTests(unittest.TestCase):
    def test_key_error_is_repaired_by_column_mapping(self) -> None:
        llm = RecordingLLM()
        source = Coder(MockLLM()).generate(
            _plan(), _retrieval(failure_warnings=[]), COLUMNS, induce_t1=True
        )
        self.assertIn('"PAY_1"', source)
        # 列名映射由 Dataset.column_aliases 派生，不写死在修复逻辑里
        fixed, record = Repairer(llm, column_aliases={"PAY_1": "PAY_0"}).repair(
            source, "KeyError: PAY_1", 1
        )
        self.assertNotIn('"PAY_1"', fixed)
        self.assertIn('"PAY_0"', fixed)
        self.assertEqual(record.outcome, "repaired")
        self.assertIn("column_aliases", record.fix_strategy)

    def test_key_error_without_alias_is_not_faked(self) -> None:
        """没有配置别名时不硬编码 PAY_1，如实记为 no_change。"""
        source = 'def build_pipeline(config):\n    return ["PAY_1"]\n'
        fixed, record = Repairer(MockLLM()).repair(source, "KeyError: PAY_1", 1)
        self.assertEqual(fixed, source)
        self.assertEqual(record.outcome, "no_change")

    def test_memory_limit_exceeded_injects_n_jobs(self) -> None:
        """MemoryLimitExceeded 注入 n_jobs=1 降低并行内存，已有 n_jobs 不动。"""
        source = (
            "from sklearn.ensemble import RandomForestClassifier\n"
            "from sklearn.pipeline import Pipeline\n\n"
            'FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0"]\n\n'
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", RandomForestClassifier(\n"
            "        n_estimators=5, random_state=42))])\n"
        )
        fixed, record = Repairer(MockLLM()).repair(source, "MemoryLimitExceeded", 1)
        self.assertIn("n_jobs=1", fixed)
        self.assertEqual(record.outcome, "repaired")
        # 已有 n_jobs 的不重复注入
        again, record2 = Repairer(MockLLM()).repair(fixed, "MemoryLimitExceeded", 1)
        self.assertEqual(again, fixed)
        self.assertEqual(record2.outcome, "no_change")

    def test_unknown_signature_is_not_silently_faked(self) -> None:
        source = "def build_pipeline(config):\n    return {}\n"
        fixed, record = Repairer(MockLLM()).repair(source, "UnknownError", 1)
        self.assertEqual(fixed, source)
        self.assertEqual(record.outcome, "no_change")

    def test_forbidden_feature_is_repaired(self) -> None:
        """ForbiddenFeature：从 FEATURE_COLUMNS 剔除 ID 与敏感字段。"""
        source = (
            "from sklearn.linear_model import LogisticRegression\n"
            "from sklearn.pipeline import Pipeline\n\n"
            'FEATURE_COLUMNS = ["LIMIT_BAL", "ID", "SEX", "PAY_0"]\n\n'
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", LogisticRegression(random_state=42))])\n"
        )
        fixed, record = Repairer(MockLLM(), ["ID", "SEX"]).repair(
            source, "ForbiddenFeature", 1
        )
        self.assertNotIn('"ID"', fixed)
        self.assertNotIn('"SEX"', fixed)
        self.assertIn('"LIMIT_BAL"', fixed)
        self.assertIn('"PAY_0"', fixed)
        self.assertEqual(record.outcome, "repaired")

    def test_leakage_detected_shares_forbidden_patch(self) -> None:
        """LeakageDetected 复用同一套剔除禁入模字段的补丁。"""
        source = (
            "from sklearn.linear_model import LogisticRegression\n"
            "from sklearn.pipeline import Pipeline\n\n"
            'FEATURE_COLUMNS = ["LIMIT_BAL", "default.payment.next.month"]\n\n'
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", LogisticRegression(random_state=42))])\n"
        )
        fixed, record = Repairer(MockLLM(), ["default.payment.next.month"]).repair(
            source, "LeakageDetected", 1
        )
        self.assertNotIn("default.payment.next.month", fixed)
        self.assertEqual(record.outcome, "repaired")

    def test_nondeterminism_injects_random_state(self) -> None:
        """Nondeterminism：给缺 random_state 的随机森林注入 random_state=42。"""
        source = (
            "from sklearn.ensemble import RandomForestClassifier\n"
            "from sklearn.pipeline import Pipeline\n\n"
            'FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0"]\n\n'
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", RandomForestClassifier(\n"
            "        n_estimators=5, max_depth=3, n_jobs=1))])\n"
        )
        fixed, record = Repairer(MockLLM()).repair(source, "Nondeterminism", 1)
        self.assertIn("random_state=42", fixed)
        self.assertEqual(record.outcome, "repaired")

    def test_nondeterminism_keeps_existing_random_state(self) -> None:
        """已有 random_state 的调用不重复注入，保证幂等。"""
        source = (
            "from sklearn.ensemble import RandomForestClassifier\n"
            "from sklearn.pipeline import Pipeline\n\n"
            'FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0"]\n\n'
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", RandomForestClassifier(random_state=7))])\n"
        )
        fixed, record = Repairer(MockLLM()).repair(source, "Nondeterminism", 1)
        self.assertEqual(fixed, source)
        self.assertEqual(record.outcome, "no_change")

    def test_reviewer_rejects_dangerous_import(self) -> None:
        settings = load_settings(CONFIG)
        task = load_task_settings(TASK_CONFIG)
        result = Reviewer(StaticChecker(settings.runtime, task.dataset)).review(
            "import subprocess\n\ndef build_pipeline(config):\n    return {}\n"
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.error_signature, "ImportError")


class PlannerFallbackTests(unittest.TestCase):
    """真实模型输出不符合契约时的兜底。

    实测：``.env`` 切到 ``openai_compat`` 后，Planner 返回自然语言，
    ``candidates`` 为空，工作流在 generate 节点以 IndexError 崩掉。
    """

    def test_fenced_json_is_parsed(self) -> None:
        from factory.llm.openai_compat import OpenAICompatLLM

        raw = '```json\n{"candidates": [{"model_family": "random_forest"}]}\n```'
        parsed = OpenAICompatLLM._parse(raw)
        self.assertEqual(parsed["candidates"][0]["model_family"], "random_forest")

    def test_plain_text_yields_no_candidates(self) -> None:
        from factory.llm.openai_compat import OpenAICompatLLM

        self.assertNotIn("candidates", OpenAICompatLLM._parse("我认为应该用逻辑回归"))

    def test_planner_falls_back_to_configured_families(self) -> None:
        from factory.agents import Interpreter

        class TextOnlyLLM(BaseLLM):
            """模拟只回自然语言的真实模型。"""

            def complete(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(raw="我认为应该用逻辑回归，先做 WOE 分箱",
                                   parsed={"text": "..."}, source="deepseek_api")

        families = ["logistic_regression", "random_forest", "hist_gradient_boosting"]
        spec = Interpreter(MockLLM()).parse("预测信用卡客户下月违约概率")
        plans = Planner(TextOnlyLLM()).plan(
            spec, _retrieval(), families=families,
            task_type="tabular_binary_classification",
        )
        self.assertEqual(len(plans), 3)
        self.assertEqual({plan.model_family for plan in plans}, set(families))
        self.assertIn("兜底", plans[0].rationale)

    def test_planner_writes_search_dimensions(self) -> None:
        """candidates.samplers / thresholds 维度写入候选，替换硬编码默认值。"""
        from factory.agents import Interpreter

        class FixedPlannerLLM(BaseLLM):
            def complete(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(
                    raw="", source="mock",
                    parsed={"candidates": [
                        {"model_family": "logistic_regression"},
                        {"model_family": "random_forest"},
                    ]},
                )

        spec = Interpreter(MockLLM()).parse("预测信用卡客户下月违约概率")
        plans = Planner(FixedPlannerLLM()).plan(
            spec, _retrieval(), families=["logistic_regression", "random_forest"],
            task_type="tabular_binary_classification",
            samplers=["none", "smote"], thresholds=[0.3, 0.5],
        )
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].sampler, "none")
        self.assertEqual(plans[0].threshold, 0.3)
        self.assertEqual(plans[1].sampler, "smote")
        self.assertEqual(plans[1].threshold, 0.5)

    def test_planner_defaults_when_dimensions_absent(self) -> None:
        """未传维度时退回 sampler="none" / threshold=0.5，旧调用行为不变。"""
        from factory.agents import Interpreter

        spec = Interpreter(MockLLM()).parse("预测信用卡客户下月违约概率")
        plans = Planner(MockLLM()).plan(
            spec, _retrieval(), families=["logistic_regression"],
            task_type="tabular_binary_classification",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].sampler, "none")
        self.assertEqual(plans[0].threshold, 0.5)


class CodeSourceLLM(BaseLLM):
    """返回指定源码的假后端，用于验证「采用 LLM 代码 / 回退模板」两条路径。"""

    def __init__(self, code: str, source: str = "deepseek_api") -> None:
        self.code = code
        self._source = source

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(raw=self.code, parsed={}, model="unit", source=self._source)


LLM_VALID_SOURCE = '''\
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0"]

def build_pipeline(config):
    return Pipeline([("model", LogisticRegression(max_iter=200, random_state=42))])
'''


class CodeSourceTests(unittest.TestCase):
    """P0-3：真实 LLM 的代码通过静态检查后采用，否则回退模板并记录原因。"""

    @classmethod
    def setUpClass(cls) -> None:
        settings = load_settings(CONFIG)
        task = load_task_settings(TASK_CONFIG)
        cls.checker = StaticChecker(settings.runtime, task.dataset)

    def test_valid_llm_code_is_adopted(self) -> None:
        coder = Coder(CodeSourceLLM(LLM_VALID_SOURCE), self.checker)
        source = coder.generate(_plan(), _retrieval(), COLUMNS)
        self.assertEqual(coder.last_source, "llm")
        self.assertIn("def build_pipeline", source)
        self.assertNotIn("StandardScaler", source)
        self.assertTrue(self.checker.check(source).passed)

    def test_dangerous_llm_code_falls_back_to_template(self) -> None:
        coder = Coder(CodeSourceLLM(
            "import subprocess\n\n"
            'FEATURE_COLUMNS = ["LIMIT_BAL"]\n\n'
            "def build_pipeline(config):\n    return {}\n"
        ), self.checker)
        source = coder.generate(_plan(), _retrieval(), COLUMNS)
        self.assertEqual(coder.last_source, "template")
        self.assertIn("静态检查未通过", coder.last_reject_reason)
        self.assertIn("Pipeline", source)

    def test_mock_output_never_counts_as_llm_code(self) -> None:
        coder = Coder(MockLLM(), self.checker)
        coder.generate(_plan(), _retrieval(), COLUMNS)
        self.assertEqual(coder.last_source, "template")
        self.assertIn("MockLLM", coder.last_reject_reason)

    def test_missing_feature_columns_is_rejected(self) -> None:
        coder = Coder(CodeSourceLLM(
            "from sklearn.pipeline import Pipeline\n\n"
            "def build_pipeline(config):\n    return Pipeline([])\n"
        ), self.checker)
        coder.generate(_plan(), _retrieval(), COLUMNS)
        self.assertEqual(coder.last_source, "template")
        self.assertIn("FEATURE_COLUMNS", coder.last_reject_reason)


class DatasetSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG)
        cls.task = load_task_settings(TASK_CONFIG)
        cls.sandbox = DatasetSandbox(
            cls.settings.runtime, cls.task.split, ROOT / cls.settings.paths.data,
            cls.task.dataset.target,
            sorted(set(cls.task.dataset.forbidden_features) | set(cls.task.sensitive_features)),
            n_samples=30000,
        )

    def test_t1_trap_raises_real_key_error(self) -> None:
        source = Coder(MockLLM()).generate(
            _plan(), _retrieval(failure_warnings=[]), COLUMNS, induce_t1=True
        )
        result = self.sandbox.run(source)
        self.assertFalse(result.sandbox.passed)
        self.assertEqual(result.sandbox.error_signature, "KeyError: PAY_1")

    def test_repaired_code_produces_real_metrics(self) -> None:
        source = Coder(MockLLM()).generate(_plan(), _retrieval(), COLUMNS)
        result = self.sandbox.run(source)
        self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
        self.assertTrue(result.context["y_true"])
        self.assertTrue(result.context["y_score"])

    def test_repeat_produces_determinism_evidence(self) -> None:
        """P0-1：repeat>=2 必须给出实测差值，而不是让该项恒真。"""
        source = Coder(MockLLM()).generate(_plan(), _retrieval(), COLUMNS)
        result = self.sandbox.run(source, repeat=2)
        self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
        variance = result.context["repeat_variance"]
        self.assertIsNotNone(variance)
        self.assertLess(variance, 1e-9)

    def test_non_deterministic_model_is_detected(self) -> None:
        """无 random_state 的随机森林两次 fit 必然不同，差值为正并被量化为方差。"""
        source = (
            "from sklearn.ensemble import RandomForestClassifier\n"
            "from sklearn.pipeline import Pipeline\n\n"
            f"FEATURE_COLUMNS = {COLUMNS!r}\n\n"
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", RandomForestClassifier(\n"
            "        n_estimators=5, max_depth=3, n_jobs=1))])\n"
        )
        result = self.sandbox.run(source, repeat=2)
        self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
        self.assertGreater(result.context["repeat_variance"], 0.0)

    def test_nondeterminism_repair_restores_determinism(self) -> None:
        """修复闭环：注入 random_state 后，二次 fit 的输出差归零。"""
        source = (
            "from sklearn.ensemble import RandomForestClassifier\n"
            "from sklearn.pipeline import Pipeline\n\n"
            f"FEATURE_COLUMNS = {COLUMNS!r}\n\n"
            "def build_pipeline(config):\n"
            "    return Pipeline([(\"model\", RandomForestClassifier(\n"
            "        n_estimators=5, max_depth=3, n_jobs=1))])\n"
        )
        fixed, record = Repairer(MockLLM()).repair(source, "Nondeterminism", 1)
        self.assertEqual(record.outcome, "repaired")
        result = self.sandbox.run(fixed, repeat=2)
        self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
        self.assertLess(result.context["repeat_variance"], 1e-9)

    def test_test_segment_is_held_out(self) -> None:
        """P0-2：test 段与 valid 段互不重叠，长度为末段样本数。"""
        source = Coder(MockLLM()).generate(_plan(), _retrieval(), COLUMNS)
        valid = self.sandbox.run(source)
        test = self.sandbox.run(source, segment="test")
        self.assertTrue(test.sandbox.passed, test.sandbox.stderr)
        self.assertEqual(test.context["segment"], "test")
        self.assertEqual(len(test.context["y_true"]),
                         self.sandbox.n_samples - self.sandbox.valid_end)
        self.assertNotEqual(valid.context["y_true"][:5], test.context["y_true"][:5])


class CuratorTests(unittest.TestCase):
    def test_sink_splits_knowledge_from_run_log(self) -> None:
        """交付图谱只留知识，运行日志另存一个文件 —— 避免「沉淀产物全是日志」。"""
        settings = load_settings(CONFIG)
        sources = read_sources(ROOT, settings.paths.docs, settings.paths.legacy)
        graph = MockExtractor().extract(sources)
        trace = RunTrace(
            run_id="unit", spec="测试",
            repairs=[Repairer(MockLLM()).repair("x", "KeyError: PAY_1", 1)[1]],
        )
        reports = [ValidationReport(run_id="unit", plan_id="plan.test", passed=False,
                                    metric_values={"auc": 0.72})]
        curator = Curator(graph, MockLLM())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "kg.json"
            diff = curator.sink(trace, reports, out)
            payload = json.loads(out.read_text(encoding="utf-8"))
            run_log = json.loads((Path(tmp) / "kg_runs.json").read_text(encoding="utf-8"))
        self.assertGreater(diff["nodes_added"], 0)
        self.assertGreater(diff["edges_added"], 0)
        node_ids = {node["node_id"] for node in payload["nodes"]}
        node_types = {node["node_type"] for node in payload["nodes"]}
        # 本轮运行日志不进交付图谱；材料里的历史实验记录仍作为证据保留
        self.assertNotIn("run.unit.01", node_ids)
        self.assertIn("FailureCase", node_types)
        self.assertEqual(diff["runs_recorded"], len(reports))
        self.assertEqual([node["node_type"] for node in run_log["nodes"]],
                         ["ValidationRun"] * len(reports))
        edge_types = {edge["edge_type"] for edge in payload["edges"]}
        self.assertIn("RESULTED_IN", edge_types)
        self.assertIn("DERIVED_FROM", edge_types)
        self.assertIn("FIXED_BY", edge_types)


class PersistenceTests(unittest.TestCase):
    """P4：回写图谱能被下一轮读取，历史失败经验改变首轮行为。"""

    def test_coder_avoids_t1_when_history_present(self) -> None:
        source = Coder(MockLLM()).generate(_plan(), _retrieval(), COLUMNS, induce_t1=True)
        self.assertNotIn('"PAY_1"', source)
        self.assertIn('"PAY_0"', source)

    def test_retrieval_prefers_measured_failure_cases(self) -> None:
        settings = load_settings(CONFIG)
        sources = read_sources(ROOT, settings.paths.docs, settings.paths.legacy)
        graph = MockExtractor().extract(sources)
        measured = KGNode(
            node_id="failure.unit.01", node_type=NodeType.FAILURE_CASE,
            name="失败案例 KeyError: PAY_1",
            attributes={"error_signature": "KeyError: PAY_1",
                        "fix_strategy": "列名映射为 PAY_0"},
        )
        graph = graph.model_copy(update={"nodes": [*graph.nodes, measured]})
        warnings = HybridRetriever(graph, top_k=5).retrieve(
            "预测信用卡客户下月违约概率"
        ).failure_warnings
        self.assertTrue(any("PAY_1" in item for item in warnings))

    def test_load_graph_roundtrip(self) -> None:
        settings = load_settings(CONFIG)
        sources = read_sources(ROOT, settings.paths.docs, settings.paths.legacy)
        graph = MockExtractor().extract(sources)
        with tempfile.TemporaryDirectory() as tmp:
            path = KnowledgeGraphStore(graph).export_json(Path(tmp) / "g.json")
            loaded = load_graph(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.nodes), len(graph.nodes))
        self.assertEqual(len(loaded.edges), len(graph.edges))

    def test_curator_sink_is_idempotent(self) -> None:
        settings = load_settings(CONFIG)
        sources = read_sources(ROOT, settings.paths.docs, settings.paths.legacy)
        graph = MockExtractor().extract(sources)
        trace = RunTrace(
            run_id="unit", spec="测试",
            repairs=[Repairer(MockLLM()).repair("x", "KeyError: PAY_1", 1)[1]],
        )
        reports = [ValidationReport(run_id="unit", plan_id="plan.test",
                                    passed=False, metric_values={"auc": 0.72})]
        curator = Curator(graph, MockLLM())
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.json"
            curator.sink(trace, reports, first)
            graph_after_first = load_graph(first)
            second = Curator(graph_after_first, MockLLM())
            second_path = Path(tmp) / "b.json"
            second.sink(trace, reports, second_path)
            graph_after_second = load_graph(second_path)
            first_log = json.loads((Path(tmp) / "a_runs.json").read_text(encoding="utf-8"))
            second_log = json.loads((Path(tmp) / "b_runs.json").read_text(encoding="utf-8"))
        self.assertEqual(len(graph_after_second.nodes), len(graph_after_first.nodes))
        self.assertEqual(len(graph_after_second.edges), len(graph_after_first.edges))
        # 知识图与运行日志都幂等：同一 run 重跑不膨胀
        self.assertEqual(len(second_log["nodes"]), len(first_log["nodes"]))


class WorkflowConfigTests(unittest.TestCase):
    """P0-5：beam_width / max_repair_rounds 必须真的从 yaml 读取。"""

    def test_workflow_section_drives_rounds_and_width(self) -> None:
        from factory.workflow import Workflow

        payload = CONFIG.read_text(encoding="utf-8")
        payload = payload.replace("beam_width: 3", "beam_width: 1")
        payload = payload.replace("max_repair_rounds: 3", "max_repair_rounds: 1")
        with tempfile.TemporaryDirectory(prefix="factory_cfg_") as tmp:
            config = Path(tmp) / "default.yaml"
            config.write_text(payload, encoding="utf-8")
            settings = load_settings(config)
            task = load_task_settings(TASK_CONFIG)
            workflow = Workflow(settings, task, ROOT)
        self.assertEqual(workflow.max_rounds, 1)
        self.assertEqual(workflow.planner.beam_width, 1)

    def test_candidate_settings_loads_search_dimensions(self) -> None:
        """candidates 的 binnings/samplers/thresholds 不再被 extra=ignore 丢弃。"""
        task = load_task_settings(TASK_CONFIG)
        self.assertEqual(task.candidates.samplers, ["none", "smote", "class_weight"])
        self.assertEqual(task.candidates.thresholds, [0.30, 0.50, "cost_optimal"])
        self.assertEqual(task.candidates.binnings, ["none", "woe"])

    def test_search_expand_composes_dimensions(self) -> None:
        """A1：候选扩展组合 model_family × sampler × threshold，受预算限制。"""
        from factory.workflow import Workflow

        workflow = Workflow(load_settings(CONFIG), load_task_settings(TASK_CONFIG), ROOT)
        base = [CandidatePlan(plan_id="plan.01", spec_id="s",
                              model_family="logistic_regression")]
        workflow.search = workflow.search.model_copy(update={
            "halving_enabled": True, "candidate_budget": 6})
        expanded = workflow._expand_candidates(base)
        self.assertEqual(len(expanded), 6)  # 1×3×3=9 截断到 6
        self.assertEqual([p.plan_id for p in expanded],
                         [f"plan.{i:02d}" for i in range(1, 7)])
        self.assertEqual(expanded[0].sampler, "none")
        self.assertEqual(expanded[0].threshold, 0.30)

    def test_after_plan_routes_by_halving_flag(self) -> None:
        """A1：开启时 plan 后走 smoke，关闭时直接 generate。"""
        from factory.workflow import Workflow

        workflow = Workflow(load_settings(CONFIG), load_task_settings(TASK_CONFIG), ROOT)
        self.assertEqual(workflow._after_plan({}), "smoke")  # 默认开启
        workflow.search = workflow.search.model_copy(update={"halving_enabled": False})
        self.assertEqual(workflow._after_plan({}), "generate")

    def test_test_gate_wired_into_workflow(self) -> None:
        """test 段一次性纪律由 TestGate 硬保证：重复消费被拒且不再跑 test 段。"""
        from factory.contracts.workflow import CandidateEvaluation
        from factory.workflow import Workflow

        workflow = Workflow(load_settings(CONFIG), load_task_settings(TASK_CONFIG), ROOT)
        self.assertTrue(workflow._test_gate.enabled)
        trace = RunTrace(
            run_id="unit", spec="测试",
            candidates=[CandidateEvaluation(
                plan_id="plan.test", model_family="logistic_regression",
                passed=True, score=0.5)],
        )
        workflow._test_gate.consume()  # 预置为已消费
        with patch.object(Path, "is_file", return_value=True), \
             patch.object(workflow.sandbox, "run") as mock_run:
            result = workflow._finalize_on_test(trace)
        self.assertFalse(result.consumed)
        self.assertIn("拒绝重复访问", result.note)
        mock_run.assert_not_called()  # 门禁拦下，未真正跑 test 段

    def test_env_overrides_apply_only_when_requested(self) -> None:
        """`.env` 的 LLM_PROVIDER 只在显式要求时生效。

        默认不读环境变量，否则开发者本地填了真实后端后，一跑单测就会
        产生真实请求与费用。
        """
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai_compat",
                                     "LLM_MODEL": "unit-model",
                                     "LLM_MAX_TOKENS": "1234"}):
            default = load_settings(CONFIG)
            applied = load_settings(CONFIG, apply_env=True)
        self.assertEqual(default.llm.provider, "mock")
        self.assertEqual(applied.llm.provider, "openai_compat")
        self.assertEqual(applied.llm.model, "unit-model")
        self.assertEqual(applied.llm.max_tokens, 1234)

    def test_invalid_env_value_is_ignored(self) -> None:
        with patch.dict(os.environ, {"LLM_MAX_TOKENS": "not-a-number"}):
            settings = load_settings(CONFIG, apply_env=True)
        self.assertEqual(settings.llm.max_tokens, 8192)

    def test_missing_workflow_section_falls_back_to_defaults(self) -> None:
        import yaml

        data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        data.pop("workflow", None)
        with tempfile.TemporaryDirectory(prefix="factory_cfg_") as tmp:
            config = Path(tmp) / "default.yaml"
            config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            settings = load_settings(config)
        self.assertEqual(settings.workflow.beam_width, 3)
        self.assertEqual(settings.workflow.max_repair_rounds, 3)


class TraceContractTests(unittest.TestCase):
    def test_seven_steps_are_declared(self) -> None:
        self.assertEqual(len(SEVEN_STEPS), 7)
        self.assertTrue(all(step.startswith(tuple("abcdefg")) for step in SEVEN_STEPS))

    def test_trace_rejects_unknown_fields(self) -> None:
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            RunTrace(run_id="x", spec="y", typo=1)


class LiveReportHeaderTests(unittest.TestCase):
    """报告页眉必须说明本次是不是真实 LLM，不能把实时调用写成 Mock 路径。"""

    def _render(self, trace: RunTrace) -> str:
        from factory.workflow.pipeline import render_run_report

        with tempfile.TemporaryDirectory() as tmp:
            path = render_run_report(trace, [], "设计依据", Path(tmp) / "r.md")
            return path.read_text(encoding="utf-8")

    def test_live_llm_report_header(self) -> None:
        trace = RunTrace(run_id="live", spec="测试",
                         interpreter_source="deepseek_api",
                         code_sources={"plan.01": "llm"})
        text = self._render(trace)
        self.assertIn("全链路接入真实 LLM", text)
        self.assertNotIn("核心闭环演示走 `MockLLM` 规则模板路径", text)

    def test_mock_report_header(self) -> None:
        trace = RunTrace(run_id="demo", spec="测试",
                         interpreter_source="mock")
        text = self._render(trace)
        self.assertIn("`MockLLM` 规则模板路径", text)
        self.assertNotIn("全链路接入真实 LLM", text)


class ReviewCollaborationTests(unittest.TestCase):
    """B2：Reviewer 语义评审 + 反馈环 + 协作记录。"""

    def test_semantic_review_parses_structured(self) -> None:
        from factory.agents.roles import _parse_semantic_review

        passed, comment = _parse_semantic_review(
            {"passed": False, "comment": "违背禁入模约束"}, "")
        self.assertFalse(passed)
        self.assertEqual(comment, "违背禁入模约束")
        ok, _ = _parse_semantic_review({"passed": True}, "")
        self.assertTrue(ok)

    def test_semantic_review_defaults_to_pass(self) -> None:
        """无法解析时按通过处理，不阻塞主流程。"""
        from factory.agents.roles import _parse_semantic_review

        passed, _ = _parse_semantic_review({"role": "Reviewer"}, "")
        self.assertTrue(passed)

    def test_reviewer_without_llm_passes(self) -> None:
        from factory.agents.roles import Reviewer
        from factory.contracts.knowledge import RetrievalResult
        from factory.runtime import StaticChecker

        settings = load_settings(CONFIG)
        task = load_task_settings(TASK_CONFIG)
        reviewer = Reviewer(StaticChecker(settings.runtime, task.dataset))
        passed, comment = reviewer.review_semantics(
            "def build_pipeline(config):\n    return {}\n",
            RetrievalResult(query="测试", top_k=0),
        )
        self.assertTrue(passed)
        self.assertEqual(comment, "")

    def test_after_review_routes(self) -> None:
        """否决且未达上限时回 generate，否则进入 execute。"""
        from factory.workflow import Workflow

        workflow = Workflow(load_settings(CONFIG), load_task_settings(TASK_CONFIG), ROOT)
        self.assertEqual(workflow._after_review({"review_comment": "违规"}), "generate")
        self.assertEqual(workflow._after_review({"review_comment": ""}), "execute")

    def test_feedback_loop_records_and_routes(self) -> None:
        """Reviewer 否决时记录协作并带意见回 generate。"""
        from factory.agents.roles import Reviewer
        from factory.contracts.knowledge import RetrievalResult
        from factory.contracts.llm import LLMResponse
        from factory.contracts.models import CandidatePlan
        from factory.contracts.workflow import RunTrace
        from factory.llm.base import BaseLLM
        from factory.runtime import StaticChecker
        from factory.workflow import Workflow

        class RejectLLM(BaseLLM):
            def complete(self, request) -> LLMResponse:
                parsed = {"passed": False, "comment": "违背禁入模约束"}
                return LLMResponse(raw=json.dumps(parsed, ensure_ascii=False),
                                   parsed=parsed, source="mock")

        settings = load_settings(CONFIG)
        task = load_task_settings(TASK_CONFIG)
        workflow = Workflow(settings, task, ROOT)
        workflow.reviewer = Reviewer(StaticChecker(settings.runtime, task.dataset),
                                     RejectLLM())
        plan = CandidatePlan(plan_id="plan.01", spec_id="s",
                             model_family="logistic_regression")
        trace = RunTrace(run_id="unit", spec="测试")
        trace.code_sources[plan.plan_id] = "llm"
        state = {
            "trace": trace, "plan": plan,
            "source": "def build_pipeline(config):\n    return {}\n",
            "retrieval": RetrievalResult(query="测试", top_k=0),
            "review_rounds": 0,
        }
        result = workflow._n_review(state)
        self.assertEqual(result["review_comment"], "违背禁入模约束")
        self.assertEqual(trace.collaborations[-1].kind, "review_reject")
        self.assertEqual(trace.collaborations[-1].sender, "Reviewer")
        self.assertEqual(workflow._after_review(result), "generate")


if __name__ == "__main__":
    unittest.main()
