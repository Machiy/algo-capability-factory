"""L4 验证层：指标插件、时间外划分、四层检查器与报告生成。"""

from factory.validation.checks import FourLayerValidator
from factory.validation.metrics import compute, list_plugins, register
from factory.validation.report import render_report
from factory.validation.split import TemporalSplitter, TestGate

__all__ = [
    "FourLayerValidator",
    "TemporalSplitter",
    "TestGate",
    "compute",
    "list_plugins",
    "register",
    "render_report",
]
