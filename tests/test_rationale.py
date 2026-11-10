"""设计依据：必须是可回溯的因果说明，而不是四行固定话术。"""

from __future__ import annotations

import unittest

from factory.agents.roles import Curator
from factory.contracts.knowledge import KnowledgeGraph, RetrievalHit, RetrievalResult
from factory.contracts.workflow import CandidateEvaluation, RepairRecord, RunTrace
from factory.llm import MockLLM


def _trace() -> RunTrace:
    return RunTrace(
        run_id="unit", spec="测试",
        candidates=[
            CandidateEvaluation(plan_id="plan.02", model_family="random_forest",
                                passed=True, score=0.7899,
                                metrics={"auc": 0.7899}, repair_rounds=0),
            CandidateEvaluation(plan_id="plan.01", model_family="logistic_regression",
                                passed=False, score=0.7206,
                                metrics={"auc": 0.7206}, repair_rounds=2),
        ],
        repairs=[RepairRecord(round=1, error_signature="KeyError: PAY_1",
                              fix_strategy="按列名映射改为 PAY_0", outcome="repaired")],
    )


def _retrieval() -> RetrievalResult:
    return RetrievalResult(
        query="预测违约概率", top_k=5,
        hits=[RetrievalHit(node_id="cap.risk_policy.C6", name="标识字段", score=0.5),
              RetrievalHit(node_id="cap.expert_rules.E4", name="Pipeline 约束", score=0.43)],
        constraints=["必须时间外划分，禁止随机打乱", "禁 ID 入模"],
        lessons=["[runtime] 内存看门狗要按进程树计量"],
    )


class DesignRationaleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.curator = Curator(KnowledgeGraph(), MockLLM(), 2)

    def _explain(self) -> str:
        return self.curator.explain(_trace(), retrieval=_retrieval(),
                                    metric_name="auc", direction="maximize",
                                    threshold=0.78)

    def test_rationale_states_criteria_and_evidence(self) -> None:
        text = self._explain()
        self.assertIn("## 设计依据", text)
        self.assertIn("`auc`", text)
        self.assertIn("门槛 0.78", text)
        self.assertIn("cap.risk_policy.C6", text)
        self.assertIn("时间外划分", text)
        self.assertIn("系统级教训 1 条", text)

    def test_rationale_explains_why_a_candidate_was_excluded(self) -> None:
        text = self._explain()
        self.assertIn("plan.02", text)
        self.assertIn("0.7899", text)
        self.assertIn("plan.01", text)
        self.assertIn("FAIL", text)
        self.assertIn("未选 plan.01", text)
        self.assertIn("排名第一且四层验证通过", text)

    def test_rationale_links_failures_to_reuse(self) -> None:
        text = self._explain()
        self.assertIn("KeyError: PAY_1", text)
        self.assertIn("列名映射", text)
        self.assertIn("`FailureCase`", text)
        self.assertIn("`Lesson`", text)

    def test_rationale_is_deterministic_and_no_llm(self) -> None:
        self.assertEqual(self._explain(), self._explain())

    def test_rationale_handles_no_failures(self) -> None:
        trace = _trace()
        trace.repairs = []
        text = self.curator.explain(trace, retrieval=_retrieval(),
                                    metric_name="auc", threshold=0.78)
        self.assertIn("本轮未触发失败签名", text)


if __name__ == "__main__":
    unittest.main()
