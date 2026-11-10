"""阈值策略、指标口径与 LLM 补丁准入的回归测试。

覆盖三件事：
1. ``cost_optimal`` 真的按成本比选阈值，并在不可用时退回 0.5 而不是编造数值；
2. 候选阈值会改写到 ``y_pred``，因此 F1 / 成本损失随阈值变化（否则搜索的
   阈值维度只是摆设）；
3. Repairer 的 LLM 补丁必须通过复验才采用，未通过时回退确定性补丁。
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from factory.agents import Repairer
from factory.contracts.llm import LLMRequest, LLMResponse
from factory.llm.base import BaseLLM
from factory.validation.thresholds import optimal_threshold
from factory.workflow.pipeline import Workflow


class OptimalThresholdTests(unittest.TestCase):
    def test_picks_low_threshold_when_misses_are_expensive(self) -> None:
        """漏报成本 5 倍时，最优阈值应低于漏报/误报等成本的情形。"""
        labels = [0] * 80 + [1] * 20
        # 正例分数集中在 0.3~0.6，负例集中在 0.0~0.4：正例与负例有重叠
        scores = [0.05 * (index % 8) for index in range(80)]
        scores += [0.35 + 0.05 * (index % 6) for index in range(20)]
        cheap = optimal_threshold(labels, scores, cost_ratio=1.0)
        costly = optimal_threshold(labels, scores, cost_ratio=5.0)
        self.assertLessEqual(costly, cheap)

    def test_threshold_reproduces_expected_cost(self) -> None:
        """返回的阈值用 ``>=`` 复算时应等于扫描出的最小代价。"""
        labels = [0, 0, 0, 1, 1, 1]
        scores = [0.1, 0.2, 0.6, 0.4, 0.7, 0.9]
        threshold = optimal_threshold(labels, scores, cost_ratio=5.0)
        predicted = [int(value >= threshold) for value in scores]
        false_negative = sum(1 for y, p in zip(labels, predicted) if y == 1 and p == 0)
        false_positive = sum(1 for y, p in zip(labels, predicted) if y == 0 and p == 1)
        cost = 5.0 * false_negative + false_positive
        best = min(
            5.0 * sum(1 for y, s in zip(labels, scores) if y == 1 and s < candidate)
            + sum(1 for y, s in zip(labels, scores) if y == 0 and s >= candidate)
            for candidate in [*scores, 1.01]
        )
        self.assertAlmostEqual(cost, best)

    def test_falls_back_on_single_class(self) -> None:
        self.assertEqual(optimal_threshold([0, 0, 0], [0.1, 0.2, 0.3]), 0.5)
        self.assertEqual(optimal_threshold([1, 1], [0.6, 0.8]), 0.5)

    def test_falls_back_on_length_mismatch(self) -> None:
        self.assertEqual(optimal_threshold([0, 1, 0], [0.2, 0.8]), 0.5)
        self.assertEqual(optimal_threshold([], []), 0.5)


def _workflow(cost_ratio: float = 5.0) -> Workflow:
    """构造只含指标口径所需属性的 Workflow，避免加载真实数据集。"""
    workflow = Workflow.__new__(Workflow)
    workflow.task = SimpleNamespace(cost_ratio_fn_fp=cost_ratio)
    workflow.groups = [0, 1]
    workflow.sandbox_mode = "tabular"
    workflow._groups_for = lambda segment: [0, 1]  # type: ignore[method-assign]
    workflow.metric_name = "auc"
    workflow.metric_direction = "maximize"
    return workflow


class MetricsContextTests(unittest.TestCase):
    def test_threshold_rewrites_predictions(self) -> None:
        """阈值必须改写到 y_pred，否则 F1 等阈值相关指标与候选配置脱节。"""
        workflow = _workflow()
        context = {"y_true": [0, 1, 1, 0], "y_score": [0.2, 0.4, 0.8, 0.9]}
        resolved = workflow._prepare_metrics_context(context, 0.5)
        self.assertEqual(resolved, 0.5)
        self.assertEqual(context["y_pred"], [0, 0, 1, 1])
        workflow._prepare_metrics_context(context, 0.3)
        self.assertEqual(context["threshold"], 0.3)
        self.assertEqual(context["y_pred"], [0, 1, 1, 1])

    def test_cost_optimal_resolves_to_numeric_threshold(self) -> None:
        workflow = _workflow(cost_ratio=5.0)
        context = {"y_true": [0, 0, 1, 1], "y_score": [0.1, 0.2, 0.6, 0.9]}
        resolved = workflow._prepare_metrics_context(context, "cost_optimal")
        self.assertIsInstance(resolved, float)
        self.assertIn(resolved, [0.1, 0.2, 0.6, 0.9])
        self.assertEqual(context["threshold"], resolved)

    def test_unknown_strategy_falls_back_to_default(self) -> None:
        workflow = _workflow()
        context = {"y_true": [0, 1], "y_score": [0.3, 0.7]}
        self.assertEqual(workflow._prepare_metrics_context(context, "magic"), 0.5)

    def test_smoke_score_breaks_ties_by_cost(self) -> None:
        """主指标相同时，成本加权损失更低的变体应排前面。"""
        workflow = _workflow()
        better = workflow._smoke_score({"auc": 0.79, "cost_weighted_loss": 0.30})
        worse = workflow._smoke_score({"auc": 0.79, "cost_weighted_loss": 0.80})
        self.assertGreater(better, worse)
        missing = workflow._smoke_score({"auc": None})
        self.assertEqual(missing[0], float("-inf"))


class _PatchLLM(BaseLLM):
    """返回固定补丁代码的桩模型，用来验证准入逻辑。"""

    def __init__(self, code: str, source: str = "cassette") -> None:
        self.code = code
        self.source = source
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(raw="{}", parsed={"reasoning": "根因", "code": self.code},
                           model="stub", source=self.source)


FIXED_SOURCE = (
    "from sklearn.linear_model import LogisticRegression\n"
    "from sklearn.pipeline import Pipeline\n\n"
    'FEATURE_COLUMNS = ["LIMIT_BAL"]\n\n'
    "def build_pipeline(config):\n"
    '    return Pipeline([("model", LogisticRegression(max_iter=1000))])\n'
)
PATCHED_SOURCE = FIXED_SOURCE.replace("max_iter=1000", "max_iter=2000")


class LlmPatchTests(unittest.TestCase):
    def test_patch_is_used_after_verification(self) -> None:
        llm = _PatchLLM(PATCHED_SOURCE)
        fixed, record = Repairer(llm).repair(
            FIXED_SOURCE, "MetricBelowThreshold", 1,
            verify=lambda source: (True, "静态检查与沙箱复验通过"),
        )
        self.assertEqual(fixed.strip(), PATCHED_SOURCE.strip())
        self.assertEqual(record.patch_source, "llm")
        self.assertEqual(record.outcome, "repaired")
        self.assertIn("通过复验", record.llm_patch_note)

    def test_patch_is_rejected_and_falls_back(self) -> None:
        """LLM 补丁没过复验时必须回退，不留半成品源码。"""
        llm = _PatchLLM(PATCHED_SOURCE)
        source = FIXED_SOURCE.replace('"LIMIT_BAL"', '"PAY_1", "LIMIT_BAL"')
        fixed, record = Repairer(llm, column_aliases={"PAY_1": "PAY_0"}).repair(
            source, "KeyError: PAY_1", 1,
            verify=lambda candidate: (False, "静态检查未通过：import_whitelist"),
        )
        self.assertIn('"PAY_0"', fixed)
        self.assertEqual(record.patch_source, "deterministic")
        self.assertIn("回退确定性补丁", record.llm_patch_note)

    def test_mock_output_is_never_treated_as_patch(self) -> None:
        llm = _PatchLLM(PATCHED_SOURCE, source="mock")
        fixed, record = Repairer(llm).repair(
            FIXED_SOURCE, "MetricBelowThreshold", 1,
            verify=lambda candidate: (True, "ok"),
        )
        self.assertEqual(fixed, FIXED_SOURCE)
        self.assertEqual(record.outcome, "no_change")
        self.assertEqual(record.llm_patch_note, "")

    def test_without_verify_keeps_deterministic_patch(self) -> None:
        """旧调用（不传 verify）行为不变：只走确定性补丁。"""
        llm = _PatchLLM(PATCHED_SOURCE)
        fixed, record = Repairer(llm).repair(FIXED_SOURCE, "Timeout", 1)
        self.assertEqual(fixed, FIXED_SOURCE)
        self.assertEqual(record.patch_source, "none")


if __name__ == "__main__":
    unittest.main()
