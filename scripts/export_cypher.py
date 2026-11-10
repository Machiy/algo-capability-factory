"""把已落盘的知识图谱导出为 Cypher 脚本（Neo4j 导入文件）。

用法：
    python scripts/export_cypher.py                 # 导出 outputs/kg 下全部已存在的图谱
    python scripts/export_cypher.py --name capabilities

不连接数据库、不引入驱动：只读 JSON、写同名 ``.cypher``，需要时再交给
``cypher-shell`` 导入。未用 Neo4j 服务的理由见 README 第 2 节选型表。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings
from factory.knowledge.cypher import graph_to_cypher
from factory.knowledge.graph import load_graph
from factory.logging_setup import configure_logging

DEFAULT_TARGETS = [
    "credit_kg",
    "credit_kg_after_run",
    "text_kg",
    "text_kg_after_run",
    "regression_kg_after_run",
    "repo_kg",
]


def export_one(kg_dir: Path, name: str) -> Path | None:
    graph = load_graph(kg_dir / f"{name}.json")
    if graph is None:
        print(f"[cypher] 跳过 {name}：未找到 {name}.json")
        return None
    path = kg_dir / f"{name}.cypher"
    path.write_text(graph_to_cypher(graph), encoding="utf-8")
    print(f"[cypher] {name}: {len(graph.nodes)} 节点 / {len(graph.edges)} 边 -> "
          f"{path.relative_to(ROOT).as_posix()}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="知识图谱导出为 Cypher（Neo4j 导入文件）")
    parser.add_argument("--config", default="configs/default.yaml", help="配置文件")
    parser.add_argument("--name", default="", help="只导出指定图谱（默认导出全部已有图谱）")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    args = parser.parse_args()

    configure_logging(args.log_level)
    settings = load_settings(ROOT / args.config)
    kg_dir = ROOT / settings.paths.kg
    targets = [args.name] if args.name else DEFAULT_TARGETS
    exported = [export_one(kg_dir, name) for name in targets]
    if not any(exported):
        print("[cypher] 没有可导出的图谱，先运行 python scripts/build_kg.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
