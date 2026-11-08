"""算法模板插件验收：注册、按族渲染、回退、静态检查与真实沙箱执行。"""

from __future__ import annotations

import unittest
from pathlib import Path

from factory.agents.templates import _REGISTRY, list_templates, register, render
from factory.config import load_settings, load_task_settings
from factory.runtime import StaticChecker
from factory.runtime.dataset_sandbox import DatasetSandbox

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"
TASK_CONFIG = ROOT / "configs/verify_credit.yaml"
COLUMNS = ["LIMIT_BAL", "PAY_0", "PAY_2", "BILL_AMT1", "PAY_AMT1"]


class RegistryTests(unittest.TestCase):
    def test_builtin_families_are_registered(self) -> None:
        families = list_templates()
        for expected in ("logistic_regression", "hist_gradient_boosting", "random_forest"):
            self.assertIn(expected, families)

    def test_render_dispatches_by_family(self) -> None:
        logreg = render("logistic_regression", COLUMNS, {"C": 0.5})
        hgb = render("hist_gradient_boosting", COLUMNS, {"max_iter": 200})
        forest = render("random_forest", COLUMNS, {"n_estimators": 100})
        self.assertIn("LogisticRegression", logreg)
        self.assertIn("HistGradientBoostingClassifier", hgb)
        self.assertIn("RandomForestClassifier", forest)
        for source in (logreg, hgb, forest):
            self.assertIn("def build_pipeline", source)

    def test_unknown_family_falls_back_with_warning(self) -> None:
        with self.assertLogs("factory.agents.templates", level="WARNING"):
            source = render("no_such_family", COLUMNS, {})
        self.assertIn("LogisticRegression", source)

    def test_register_extends_registry(self) -> None:
        @register("unit_test_family")
        def _unit(columns: list[str], hyperparams: dict) -> str:
            return "def build_pipeline(config):\n    return None\n"

        try:
            self.assertIn("unit_test_family", list_templates())
            self.assertIn("build_pipeline", render("unit_test_family", COLUMNS, {}))
        finally:
            _REGISTRY.pop("unit_test_family", None)


class TemplateExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG)
        cls.task = load_task_settings(TASK_CONFIG)
        cls.checker = StaticChecker(cls.settings.runtime, cls.task.dataset)
        cls.sandbox = DatasetSandbox(
            cls.settings.runtime, cls.task.split, ROOT / cls.settings.paths.data,
            cls.task.dataset.target, cls.task.dataset.forbidden_features, 30000,
        )

    def test_all_templates_pass_static_check(self) -> None:
        for family in ("logistic_regression", "hist_gradient_boosting", "random_forest"):
            with self.subTest(family=family):
                result = self.checker.check(render(family, COLUMNS, {}))
                self.assertTrue(result.passed, result.violations)

    def test_gradient_boosting_and_forest_run_on_real_data(self) -> None:
        """新族不只是文本模板，必须能在子进程里真实 fit / predict。"""
        for family, hyperparams in (
            ("hist_gradient_boosting", {"max_iter": 200, "learning_rate": 0.1}),
            ("random_forest", {"n_estimators": 100, "max_depth": 8}),
        ):
            with self.subTest(family=family):
                source = render(family, COLUMNS, hyperparams)
                check = self.checker.check(source)
                self.assertTrue(check.passed, check.violations)
                result = self.sandbox.run(source)
                self.assertTrue(result.sandbox.passed, result.sandbox.stderr)
                self.assertTrue(result.context["y_score"])


if __name__ == "__main__":
    unittest.main()
