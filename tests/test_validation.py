"""P2 验证层测试：指标插件、换任务配置、时间外划分与四层检查器。

「不同任务类型的验证配置」用三份 verify_*.yaml 逐一加载并核对插件可用性，
证明切换任务不改核心验证器；进阶要求的验收点在此覆盖。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory.config import load_task_settings
from factory.contracts.models import ValidationReport
from factory.contracts.validation import (
    MetricResult,
    MetricSpec,
    SandboxResult,
    SplitSpec,
    StaticCheckResult,
)
from factory.validation import (
    FourLayerValidator,
    TemporalSplitter,
    TestGate,
    compute,
    list_plugins,
    render_report,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"


def _static(passed: bool = True) -> StaticCheckResult:
    return StaticCheckResult(
        passed=passed,
        checks={"syntax": passed, "import_whitelist": passed},
        source_sha256="a" * 64,
        error_signature=None if passed else "ImportError",
    )


def _sandbox(passed: bool = True) -> SandboxResult:
    return SandboxResult(
        passed=passed,
        returncode=0 if passed else 1,
        duration_seconds=1.2,
        peak_memory_mb=128.0,
        memory_limit_applied=True,
        error_signature=None if passed else "RuntimeError",
    )


class MetricPluginTests(unittest.TestCase):
    def test_all_task_configs_are_backed_by_plugins(self) -> None:
        plugins = list_plugins()
        for name in ("verify_credit.yaml", "verify_regression.yaml", "verify_text.yaml"):
            task = load_task_settings(CONFIG_DIR / name)
            with self.subTest(config=name):
                self.assertTrue(task.metrics)
                for spec in task.metrics:
                    self.assertIn(spec.plugin, plugins)
                    self.assertIn(spec.name, plugins[spec.plugin])

    def test_classification_metrics(self) -> None:
        y_true = [0, 0, 1, 1, 0, 1, 1, 0]
        y_score = [0.1, 0.2, 0.8, 0.9, 0.3, 0.7, 0.85, 0.15]
        auc = compute("sklearn_metrics", "auc", y_true=y_true, y_score=y_score)
        ks = compute("credit_metrics", "ks", y_true=y_true, y_score=y_score)
        self.assertAlmostEqual(auc or 0.0, 1.0, places=5)
        self.assertAlmostEqual(ks or 0.0, 1.0, places=5)

    def test_cost_loss_and_psi(self) -> None:
        y_true = [0, 1, 1, 0]
        y_score = [0.1, 0.2, 0.9, 0.8]
        cost = compute("credit_metrics", "cost_weighted_loss",
                       y_true=y_true, y_score=y_score, cost_ratio=5.0)
        self.assertIsNotNone(cost)
        self.assertGreater(cost or 0.0, 0.0)
        reference = [0.1, 0.2, 0.3, 0.4]
        psi = compute("credit_metrics", "psi", reference=reference, current=reference)
        self.assertIsNotNone(psi)
        self.assertAlmostEqual(float(psi or 0.0), 0.0, places=6)

    def test_unknown_plugin_raises(self) -> None:
        with self.assertRaises(KeyError):
            compute("missing_plugin", "missing_metric")

    def test_regression_config_switches_without_code_change(self) -> None:
        task = load_task_settings(CONFIG_DIR / "verify_regression.yaml")
        validator = FourLayerValidator(task)
        results = validator.evaluate_metrics({
            "y_true": [1.0, 2.0, 3.0, 4.0],
            "y_pred": [1.0, 2.0, 3.0, 4.0],
        })
        self.assertEqual(len(results), 3)
        self.assertTrue(all(item.passed for item in results))

    def test_thresholds_come_from_yaml(self) -> None:
        task = load_task_settings(CONFIG_DIR / "verify_credit.yaml")
        by_name = {spec.name: spec for spec in task.metrics}
        self.assertEqual(by_name["auc"].threshold, 0.78)
        self.assertEqual(by_name["ks"].threshold, 0.35)
        self.assertIsNone(by_name["cost_weighted_loss"].threshold)


class SplitTests(unittest.TestCase):
    def test_temporal_order_and_disjoint(self) -> None:
        result = TemporalSplitter(SplitSpec()).split(100)
        self.assertEqual(result.train, list(range(60)))
        self.assertEqual(result.valid, list(range(60, 80)))
        self.assertEqual(result.test, list(range(80, 100)))
        self.assertEqual(result.strategy, "temporal_holdout")

    def test_bad_ratio_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TemporalSplitter(SplitSpec(train_ratio=0.5))

    def test_gate_allows_only_one_access(self) -> None:
        gate = TestGate(True)
        self.assertEqual(gate.consume([1, 2]), [1, 2])
        self.assertTrue(gate.consumed)
        with self.assertRaises(PermissionError):
            gate.consume([1, 2])


class FourLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.task = load_task_settings(CONFIG_DIR / "verify_credit.yaml")
        cls.validator = FourLayerValidator(cls.task)

    def test_all_layers_pass(self) -> None:
        metrics = [MetricResult(name="auc", value=0.9, direction="maximize",
                                threshold=0.78, passed=True, plugin="sklearn_metrics")]
        report = self.validator.validate(run_id="r1", plan_id="p1",
                                         static=_static(), sandbox=_sandbox(),
                                         metrics=metrics)
        self.assertIsInstance(report, ValidationReport)
        self.assertTrue(report.passed)
        self.assertEqual(report.failed_checks(), [])

    def test_interface_failure_blocks_pass(self) -> None:
        report = self.validator.validate(run_id="r2", plan_id="p1",
                                         static=_static(False), sandbox=_sandbox(),
                                         metrics=[])
        self.assertFalse(report.passed)
        self.assertEqual(report.error_signature, "ImportError")

    def test_metric_below_threshold(self) -> None:
        metrics = [MetricResult(name="auc", value=0.6, direction="maximize",
                                threshold=0.78, passed=False, plugin="sklearn_metrics")]
        report = self.validator.validate(run_id="r3", plan_id="p1",
                                         static=_static(), sandbox=_sandbox(),
                                         metrics=metrics)
        self.assertFalse(report.passed)
        self.assertEqual(report.error_signature, "MetricBelowThreshold")

    def test_timeout_blocks_pass(self) -> None:
        sandbox = _sandbox(False)
        sandbox = sandbox.model_copy(update={"timed_out": True,
                                             "error_signature": "Timeout"})
        report = self.validator.validate(run_id="r4", plan_id="p1",
                                         static=_static(), sandbox=sandbox, metrics=[])
        self.assertFalse(report.passed)
        self.assertEqual(report.error_signature, "Timeout")

    def test_metric_spec_passes(self) -> None:
        self.assertTrue(MetricSpec(name="auc", threshold=0.78).passes(0.8))
        self.assertFalse(MetricSpec(name="auc", threshold=0.78).passes(0.7))
        self.assertFalse(MetricSpec(name="auc", threshold=0.78).passes(None))


class ReportTests(unittest.TestCase):
    def test_report_contains_four_layers(self) -> None:
        task = load_task_settings(CONFIG_DIR / "verify_credit.yaml")
        report = ValidationReport(run_id="report-1", plan_id="p1", passed=True,
                                  interface_checks={"syntax": True},
                                  functional_checks={"smoke_passed": True},
                                  threshold_checks={"auc": True},
                                  metric_values={"auc": 0.8})
        with tempfile.TemporaryDirectory() as tmp:
            path = render_report(report, [], task, Path(tmp) / "report.md")
            text = path.read_text(encoding="utf-8")
        for heading in ("接口规范", "功能正确性", "指标表现", "运行稳定性"):
            self.assertIn(heading, text)
        self.assertIn("非最终验收", text)
        self.assertNotIn("timestamp", text)


if __name__ == "__main__":
    unittest.main()
