"""L4 验证层：指标插件、时间外划分、四层检查器、阈值策略与报告生成。"""

from factory.validation.checks import FourLayerValidator
from factory.validation.metrics import compute, list_plugins, register
from factory.validation.report import render_report
from factory.validation.split import TemporalSplitter, TestGate
from factory.validation.thresholds import (
    SUPPORTED_THRESHOLD_STRATEGIES,
    optimal_threshold,
)

__all__ = [
    "SUPPORTED_THRESHOLD_STRATEGIES",
    "FourLayerValidator",
    "TemporalSplitter",
    "TestGate",
    "compute",
    "list_plugins",
    "optimal_threshold",
    "register",
    "render_report",
]
