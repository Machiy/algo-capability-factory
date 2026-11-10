"""构建文本场景（短信垃圾过滤）的知识子图并导出交付物。

运行（项目根目录）：
    python scripts/build_text_kg.py

与主场景 `build_kg.py` 共用同一套抽取与导出代码，只是材料目录与产物前缀不同；
这正是「换场景只换材料与配置」的证据。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings, load_task_settings
from factory.contracts.knowledge import NodeType
from factory.knowledge import build_knowledge_graph
from factory.logging_setup import configure_logging

TASK_CONFIG = "configs/verify_text.yaml"


def main() -> int:
    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml")
    task = load_task_settings(ROOT / TASK_CONFIG)
    if not task.knowledge.docs:
        print("verify_text.yaml 未声明 knowledge.docs，无法构建独立子图")
        return 1
    graph = build_knowledge_graph(
        settings, ROOT,
        docs_dir=task.knowledge.docs,
        legacy_dir=task.knowledge.legacy,
        scene="text",
        dataset_profile=task.dataset_profile,
    )
    counts = {kind.value: len(graph.by_type(kind)) for kind in NodeType}
    print(f"[text-kg] 节点 {len(graph.nodes)} / 边 {len(graph.edges)}")
    print("[text-kg] 节点类型：" + "，".join(f"{k}={v}" for k, v in counts.items() if v))
    print("[text-kg] 产物：outputs/kg/text_kg.{json,csv,graphml,db,html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
