"""知识图谱 → Cypher 导入脚本。

交付物清单里「知识抽取结果文件」举例包括 Neo4j 导入文件。本项目不启动 Neo4j
服务（理由见 README 选型表），但把图谱导成 Cypher 让需要的人可以直接导入：

```bash
cat outputs/kg/capabilities.cypher | cypher-shell -u neo4j -p <password>
```

只做字符串拼接，不引入任何驱动依赖；节点 ``attributes`` 是嵌套结构，
按 JSON 字符串放进 ``attributes_json``，避免 Cypher 属性类型限制。
"""

from __future__ import annotations

import json

from factory.contracts.knowledge import KnowledgeGraph, NodeType


def _escape(value: str) -> str:
    """Cypher 单引号字符串转义。"""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _node_line(node) -> str:
    attributes = json.dumps(node.attributes, ensure_ascii=False, sort_keys=True, default=str)
    return (
        f"MERGE (n:{node.node_type.value} {{node_id: '{_escape(node.node_id)}'}})\n"
        f"SET n.name = '{_escape(node.name)}', n.version = '{_escape(node.version)}', "
        f"n.task_type = '{_escape(node.task_type)}', n.status = '{_escape(node.status)}', "
        f"n.attributes_json = '{_escape(attributes)}';"
    )


def graph_to_cypher(graph: KnowledgeGraph) -> str:
    """把图谱转成可直接执行的 Cypher 脚本。"""
    lines = [
        "// AlgoCap Factory 知识图谱导出（Cypher，Neo4j 5.x）",
        f"// 节点 {len(graph.nodes)} 个 / 边 {len(graph.edges)} 条",
        "// 用法：cat <this-file>.cypher | cypher-shell -u neo4j -p <password>",
        "",
    ]
    present = {node.node_type for node in graph.nodes}
    for node_type in NodeType:
        if node_type in present:
            lines.append(
                f"CREATE CONSTRAINT {node_type.value.lower()}_node_id IF NOT EXISTS "
                f"FOR (n:{node_type.value}) REQUIRE n.node_id IS UNIQUE;"
            )
    lines.append("")
    lines.extend(_node_line(node) for node in graph.nodes)
    lines.append("")
    for edge in graph.edges:
        relation = edge.edge_type.value
        lines.append(
            f"MATCH (a {{node_id: '{_escape(edge.source)}'}}), "
            f"(b {{node_id: '{_escape(edge.target)}'}})\n"
            f"MERGE (a)-[:{relation}]->(b);"
        )
    lines.append("")
    return "\n".join(lines)


__all__ = ["graph_to_cypher"]
