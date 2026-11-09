"""能力抽取器：``BaseExtractor`` 抽象的 Mock / 规则模板实现。

所有节点内容来自 ``assets/`` 下真实材料的表格行、章节或 AST 片段，
不把业务结论写死在代码里；每个节点携带可重算 SHA-256 的原文证据，
供 M1「抽取结果是否真的来自 6 份业务材料」检查点核对。
真实 LLM 抽取器在 P3 通过同一接口接入，不改变下游契约。
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from itertools import combinations
from pathlib import Path
from typing import Any

from factory.contracts.knowledge import (
    EdgeType,
    Evidence,
    KGEdge,
    KGNode,
    KnowledgeGraph,
    NodeType,
    SourceDocument,
)
from factory.knowledge.parsing import (
    Table,
    TableRow,
    parse_pipeline_order,
    parse_sections,
    parse_tables,
)

logger = logging.getLogger(__name__)

DOC_TYPE_BY_FILENAME: dict[str, str] = {
    "data_dictionary.md": "业务文档",
    "risk_policy.md": "风控策略",
    "expert_rules.md": "专家经验",
    "experiment_log.md": "实验记录",
    "test_report.md": "测试报告",
    "failure_review.md": "失败复盘",
    # 文本场景材料（assets/docs/text/）：结构与主场景一致，复用同一解析路径
    "sms_data_dictionary.md": "业务文档",
    "sms_policy.md": "风控策略",
    "sms_failure_review.md": "失败复盘",
}
LEGACY_DOC_TYPE = "历史代码"

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*\d+[a-z]?$")
_DEFECT_RE = re.compile(r"#\s*缺陷\s*\d+[：:]\s*(.+)")
_SIGNATURE_RE = re.compile(
    r"KeyError|SchemaError|LeakageDetected|MetricSuspiciouslyHigh|"
    r"MetricBelowThreshold|Nondeterminism|Timeout|CostLossAboveBaseline"
)
_PREFIX_BY_TYPE: dict[NodeType, str] = {
    NodeType.CAPABILITY: "cap",
    NodeType.OPERATOR: "op",
    NodeType.ALGORITHM: "algo",
    NodeType.METRIC: "metric",
    NodeType.DATASET: "dataset",
    NodeType.ENVIRONMENT: "env",
    NodeType.VALIDATION_RUN: "run",
    NodeType.FAILURE_CASE: "fail",
    NodeType.EVIDENCE: "evidence",
}


class ExtractionError(RuntimeError):
    """源材料缺失或解析失败。"""


def sha256_text(text: str) -> str:
    """对文本计算 SHA-256，证据校验与测试共用同一口径。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned[:60] or "item"


def _to_float(value: str) -> float | None:
    """从材料单元格提取数值；含冒号的比值文本不当作数值。"""
    if ":" in value or not value.strip():
        return None
    cleaned = re.sub(r"[^\d.\-]", "", value.replace(",", ""))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _row_node_type(doc_type: str, section_title: str) -> NodeType | None:
    """决定某章节的表格行应映射为哪类节点；``None`` 表示不逐行生成。"""
    if doc_type == "业务文档":
        return NodeType.CAPABILITY if "已知数据问题" in section_title else None
    if doc_type == "风控策略":
        if "适用条件" in section_title:
            return NodeType.CAPABILITY
        if "验收门槛" in section_title:
            return NodeType.METRIC
        return None
    if doc_type == "专家经验":
        return NodeType.CAPABILITY
    if doc_type == "实验记录":
        if "记录汇总" in section_title:
            return NodeType.VALIDATION_RUN
        if "可复用经验" in section_title:
            return NodeType.CAPABILITY
        return None
    if doc_type == "测试报告":
        if "四层验证检查项" in section_title:
            return NodeType.METRIC
        if "历史样例结论" in section_title:
            return NodeType.VALIDATION_RUN
        return None
    if doc_type == "失败复盘" and "速查" in section_title:
        return NodeType.FAILURE_CASE
    return None


def _row_attributes(headers: tuple[str, ...], cells: tuple[str, ...], section: str,
                    item_id: str) -> dict[str, Any]:
    """把表格行转成节点属性，数值列额外汇总为 ``metrics``。"""
    attributes: dict[str, Any] = {"source_id": item_id, "section": section}
    metrics: dict[str, float] = {}
    for header, cell in zip(headers, cells):
        key = header or f"col{list(headers).index(header)}"
        attributes[key] = cell
        number = _to_float(cell)
        if number is not None:
            metrics[key] = number
    if metrics:
        attributes["metrics"] = metrics
    return attributes


def _name_from_row(cells: tuple[str, ...], item_id: str) -> str:
    candidate = cells[1] if len(cells) > 1 else cells[0]
    candidate = candidate.replace("**", "").replace("`", "").strip()
    return f"[{item_id}] {candidate[:80]}" if candidate else item_id


def read_sources(root: Path, docs_dir: str, legacy_dir: str) -> list[SourceDocument]:
    """读取业务材料与历史代码，返回带整文件哈希的契约对象。

    ``legacy_dir`` 传空字符串表示该场景没有历史代码（如纯文本任务），
    不会被误判为「材料缺失」。
    """
    sources: list[SourceDocument] = []
    docs = root / docs_dir
    if not docs.is_dir():
        raise ExtractionError(f"业务材料目录不存在：{docs}")

    def _read(path: Path) -> str:
        # 统一换行：Windows 检出为 CRLF、Linux 为 LF，不归一化会让
        # 表格单元格带上 "\r"，跨平台抽出不同的边数（实测 188 vs 179）
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")

    for path in sorted(docs.glob("*.md")):
        content = _read(path)
        sources.append(SourceDocument(
            path=path.relative_to(root).as_posix(),
            doc_type=DOC_TYPE_BY_FILENAME.get(path.name, "业务文档"),
            content=content,
            sha256=sha256_text(content),
        ))
    legacy = root / legacy_dir if legacy_dir else None
    for path in sorted(legacy.glob("*.py")) if legacy else []:
        content = _read(path)
        sources.append(SourceDocument(
            path=path.relative_to(root).as_posix(),
            doc_type=LEGACY_DOC_TYPE,
            content=content,
            sha256=sha256_text(content),
        ))
    if not sources:
        raise ExtractionError("没有任何可抽取的源材料")
    logger.info("读入 %d 份源材料", len(sources))
    return sources


class BaseExtractor(ABC):
    """抽取器抽象；Mock 与后续真实 LLM 实现共用此接口。"""

    @abstractmethod
    def extract(self, sources: list[SourceDocument]) -> KnowledgeGraph:
        """把源材料抽取为知识图谱契约。"""


_ASCII_TERM_RE = re.compile(r"[A-Za-z]")


def _flatten(value: Any) -> list[str]:
    """把属性值摊平成字符串列表，供文本匹配使用。"""
    if isinstance(value, (str, int, float)):
        return [str(value)]
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [str(item) for item in value.values()] + [str(key) for key in value]
    return []


def _node_text(node: KGNode) -> str:
    """节点可被匹配的人读文本：名称 + 全部属性值。"""
    parts = [node.name]
    for value in node.attributes.values():
        parts.extend(_flatten(value))
    return " ".join(parts).lower()


def _contains(text: str, term: str) -> bool:
    """英文词按词边界匹配，避免 ``KS`` 命中 ``risk``；中文直接子串匹配。"""
    if not term:
        return False
    if _ASCII_TERM_RE.search(term):
        return re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text) is not None
    return term in text


def _terms(value: Any, min_length: int = 2) -> set[str]:
    """把「AUC / KS / 成本损失」这类单元格拆成可匹配的关键词。"""
    if not isinstance(value, str):
        return set()
    return {part.strip().lower() for part in value.split("/")
            if len(part.strip()) >= min_length}


DEFAULT_DATASET_PROFILE: dict[str, Any] = {
    "name": "",
    "target": "",
    "forbidden_features": [],
    "sensitive_features": [],
    "split_policy": "temporal_holdout",
}


class _GraphBuilder:
    """收集节点与边，并在输出前校验引用完整性。

    ``dataset_profile`` 由任务配置（``verify_*.yaml``）构造后传入，避免把
    某个数据集的标签名与敏感字段写死在抽取器里。
    """

    def __init__(self, dataset_profile: dict[str, Any] | None = None) -> None:
        self._nodes: dict[str, KGNode] = {}
        self._edges: list[KGEdge] = []
        self._edge_keys: set[tuple[str, str, EdgeType]] = set()
        self._dataset_profile = {**DEFAULT_DATASET_PROFILE,
                                 **(dataset_profile or {})}

    def add_node(self, node: KGNode) -> KGNode:
        existing = self._nodes.get(node.node_id)
        if existing is None:
            self._nodes[node.node_id] = node
            return node
        known = {item.sha256 for item in existing.evidence}
        merged = existing.model_copy(update={
            "evidence": existing.evidence
            + [item for item in node.evidence if item.sha256 not in known]
        })
        self._nodes[node.node_id] = merged
        return merged

    def add_edge(self, source: str, target: str, edge_type: EdgeType,
                 **attributes: Any) -> None:
        key = (source, target, edge_type)
        if key in self._edge_keys or source not in self._nodes or target not in self._nodes:
            return
        self._edge_keys.add(key)
        self._edges.append(KGEdge(source=source, target=target,
                                  edge_type=edge_type, attributes=attributes))

    def evidence_node(self, doc: SourceDocument) -> str:
        """每份材料对应一个 Evidence 节点，作为 EVIDENCED_BY 的锚点。"""
        stem = Path(doc.path).stem
        node_id = f"evidence.{_slug(stem)}"
        excerpt = doc.content[:200]
        self.add_node(KGNode(
            node_id=node_id,
            node_type=NodeType.EVIDENCE,
            name=f"证据源：{doc.path}",
            attributes={"path": doc.path, "doc_type": doc.doc_type,
                        "file_sha256": doc.sha256},
            evidence=[Evidence(path=doc.path, excerpt=excerpt,
                               sha256=sha256_text(excerpt), doc_type=doc.doc_type)],
        ))
        return node_id

    def row_node(self, doc: SourceDocument, stem: str, section: str,
                 table: Table, row: TableRow, index: int, node_type: NodeType,
                 anchor: str) -> None:
        """由一行原文表格生成一个节点，并连回证据锚点。"""
        raw, cells = row.raw, row.cells
        if not cells:
            return
        item_id = cells[0] if _ID_RE.match(cells[0]) else f"r{index:02d}"
        node_id = f"{_PREFIX_BY_TYPE[node_type]}.{_slug(stem)}.{_slug(item_id)}"
        self.add_node(KGNode(
            node_id=node_id,
            node_type=node_type,
            name=_name_from_row(cells, item_id),
            attributes=_row_attributes(table.headers, cells, section, item_id),
            evidence=[Evidence(path=doc.path, excerpt=raw,
                               sha256=sha256_text(raw), doc_type=doc.doc_type)],
        ))
        self.add_edge(node_id, anchor, EdgeType.EVIDENCED_BY)

    def consume_markdown(self, doc: SourceDocument, anchor: str, stem: str) -> None:
        """按章节解析 Markdown 材料，特殊章节单独汇总。"""
        for section in parse_sections(doc.content):
            if section.title.startswith("FR-"):
                self._consume_failure_case(doc, stem, section, anchor)
            node_type = _row_node_type(doc.doc_type, section.title)
            for table in parse_tables(section.body):
                if node_type is None:
                    continue
                for index, row in enumerate(table.rows, start=1):
                    self.row_node(doc, stem, section.title, table, row,
                                  index, node_type, anchor)
            if doc.doc_type == "业务文档" and "数据集概况" in section.title:
                self._consume_dataset(doc, stem, section, anchor)
        if doc.doc_type == "专家经验":
            self._consume_pipeline(doc, stem, anchor)

    def _consume_dataset(self, doc: SourceDocument, stem: str, section: object,
                         anchor: str) -> None:
        """汇总数据集概况为一个 Dataset 节点，不逐行造节点。"""
        body = section.body  # type: ignore[attr-defined]
        fields: dict[str, str] = {}
        for table in parse_tables(body):
            for row in table.rows:
                if len(row.cells) >= 2:
                    fields[row.cells[0]] = row.cells[1]
        node_id = f"dataset.{_slug(stem)}"
        profile = self._dataset_profile
        self.add_node(KGNode(
            node_id=node_id,
            node_type=NodeType.DATASET,
            name=str(profile.get("name") or f"数据集：{stem}"),
            attributes={
                "fields": fields,
                "target": str(profile.get("target", "")),
                "forbidden_features": list(profile.get("forbidden_features", [])),
                "sensitive_features": list(profile.get("sensitive_features", [])),
                "split_policy": str(profile.get("split_policy", "temporal_holdout")),
            },
            evidence=[Evidence(path=doc.path, excerpt=body.strip()[:400],
                               sha256=sha256_text(body.strip()[:400]),
                               doc_type=doc.doc_type)],
        ))
        self.add_edge(node_id, anchor, EdgeType.EVIDENCED_BY)

    def _consume_failure_case(self, doc: SourceDocument, stem: str,
                              section: object, anchor: str) -> None:
        """FR-xx 小节是「项 | 内容」表，整体折叠为一个 FailureCase。"""
        title, body = section.title, section.body  # type: ignore[attr-defined]
        fields: dict[str, str] = {}
        for table in parse_tables(body):
            for row in table.rows:
                if len(row.cells) >= 2:
                    fields[row.cells[0]] = row.cells[1]
        item_id = title.split()[0]
        excerpt = body.strip()
        node_id = f"fail.{_slug(stem)}.{_slug(item_id)}"
        signature_match = _SIGNATURE_RE.search(fields.get("错误签名", ""))
        self.add_node(KGNode(
            node_id=node_id,
            node_type=NodeType.FAILURE_CASE,
            name=f"[{item_id}] {title[len(item_id):].strip()}",
            attributes={
                **fields,
                "error_signature": signature_match.group(0) if signature_match else None,
            },
            evidence=[Evidence(path=doc.path, excerpt=excerpt,
                               sha256=sha256_text(excerpt), doc_type=doc.doc_type)],
        ))
        self.add_edge(node_id, anchor, EdgeType.EVIDENCED_BY)

    def _consume_pipeline(self, doc: SourceDocument, stem: str, anchor: str) -> None:
        """从代码块解析 PRECEDES 顺序，生成 Operator 节点与顺序边。"""
        order = parse_pipeline_order(doc.content)
        previous: str | None = None
        for index, operator in enumerate(order, start=1):
            node_id = f"op.pipeline.{index:02d}"
            excerpt = " → ".join(order)
            self.add_node(KGNode(
                node_id=node_id,
                node_type=NodeType.OPERATOR,
                name=operator,
                attributes={"order": index, "fit_on_train_only": True,
                            "source_section": "依赖与顺序约束"},
                evidence=[Evidence(path=doc.path, excerpt=excerpt,
                                   sha256=sha256_text(excerpt), doc_type=doc.doc_type)],
            ))
            self.add_edge(node_id, anchor, EdgeType.EVIDENCED_BY)
            if previous:
                self.add_edge(previous, node_id, EdgeType.PRECEDES,
                              rule="fit 仅作用于训练集")
            previous = node_id
        logger.info("解析出 %d 个 pipeline 算子", len(order))

    def consume_legacy(self, doc: SourceDocument, anchor: str, stem: str) -> None:
        """用 AST 抽取函数、依赖与缺陷注释，不执行历史代码。"""
        try:
            tree = ast.parse(doc.content)
        except SyntaxError as exc:
            raise ExtractionError(f"历史代码解析失败：{doc.path}") from exc
        dependencies: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                dependencies.append(node.module)
            elif isinstance(node, ast.FunctionDef):
                excerpt = ast.get_source_segment(doc.content, node) or node.name
                node_id = f"algo.{_slug(stem)}.{_slug(node.name)}"
                self.add_node(KGNode(
                    node_id=node_id,
                    node_type=NodeType.ALGORITHM,
                    name=node.name,
                    attributes={"docstring": ast.get_docstring(node) or "",
                                "args": [arg.arg for arg in node.args.args],
                                "lineno": node.lineno},
                    evidence=[Evidence(path=doc.path, excerpt=excerpt,
                                       sha256=sha256_text(excerpt),
                                       doc_type=doc.doc_type)],
                ))
                self.add_edge(node_id, anchor, EdgeType.EVIDENCED_BY)
        for lineno, line in enumerate(doc.content.splitlines(), start=1):
            match = _DEFECT_RE.search(line)
            if not match:
                continue
            description = match.group(1).strip()
            node_id = f"fail.{_slug(stem)}.defect{lineno:03d}"
            signature_match = _SIGNATURE_RE.search(description)
            self.add_node(KGNode(
                node_id=node_id,
                node_type=NodeType.FAILURE_CASE,
                name=f"[缺陷{lineno}] {description[:60]}",
                attributes={"description": description, "lineno": lineno,
                            "error_signature": signature_match.group(0)
                            if signature_match else None},
                evidence=[Evidence(path=doc.path, excerpt=line.strip(),
                                   sha256=sha256_text(line.strip()),
                                   doc_type=doc.doc_type)],
            ))
            self.add_edge(node_id, anchor, EdgeType.EVIDENCED_BY)
        env_id = f"env.{_slug(stem)}"
        self.add_node(KGNode(
            node_id=env_id,
            node_type=NodeType.ENVIRONMENT,
            name="历史代码依赖环境",
            attributes={"lib_deps": sorted(set(dependencies)),
                        "python_version": "3.11+"},
            evidence=[Evidence(path=doc.path, excerpt="\n".join(sorted(set(dependencies))),
                               sha256=sha256_text("\n".join(sorted(set(dependencies)))),
                               doc_type=doc.doc_type)],
        ))
        self.add_edge(env_id, anchor, EdgeType.EVIDENCED_BY)

    def add_semantic_edges(self) -> None:
        """补齐语义关系；每条边都有可解释的匹配依据。

        早期版本按列表下标轮转（``index % len(metrics)``）让每条能力连到不同
        指标，边数好看但语义随机，评审问到「这条 REQUIRES 凭什么」就答不上来。
        现在改为「名称或属性文本命中才连边」，宁可少连也不乱连；边数下降属于
        正确性的代价，不靠位置补齐数量。
        """
        def by_type(kind: NodeType) -> list[KGNode]:
            return [node for node in self._nodes.values() if node.node_type is kind]

        caps = by_type(NodeType.CAPABILITY)
        ops = by_type(NodeType.OPERATOR)
        metrics = by_type(NodeType.METRIC)
        datasets = by_type(NodeType.DATASET)
        envs = by_type(NodeType.ENVIRONMENT)
        runs = by_type(NodeType.VALIDATION_RUN)
        fails = by_type(NodeType.FAILURE_CASE)
        if not caps:
            return

        # 关键词全部取自节点自身属性，不写死业务名词
        metric_terms = {
            node.node_id: (_terms(node.attributes.get("指标"))
                           | _terms(node.attributes.get("检查项")))
            for node in metrics
        }
        operator_terms = {
            node.node_id: _terms(node.name) | {node.name.lower()} for node in ops
        }
        dataset_terms: set[str] = set()
        for node in datasets:
            for key in ("sensitive_features", "forbidden_features"):
                dataset_terms.update(str(item).lower()
                                     for item in node.attributes.get(key, []))
            target = node.attributes.get("target")
            if target:
                dataset_terms.add(str(target).lower())
        env_terms: set[str] = set()
        for node in envs:
            for dependency in node.attributes.get("lib_deps", []):
                name = str(dependency).strip().lower()
                if not name or name.startswith("__"):
                    continue
                env_terms.add(name)
                # 依赖 ``sklearn.linear_model`` 意味着依赖 ``sklearn``
                env_terms.add(name.split(".")[0])

        texts = {cap.node_id: _node_text(cap) for cap in caps}

        for cap in caps:
            text = texts[cap.node_id]
            section = str(cap.attributes.get("section", ""))
            for node_id, terms in metric_terms.items():
                if any(_contains(text, term) for term in terms):
                    self.add_edge(cap.node_id, node_id, EdgeType.EVALUATED_BY)
            for node_id, terms in operator_terms.items():
                if any(_contains(text, term) for term in terms):
                    self.add_edge(cap.node_id, node_id, EdgeType.USES)
            if envs and any(_contains(text, term) for term in env_terms):
                self.add_edge(cap.node_id, envs[0].node_id, EdgeType.DEPENDS_ON)
            if datasets and ("适用条件" in section or "约束" in section):
                self.add_edge(cap.node_id, datasets[0].node_id, EdgeType.APPLIES_TO)
            if datasets and any(_contains(text, term) for term in dataset_terms):
                self.add_edge(cap.node_id, datasets[0].node_id, EdgeType.REQUIRES)

        # 版本谱系：同一 source_id 在多份材料出现时，后出现的派生自最早那份
        by_source: dict[str, list[KGNode]] = {}
        for cap in caps:
            source_id = str(cap.attributes.get("source_id", "")).strip().lower()
            if source_id:
                by_source.setdefault(source_id, []).append(cap)
        for group in by_source.values():
            if len(group) > 1:
                for other in group[1:]:
                    self.add_edge(other.node_id, group[0].node_id, EdgeType.DERIVED_FROM)

        # 相似 / 可迁移：按共享关键词判定；同章节记 SIMILAR_TO，跨章节记可迁移
        shared: set[str] = set(dataset_terms)
        for terms in metric_terms.values():
            shared.update(terms)
        for terms in operator_terms.values():
            shared.update(terms)
        signatures = {
            cap.node_id: {term for term in shared if _contains(texts[cap.node_id], term)}
            for cap in caps
        }
        for left, right in combinations(caps, 2):
            if not (signatures[left.node_id] & signatures[right.node_id]):
                continue
            same_section = (str(left.attributes.get("section", ""))
                            == str(right.attributes.get("section", "")))
            edge_type = (EdgeType.SIMILAR_TO if same_section
                         else EdgeType.TRANSFERABLE_TO)
            self.add_edge(left.node_id, right.node_id, edge_type)

        # 历史验证：运行记录按检查项 / 候选 id 反查对应能力
        for run in runs:
            terms = (_terms(run.attributes.get("检查项"))
                     | _terms(run.attributes.get("指标")))
            candidate = str(run.attributes.get("candidate_id", "")).strip().lower()
            target = next((cap for cap in caps
                           if any(_contains(texts[cap.node_id], term) for term in terms)),
                          None)
            if target is None and candidate:
                target = next((cap for cap in caps
                               if candidate in cap.node_id.lower()), None)
            if target is None:
                continue
            self.add_edge(target.node_id, run.node_id, EdgeType.HAS_RUN)
            for fail in fails:
                if (run.attributes.get("run_id")
                        and run.attributes.get("run_id") == fail.attributes.get("run_id")):
                    self.add_edge(run.node_id, fail.node_id, EdgeType.RESULTED_IN)

        # 失败案例：修复策略命中的能力才是它修好的对象
        for fail in fails:
            terms = (_terms(fail.attributes.get("fix_strategy"))
                     | _terms(fail.attributes.get("修复策略"))
                     | _terms(fail.attributes.get("定向修复")))
            signature = str(fail.attributes.get("error_signature", "")).strip().lower()
            target = next(
                (cap for cap in caps
                 if any(_contains(texts[cap.node_id], term) for term in terms)
                 or (signature and signature in texts[cap.node_id])),
                None,
            )
            if target is not None:
                self.add_edge(fail.node_id, target.node_id, EdgeType.FIXED_BY)

    def build(self, source_files: list[str]) -> KnowledgeGraph:
        graph = KnowledgeGraph(nodes=list(self._nodes.values()),
                               edges=self._edges, source_files=source_files)
        graph.validate_references()
        return graph


class MockExtractor(BaseExtractor):
    """规则模板抽取器：离线默认路径，输出确定、可复现。

    ``dataset_profile`` 来自 ``verify_*.yaml``，换数据集时只改配置，
    抽取器不再内嵌某个数据集的标签名与敏感字段。
    """

    def __init__(self, dataset_profile: dict[str, Any] | None = None) -> None:
        self.dataset_profile = dataset_profile or {}

    def extract(self, sources: list[SourceDocument]) -> KnowledgeGraph:
        if not sources:
            raise ExtractionError("源材料列表为空")
        builder = _GraphBuilder(self.dataset_profile)
        for doc in sources:
            anchor = builder.evidence_node(doc)
            stem = Path(doc.path).stem
            if doc.doc_type == LEGACY_DOC_TYPE:
                builder.consume_legacy(doc, anchor, stem)
            else:
                builder.consume_markdown(doc, anchor, stem)
        builder.add_semantic_edges()
        graph = builder.build([doc.path for doc in sources])
        logger.info("抽取完成：%d 节点 / %d 边 / %d 类能力",
                    len(graph.nodes), len(graph.edges),
                    len(graph.by_type(NodeType.CAPABILITY)))
        return graph


__all__ = ["BaseExtractor", "ExtractionError", "MockExtractor", "read_sources", "sha256_text"]
