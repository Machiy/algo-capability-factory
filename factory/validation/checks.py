"""四层统一验证：接口规范 / 功能正确性 / 指标表现 / 运行稳定性。

输出复用 ``ValidationReport`` 契约，P3 的 Verifier 与 Repairer 直接消费；
指标门槛一律来自 ``verify_*.yaml``，本模块不内置任何数值。
"""

from __future__ import annotations

import logging
from typing import Any

from factory.config import TaskSettings
from factory.contracts.models import ValidationReport
from factory.contracts.validation import MetricResult, SandboxResult, StaticCheckResult
from factory.validation.metrics import compute

logger = logging.getLogger(__name__)


class FourLayerValidator:
    """把各层证据汇总为一份 ValidationReport。"""

    def __init__(self, task: TaskSettings) -> None:
        self.task = task

    def evaluate_metrics(self, context: dict[str, Any]) -> list[MetricResult]:
        """按任务配置的指标清单调用插件，算不出的指标记为 FAIL。"""
        results: list[MetricResult] = []
        for spec in self.task.metrics:
            value = compute(spec.plugin, spec.name, **context)
            results.append(MetricResult(
                name=spec.name,
                value=value,
                direction=spec.direction,
                threshold=spec.threshold,
                passed=spec.passes(value),
                plugin=spec.plugin,
            ))
        return results

    def validate(
        self,
        *,
        run_id: str,
        plan_id: str,
        static: StaticCheckResult,
        sandbox: SandboxResult,
        metrics: list[MetricResult],
        repeat_variance: float | None = None,
    ) -> ValidationReport:
        interface_checks = dict(static.checks)
        interface_checks["source_hash_recorded"] = bool(static.source_sha256)
        functional_checks = {
            "smoke_passed": sandbox.passed,
            "no_exception": sandbox.returncode == 0,
            "deterministic": repeat_variance is None or repeat_variance < 1e-6,
        }
        threshold_checks = {item.name: item.passed for item in metrics}
        stability: dict[str, Any] = {
            "duration_seconds": sandbox.duration_seconds,
            "peak_memory_mb": sandbox.peak_memory_mb,
            "memory_limit_applied": sandbox.memory_limit_applied,
            "timed_out": sandbox.timed_out,
            "memory_exceeded": sandbox.memory_exceeded,
            "repeat_variance": repeat_variance,
        }
        failed = [
            name
            for group in (interface_checks, functional_checks, threshold_checks)
            for name, ok in group.items()
            if not ok
        ]
        passed = (not failed and not sandbox.timed_out and not sandbox.memory_exceeded)
        signature = None
        if not passed:
            signature = (static.error_signature or sandbox.error_signature
                         or ("MetricBelowThreshold" if any(
                             name in threshold_checks for name in failed
                         ) else "ValidationFailed"))
        report = ValidationReport(
            run_id=run_id,
            plan_id=plan_id,
            passed=passed,
            interface_checks=interface_checks,
            functional_checks=functional_checks,
            metric_values={item.name: item.value for item in metrics},
            threshold_checks=threshold_checks,
            stability=stability,
            error_signature=signature,
            notes="; ".join(failed) if failed else "四层全部通过",
        )
        logger.info("四层验证 %s：passed=%s failed=%s", run_id, passed, failed)
        return report


__all__ = ["FourLayerValidator"]
