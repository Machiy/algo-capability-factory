"""指标插件注册：新增任务类型只加 ``verify_*.yaml`` 与插件，不改核心验证器。

插件统一接收关键字上下文（``y_true`` / ``y_score`` / ``y_pred`` / ``groups``
/ ``cost_ratio`` / ``reference`` / ``current``），算不出时返回 ``None`` 并
由调用方记为 FAIL，不静默填充数值。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
    roc_curve,
)

logger = logging.getLogger(__name__)

MetricFn = Callable[..., float | None]
_REGISTRY: dict[str, dict[str, MetricFn]] = {}


def register(plugin: str, name: str) -> Callable[[MetricFn], MetricFn]:
    """注册一个指标实现；重复注册会覆盖并记日志。"""
    def decorator(function: MetricFn) -> MetricFn:
        if name in _REGISTRY.setdefault(plugin, {}):
            logger.warning("指标插件被覆盖：%s.%s", plugin, name)
        _REGISTRY[plugin][name] = function
        return function
    return decorator


def compute(plugin: str, name: str, **context: Any) -> float | None:
    """按插件名与指标名计算，异常时返回 ``None`` 而不是编造数值。"""
    function = _REGISTRY.get(plugin, {}).get(name)
    if function is None:
        raise KeyError(f"未注册指标插件：{plugin}.{name}")
    try:
        return function(**context)
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        logger.warning("指标 %s.%s 计算失败：%s", plugin, name, exc)
        return None


def list_plugins() -> dict[str, list[str]]:
    """返回已注册插件及其指标，供报告说明插件式接入能力。"""
    return {plugin: sorted(names) for plugin, names in sorted(_REGISTRY.items())}


@register("sklearn_metrics", "auc")
def _auc(**context: Any) -> float:
    return float(roc_auc_score(context["y_true"], context["y_score"]))


@register("sklearn_metrics", "pr_auc")
def _pr_auc(**context: Any) -> float:
    return float(average_precision_score(context["y_true"], context["y_score"]))


@register("sklearn_metrics", "f1")
def _f1(**context: Any) -> float:
    return float(f1_score(context["y_true"], context["y_pred"]))


@register("sklearn_metrics", "macro_f1")
def _macro_f1(**context: Any) -> float:
    return float(f1_score(context["y_true"], context["y_pred"], average="macro"))


@register("sklearn_metrics", "accuracy")
def _accuracy(**context: Any) -> float:
    return float(accuracy_score(context["y_true"], context["y_pred"]))


@register("sklearn_metrics", "rmse")
def _rmse(**context: Any) -> float:
    return float(np.sqrt(mean_squared_error(context["y_true"], context["y_pred"])))


@register("sklearn_metrics", "mae")
def _mae(**context: Any) -> float:
    return float(mean_absolute_error(context["y_true"], context["y_pred"]))


@register("sklearn_metrics", "r2")
def _r2(**context: Any) -> float:
    return float(r2_score(context["y_true"], context["y_pred"]))


@register("credit_metrics", "ks")
def _ks(**context: Any) -> float:
    fpr, tpr, _ = roc_curve(context["y_true"], context["y_score"])
    return float(np.max(tpr - fpr))


@register("credit_metrics", "cost_weighted_loss")
def _cost_weighted_loss(**context: Any) -> float:
    ratio = float(context.get("cost_ratio", 5.0))
    threshold = float(context.get("threshold", 0.5))
    y_true = np.asarray(context["y_true"])
    y_pred = (np.asarray(context["y_score"]) >= threshold).astype(int)
    false_negative = int(np.sum((y_true == 1) & (y_pred == 0)))
    false_positive = int(np.sum((y_true == 0) & (y_pred == 1)))
    return float((ratio * false_negative + false_positive) / len(y_true))


@register("credit_metrics", "psi")
def _psi(**context: Any) -> float:
    reference = np.asarray(context["reference"], dtype=float)
    current = np.asarray(context["current"], dtype=float)
    bins = np.linspace(0.0, 1.0, 11)
    ref_pct = np.histogram(reference, bins=bins)[0] / len(reference)
    cur_pct = np.histogram(current, bins=bins)[0] / len(current)
    epsilon = 1e-6
    return float(np.sum((cur_pct - ref_pct) *
                        np.log((cur_pct + epsilon) / (ref_pct + epsilon))))


@register("fairness_metrics", "grouped_auc_gap")
def _grouped_auc_gap(**context: Any) -> float:
    y_true = np.asarray(context["y_true"])
    y_score = np.asarray(context["y_score"])
    groups = np.asarray(context["groups"])
    values: list[float] = []
    for group in np.unique(groups):
        mask = groups == group
        if len(np.unique(y_true[mask])) < 2:
            continue
        values.append(float(roc_auc_score(y_true[mask], y_score[mask])))
    return float(max(values) - min(values)) if len(values) >= 2 else 0.0


__all__ = ["compute", "list_plugins", "register"]
