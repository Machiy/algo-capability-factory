"""产物命名规范（单点定义，全局唯一）。

以前产物名散落在配置、脚本、测试与文档里，同一个场景出现 ``capabilities.json``、
``text_capabilities.json``、``capabilities_text_after_run.json`` 三种风格，读者需要
逐个猜。这里把规则收成一处，代码只调这些函数，改规范只改本文件。

规范：``<scope>_<kind>[_<variant>].<ext>``

- **scope**：场景，取自 ``configs/verify_<scope>.yaml``，仓库抽取用 ``repo``；
- **kind**：``kg``（图谱）/ ``graph``（GraphML）/ ``cypher`` / ``runs``（运行日志）；
- **variant**：``after_run``（回写后）、``lesson``（沉淀演示）等；报告用 run 变体名。

目录：

- ``outputs/kg/<scope>_kg.{json,csv,graphml,cypher,db,html}``
- ``outputs/kg/<scope>_kg[_<variant>].json``（回写图谱）与 ``_runs.json``（运行日志）
- ``outputs/reports/<scope>_run_<variant>.md``；跨场景实验用 ``shared_*``
- ``outputs/generated/<scope>/candidate_plan.0X.py``
- ``outputs/runs/trace_<scope>_<variant>.json``（不入库）
"""

from __future__ import annotations

from pathlib import Path

VERIFY_PREFIX = "verify_"
SHARED = "shared"

KG_SUFFIXES = {
    "json": "json",
    "csv": "csv",
    "graphml": "graphml",
    "cypher": "cypher",
    "db": "db",
    "html": "html",
}


def scene_of(task_config: str | Path, default: str = "credit") -> str:
    """从任务配置名取场景：``configs/verify_text.yaml`` → ``text``。"""
    stem = Path(task_config).stem
    if stem.startswith(VERIFY_PREFIX):
        return stem[len(VERIFY_PREFIX):] or default
    return stem or default


def kg_stem(scene: str, variant: str = "") -> str:
    """``("credit", "after_run")`` → ``credit_kg_after_run``。"""
    return f"{scene}_kg_{variant}" if variant else f"{scene}_kg"


def kg_paths(kg_dir: Path, scene: str, variant: str = "") -> dict[str, Path]:
    """一个场景（或一个变体）的全部图谱产物路径。"""
    stem = kg_stem(scene, variant)
    return {kind: kg_dir / f"{stem}.{suffix}" for kind, suffix in KG_SUFFIXES.items()}


def kg_runs_path(kg_dir: Path, scene: str, variant: str = "") -> Path:
    """运行日志与知识图谱成对命名，避免「哪个是日志」靠猜。"""
    return kg_dir / f"{kg_stem(scene, variant)}_runs.json"


def report_path(reports_dir: Path, scene: str, variant: str) -> Path:
    """``("credit", "demo")`` → ``reports/credit_run_demo.md``。"""
    return reports_dir / f"{scene}_run_{variant}.md"


def shared_report_path(reports_dir: Path, name: str) -> Path:
    """跨场景实验报告：``shared_ablation.md``。"""
    return reports_dir / f"{SHARED}_{name}.md"


def trace_path(runs_dir: Path, scene: str, variant: str) -> Path:
    """运行轨迹：``runs/trace_credit_demo.json``（不入库）。"""
    return runs_dir / f"trace_{scene}_{variant}.json"


def generated_dir(generated_root: Path, scene: str) -> Path:
    """生成代码按场景分目录：``generated/credit/``。"""
    return generated_root / scene


__all__ = [
    "KG_SUFFIXES",
    "SHARED",
    "VERIFY_PREFIX",
    "generated_dir",
    "kg_paths",
    "kg_runs_path",
    "kg_stem",
    "report_path",
    "scene_of",
    "shared_report_path",
    "trace_path",
]
