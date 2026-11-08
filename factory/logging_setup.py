"""统一日志配置（structlog）与结构化运行轨迹。

``outputs/runs/`` 被 .gitignore 排除，属于运行时临时轨迹；交付报告与
图谱产物不写在这里，避免把运行噪声带进仓库。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import structlog


def configure_logging(level: str = "INFO") -> None:
    """用 structlog 统一配置根日志器，兼容模块内的标准库 getLogger 调用。"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.ExtraAdder(),
        ],
        processor=structlog.dev.ConsoleRenderer(colors=False),
    ))
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def write_trace(path: Path, payload: dict[str, Any]) -> Path:
    """落盘一次运行的结构化轨迹，供 P5 端到端回放使用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


__all__ = ["configure_logging", "write_trace"]
