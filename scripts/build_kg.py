"""P1 入口：从 6 份业务材料构建能力知识图谱，并示范一次检索。

运行（项目根目录）：
    .venv\\Scripts\\python.exe scripts/build_kg.py
    .venv\\Scripts\\python.exe scripts/build_kg.py --query "WOE 分箱 评分卡"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings
from factory.contracts.knowledge import NodeType
from factory.knowledge import HybridRetriever, build_knowledge_graph
from factory.logging_setup import configure_logging

DEFAULT_QUERY = "预测信用卡客户下月违约概率，时间外划分，成本敏感阈值，禁止数据泄漏"


def main() -> int:
    parser = argparse.ArgumentParser(description="构建能力知识图谱（P1）")
    parser.add_argument("--config", default="configs/default.yaml", help="配置文件路径")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="示范检索的自然语言描述")
    parser.add_argument("--top-k", type=int, default=None, help="覆盖配置中的检索 Top-K")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    args = parser.parse_args()

    configure_logging(args.log_level)
    settings = load_settings(ROOT / args.config)
    graph = build_knowledge_graph(settings, ROOT)
    print(f"[P1] 节点 {len(graph.nodes)} / 边 {len(graph.edges)} / "
          f"能力节点 {len(graph.by_type(NodeType.CAPABILITY))}")

    retriever = HybridRetriever(graph, settings.knowledge.top_k,
                                settings.knowledge.weights)
    result = retriever.retrieve(args.query, args.top_k)
    print(result.as_prompt_context())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
