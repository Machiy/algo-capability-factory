"""统一日志配置与结构化运行轨迹。

``outputs/runs/`` 被 .gitignore 排除，属于运行时临时轨迹；交付报告与
图谱产物不写在这里，避免把运行噪声带进仓库。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    """在入口处统一配置根日志器，模块内只用 getLogger(__name__)。"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def write_trace(path: Path, payload: dict[str, Any]) -> Path:
    """落盘一次运行的结构化轨迹，供 P5 端到端回放使用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


__all__ = ["configure_logging", "write_trace"]
