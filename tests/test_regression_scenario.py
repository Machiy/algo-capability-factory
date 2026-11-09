"""第二任务类型（回归）端到端测试：验证「换 yaml 即换任务」而不改核心验证器。

与信用卡场景的差异只有三处：``verify_regression.yaml``、``tabular_regression.*``
模板、以及 ``direction: minimize`` 的排序语义。
"""

from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from factory.agents import Coder, Planner
from factory.agents.templates import list_templates
from factory.config import load_settings, load_task_settings
from factory.contracts.knowledge import RetrievalResult
from factory.contracts.models import CapabilitySpec, TaskType
from factory.llm import MockLLM
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox
from factory.validation.metrics import compute, list_plugins

ROOT = Path(__file__).resolve().parents[1]
REGRESSION_CONFIG = ROOT / "configs/verify_regression.yaml"
SPEC = CapabilitySpec(spec_id="spec.regression.demand", description="预测日需求量",
                      task_type=TaskType.TABULAR_REGRESSION)


class RegressionConfigTests(unittest.TestCase):
    def test_config_is_active_and_regression_mode(self) -> None:
        task = load_task_settings(REGRESSION_CONFIG)
        self.assertEqual(task.task_type, "tabular_regression")
        self.assertTrue(task.dataset.path.endswith("synthetic_demand.csv"))
        self.assertEqual(task.dataset.target, "demand")
        self.assertEqual(task.metrics[0].name, "rmse")
        self.assertEqual(task.metrics[0].direction, "minimize")

    def test_metrics_and_templates_are_plugged_in(self) -> None:
        task = load_task_settings(REGRESSION_CONFIG)
        plugins = list_plugins()
        for spec in task.metrics:
            self.assertIn(spec.name, plugins[spec.plugin])
        registered = set(list_templates())
        for family in task.candidates.model_families:
            self.assertIn(f"tabular_regression.{family}", registered)


class RegressionTemplateTests(unittest.TestCase):
    def test_coder_renders_regressor_not_classifier(self) -> None:
        settings = load_settings(ROOT / "configs/default.yaml")
        task = load_task_settings(REGRESSION_CONFIG)
        plan = Planner(MockLLM()).plan(
            spec=SPEC, retrieval=RetrievalResult(query="需求量回归", top_k=0),
            families=task.candidates.model_families, task_type=task.task_type,
        )[0]
        source = Coder(MockLLM()).generate(
            plan, RetrievalResult(query="需求量回归", top_k=0), ["feature_1", "feature_2"],
            task_type=task.task_type,
        )
        self.assertIn("FEATURE_COLUMNS", source)
        self.assertTrue("Regressor" in source or "Ridge(" in source, source)
        result = StaticChecker(settings.runtime, task.dataset).check(source)
        self.assertTrue(result.passed, result.violations)


class RegressionSandboxTests(unittest.TestCase):
    def test_regression_metrics_are_real(self) -> None:
        settings = load_settings(ROOT / "configs/default.yaml")
        task = load_task_settings(REGRESSION_CONFIG)
        plan = Planner(MockLLM()).plan(
            spec=SPEC, retrieval=RetrievalResult(query="需求量回归", top_k=0),
            families=task.candidates.model_families, task_type=task.task_type,
        )[0]
        with (ROOT / task.dataset.path).open(encoding="utf-8") as handle:
            columns = [name for name in next(csv.reader(handle))
                       if name != task.dataset.target]
        source = Coder(MockLLM()).generate(
            plan, RetrievalResult(query="需求量回归", top_k=0), columns,
            task_type=task.task_type,
        )
        sandbox = DatasetSandbox(
            settings.runtime, task.split, ROOT / task.dataset.path,
            task.dataset.target, ["demand"], 3000, mode="regression",
        )
        result = sandbox.run(source)
        self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
        self.assertTrue(result.context["y_pred"])
        rmse = compute("sklearn_metrics", "rmse", **result.context)
        r2 = compute("sklearn_metrics", "r2", **result.context)
        self.assertIsNotNone(rmse)
        self.assertIsNotNone(r2)
        self.assertGreater(r2 or 0.0, 0.5)


class RegressionWorkflowTests(unittest.TestCase):
    def test_end_to_end_ranks_by_minimized_metric(self) -> None:
        from factory.workflow import Workflow

        with tempfile.TemporaryDirectory(prefix="factory_reg_ws_") as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "configs", root / "configs")
            shutil.copytree(
                ROOT / "assets", root / "assets",
                ignore=shutil.ignore_patterns("repo", "*.arff", "UCI_Credit_Card.csv",
                                              "sms_spam.csv"),
            )
            for sub in ("generated", "reports", "kg", "runs"):
                (root / "outputs" / sub).mkdir(parents=True, exist_ok=True)
            settings = load_settings(root / "configs/default.yaml")
            task = load_task_settings(root / "configs/verify_regression.yaml")
            workflow = Workflow(
                settings, task, root, task_config="configs/verify_regression.yaml",
                kg_filename="capabilities_regression_after_run.json",
            )
            trace = workflow.run("预测日需求量，最小化 RMSE", "unit_regression")
            self.assertTrue(trace.passed, trace.report_path)
            self.assertEqual(workflow.metric_name, "rmse")
            ranked = sorted(trace.candidates, key=lambda item: -item.score)
            rmse_values = [item.metrics["rmse"] for item in ranked]
            self.assertEqual(rmse_values, sorted(rmse_values),
                             "minimize 指标应让最好的候选排在最前")
            families = {item.model_family for item in trace.candidates}
            self.assertEqual(families, {"ridge", "hist_gradient_boosting_regressor",
                                        "random_forest_regressor"})
            report = (root / trace.report_path).read_text(encoding="utf-8")
            self.assertIn("verify_regression.yaml", report)
            self.assertIn("主指标 rmse", report)


if __name__ == "__main__":
    unittest.main()
