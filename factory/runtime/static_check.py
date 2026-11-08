"""AST 静态检查：import 白名单、危险调用、禁入模字段、契约签名。

白名单与禁用模式来自 ``configs/default.yaml``，禁入模字段来自
``configs/verify_credit.yaml``，本模块不内置任何业务列名或阈值。
"""

from __future__ import annotations

import ast
import hashlib
from typing import Any

from factory.config import DatasetSettings, RuntimeSettings
from factory.contracts.validation import StaticCheckResult

_FUTURE_IMPORT = "__future__"
_REQUIRED_FUNCTION = "build_pipeline"


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _subscript_keys(slice_node: ast.AST) -> list[str]:
    """取出 ``df["ID"]`` 或 ``df[["ID", "X"]]`` 中的列名字面量。"""
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return [slice_node.value]
    if isinstance(slice_node, (ast.List, ast.Tuple, ast.Set)):
        return [
            element.value
            for element in slice_node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
    return []


def _signature_for(violations: list[str]) -> str:
    joined = " ".join(violations)
    if "白名单外 import" in joined or "危险调用" in joined:
        return "ImportError"
    if "禁入模字段" in joined:
        return "LeakageDetected"
    if "语法错误" in joined:
        return "SyntaxError"
    if _REQUIRED_FUNCTION in joined:
        return "ContractError"
    return "StaticCheckFailed"


class StaticChecker:
    """把生成代码在 AST 层拦在沙箱之外，不执行任何不受信代码。"""

    def __init__(self, runtime: RuntimeSettings, dataset: DatasetSettings) -> None:
        self.runtime = runtime
        self.dataset = dataset

    def check(self, source: str) -> StaticCheckResult:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        violations: list[str] = []
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return StaticCheckResult(
                passed=False,
                checks={"syntax": False},
                violations=[f"语法错误：{exc.msg} (line {exc.lineno})"],
                source_sha256=digest,
                error_signature="SyntaxError",
            )
        checks = {
            "syntax": True,
            "build_pipeline_signature": self._check_signature(tree, violations),
            "import_whitelist": self._check_imports(tree, violations),
            "forbidden_calls": self._check_calls(tree, violations),
            "forbidden_features": self._check_features(tree, violations),
        }
        passed = all(checks.values())
        return StaticCheckResult(
            passed=passed,
            checks=checks,
            violations=violations,
            source_sha256=digest,
            error_signature=None if passed else _signature_for(violations),
        )

    def _check_signature(self, tree: ast.AST, violations: list[str]) -> bool:
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == _REQUIRED_FUNCTION):
                return True
        violations.append(f"未定义 {_REQUIRED_FUNCTION}() 契约函数")
        return False

    def _check_imports(self, tree: ast.AST, violations: list[str]) -> bool:
        allowed = set(self.runtime.allowed_imports) | {_FUTURE_IMPORT}
        passed = True
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] not in allowed:
                    violations.append(f"白名单外 import：{name}")
                    passed = False
        return passed

    def _check_calls(self, tree: ast.AST, violations: list[str]) -> bool:
        patterns = tuple(self.runtime.forbidden_patterns)
        passed = True
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _dotted_name(node.func)
            for pattern in patterns:
                if name == pattern or name.startswith(f"{pattern}."):
                    violations.append(f"危险调用：{name}")
                    passed = False
                    break
        return passed

    def _check_features(self, tree: ast.AST, violations: list[str]) -> bool:
        forbidden = set(self.dataset.forbidden_features)
        forbidden.update({self.dataset.target, self.dataset.id_column})
        forbidden.discard("")
        passed = True
        for node in ast.walk(tree):
            keys: list[str] = []
            if isinstance(node, ast.Subscript):
                keys = _subscript_keys(node.slice)
            elif isinstance(node, ast.Attribute):
                keys = [node.attr]
            for key in keys:
                if key in forbidden:
                    violations.append(f"禁入模字段：{key}")
                    passed = False
        return passed

    def describe(self) -> dict[str, Any]:
        """返回本次检查所用的规则来源，便于报告说明检查口径。"""
        return {
            "allowed_imports": list(self.runtime.allowed_imports),
            "forbidden_patterns": list(self.runtime.forbidden_patterns),
            "forbidden_features": list(self.dataset.forbidden_features),
            "target": self.dataset.target,
            "required_function": _REQUIRED_FUNCTION,
        }


__all__ = ["StaticChecker"]
