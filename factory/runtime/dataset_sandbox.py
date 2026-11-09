"""带真实数据集的子进程沙箱：生成代码在此 fit / predict，错误真实发生。

超时与内存监控复用 P2 的 ``sandbox_env`` / ``process_memory_bytes``（psutil）；
列名不存在、禁入模字段等数据陷阱会在子进程内抛出真实异常，供 Repairer
按错误签名定向修复。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from factory.config import RuntimeSettings, SplitSpec
from factory.contracts.validation import SandboxResult
from factory.contracts.workflow import DatasetRunResult
from factory.runtime.sandbox import (
    kill_process_tree,
    process_memory_bytes,
    sandbox_env,
)

logger = logging.getLogger(__name__)

DATASET_RUNNER = '''\
import json
import runpy
import sys
import time
import traceback

candidate, data_path, target, train_end, valid_end, forbidden_json = sys.argv[1:7]
mode = sys.argv[7] if len(sys.argv) > 7 else "tabular"
text_column = sys.argv[8] if len(sys.argv) > 8 else ""
train_end = int(train_end)
valid_end = int(valid_end)
forbidden = set(json.loads(forbidden_json))

def _percentile(values, ratio):
    ordered = sorted(values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, max(0, int(round(ratio * (len(ordered) - 1)))))
    return round(ordered[index], 4)

def _predict_score(pipeline, features):
    """二分类概率优先；无 predict_proba 的模型退回 decision_function。"""
    try:
        proba = pipeline.predict_proba(features)
        if getattr(proba, "ndim", 0) == 2 and proba.shape[1] == 2:
            return [float(value) for value in proba[:, 1]]
    except (AttributeError, NotImplementedError):
        pass
    try:
        decision = pipeline.decision_function(features)
        return [float(value) for value in decision]
    except (AttributeError, NotImplementedError):
        return []

def _warm_predict(pipeline, features):
    """推理延迟探针：优先 predict_proba，没有就 predict。"""
    if hasattr(pipeline, "predict_proba"):
        return pipeline.predict_proba(features)
    return pipeline.predict(features)

try:
    import pandas as pd
    namespace = runpy.run_path(candidate)
    frame = pd.read_csv(data_path)
    labels = frame[target]
    y_train = labels.iloc[:train_end]
    y_valid = labels.iloc[train_end:valid_end]
    if mode == "text":
        texts = frame[text_column].astype(str)
        x_train = texts.iloc[:train_end]
        x_valid = texts.iloc[train_end:valid_end]
        feature_count = 1
    else:
        columns = namespace["FEATURE_COLUMNS"]
        overlap = forbidden.intersection(columns)
        if overlap:
            raise ValueError("ForbiddenFeature: " + ",".join(sorted(overlap)))
        features = frame[columns]
        x_train = features.iloc[:train_end]
        x_valid = features.iloc[train_end:valid_end]
        feature_count = len(columns)
    pipeline = namespace["build_pipeline"]({})
    pipeline.fit(x_train, y_train)
    y_pred = None
    if mode == "regression":
        # 回归直接产出连续值；y_score 与 y_pred 同源，供 PSI 等可选指标复用
        y_score = [float(value) for value in pipeline.predict(x_valid)]
        train_score = [float(value) for value in pipeline.predict(x_train)]
    else:
        y_score = _predict_score(pipeline, x_valid)
        train_score = _predict_score(pipeline, x_train)
        if mode == "text":
            y_pred = [value.item() if hasattr(value, "item") else value
                      for value in pipeline.predict(x_valid)]
    latencies = []
    for start in range(0, len(x_valid), 64):
        chunk = x_valid.iloc[start:start + 64]
        began = time.perf_counter()
        _warm_predict(pipeline, chunk)
        latencies.append((time.perf_counter() - began) * 1000.0 / len(chunk))
    print(json.dumps({
        "status": "ok",
        "y_true": [float(value) for value in y_valid],
        "y_score": y_score,
        "y_pred": y_pred,
        "reference": train_score[:500],
        "current": y_score[:500],
        "feature_count": feature_count,
        "inference_p50_ms": _percentile(latencies, 0.50),
        "inference_p95_ms": _percentile(latencies, 0.95),
    }))
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''


# pandas 抛的是 KeyError: "['PAY_1'] not in index"，dict 抛的是 KeyError: 'label'
_KEY_ERROR_INDEX_RE = re.compile(r"KeyError:\s*\"?\[['\"]([^'\"]+)['\"]\]")
_KEY_ERROR_PLAIN_RE = re.compile(r"KeyError:\s*['\"]?([A-Za-z_][A-Za-z0-9_.]*)['\"]?")


def _signature(stderr: str) -> str:
    """把子进程 stderr 归一到可复用的错误签名，供 Repairer 策略表命中。

    列名类错误统一写成 ``KeyError: <列名>``，而不是只认 ``PAY_1``——
    换数据集时同样的修复策略仍然可用。
    """
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    for pattern in (_KEY_ERROR_INDEX_RE, _KEY_ERROR_PLAIN_RE):
        match = pattern.search(last)
        if match:
            return f"KeyError: {match.group(1)}"
    if "ForbiddenFeature" in last:
        return "ForbiddenFeature"
    return last or "RuntimeError"


class DatasetSandbox:
    """在独立进程里执行生成代码并做时间外验证。"""

    def __init__(self, runtime: RuntimeSettings, split: SplitSpec,
                 data_path: Path, target: str, forbidden: list[str],
                 n_samples: int = 30000, text_column: str = "",
                 mode: str = "") -> None:
        self.runtime = runtime
        self.data_path = data_path
        self.target = target
        self.forbidden = forbidden
        self.text_column = text_column
        # mode 决定子进程如何取特征与产出：tabular 分类 / text 文本 / regression 回归
        self.mode = mode or ("text" if text_column else "tabular")
        self.train_end = int(n_samples * split.train_ratio)
        self.valid_end = int(n_samples * (split.train_ratio + split.valid_ratio))

    def run(self, source: str) -> DatasetRunResult:
        state: dict[str, Any] = {"peak": 0, "exceeded": False}
        with tempfile.TemporaryDirectory(prefix="factory_dataset_sandbox_") as tmp:
            workdir = Path(tmp)
            candidate = workdir / "candidate.py"
            runner = workdir / "runner.py"
            candidate.write_text(source, encoding="utf-8")
            runner.write_text(DATASET_RUNNER, encoding="utf-8")
            env = sandbox_env()
            arguments = [
                sys.executable, str(runner), str(candidate), str(self.data_path),
                self.target, str(self.train_end), str(self.valid_end),
                json.dumps(self.forbidden), self.mode, self.text_column,
            ]
            started = time.monotonic()
            proc = subprocess.Popen(
                arguments, cwd=str(workdir), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding="utf-8", errors="replace", env=env,
            )
            watcher = None
            if os.name == "nt":
                watcher = threading.Thread(target=self._watch,
                                           args=(proc, state), daemon=True)
                watcher.start()
            timed_out = False
            try:
                stdout, stderr = proc.communicate(timeout=self.runtime.timeout_seconds)
            except subprocess.TimeoutExpired:
                kill_process_tree(proc)
                stdout, stderr = proc.communicate()
                timed_out = True
            duration = time.monotonic() - started
            if watcher is not None:
                watcher.join(timeout=0.2)
        try:
            payload = json.loads(stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            payload = {}
        # 文本任务由子进程直接给出预测标签；回归任务预测值即输出；
        # 表格分类任务由概率按 0.5 阈值派生
        if self.mode == "regression":
            predicted = payload.get("y_score", [])
        else:
            predicted = payload.get("y_pred") or [
                int(value >= 0.5) for value in payload.get("y_score", [])
            ]
        context = {
            "y_true": payload.get("y_true", []),
            "y_score": payload.get("y_score") or [],
            "y_pred": predicted,
            "reference": payload.get("reference", []),
            "current": payload.get("current", []),
        }
        signature = ("Timeout" if timed_out else
                     "MemoryLimitExceeded" if state["exceeded"] else
                     None if proc.returncode == 0 else _signature(stderr))
        sandbox = SandboxResult(
            passed=proc.returncode == 0 and not timed_out and not state["exceeded"],
            returncode=proc.returncode,
            stdout=stdout[:2000],
            stderr=stderr[:2000],
            duration_seconds=round(duration, 3),
            peak_memory_mb=(round(state["peak"] / (1024 * 1024), 2)
                            if state["peak"] else None),
            memory_limit_applied=state["peak"] > 0,
            timed_out=timed_out,
            memory_exceeded=bool(state["exceeded"]),
            error_signature=signature,
            inference_p50_ms=payload.get("inference_p50_ms"),
            inference_p95_ms=payload.get("inference_p95_ms"),
        )
        logger.info("数据沙箱：passed=%s 耗时=%.3fs 签名=%s",
                    sandbox.passed, sandbox.duration_seconds, signature)
        return DatasetRunResult(sandbox=sandbox, context=context if sandbox.passed else {})

    def _watch(self, proc: subprocess.Popen[str], state: dict[str, Any]) -> None:
        limit = self.runtime.memory_limit_mb * 1024 * 1024
        while proc.poll() is None:
            usage = process_memory_bytes(proc)
            if usage:
                state["peak"] = max(int(state["peak"]), usage)
                if usage > limit:
                    state["exceeded"] = True
                    kill_process_tree(proc)
                    return
            time.sleep(0.05)


__all__ = ["DatasetSandbox"]
