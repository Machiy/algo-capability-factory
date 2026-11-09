"""真实代码仓库抽取：用标准库 ``ast`` 从开源仓库抽函数、依赖与能力描述。

与 ``assets/legacy/legacy_default_model.py``（自建代码示例）不同，本模块面向
**真实开源仓库**：只读文件、不 import、不执行，因此没有任何供应链风险。
抽取产物映射到题目要求的 ``Capability`` / ``Environment`` / ``Evidence`` 节点，
能力描述取自函数 docstring，依赖取自 module 级 import，证据保留源码行号。

入口：``scripts/extract_repo.py``；被 ``tests/test_repo_extractor.py`` 覆盖。
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from factory.contracts.knowledge import (
    EdgeType,
    Evidence,
    KGEdge,
    KGNode,
    KnowledgeGraph,
    NodeType,
)

logger = logging.getLogger(__name__)

DOC_TYPE = "历史代码仓库（开源）"
_SECTION_STOP = re.compile(
    r"^(Returns?|Yields?|Raises|Examples?|Notes?|References?|See Also|Attributes)\s*:?\s*$",
    re.IGNORECASE,
)
_PARAM_LINE = re.compile(r"^([A-Za-z_][\w,\s\*]*)\s*:\s*(.+)$")
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))


def sha256_text(text: str) -> str:
    """证据摘要与知识层使用同一哈希口径。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned[:60] or "item"


@dataclass(frozen=True)
class RepoFunction:
    """仓库中的一个函数（或方法）及其可抽取的能力描述。"""

    path: str
    module: str
    qualname: str
    name: str
    signature: str
    summary: str
    docstring: str
    parameters: list[str]
    returns: str
    decorators: list[str]
    calls: list[str]
    lineno: int
    public: bool

    @property
    def excerpt(self) -> str:
        """证据摘录：签名行 + docstring 首行，评审可肉眼回溯。"""
        head = f"{self.path}:{self.lineno}: {self.signature}"
        return f"{head}\n{self.summary}" if self.summary else head


@dataclass(frozen=True)
class RepoScan:
    """一次仓库扫描的结构化结果。"""

    repo: str
    root: str
    functions: list[RepoFunction] = field(default_factory=list)
    module_imports: dict[str, list[str]] = field(default_factory=dict)
    python_requires: str = ""
    skipped: list[str] = field(default_factory=list)

    @property
    def public_functions(self) -> list[RepoFunction]:
        return [item for item in self.functions if item.public]

    @property
    def internal_modules(self) -> set[str]:
        """包内模块名（末段），用于把 `import woebin` 这类自引用剔除出依赖。"""
        names = {module.split(".")[-1] for module in self.module_imports}
        return names | {self.repo}

    @property
    def dependencies(self) -> list[str]:
        """跨模块汇总的第三方依赖（剔除标准库与包内自引用）。"""
        internal = self.internal_modules
        found: set[str] = set()
        for imports in self.module_imports.values():
            for name in imports:
                root = name.split(".")[0]
                if not root or root in _STDLIB or root in internal or root.startswith("_"):
                    continue
                found.add(root)
        return sorted(found)


def _docstring_summary(node: ast.AST) -> tuple[str, str]:
    doc = ast.get_docstring(node) or ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped, doc
    return "", doc


_PARAM_HEADERS = frozenset(
    {"parameters", "parameter", "params", "param", "args", "arguments"}
)


def _docstring_params(doc: str) -> list[str]:
    """从 docstring 的 Parameters / Params / Args 段抽取「参数: 说明」。"""
    lines = doc.splitlines()
    params: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if not inside:
            if stripped.rstrip(":").lower() in _PARAM_HEADERS:
                inside = True
            continue
        if _SECTION_STOP.match(stripped):
            break
        if set(stripped) <= {"-", "—", "="} and stripped:
            continue
        match = _PARAM_LINE.match(stripped)
        if match:
            params.append(f"{match.group(1).strip()}: {match.group(2).strip()}")
    return params


def _docstring_returns(doc: str) -> str:
    lines = doc.splitlines()
    for index, line in enumerate(lines):
        if line.strip().rstrip(":").lower() in {"returns", "return", "yields"}:
            for follow in lines[index + 1:]:
                stripped = follow.strip()
                if not stripped or set(stripped) <= {"-", "—"}:
                    continue
                return stripped
    return ""


def _call_names(node: ast.AST) -> list[str]:
    """收集函数体内被调用的点号名，作为能力组合线索。"""
    names: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = child.func
        parts: list[str] = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        if parts:
            names.append(".".join(reversed(parts)))
    return sorted(set(names))


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or root.name


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    try:
        return f"{prefix} {node.name}({ast.unparse(node.args)})"
    except (ValueError, RecursionError):
        return f"{prefix} {node.name}(...)"


class RepoExtractor:
    """AST 抽取器：只读源码，不导入、不执行仓库中的任何代码。"""

    def scan(self, repo_dir: Path, repo_name: str = "") -> RepoScan:
        root = repo_dir.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"仓库目录不存在：{repo_dir}")
        repo = repo_name or root.name
        functions: list[RepoFunction] = []
        module_imports: dict[str, list[str]] = {}
        skipped: list[str] = []
        python_requires = ""
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                with warnings.catch_warnings():
                    # 第三方源码里的正则转义会触发 SyntaxWarning，不影响 AST
                    warnings.simplefilter("ignore", SyntaxWarning)
                    tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError) as exc:
                logger.warning("跳过无法解析的源码 %s：%s", relative, exc)
                skipped.append(relative)
                continue
            module = _module_name(path, root)
            imports = self._imports(tree)
            module_imports[module] = imports
            python_requires = python_requires or self._python_requires(tree, relative)
            functions.extend(
                self._functions(tree, source, relative, module, imports)
            )
        scan = RepoScan(
            repo=repo, root=root.as_posix(), functions=functions,
            module_imports=module_imports, python_requires=python_requires,
            skipped=skipped,
        )
        logger.info("仓库抽取：%d 个 .py 文件 / %d 个函数 / 依赖 %d 个",
                    len(module_imports), len(functions), len(scan.dependencies))
        return scan

    @staticmethod
    def _imports(tree: ast.AST) -> list[str]:
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        return sorted(set(names))

    @staticmethod
    def _python_requires(tree: ast.AST, relative: str) -> str:
        """从 ``setup.py`` 的 ``python_requires`` 关键字读取版本约束。"""
        if not relative.endswith("setup.py"):
            return ""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "python_requires" and isinstance(
                        keyword.value, ast.Constant):
                    return str(keyword.value.value)
        return ""

    def _functions(self, tree: ast.AST, source: str, relative: str,
                   module: str, imports: list[str]) -> list[RepoFunction]:
        results: list[RepoFunction] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            summary, doc = _docstring_summary(node)
            results.append(RepoFunction(
                path=relative,
                module=module,
                qualname=node.name,
                name=node.name,
                signature=_signature(node),
                summary=summary,
                docstring=doc,
                parameters=_docstring_params(doc),
                returns=_docstring_returns(doc),
                decorators=[ast.unparse(item) for item in node.decorator_list],
                calls=_call_names(node),
                lineno=node.lineno,
                public=not node.name.startswith("_"),
            ))
        return results

    def to_graph(self, scan: RepoScan) -> KnowledgeGraph:
        """把扫描结果映射成 Capability / Environment / Evidence 节点图。"""
        repo_slug = _slug(scan.repo)
        env_id = f"env.repo.{repo_slug}"
        env_excerpt = (
            f"{scan.repo}: python_requires={scan.python_requires or '未声明'}; "
            f"deps={', '.join(scan.dependencies) or '无'}"
        )
        nodes: list[KGNode] = [KGNode(
            node_id=env_id,
            node_type=NodeType.ENVIRONMENT,
            name=f"{scan.repo} 依赖环境",
            attributes={
                "lib_deps": scan.dependencies,
                "python_requires": scan.python_requires,
                "repository": scan.root,
            },
            evidence=[Evidence(path=scan.repo, excerpt=env_excerpt,
                               sha256=sha256_text(env_excerpt), doc_type=DOC_TYPE)],
        )]
        edges: list[KGEdge] = []
        # 同模块内可能有同名嵌套函数，按 node_id 去重；调用关系另按全局唯一名解析
        capability_ids: dict[str, str] = {}
        seen: set[str] = set()
        by_name: dict[str, str] = {}
        for item in scan.public_functions:
            node_id = f"cap.repo.{repo_slug}.{_slug(item.module)}.{_slug(item.name)}"
            if node_id in seen:
                # 同模块同名嵌套函数：用行号区分，避免静默丢弃能力
                node_id = f"{node_id}.L{item.lineno}"
                logger.info("能力 id 重名，改用行号区分：%s", node_id)
            seen.add(node_id)
            capability_ids[f"{item.module}.{item.name}"] = node_id
            by_name.setdefault(item.name, node_id)
            nodes.append(KGNode(
                node_id=node_id,
                node_type=NodeType.CAPABILITY,
                name=(item.summary or item.name)[:80],
                task_type="tabular_binary_classification",
                status="candidate",
                attributes={
                    "repository": scan.repo,
                    "module": item.module,
                    "qualname": item.qualname,
                    "signature": item.signature,
                    "parameters": item.parameters,
                    "returns": item.returns,
                    "decorators": item.decorators,
                    "calls": item.calls,
                    "source_path": item.path,
                    "lineno": item.lineno,
                    "docstring": item.docstring[:2000],
                },
                evidence=[Evidence(path=item.path, excerpt=item.excerpt,
                                   sha256=sha256_text(item.excerpt),
                                   doc_type=DOC_TYPE)],
            ))
            edges.append(KGEdge(source=node_id, target=env_id,
                                edge_type=EdgeType.DEPENDS_ON))
        for module, imports in sorted(scan.module_imports.items()):
            evidence_id = f"evidence.repo.{repo_slug}.{_slug(module)}"
            excerpt = f"{module}: {', '.join(imports) or '无 import'}"
            nodes.append(KGNode(
                node_id=evidence_id,
                node_type=NodeType.EVIDENCE,
                name=f"{scan.repo}/{module} 源码",
                attributes={"module": module, "imports": imports},
                evidence=[Evidence(path=f"{scan.repo}/{module}",
                                   excerpt=excerpt, sha256=sha256_text(excerpt),
                                   doc_type=DOC_TYPE)],
            ))
            for item in scan.public_functions:
                target = capability_ids.get(f"{item.module}.{item.name}")
                if item.module == module and target:
                    edges.append(KGEdge(source=target, target=evidence_id,
                                        edge_type=EdgeType.EVIDENCED_BY))
        for item in scan.public_functions:
            source_id = capability_ids.get(f"{item.module}.{item.name}")
            if not source_id:
                continue
            for called in item.calls:
                target_id = by_name.get(called.split(".")[-1])
                if target_id and target_id != source_id:
                    edges.append(KGEdge(source=source_id, target=target_id,
                                        edge_type=EdgeType.USES,
                                        attributes={"call": called}))
        graph = KnowledgeGraph(
            nodes=nodes, edges=edges,
            source_files=sorted(scan.module_imports),
        )
        graph.validate_references()
        logger.info("仓库能力图：%d 节点 / %d 边（%d 个公开能力）",
                    len(graph.nodes), len(graph.edges), len(capability_ids))
        return graph


__all__ = ["RepoExtractor", "RepoFunction", "RepoScan", "sha256_text"]
