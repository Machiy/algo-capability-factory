"""生成回归任务用的合成数据（离线、确定、不入模）。

为什么用合成数据：回归场景只用来证明「换一份 verify_*.yaml 就能跑通另一类任务」，
不需要真实业务数据；``sklearn.datasets.make_regression`` 固定种子即可复现，
且不引入任何下载依赖。数据来源与局限在 ``configs/verify_regression.yaml``
的 ``dataset.source`` 中如实标注。
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from sklearn.datasets import make_regression

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets/data/synthetic_demand.csv"
N_SAMPLES = 3000
N_FEATURES = 8
NOISE = 20.0
SEED = 42


def build_rows() -> list[list[float]]:
    """生成特征矩阵与需求目标，目标平移到非负区间。"""
    features, target = make_regression(
        n_samples=N_SAMPLES, n_features=N_FEATURES, noise=NOISE, random_state=SEED,
    )
    demand = target - target.min() + 50.0
    rows = [
        [round(float(value), 3) for value in features[index]]
        + [round(float(demand[index]), 3)]
        for index in range(N_SAMPLES)
    ]
    return rows


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    header = [f"feature_{index}" for index in range(1, N_FEATURES + 1)] + ["demand"]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"已生成 {OUTPUT.relative_to(ROOT)}：{len(rows)} 行 × {len(header)} 列")
    print(f"目标区间：[{min(row[-1] for row in rows):.1f}, "
          f"{max(row[-1] for row in rows):.1f}]，均值 "
          f"{np.mean([row[-1] for row in rows]):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
