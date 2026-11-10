"""知识沉淀测试：图谱里沉淀的必须是「系统层面的教训」，而不是运行日志。

导师反馈的核心是「你的知识沉淀看起来就是个日志」。因此这里锁定三条口径：

1. ``ValidationRun`` 是日志：不参与检索、可被同一 run 重跑覆盖；
2. ``Lesson`` 是知识：必须带根因 / 处置 / 预防 / 适用面，且随证据累积置信度；
3. 教训必须真的进入 Planner 与 Coder 的 prompt，不能只躺在文件里。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factory.agents.roles import Curator
from factory.config import load_settings, load_task_settings
from factory.contracts.knowledge import (
    KGNode,
    LessonScope,
    NodeType,
)
from factory.contracts.models import ValidationReport
from factory.contracts.workflow import RepairRecord, RunTrace
from factory.knowledge import HybridRetriever, MockExtractor, read_sources
from factory.knowledge.lessons import (
    confidence_for,
    lesson_from_failure,
    lesson_records,
    promote_failures,
)
from factory.llm import MockLLM
from factory.workflow.pipeline import render_kg_diff

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"
REQUIRED_KEYS = ("scope", "symptom", "root_cause", "action", "prevention", "applies_to")


def build_graph():
    settings = load_settings(CONFIG)
    task = load_task_settings(ROOT / "configs/verify_credit.yaml")
    sources = read_sources(ROOT, settings.paths.docs, settings.paths.legacy,
                           settings.knowledge.shared_docs)
    return settings, task, sources, MockExtractor(task.dataset_profile).extract(sources)


class SeededLessonTests(unittest.TestCase):
    """工程教训库抽取：系统级知识要能回溯到原文，且字段完整。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.settings, cls.task, cls.sources, cls.graph = build_graph()

    def test_engineering_lessons_become_nodes(self) -> None:
        lessons = self.graph.by_type(NodeType.LESSON)
        self.assertGreaterEqual(len(lessons), 10)
        scopes = {node.attributes.get("scope") for node in lessons}
        # 至少覆盖运行环境 / 平台 / 验证 / LLM 四个系统层
        self.assertGreaterEqual(len(scopes), 4)
        self.assertIn(LessonScope.RUNTIME.value, scopes)
        self.assertIn(LessonScope.PLATFORM.value, scopes)

    def test_every_lesson_answers_why_and_how(self) -> None:
        """缺根因或缺处置的条目只是记录，不能算知识。"""
        for node in self.graph.by_type(NodeType.LESSON):
            with self.subTest(node=node.node_id):
                for key in REQUIRED_KEYS:
                    self.assertTrue(str(node.attributes.get(key, "")).strip(),
                                    f"{node.node_id} 缺少 {key}")

    def test_lessons_are_traceable(self) -> None:
        contents = {doc.path: doc.content for doc in self.sources}
        for node in self.graph.by_type(NodeType.LESSON):
            with self.subTest(node=node.node_id):
                self.assertTrue(node.evidence)
                evidence = node.evidence[0]
                self.assertEqual(evidence.doc_type, "工程教训")
                self.assertIn(evidence.excerpt, contents[evidence.path])

    def test_shared_docs_follow_other_scenarios(self) -> None:
        """换到文本场景，工程教训库仍然读入 —— 系统级知识不按场景切分。"""
        settings = load_settings(CONFIG)
        text_task = load_task_settings(ROOT / "configs/verify_text.yaml")
        sources = read_sources(ROOT, text_task.knowledge.docs,
                               text_task.knowledge.legacy,
                               settings.knowledge.shared_docs)
        doc_types = {doc.doc_type for doc in sources}
        self.assertIn("工程教训", doc_types)
        graph = MockExtractor().extract(sources)
        self.assertTrue(graph.by_type(NodeType.LESSON))


class RetrievalLessonTests(unittest.TestCase):
    """检索注入：教训进 prompt，运行日志不进。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.settings, cls.task, _, cls.graph = build_graph()

    def test_lessons_are_injected_into_prompt(self) -> None:
        retriever = HybridRetriever(self.graph, self.settings.knowledge.top_k,
                                    self.settings.knowledge.weights,
                                    self.settings.knowledge.lesson_prompt_limit)
        result = retriever.retrieve("预测信用卡客户下月违约概率，时间外划分")
        self.assertTrue(result.lessons)
        prompt = result.as_prompt_context()
        self.assertIn("## 系统级教训", prompt)
        self.assertIn("根因：", prompt)
        # 教训要说明处置，否则生成代码不知道改什么
        self.assertIn("处置：", prompt)

    def test_validation_runs_are_not_retrieval_candidates(self) -> None:
        """运行日志不占 prompt 名额：日志是日志，知识才是知识。"""
        graph = self.graph.model_copy(update={"nodes": [*self.graph.nodes, KGNode(
            node_id="run.demo.01", node_type=NodeType.VALIDATION_RUN,
            name="验证运行 run.demo.01",
            attributes={"metrics": {"auc": 0.99}, "passed": True,
                        "run_id": "demo"},
        )]})
        retriever = HybridRetriever(graph, 50, self.settings.knowledge.weights, 0)
        result = retriever.retrieve("验证运行 run.demo.01 auc")
        self.assertNotIn("run.demo.01", [hit.node_id for hit in result.hits])

    def test_lesson_limit_zero_disables_injection(self) -> None:
        retriever = HybridRetriever(self.graph, 5, None, 0)
        self.assertEqual(retriever.retrieve("违约预测").lessons, [])


class PromotionTests(unittest.TestCase):
    """失败案例 → 教训：必须按独立 run 数累积，重跑不能把偶发失败变成知识。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.settings, cls.task, _, cls.graph = build_graph()

    def _trace(self, run_id: str) -> RunTrace:
        return RunTrace(
            run_id=run_id, spec="测试",
            repairs=[RepairRecord(round=1, error_signature="KeyError: PAY_1",
                                  fix_strategy="列名映射为 PAY_0", outcome="repaired")],
        )

    def _report(self) -> list[ValidationReport]:
        return [ValidationReport(run_id="unit", plan_id="plan.test",
                                 passed=False, metric_values={"auc": 0.72})]

    def test_single_run_does_not_become_knowledge(self) -> None:
        curator = Curator(self.graph, MockLLM(), self.settings.knowledge
                          .lesson_promote_threshold)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kg.json"
            diff = curator.sink(self._trace("run.only_once"), self._report(), path)
            graph = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(diff["lessons_promoted"], 0)
        measured = [node for node in graph["nodes"]
                    if node["node_type"] == "Lesson"
                    and node["attributes"].get("source") == "measured"]
        self.assertEqual(measured, [])

    def test_repeated_signature_becomes_lesson(self) -> None:
        """两个独立 run 命中同一签名后才提升，并带上根因与处置。"""
        from factory.knowledge.graph import load_graph

        curator = Curator(self.graph, MockLLM(), 2)
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.json"
            curator.sink(self._trace("run.a"), self._report(), first)
            second = Path(tmp) / "b.json"
            Curator(load_graph(first), MockLLM(), 2).sink(
                self._trace("run.b"), self._report(), second
            )
            graph = load_graph(second)
        lessons = graph.by_type(NodeType.LESSON)
        promoted = [node for node in lessons if node.attributes.get("source") == "measured"]
        self.assertEqual(len(promoted), 1)
        lesson = promoted[0]
        self.assertEqual(lesson.attributes["occurrences"], 2)
        self.assertIn("KeyError", lesson.attributes["symptom"])
        self.assertTrue(lesson.attributes["root_cause"])
        self.assertTrue(lesson.attributes["action"])
        self.assertGreater(lesson.attributes["confidence"], 0.5)
        # 失败案例与教训之间有溯源边
        self.assertIn(lesson.node_id,
                      [edge.source for edge in graph.edges
                       if edge.edge_type.value == "DERIVED_FROM"])

    def test_same_run_rerun_is_idempotent(self) -> None:
        """同一 run 重跑不增加证据次数，也不会重复提升。"""
        from factory.knowledge.graph import load_graph

        curator = Curator(self.graph, MockLLM(), 2)
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.json"
            curator.sink(self._trace("run.same"), self._report(), first)
            again = Path(tmp) / "b.json"
            Curator(load_graph(first), MockLLM(), 2).sink(
                self._trace("run.same"), self._report(), again
            )
            graph = load_graph(again)
        failures = graph.by_type(NodeType.FAILURE_CASE)
        measured = [node for node in failures
                    if node.attributes.get("run_ids") == ["run.same"]]
        self.assertEqual(len(measured), 1)
        self.assertEqual(measured[0].attributes["occurrences"], 1)
        self.assertFalse([node for node in graph.by_type(NodeType.LESSON)
                          if node.attributes.get("source") == "measured"])

    def test_lesson_from_failure_threshold_and_confidence(self) -> None:
        node = KGNode(node_id="failure.x", node_type=NodeType.FAILURE_CASE,
                      name="失败案例 Timeout",
                      attributes={"error_signature": "Timeout", "occurrences": 2})
        record = lesson_from_failure(node, threshold=2)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.scope, LessonScope.RUNTIME)
        self.assertIn("超时", record.root_cause)
        self.assertEqual(record.confidence, confidence_for(2))
        self.assertIsNone(lesson_from_failure(node.model_copy(
            update={"attributes": {**node.attributes, "occurrences": 1}}), 2))

    def test_promotion_is_deduplicated(self) -> None:
        """同签名只沉淀一条教训，重复调用不产生同义节点。"""
        graph = self.graph.model_copy(update={"nodes": [
            *self.graph.nodes,
            KGNode(node_id="failure.x", node_type=NodeType.FAILURE_CASE,
                   name="失败案例", attributes={"error_signature": "SchemaError",
                                            "occurrences": 3, "run_ids": ["a", "b", "c"]}),
        ]})
        first, nodes, _ = promote_failures(graph, 2)
        self.assertEqual(len(first), 1)
        merged = graph.model_copy(update={"nodes": [*graph.nodes, *nodes]})
        second, more_nodes, _ = promote_failures(merged, 2)
        self.assertEqual(second, [])
        self.assertEqual(more_nodes, [])
        self.assertEqual(len(lesson_records(merged)), len(self.graph.by_type(NodeType.LESSON)) + 1)


class ReportTests(unittest.TestCase):
    """报告口径：知识与运行记录分开写，避免把日志当成果展示。"""

    def test_diff_labels_separate_knowledge_from_log(self) -> None:
        lines = "\n".join(render_kg_diff({
            "nodes_added": 4, "edges_added": 3, "runs_recorded": 1,
            "failures_merged": 1, "lessons_promoted": 1, "lessons_total": 13,
        }))
        self.assertIn("运行记录 ValidationRun", lines)
        self.assertIn("教训", lines)
        self.assertIn("13", lines)

    def test_empty_diff_explains_ablation(self) -> None:
        self.assertIn("消融对照组", "\n".join(render_kg_diff({})))


if __name__ == "__main__":
    unittest.main()
