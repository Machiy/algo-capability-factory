"""知识图谱持久化：NetworkX 属性图、SQLite 与 JSON / CSV / GraphML 导出。

输出路径全部来自 ``configs/default.yaml``，本模块不内置任何绝对路径。
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import networkx as nx

from factory.config import Settings
from factory.contracts.knowledge import KnowledgeGraph

logger = logging.getLogger(__name__)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _graphml_value(value: Any) -> str | int | float | bool:
    """GraphML 只接受标量；嵌套结构序列化为 JSON 字符串。"""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return _json_text(value)


def _resolve(root: Path, configured: str) -> Path:
    path = Path(configured)
    return path if path.is_absolute() else root / path


class KnowledgeGraphStore:
    """把 ``KnowledgeGraph`` 契约落盘为多种交付物。"""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self.nx_graph: nx.MultiDiGraph = nx.MultiDiGraph()
        for node in graph.nodes:
            attributes: dict[str, Any] = {
                "node_id": node.node_id,
                "node_type": node.node_type.value,
                "name": node.name,
                "version": node.version,
                "task_type": node.task_type,
                "status": node.status,
                "evidence_count": len(node.evidence),
            }
            for key, value in node.attributes.items():
                attributes[f"attr_{key}"] = _graphml_value(value)
            self.nx_graph.add_node(node.node_id, **attributes)
        for edge in graph.edges:
            attributes = {"edge_type": edge.edge_type.value}
            for key, value in edge.attributes.items():
                attributes[f"attr_{key}"] = _graphml_value(value)
            self.nx_graph.add_edge(edge.source, edge.target, **attributes)

    def export_json(self, path: Path) -> Path:
        """导出不含运行时间的确定性 JSON，便于产物比对与入库。

        ``built_at`` 属于运行时元数据，写入交付物会让每次构建都产生 diff；
        改用节点与边的内容哈希标识版本。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.graph.model_dump(mode="json", exclude={"built_at"})
        canonical = json.dumps(
            {"nodes": payload["nodes"], "edges": payload["edges"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def export_csv(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["node_id", "node_type", "name", "version", "task_type",
                             "status", "evidence_count", "source_path", "attributes"])
            for node in self.graph.nodes:
                source_path = node.evidence[0].path if node.evidence else ""
                writer.writerow([
                    node.node_id, node.node_type.value, node.name, node.version,
                    node.task_type, node.status, len(node.evidence), source_path,
                    _json_text(node.attributes),
                ])
        return path

    def export_graphml(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        nx.write_graphml(self.nx_graph, str(path))
        return path

    def persist_sqlite(self, path: Path) -> Path:
        """节点与边存入 SQLite，供后续版本谱系与验证记录查询。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("DROP TABLE IF EXISTS nodes")
            connection.execute("DROP TABLE IF EXISTS edges")
            connection.execute(
                "CREATE TABLE nodes (node_id TEXT PRIMARY KEY, node_type TEXT, "
                "name TEXT, version TEXT, task_type TEXT, status TEXT, "
                "attributes TEXT, evidence TEXT)"
            )
            connection.execute(
                "CREATE TABLE edges (source TEXT, target TEXT, edge_type TEXT, "
                "attributes TEXT, PRIMARY KEY (source, target, edge_type))"
            )
            connection.executemany(
                "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (node.node_id, node.node_type.value, node.name, node.version,
                     node.task_type, node.status, _json_text(node.attributes),
                     _json_text([item.model_dump(mode="json") for item in node.evidence]))
                    for node in self.graph.nodes
                ],
            )
            connection.executemany(
                "INSERT INTO edges VALUES (?, ?, ?, ?)",
                [
                    (edge.source, edge.target, edge.edge_type.value,
                     _json_text(edge.attributes))
                    for edge in self.graph.edges
                ],
            )
        return path

    def export_all(self, settings: Settings, root: Path) -> dict[str, Path]:
        """按配置导出全部交付物，返回 ``产物名 -> 路径``。"""
        exported: dict[str, Path] = {
            "graphml": self.export_graphml(_resolve(root, settings.knowledge.graph_path)),
            "sqlite": self.persist_sqlite(_resolve(root, settings.knowledge.sqlite_path)),
        }
        for configured in settings.knowledge.extraction_results:
            path = _resolve(root, configured)
            if path.suffix == ".json":
                exported["json"] = self.export_json(path)
            elif path.suffix == ".csv":
                exported["csv"] = self.export_csv(path)
        logger.info("导出 %d 类知识图谱产物", len(exported))
        return exported


__all__ = ["KnowledgeGraphStore"]
