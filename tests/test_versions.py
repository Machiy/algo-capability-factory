"""能力版本谱系查询：list / show / diff 与交付图谱一致性。"""

from __future__ import annotations

import unittest
from pathlib import Path

from factory.contracts.knowledge import KGNode, KnowledgeGraph, NodeType
from factory.knowledge.graph import load_graph
from factory.knowledge.versions import (
    base_capability_id,
    is_version_node,
    list_versions,
    show_version,
    version_diff,
    version_number,
)

ROOT = Path(__file__).resolve().parents[1]


def _capability(node_id: str, **attributes) -> KGNode:
    return KGNode(node_id=node_id, node_type=NodeType.CAPABILITY,
                  name=node_id, attributes=attributes)


class VersionGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = KnowledgeGraph(nodes=[
            _capability("cap.x", version="v1", status="active"),
            _capability("cap.x.v2", version="v2",
                        fixed_signatures=["KeyError: PAY_1"],
                        lesson_ids=["lesson.workflow.metricbelowthreshold"]),
            _capability("cap.y", version="v1"),
        ])

    def test_version_helpers(self) -> None:
        self.assertEqual(base_capability_id("cap.x.v2"), "cap.x")
        self.assertEqual(version_number("cap.x"), 1)
        self.assertEqual(version_number("cap.x.v2"), 2)
        self.assertTrue(is_version_node(self.graph.node_index()["cap.x.v2"]))
        self.assertFalse(is_version_node(self.graph.node_index()["cap.x"]))

    def test_list_only_capabilities_with_evolution(self) -> None:
        chains = list_versions(self.graph)
        self.assertEqual(list(chains), ["cap.x"])
        self.assertEqual([node.node_id for node in chains["cap.x"]],
                         ["cap.x", "cap.x.v2"])

    def test_show_single_version(self) -> None:
        self.assertEqual(len(show_version(self.graph, "cap.x")), 2)
        selected = show_version(self.graph, "cap.x", "v2")
        self.assertEqual([node.node_id for node in selected], ["cap.x.v2"])

    def test_diff_reports_only_changed_keys(self) -> None:
        diff = version_diff(self.graph, "cap.x", "v1", "v2")
        self.assertIn("fixed_signatures", diff)
        self.assertIsNone(diff["fixed_signatures"]["from"])
        self.assertEqual(diff["fixed_signatures"]["to"], ["KeyError: PAY_1"])

    def test_diff_rejects_missing_version(self) -> None:
        with self.assertRaises(KeyError):
            version_diff(self.graph, "cap.x", "v1", "v9")


class DeliveredGraphTests(unittest.TestCase):
    def test_after_run_graph_has_real_v2(self) -> None:
        graph = load_graph(ROOT / "outputs/kg/credit_kg_after_run.json")
        self.assertIsNotNone(graph)
        chains = list_versions(graph)
        self.assertTrue(chains)
        self.assertIn("cap.data_dictionary.T1", chains)
        ids = [node.node_id for node in chains["cap.data_dictionary.T1"]]
        self.assertIn("cap.data_dictionary.T1.v2", ids)


if __name__ == "__main__":
    unittest.main()
