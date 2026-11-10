"""P6-2 测试：真实开源仓库的 AST 抽取结果必须可校验、可回溯。

被抽取仓库为 ``assets/repo/scorecardpy``（MIT，随仓库固定入库），
因此本测试**不联网**；只读源码，不 import、不执行第三方代码。
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from factory.contracts.knowledge import EdgeType, NodeType
from factory.knowledge.repo_extractor import RepoExtractor

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "assets/repo/scorecardpy"


class RepoScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = RepoExtractor()
        cls.scan = cls.extractor.scan(REPO, "scorecardpy")
        cls.graph = cls.extractor.to_graph(cls.scan)

    def test_scan_reads_all_modules(self) -> None:
        self.assertGreaterEqual(len(self.scan.module_imports), 10)
        self.assertGreaterEqual(len(self.scan.functions), 60)
        self.assertEqual(self.scan.skipped, [])

    def test_repository_label_is_never_absolute(self) -> None:
        """产物里的仓库标识必须相对：不泄漏本机目录、换机器仍可复现。"""
        self.assertFalse(Path(self.scan.root).is_absolute())
        self.assertNotIn(":", self.scan.root)
        env = self.graph.by_type(NodeType.ENVIRONMENT)[0]
        repository = str(env.attributes["repository"])
        self.assertFalse(Path(repository).is_absolute())
        self.assertNotIn(":", repository)

    def test_dependencies_exclude_stdlib_and_itself(self) -> None:
        dependencies = self.scan.dependencies
        self.assertIn("pandas", dependencies)
        self.assertIn("numpy", dependencies)
        self.assertNotIn("os", dependencies)
        self.assertNotIn("woebin", dependencies)

    def test_function_carries_signature_and_location(self) -> None:
        woebin = next(item for item in self.scan.functions
                      if item.name == "woebin" and item.public)
        self.assertTrue(woebin.signature.startswith("def woebin("))
        self.assertIn("WOE", woebin.summary.upper())
        self.assertTrue(woebin.path.endswith("woebin.py"))
        self.assertGreater(woebin.lineno, 0)

    def test_docstring_parameters_are_extracted(self) -> None:
        described = [item for item in self.scan.public_functions if item.parameters]
        self.assertGreaterEqual(len(described), 10)
        iv = next(item for item in described if item.name == "iv")
        self.assertTrue(any(param.startswith("dt:") for param in iv.parameters))


class RepoGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = RepoExtractor()
        cls.scan = cls.extractor.scan(REPO, "scorecardpy")
        cls.graph = cls.extractor.to_graph(cls.scan)

    def test_graph_references_are_valid(self) -> None:
        self.graph.validate_references()
        self.assertGreaterEqual(len(self.graph.by_type(NodeType.CAPABILITY)), 50)
        self.assertTrue(self.graph.by_type(NodeType.ENVIRONMENT))

    def test_every_capability_is_traceable(self) -> None:
        for node in self.graph.by_type(NodeType.CAPABILITY):
            with self.subTest(node=node.node_id):
                self.assertTrue(node.evidence)
                evidence = node.evidence[0]
                digest = hashlib.sha256(evidence.excerpt.encode("utf-8")).hexdigest()
                self.assertEqual(digest, evidence.sha256)
                self.assertTrue(evidence.path.endswith(".py"))
                self.assertGreater(node.attributes["lineno"], 0)

    def test_capability_has_executable_description(self) -> None:
        node = next(item for item in self.graph.by_type(NodeType.CAPABILITY)
                    if item.attributes.get("qualname") == "woebin")
        self.assertIn("def woebin(", node.attributes["signature"])
        self.assertTrue(node.attributes["docstring"])
        self.assertTrue(node.name)

    def test_dependency_and_evidence_edges(self) -> None:
        capabilities = len(self.graph.by_type(NodeType.CAPABILITY))
        depends_on = self.graph.edges_of(EdgeType.DEPENDS_ON)
        evidenced_by = self.graph.edges_of(EdgeType.EVIDENCED_BY)
        self.assertEqual(len(depends_on), capabilities)
        self.assertGreater(len(evidenced_by), 0)
        self.assertGreater(len(self.graph.edges_of(EdgeType.USES)), 0)

    def test_missing_repo_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.extractor.scan(ROOT / "assets/repo/not-exists", "none")


if __name__ == "__main__":
    unittest.main()
