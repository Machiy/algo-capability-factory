"""能力版本谱系查询（只读，不改图谱）。

    python scripts/capability_versions.py --list
    python scripts/capability_versions.py --show cap.data_dictionary.T1
    python scripts/capability_versions.py --diff cap.data_dictionary.T1 v1 v2
    python scripts/capability_versions.py --list --json

只回答「有哪些版本 / 某版因什么升版 / 两版差在哪」；回滚（切换检索证据源）
会改变已验证的选型行为，当前不提供。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings
from factory.knowledge.graph import load_graph
from factory.knowledge.versions import (
    list_versions,
    show_version,
    version_diff,
    version_number,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="算法能力版本谱系查询")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--graph", default="", help="图谱 JSON；默认回写后的知识图谱")
    parser.add_argument("--list", action="store_true", help="列出所有有版本演进的能力")
    parser.add_argument("--show", default="", help="查看某能力的版本链")
    parser.add_argument("--diff", nargs=3, metavar=("CAPABILITY", "FROM", "TO"),
                        help="对比两个版本，如 cap.data_dictionary.T1 v1 v2")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    settings = load_settings(ROOT / args.config)
    path = (ROOT / args.graph if args.graph else
            ROOT / settings.paths.kg / "credit_kg_after_run.json")
    graph = load_graph(path)
    if graph is None:
        print(f"图谱不存在：{path}")
        return 1

    if args.diff:
        capability, from_version, to_version = args.diff
        result = version_diff(graph, capability, from_version, to_version)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
              "\n".join(f"{key}: {value['from']} -> {value['to']}"
                        for key, value in result.items()) or "两版属性一致")
        return 0

    chains = list_versions(graph)
    if args.show:
        nodes = show_version(graph, args.show)
        if not nodes:
            print(f"未找到版本链：{args.show}")
            return 1
        payload = [{"node_id": node.node_id, "version": node.attributes.get("version"),
                    "fixed_signatures": node.attributes.get("fixed_signatures"),
                    "lesson_ids": node.attributes.get("lesson_ids")}
                   for node in nodes]
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else
              "\n".join(f"{item['node_id']} | fixed={item['fixed_signatures']} "
                        f"| lessons={item['lesson_ids']}" for item in payload))
        return 0

    payload = {base: [{"node_id": node.node_id,
                       "version": f"v{version_number(node.node_id)}",
                       "fixed_signatures": node.attributes.get("fixed_signatures")}
                      for node in nodes]
               for base, nodes in chains.items()}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"有版本演进的能力：{len(chains)} 个（图谱 {path.relative_to(ROOT)}）")
        for base, nodes in chains.items():
            print(f"  {base}: " + " -> ".join(node.node_id for node in nodes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
