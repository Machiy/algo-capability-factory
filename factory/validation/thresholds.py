"""阈值选择策略：把 ``CandidatePlan.threshold`` 的语义值解析成可复现的数值。

数值阈值原样使用；``cost_optimal`` 在给定评估段上按成本比重扫阈值
（``cost = cost_ratio * FN + FP``），取代价最低的分数点。

阈值口径与 ``credit_metrics.cost_weighted_loss`` 保持一致：预测正类为
``score >= threshold``，因此返回的是**样本实际分数**而不是中点，保证下游用
``>=`` 复算时得到同一组预测。本模块只负责选阈值，不定义指标门槛——门槛仍由
``configs/verify_*.yaml`` 给出，二者不互相覆盖。
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# 支持在 yaml 的 candidates.thresholds 里写的语义值；新增策略需同时注册到
# 本元组与 ``factory.workflow.pipeline.Workflow._resolve_threshold``。
SUPPORTED_THRESHOLD_STRATEGIES: tuple[str, ...] = ("cost_optimal",)


def optimal_threshold(y_true: object, y_score: object,
                      cost_ratio: float = 5.0) -> float:
    """返回使 ``cost_ratio * FN + FP`` 最小的阈值。

    ``cost_ratio`` 是漏报成本与误报成本之比（信用卡场景为 5:1），与
    ``metrics._cost_weighted_loss`` 同源。相邻同分样本整体划入同一侧，所以
    返回的是样本实际分数值。

    输入不可用（空、长度不一致、单一类别）时返回 0.5 并记 warning：宁可退回
    默认阈值，也不编造一个看起来精确的数字。
    """
    labels = np.asarray(y_true, dtype=float).ravel()
    scores = np.asarray(y_score, dtype=float).ravel()
    if labels.size == 0 or labels.size != scores.size:
        logger.warning("成本最优阈值：样本为空或 y_true / y_score 长度不一致，回退 0.5")
        return 0.5
    positive = labels == 1
    if not positive.any() or positive.all():
        logger.warning("成本最优阈值：评估段只有单一类别，成本曲线无意义，回退 0.5")
        return 0.5
    ratio = float(cost_ratio)

    # 升序排列后，「阈值 = 某个分数」等价于「只把该分数及其右侧判为正类」，
    # 于是 FP / FN 都能用后缀和一次算完，复杂度 O(n log n)。
    order = np.argsort(scores, kind="mergesort")
    ordered_scores = scores[order]
    ordered_positive = positive[order]
    unique_scores = np.unique(ordered_scores)
    starts = np.searchsorted(ordered_scores, unique_scores, side="left")
    suffix_negative = np.cumsum(~ordered_positive[::-1])[::-1]
    suffix_positive = np.cumsum(ordered_positive[::-1])[::-1]
    total_positive = int(ordered_positive.sum())
    false_positive = suffix_negative[starts].astype(float)
    false_negative = (total_positive - suffix_positive[starts]).astype(float)
    costs = ratio * false_negative + false_positive

    best = int(np.argmin(costs))
    # 「全部判负」也是一个候选策略：阈值高于最高分时不会被上面任何切分覆盖
    if ratio * total_positive < costs[best]:
        return float(np.nextafter(unique_scores[-1], np.inf))
    threshold = float(unique_scores[best])
    logger.info("成本最优阈值：ratio=%.1f → %.4f（代价 %.2f）",
                ratio, threshold, float(costs[best]))
    return threshold


__all__ = ["SUPPORTED_THRESHOLD_STRATEGIES", "optimal_threshold"]
