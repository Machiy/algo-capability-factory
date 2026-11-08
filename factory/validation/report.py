"""Jinja2 验证报告生成：四层结论、指标实测值、稳定性与失败项。

报告不含运行时间戳，重复运行的产物稳定；scope 用于区分「框架自检」
与「最终验收」，避免把 baseline 数值误当作生成算法的验收结果。
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from factory.config import TaskSettings
from factory.contracts.models import ValidationReport
from factory.contracts.validation import MetricResult

REPORT_TEMPLATE = """# 验证报告 · {{ report.run_id }}

> 范围：{{ scope }}。最终验收数值在 P5 实测后由生成算法的验证报告替换。

- 方案：{{ report.plan_id }}
- 任务类型：{{ task.task_type }}
- 通过状态：**{{ "PASS" if report.passed else "FAIL" }}**
- 错误签名：{{ report.error_signature or "无" }}

## 1. 接口规范

{% for name, ok in report.interface_checks.items() %}
- {{ name }}：{{ "PASS" if ok else "FAIL" }}
{% endfor %}

## 2. 功能正确性

{% for name, ok in report.functional_checks.items() %}
- {{ name }}：{{ "PASS" if ok else "FAIL" }}
{% endfor %}

## 3. 指标表现

| 指标 | 实测值 | 方向 | 门槛 | 插件 | 判定 |
|---|---|---|---|---|---|
{% for item in metrics %}
| {{ item.name }} | {{ "%.4f"|format(item.value) if item.value is not none else "N/A" }} | {{ item.direction }} | {{ item.threshold if item.threshold is not none else "—" }} | {{ item.plugin }} | {{ "PASS" if item.passed else "FAIL" }} |
{% endfor %}

## 4. 运行稳定性

{% for name, value in report.stability.items() %}
- {{ name }}：{{ value }}
{% endfor %}

## 5. 说明

{{ report.notes }}
"""


def render_report(
    report: ValidationReport,
    metrics: list[MetricResult],
    task: TaskSettings,
    path: Path,
    scope: str = "验证框架自检 / baseline（非最终验收）",
) -> Path:
    """渲染 Markdown 报告并返回写入路径。"""
    environment = Environment(undefined=StrictUndefined, autoescape=False)
    template = environment.from_string(REPORT_TEMPLATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        template.render(report=report, metrics=metrics, task=task, scope=scope),
        encoding="utf-8",
    )
    return path


__all__ = ["render_report"]
