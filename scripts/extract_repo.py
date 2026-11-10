"""P6-2 入口：从真实开源仓库抽取函数、依赖与能力描述。

运行（项目根目录）：
    .venv\\Scripts\\python.exe scripts/extract_repo.py
    .venv\\Scripts\\python.exe scripts/extract_repo.py --repo assets/repo/scorecardpy

只读源码，不 import、不执行被抽取仓库；产物为可被 ``KnowledgeGraph`` 契约
校验的能力图谱，落在 ``outputs/kg/repo_*``。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.artifacts import kg_paths
from factory.contracts.knowledge import NodeType
from factory.knowledge.cypher import graph_to_cypher
from factory.knowledge.graph import KnowledgeGraphStore
from factory.knowledge.repo_extractor import RepoExtractor
from factory.knowledge.visualize import render_html
from factory.logging_setup import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="真实仓库能力抽取（P6-2）")
    parser.add_argument("--repo", default="assets/repo/scorecardpy")
    parser.add_argument("--name", default="scorecardpy")
    parser.add_argument("--kg-dir", default="outputs/kg")
    args = parser.parse_args()

    configure_logging()
    repo_dir = ROOT / args.repo
    scan = RepoExtractor().scan(repo_dir, args.name)
    graph = RepoExtractor().to_graph(scan)
    kg_dir = ROOT / args.kg_dir
    paths = kg_paths(kg_dir, "repo")
    store = KnowledgeGraphStore(graph)
    json_path = store.export_json(paths["json"])
    csv_path = store.export_csv(paths["csv"])
    graphml_path = store.export_graphml(paths["graphml"])
    paths["cypher"].write_text(graph_to_cypher(graph), encoding="utf-8")
    render_html(graph, paths["html"])

    capabilities = graph.by_type(NodeType.CAPABILITY)
    print(f"[P6-2] 仓库 {args.name}：{len(scan.functions)} 个函数 / "
          f"{len(capabilities)} 个公开能力 / {len(graph.edges)} 条边")
    print(f"        依赖：{', '.join(scan.dependencies) or '无'}")
    print(f"        产物：{json_path.relative_to(ROOT)}、{csv_path.relative_to(ROOT)}、"
          f"{graphml_path.relative_to(ROOT)}")
    for node in capabilities[:5]:
        params = node.attributes.get("parameters") or []
        print(f"  - {node.node_id} | {node.name}")
        print(f"      签名：{node.attributes.get('signature')}")
        print(f"      参数：{len(params)} 项；证据：{node.evidence[0].path}:"
              f"{node.attributes.get('lineno')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
