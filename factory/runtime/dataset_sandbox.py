"""带真实数据集的子进程沙箱：生成代码在此 fit / predict，错误真实发生。

复用 P2 的超时与内存监控口径；列名不存在、禁入模字段等数据陷阱会在子进程
内抛出真实异常，供 Repairer 按错误签名定向修复。
"""

from __future__ import annotations

import json
import logging
import os
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
from factory.runtime.sandbox import _windows_peak_bytes, sandbox_env

logger = logging.getLogger(__name__)

DATASET_RUNNER = '''\
import json
import runpy
import sys
import traceback

candidate, data_path, target, train_end, valid_end, forbidden_json = sys.argv[1:7]
train_end = int(train_end)
valid_end = int(valid_end)
forbidden = set(json.loads(forbidden_json))

try:
    import pandas as pd
    namespace = runpy.run_path(candidate)
    columns = namespace["FEATURE_COLUMNS"]
    overlap = forbidden.intersection(columns)
    if overlap:
        raise ValueError("ForbiddenFeature: " + ",".join(sorted(overlap)))
    frame = pd.read_csv(data_path)
    features = frame[columns]
    labels = frame[target]
    x_train = features.iloc[:train_end]
    y_train = labels.iloc[:train_end]
    x_valid = features.iloc[train_end:valid_end]
    y_valid = labels.iloc[train_end:valid_end]
    pipeline = namespace["build_pipeline"]({})
    pipeline.fit(x_train, y_train)
    valid_score = pipeline.predict_proba(x_valid)[:, 1]
    train_score = pipeline.predict_proba(x_train)[:, 1]
    print(json.dumps({
        "status": "ok",
        "y_true": [float(value) for value in y_valid],
        "y_score": [float(value) for value in valid_score],
        "reference": [float(value) for value in train_score[:500]],
        "current": [float(value) for value in valid_score[:500]],
        "feature_count": len(columns),
    }))
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''


def _signature(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    if "KeyError" in last and "PAY_1" in last:
        return "KeyError: PAY_1"
    if "ForbiddenFeature" in last:
        return "ForbiddenFeature"
    return last or "RuntimeError"


class DatasetSandbox:
    """在独立进程里执行生成代码并做时间外验证。"""

    def __init__(self, runtime: RuntimeSettings, split: SplitSpec,
                 data_path: Path, target: str, forbidden: list[str],
                 n_samples: int = 30000) -> None:
        self.runtime = runtime
        self.data_path = data_path
        self.target = target
        self.forbidden = forbidden
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
                json.dumps(self.forbidden),
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
                proc.kill()
                stdout, stderr = proc.communicate()
                timed_out = True
            duration = time.monotonic() - started
            if watcher is not None:
                watcher.join(timeout=0.2)
        try:
            payload = json.loads(stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            payload = {}
        context = {
            "y_true": payload.get("y_true", []),
            "y_score": payload.get("y_score", []),
            "y_pred": [int(value >= 0.5) for value in payload.get("y_score", [])],
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
        )
        logger.info("数据沙箱：passed=%s 耗时=%.3fs 签名=%s",
                    sandbox.passed, sandbox.duration_seconds, signature)
        return DatasetRunResult(sandbox=sandbox, context=context if sandbox.passed else {})

    def _watch(self, proc: subprocess.Popen[str], state: dict[str, Any]) -> None:
        limit = self.runtime.memory_limit_mb * 1024 * 1024
        while proc.poll() is None:
            usage = _windows_peak_bytes(proc)
            if usage:
                state["peak"] = max(int(state["peak"]), usage)
                if usage > limit:
                    state["exceeded"] = True
                    proc.kill()
                    return
            time.sleep(0.05)


__all__ = ["DatasetSandbox"]
