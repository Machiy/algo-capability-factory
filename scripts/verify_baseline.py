"""P2 入口：用 baseline 跑通四层验证框架（框架自检，非最终验收）。

运行（项目根目录）：
    .venv\\Scripts\\python.exe scripts/verify_baseline.py

只使用 train / valid 做验证，test 段不访问；敏感字段仅用于分组审计，
``ID`` 与标签均不入模，所有预处理器置于 sklearn.Pipeline 内且仅 fit 训练集。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.config import load_settings, load_task_settings
from factory.logging_setup import configure_logging, write_trace
from factory.runtime import StaticChecker, SubprocessSandbox
from factory.validation import FourLayerValidator, TemporalSplitter, render_report

logger = logging.getLogger(__name__)

BASELINE_SOURCE = '''
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

def build_pipeline(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=42)),
    ])
'''


def build_baseline() -> Pipeline:
    """构造与被测源码等价的本地 baseline，用于产生真实指标。"""
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=42)),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="P2 四层验证框架自检")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--task-config", default="configs/verify_credit.yaml")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--publish", action="store_true",
                        help="额外产出一份冻结样例到 outputs/reports/（交付物）")
    args = parser.parse_args()
    configure_logging(args.log_level)

    settings = load_settings(ROOT / args.config)
    task = load_task_settings(ROOT / args.task_config)
    frame = pd.read_csv(ROOT / settings.paths.data)

    excluded = set(task.dataset.forbidden_features)
    excluded.update({task.dataset.target, task.dataset.id_column})
    excluded.update(task.sensitive_features)
    features = frame.drop(columns=[name for name in excluded if name in frame.columns])
    target = frame[task.dataset.target].to_numpy()

    split = TemporalSplitter(task.split).split(len(frame))
    x_train = features.iloc[split.train]
    x_valid = features.iloc[split.valid]
    y_train = target[split.train]
    y_valid = target[split.valid]

    pipeline = build_baseline()
    pipeline.fit(x_train, y_train)
    valid_score = pipeline.predict_proba(x_valid)[:, 1]
    train_score = pipeline.predict_proba(x_train)[:, 1]
    prediction = (valid_score >= 0.5).astype(int)

    group_column = task.sensitive_features[0] if task.sensitive_features else None
    groups = (frame[group_column].to_numpy()[split.valid]
              if group_column in frame.columns else np.zeros(len(y_valid)))
    context = {
        "y_true": y_valid.tolist(),
        "y_score": valid_score.tolist(),
        "y_pred": prediction.tolist(),
        "cost_ratio": task.cost_ratio_fn_fp,
        "threshold": 0.5,
        "reference": train_score.tolist(),
        "current": valid_score.tolist(),
        "groups": groups.tolist(),
    }

    static = StaticChecker(settings.runtime, task.dataset).check(BASELINE_SOURCE)
    sandbox = SubprocessSandbox(settings.runtime).run(BASELINE_SOURCE, static)
    validator = FourLayerValidator(task)
    metrics = validator.evaluate_metrics(context)
    report = validator.validate(
        run_id="baseline-p2",
        plan_id="baseline_logreg",
        static=static,
        sandbox=sandbox,
        metrics=metrics,
    )
    # 运行时报告含真实耗时/内存，每次不同，落在被 .gitignore 排除的 runs/；
    # 交付样例是一次真实快照，仅 --publish 时冻结到 reports/，避免反复产生 diff。
    report_path = render_report(
        report, metrics, task,
        ROOT / settings.paths.runs / "baseline_validation.md",
    )
    published_path = None
    if args.publish:
        published_path = render_report(
            report, metrics, task,
            ROOT / settings.paths.reports / "validation_sample.md",
        )
    write_trace(ROOT / settings.paths.runs / "trace_baseline.json", {
        "run_id": report.run_id,
        "plan_id": report.plan_id,
        "passed": report.passed,
        "feature_count": len(features.columns),
        "train_size": len(split.train),
        "valid_size": len(split.valid),
        "test_accessed": False,
        "metrics": report.metric_values,
        "stability": report.stability,
    })
    print(f"[P2] 四层验证 passed={report.passed} 指标数={len(metrics)} "
          f"报告={report_path.relative_to(ROOT)}")
    if published_path is not None:
        print(f"  交付样例={published_path.relative_to(ROOT)}")
    for item in metrics:
        value = "N/A" if item.value is None else f"{item.value:.4f}"
        print(f"  {item.name}: {value} ({'PASS' if item.passed else 'FAIL'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
