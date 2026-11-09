"""P6-3 资源消耗与性能基准：同一批候选在 1× 与 N× 数据上的实测对比。

    .venv\\Scripts\\python.exe scripts/resource_benchmark.py
    .venv\\Scripts\\python.exe scripts/resource_benchmark.py --scales 1 10 --repeats 3 1

要点：
- 候选代码由算法模板注册表渲染后，仍放进**子进程沙箱**执行，耗时 / 峰值内存
  取沙箱实测值，推理 P95 由子进程按批（64 条）计时，不是父进程估算。
- N× 数据由真实样本有放回抽样后按原索引排序生成，仅用于放大资源规模；
  其指标不用于业务结论，报告里明确标注。
- 门槛只来自 ``configs/verify_credit.yaml`` 与 ``configs/default.yaml`` 的 ``runtime`` 段，
  本脚本不写任何数值上限。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from factory.agents import templates
from factory.config import load_settings, load_task_settings
from factory.logging_setup import configure_logging
from factory.runtime.dataset_sandbox import DatasetSandbox

FAMILY_HYPERPARAMS: dict[str, dict[str, object]] = {
    "logistic_regression": {"C": 1.0, "max_iter": 1000},
    "hist_gradient_boosting": {"max_iter": 200, "learning_rate": 0.1},
    "random_forest": {"n_estimators": 200, "max_depth": 8},
}


def _feature_columns(frame: pd.DataFrame, task) -> list[str]:
    """与 Workflow 一致：剔除标签、ID、禁入模字段与敏感属性。"""
    excluded = set(task.dataset.forbidden_features)
    excluded.update(task.sensitive_features)
    excluded.update({task.dataset.target, task.dataset.id_column})
    return [name for name in frame.columns if name not in excluded]


def _expanded_csv(frame: pd.DataFrame, scale: int, directory: Path,
                  name: str) -> Path:
    """按 scale 放大样本；放大后按原索引排序，保持时间外划分的行序语义。"""
    if scale == 1:
        path = directory / f"{name}_1x.csv"
        frame.to_csv(path, index=False)
        return path
    expanded = frame.sample(n=len(frame) * scale, replace=True,
                            random_state=42).sort_index()
    path = directory / f"{name}_{scale}x.csv"
    expanded.to_csv(path, index=False)
    return path


def _run_once(settings, task, data_path: Path, n_samples: int, source: str):
    sandbox = DatasetSandbox(
        settings.runtime, task.split, data_path, task.dataset.target,
        sorted(set(task.dataset.forbidden_features) | {task.dataset.target}),
        n_samples,
    )
    return sandbox.run(source).sandbox


def _benchmark(settings, task, columns: list[str], family: str, scale: int,
               repeats: int, data_path: Path, n_samples: int) -> dict:
    source = templates.render(family, columns, FAMILY_HYPERPARAMS.get(family, {}))
    runs = []
    for _ in range(repeats):
        result = _run_once(settings, task, data_path, n_samples, source)
        runs.append({
            "passed": result.passed,
            "duration": result.duration_seconds,
            "peak_mb": result.peak_memory_mb,
            "p95_ms": result.inference_p95_ms,
            "p50_ms": result.inference_p50_ms,
            "signature": result.error_signature,
        })
    durations = [run["duration"] for run in runs]
    peaks = [run["peak_mb"] for run in runs if run["peak_mb"] is not None]
    p95 = [run["p95_ms"] for run in runs if run["p95_ms"] is not None]
    return {
        "family": family,
        "scale": scale,
        "rows": n_samples,
        "repeats": repeats,
        "passed": all(run["passed"] for run in runs),
        "signatures": sorted({run["signature"] for run in runs if run["signature"]}),
        "duration_median": round(statistics.median(durations), 3),
        "duration_max": round(max(durations), 3),
        "peak_mb_max": round(max(peaks), 2) if peaks else None,
        "p95_ms_median": round(statistics.median(p95), 4) if p95 else None,
    }


def _render(rows: list[dict], path: Path, runtime) -> Path:
    lines = [
        "# 资源消耗与性能对比",
        "",
        "> 全部数值为本脚本在子进程沙箱内的实测结果，非估算；",
        "> 耗时取多次重复的中位数与最大值，峰值内存取各次最大值，",
        "> 推理 P95 为子进程按 64 条一批调用 `predict_proba` 的每行毫秒数。",
        (f"> 沙箱上限来自 `configs/default.yaml`：超时 {runtime.timeout_seconds}s、"
         f"内存 {runtime.memory_limit_mb}MB。"),
        "",
        "## 1. 1× 与 N× 数据对比",
        "",
        "| 模型族 | 样本数 | 重复 | 耗时中位数 (s) | 耗时最大 (s) | 峰值内存 (MB) | 推理 P95 (ms/行) | 是否通过 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        peak = "N/A" if row["peak_mb_max"] is None else f"{row['peak_mb_max']:.2f}"
        p95 = "N/A" if row["p95_ms_median"] is None else f"{row['p95_ms_median']:.4f}"
        passed = "PASS" if row["passed"] else "FAIL（" + "、".join(row["signatures"]) + "）"
        lines.append(
            f"| {row['family']} | {row['rows']} | {row['repeats']} | "
            f"{row['duration_median']:.3f} | {row['duration_max']:.3f} | "
            f"{peak} | {p95} | {passed} |"
        )
    lines.extend(["", "## 2. 放大倍数（同族 N× / 1×）", ""])
    scales = sorted({row["scale"] for row in rows})
    base_scale = min(scales)
    large_scale = max(scales)
    lines.extend([
        "| 模型族 | 耗时放大 | 峰值内存放大 | 推理 P95 放大 |",
        "|---|---|---|---|",
    ])
    by_family: dict[str, dict[int, dict]] = {}
    for row in rows:
        by_family.setdefault(row["family"], {})[row["scale"]] = row
    for family, items in by_family.items():
        if base_scale not in items or large_scale not in items:
            continue
        base, large = items[base_scale], items[large_scale]

        def ratio(left: float | None, right: float | None) -> str:
            if not left or right is None:
                return "N/A"
            return f"{right / left:.2f}×"

        lines.append(
            f"| {family} | {ratio(base['duration_median'], large['duration_median'])} | "
            f"{ratio(base['peak_mb_max'], large['peak_mb_max'])} | "
            f"{ratio(base['p95_ms_median'], large['p95_ms_median'])} |"
        )
    lines.extend([
        "",
        "## 3. 口径与使用方式",
        "",
        "- 放大数据由真实样本有放回抽样后按原索引排序生成，只用于资源规模测试；",
        "  该数据上的指标（AUC 等）不代表业务质量，故未在表中列出。",
        "- 耗时与内存的排序以本表实测为准，脚本不做任何预先判断；",
        "  选型时应把「耗时 / 峰值内存 / 推理 P95」与 `verify_credit.yaml` 的指标门槛一起看。",
        "- 出现 FAIL 表示该族在该规模下触发了沙箱超时或内存上限，属于真实结论，未做重试美化。",
        "- 复现命令：`python scripts/resource_benchmark.py`（参数见脚本顶部 docstring）。",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="资源消耗与性能基准")
    parser.add_argument("--scales", nargs="+", type=int, default=[1, 10])
    parser.add_argument("--repeats", nargs="+", type=int, default=[3, 1])
    parser.add_argument("--task-config", default="configs/verify_credit.yaml")
    parser.add_argument("--families", nargs="+",
                        default=list(FAMILY_HYPERPARAMS))
    parser.add_argument("--out", default="outputs/reports/resources.md")
    args = parser.parse_args()
    if len(args.repeats) != len(args.scales):
        parser.error("--repeats 与 --scales 数量必须一致")

    configure_logging()
    settings = load_settings(ROOT / "configs/default.yaml")
    task = load_task_settings(ROOT / args.task_config)
    frame = pd.read_csv(ROOT / settings.paths.data)
    columns = _feature_columns(frame, task)
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="factory_bench_") as tmp:
        directory = Path(tmp)
        for scale, repeats in zip(args.scales, args.repeats):
            data_path = _expanded_csv(frame, scale, directory, "credit")
            n_samples = len(frame) * scale
            for family in args.families:
                row = _benchmark(settings, task, columns, family, scale,
                                 repeats, data_path, n_samples)
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False))
    out = _render(rows, ROOT / args.out, settings.runtime)
    print(f"[P6-3] 资源对比报告：{out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
