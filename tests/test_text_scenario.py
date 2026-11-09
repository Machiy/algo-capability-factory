"""P6-1 跨场景迁移测试：同一套框架跑通文本分类，不改核心验证器。

表格场景用时间外划分与 AUC/KS，文本场景用随机切分与 accuracy/macro-F1；
两者只差 ``verify_*.yaml`` 与算法模板，验证器 / 沙箱 / 工作流代码不变。
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from factory.agents import Coder, Planner
from factory.agents.templates import list_templates
from factory.config import load_settings, load_task_settings
from factory.contracts.knowledge import NodeType, RetrievalResult
from factory.contracts.models import CapabilitySpec, TaskType
from factory.knowledge import MockExtractor, read_sources
from factory.llm import MockLLM
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox
from factory.validation.metrics import compute, list_plugins

ROOT = Path(__file__).resolve().parents[1]
TEXT_CONFIG = ROOT / "configs/verify_text.yaml"
CREDIT_CONFIG = ROOT / "configs/verify_credit.yaml"
SPEC = CapabilitySpec(spec_id="spec.text.spam", description="把短信分类为垃圾短信或正常短信",
                      task_type=TaskType.TEXT_CLASSIFICATION)


class TextKnowledgeTests(unittest.TestCase):
    """场景子图：文本任务从自己的材料抽能力，不混入信用卡域约束。"""

    def test_text_sources_produce_own_subgraph(self) -> None:
        task = load_task_settings(TEXT_CONFIG)
        self.assertEqual(task.knowledge.docs, "assets/docs/text")
        sources = read_sources(ROOT, task.knowledge.docs, task.knowledge.legacy)
        self.assertEqual(len(sources), 3)
        graph = MockExtractor().extract(sources)
        capabilities = graph.by_type(NodeType.CAPABILITY)
        self.assertGreaterEqual(len(capabilities), 8)
        self.assertTrue(all("sms_" in node.node_id for node in capabilities))
        signatures = {node.attributes.get("error_signature")
                      for node in graph.by_type(NodeType.FAILURE_CASE)}
        self.assertIn("LeakageDetected", signatures)
        self.assertIn("MetricBelowThreshold", signatures)


class TextConfigTests(unittest.TestCase):
    def test_config_is_active_and_text_mode(self) -> None:
        task = load_task_settings(TEXT_CONFIG)
        self.assertEqual(task.task_type, "text_classification")
        self.assertEqual(task.dataset.text_column, "text")
        self.assertEqual(task.dataset.target, "label")
        self.assertTrue(task.dataset.path.endswith("sms_spam.csv"))
        self.assertEqual(task.metrics[0].name, "accuracy")

    def test_metrics_and_templates_are_plugged_in(self) -> None:
        task = load_task_settings(TEXT_CONFIG)
        plugins = list_plugins()
        for spec in task.metrics:
            self.assertIn(spec.name, plugins[spec.plugin])
        registered = set(list_templates())
        for family in task.candidates.model_families:
            self.assertIn(f"text_classification.{family}", registered)

    def test_credit_scenario_still_tabular(self) -> None:
        task = load_task_settings(CREDIT_CONFIG)
        self.assertEqual(task.dataset.text_column, "")
        self.assertEqual(task.metrics[0].name, "auc")


class TextTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(ROOT / "configs/default.yaml")
        cls.task = load_task_settings(TEXT_CONFIG)
        cls.checker = StaticChecker(cls.settings.runtime, cls.task.dataset)

    def test_planner_uses_config_families_for_text(self) -> None:
        plans = Planner(MockLLM()).plan(
            spec=SPEC,
            retrieval=RetrievalResult(query="短信分类", top_k=3),
            families=self.task.candidates.model_families,
            task_type=self.task.task_type,
        )
        families = [plan.model_family for plan in plans]
        self.assertEqual(families, ["logistic_regression", "linear_svc", "complement_nb"])

    def test_coder_renders_text_pipeline(self) -> None:
        plan = Planner(MockLLM()).plan(
            spec=SPEC,
            retrieval=RetrievalResult(query="短信分类", top_k=3),
            families=self.task.candidates.model_families,
            task_type=self.task.task_type,
        )[0]
        source = Coder(MockLLM()).generate(
            plan, RetrievalResult(query="短信分类", top_k=0), [],
            task_type=self.task.task_type, text_column=self.task.dataset.text_column,
        )
        self.assertIn("TfidfVectorizer", source)
        self.assertIn('TEXT_COLUMN = "text"', source)
        result = self.checker.check(source)
        self.assertTrue(result.passed, result.violations)


class TextSandboxTests(unittest.TestCase):
    def test_text_pipeline_produces_real_accuracy(self) -> None:
        settings = load_settings(ROOT / "configs/default.yaml")
        task = load_task_settings(TEXT_CONFIG)
        plan = Planner(MockLLM()).plan(
            spec=SPEC,
            retrieval=RetrievalResult(query="短信分类", top_k=0),
            families=task.candidates.model_families, task_type=task.task_type,
        )[0]
        source = Coder(MockLLM()).generate(
            plan, RetrievalResult(query="短信分类", top_k=0), [],
            task_type=task.task_type, text_column=task.dataset.text_column,
        )
        sandbox = DatasetSandbox(
            settings.runtime, task.split, ROOT / task.dataset.path,
            task.dataset.target, ["label"], 5574,
            text_column=task.dataset.text_column,
        )
        result = sandbox.run(source)
        self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
        self.assertTrue(result.context["y_pred"])
        accuracy = compute("sklearn_metrics", "accuracy", **result.context)
        self.assertIsNotNone(accuracy)
        self.assertGreater(accuracy or 0.0, 0.90)


class TextWorkflowTests(unittest.TestCase):
    """端到端：在临时工作区跑七步闭环，避免污染仓库内已入库的示例产物。"""

    def test_end_to_end_text_run_passes(self) -> None:
        from factory.workflow import Workflow

        with tempfile.TemporaryDirectory(prefix="factory_text_ws_") as tmp:
            root = Path(tmp)
            for name in ("configs", "assets"):
                shutil.copytree(ROOT / name, root / name,
                                ignore=shutil.ignore_patterns(
                                    "repo", "*.arff", "UCI_Credit_Card.csv"))
            for sub in ("generated", "reports", "kg", "runs"):
                (root / "outputs" / sub).mkdir(parents=True, exist_ok=True)
            settings = load_settings(root / "configs/default.yaml")
            task = load_task_settings(root / "configs/verify_text.yaml")
            workflow = Workflow(
                settings, task, root, task_config="configs/verify_text.yaml",
                kg_filename="capabilities_text_after_run.json",
            )
            trace = workflow.run("把短信分类为垃圾短信或正常短信", "unit_text")
            self.assertTrue(trace.passed, trace.report_path)
            self.assertEqual(len(trace.candidates), 3)
            families = {item.model_family for item in trace.candidates}
            self.assertEqual(families, {"logistic_regression", "linear_svc",
                                        "complement_nb"})
            # 检索证据必须来自文本域子图，不能混入信用卡列名约束
            self.assertIn("词表", trace.retrieval_prompt)
            self.assertNotIn("PAY_1", trace.retrieval_prompt)
            for item in trace.candidates:
                self.assertGreater(item.metrics.get("accuracy") or 0.0, 0.90)
            report = root / trace.report_path
            self.assertTrue(report.is_file())
            self.assertIn("verify_text.yaml", report.read_text(encoding="utf-8"))
            self.assertTrue((root / "outputs/kg/capabilities_text_after_run.json").is_file())


if __name__ == "__main__":
    unittest.main()
