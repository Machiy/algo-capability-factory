"""P1 知识层测试：M1 检查点、契约严格性、检索确定性与交付物校验。

依赖 pydantic / PyYAML / networkx / pyvis，均为 requirements.txt 中的包；
pytest 与 unittest 均可收集本文件。
"""

from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import networkx as nx
from pydantic import ValidationError

from factory.config import load_settings, load_task_settings
from factory.contracts.knowledge import EdgeType, KGEdge, KGNode, KnowledgeGraph, NodeType
from factory.knowledge import (
    HybridRetriever,
    KnowledgeGraphStore,
    MockExtractor,
    build_knowledge_graph,
    read_sources,
)
from factory.knowledge.extractor import sha256_text

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/default.yaml"
QUERY = "预测信用卡客户下月违约概率，时间外划分，成本敏感阈值，禁止数据泄漏"


class KnowledgeLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG_PATH)
        cls.task = load_task_settings(ROOT / "configs/verify_credit.yaml")
        cls.profile = cls.task.dataset_profile
        cls.sources = read_sources(ROOT, cls.settings.paths.docs, cls.settings.paths.legacy)
        cls.graph = MockExtractor(cls.profile).extract(cls.sources)
        build_knowledge_graph(cls.settings, ROOT, dataset_profile=cls.profile)

    def test_source_materials_complete(self) -> None:
        # 6 份业务材料 + 1 份工程教训库（系统层面知识，跨场景共享）
        self.assertEqual(len(self.sources), 8)
        self.assertEqual(len({doc.doc_type for doc in self.sources}), 8)
        for doc in self.sources:
            with self.subTest(path=doc.path):
                self.assertTrue(doc.content)
                self.assertEqual(doc.sha256, sha256_text(doc.content))

    def test_contract_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            KGNode(node_id="x", node_type=NodeType.CAPABILITY, name="x", typo=1)

    def test_graph_reference_integrity(self) -> None:
        self.assertIsNone(self.graph.validate_references())
        self.assertEqual(len(self.graph.node_index()), len(self.graph.nodes))

    def test_m1_schema_coverage(self) -> None:
        # 9 类节点 + Lesson（教训）：知识层与运行日志层在 schema 上就分开
        self.assertEqual(len(NodeType), 10)
        self.assertEqual(len(EdgeType), 13)

    def test_cypher_export_covers_nodes_and_edges(self) -> None:
        """交付物含 Neo4j 导入文件：Cypher 文本要能覆盖全部节点与关系。"""
        from factory.knowledge.cypher import graph_to_cypher

        script = graph_to_cypher(self.graph)
        self.assertIn("CREATE CONSTRAINT", script)
        self.assertEqual(script.count("MERGE (n:"), len(self.graph.nodes))
        self.assertEqual(script.count("MERGE (a)-[:"), len(self.graph.edges))
        for node_type in {node.node_type.value for node in self.graph.nodes}:
            self.assertIn(f"(n:{node_type} {{node_id:", script)
        for edge in self.graph.edges[:5]:
            self.assertIn(f"MERGE (a)-[:{edge.edge_type.value}]->(b);", script)

    def test_cypher_escapes_quotes(self) -> None:
        """属性里出现单引号时不能破坏 Cypher 语法。"""
        from factory.contracts.knowledge import KGNode, KnowledgeGraph
        from factory.knowledge.cypher import graph_to_cypher

        graph = KnowledgeGraph(nodes=[KGNode(
            node_id="cap.quote.v1", node_type=NodeType.CAPABILITY,
            name="含 ' 单引号的节点", attributes={"note": "it's fine"},
        )])
        script = graph_to_cypher(graph)
        self.assertIn("含 \\' 单引号", script)
        self.assertIn("it\\'s fine", script)
        used = {edge.edge_type for edge in self.graph.edges}
        # 源材料里没有验证运行记录，HAS_RUN / RESULTED_IN / DERIVED_FROM 由
        # Curator 回写时建立（见 test_workflow.CuratorTests），源图谱要求覆盖其余 10 类
        self.assertGreaterEqual(len(used), 10)

    def test_m1_extraction_volume(self) -> None:
        self.assertGreaterEqual(len(self.graph.by_type(NodeType.CAPABILITY)), 15)
        self.assertGreaterEqual(len(self.graph.edges), 40)

    def test_m1_t1_to_t4_are_nodes(self) -> None:
        source_ids = {
            node.attributes.get("source_id")
            for node in self.graph.by_type(NodeType.CAPABILITY)
        }
        for key in ("T1", "T2", "T3", "T4"):
            with self.subTest(key=key):
                self.assertIn(key, source_ids)

    def test_m1_evidence_is_verifiable(self) -> None:
        """每个能力节点都能回溯到原文，且哈希可重算 —— M1 的核心判定。"""
        contents = {doc.path: doc.content for doc in self.sources}
        for node in self.graph.by_type(NodeType.CAPABILITY):
            with self.subTest(node=node.node_id):
                self.assertTrue(node.evidence)
                for item in node.evidence:
                    self.assertEqual(item.sha256, sha256_text(item.excerpt))
                    self.assertIn(item.excerpt, contents[item.path])

    def test_precedes_order_and_fit_constraint(self) -> None:
        self.assertGreaterEqual(len(self.graph.edges_of(EdgeType.PRECEDES)), 6)
        for operator in self.graph.by_type(NodeType.OPERATOR):
            self.assertTrue(operator.attributes["fit_on_train_only"])

    def test_sensitive_and_id_constraints(self) -> None:
        datasets = self.graph.by_type(NodeType.DATASET)
        self.assertEqual(len(datasets), 1)
        self.assertIn("ID", datasets[0].attributes["forbidden_features"])
        self.assertIn("SEX", datasets[0].attributes["sensitive_features"])

    def test_retrieval_is_deterministic_and_actionable(self) -> None:
        retriever = HybridRetriever(self.graph, self.settings.knowledge.top_k,
                                    self.settings.knowledge.weights)
        first = retriever.retrieve(QUERY)
        second = retriever.retrieve(QUERY)
        self.assertEqual([hit.node_id for hit in first.hits],
                         [hit.node_id for hit in second.hits])
        self.assertLessEqual(len(first.hits), first.top_k)
        self.assertTrue(first.constraints)
        self.assertTrue(first.failure_warnings)
        self.assertIn("适用条件", first.as_prompt_context())
        self.assertIn("历史失败规避项", first.as_prompt_context())
        for hit in first.hits:
            self.assertIn("constraint_match", hit.reasons)

    def test_exported_artifacts(self) -> None:
        kg_dir = ROOT / self.settings.paths.kg
        payload = json.loads((kg_dir / "credit_kg.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["nodes"]), len(self.graph.nodes))
        self.assertEqual(len(payload["edges"]), len(self.graph.edges))
        with (kg_dir / "credit_kg.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), len(self.graph.nodes))
        graphml = nx.read_graphml(str(kg_dir / "credit_kg.graphml"))
        self.assertEqual(graphml.number_of_nodes(), len(self.graph.nodes))
        with sqlite3.connect(kg_dir / "credit_kg.db") as connection:
            count = connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        self.assertEqual(count, len(self.graph.nodes))
        self.assertTrue((kg_dir / "credit_kg.html").is_file())

    def test_json_export_is_deterministic(self) -> None:
        """重复构建产物字节一致，避免入库后每次跑测试都产生脏工作区。"""
        first = MockExtractor(self.profile).extract(self.sources)
        second = MockExtractor(self.profile).extract(self.sources)
        with tempfile.TemporaryDirectory() as tmp:
            path_a = KnowledgeGraphStore(first).export_json(Path(tmp) / "a.json")
            path_b = KnowledgeGraphStore(second).export_json(Path(tmp) / "b.json")
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())
            payload = json.loads(path_a.read_text(encoding="utf-8"))
            self.assertNotIn("built_at", payload)
            self.assertEqual(len(payload["content_sha256"]), 64)

    def test_settings_come_from_yaml(self) -> None:
        self.assertEqual(self.settings.knowledge.top_k, 5)
        weights = self.settings.knowledge.weights
        self.assertTrue(weights)
        self.assertIn("constraint_match", weights)
        self.assertAlmostEqual(sum(weights.values()), 1.0)


class GraphExpandTests(unittest.TestCase):
    """A3：受限多跳 BFS 召回二跳节点并记录显式路径。"""

    @staticmethod
    def _graph() -> KnowledgeGraph:
        return KnowledgeGraph(
            nodes=[
                KGNode(node_id="cap.a", node_type=NodeType.CAPABILITY, name="能力A"),
                KGNode(node_id="alg.b", node_type=NodeType.ALGORITHM, name="算法B"),
                KGNode(node_id="metric.c", node_type=NodeType.METRIC, name="指标C"),
            ],
            edges=[
                KGEdge(source="cap.a", target="alg.b", edge_type=EdgeType.USES),
                KGEdge(source="alg.b", target="metric.c",
                       edge_type=EdgeType.EVALUATED_BY),
            ],
        )

    def test_expand_recalls_two_hop_with_paths(self) -> None:
        expansion = HybridRetriever(self._graph(), top_k=5)._expand({"cap.a"})
        self.assertIn("alg.b", expansion)
        self.assertIn("metric.c", expansion)
        # 一跳路径显式可回溯
        self.assertIn("cap.a --USES--> alg.b", expansion["alg.b"][1])
        # 二跳路径含两段边
        self.assertTrue(any("--EVALUATED_BY--> metric.c" in path
                            for path in expansion["metric.c"][1]))

    def test_expand_excludes_seeds(self) -> None:
        expansion = HybridRetriever(self._graph(), top_k=5)._expand({"cap.a"})
        self.assertNotIn("cap.a", expansion)  # 种子节点本身不返回


if __name__ == "__main__":
    unittest.main()
