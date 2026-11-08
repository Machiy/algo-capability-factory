"""子进程沙箱：临时目录、超时、内存上限与最小环境变量隔离。

POSIX 通过 ``resource.RLIMIT_AS`` 硬限制子进程地址空间；Windows 无该接口，
父进程用 ``psutil`` 跨平台轮询子进程内存并在超限时终止。是否真正生效会
如实写入 ``SandboxResult.memory_limit_applied``，不谎报已强制。
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

import psutil

from factory.config import RuntimeSettings
from factory.contracts.validation import SandboxResult, StaticCheckResult

logger = logging.getLogger(__name__)

_ALLOWED_ENV_KEYS = frozenset({
    "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE",
    "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    "PYTHONIOENCODING",
})


def sandbox_env() -> dict[str, str]:
    """白名单式环境隔离：保留 Windows / Python 必需变量，剔除凭据与代理设置。"""
    env = {
        key: value for key, value in os.environ.items()
        if key.upper() in _ALLOWED_ENV_KEYS
    }
    env.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    })
    return env


RUNNER_SOURCE = '''\
import json
import runpy
import sys
import traceback

limit = int(sys.argv[1])
candidate = sys.argv[2]
rlimit_applied = False
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    rlimit_applied = True
except (ImportError, ValueError, OSError):
    pass

try:
    namespace = runpy.run_path(candidate)
    if "build_pipeline" not in namespace:
        raise RuntimeError("build_pipeline 未定义")
    pipeline = namespace["build_pipeline"]({})
    try:
        import resource
        maxrss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        maxrss_mb = 0
    print(json.dumps({
        "status": "ok",
        "symbols": sorted(k for k in namespace if not k.startswith("_")),
        "result_type": type(pipeline).__name__,
        "maxrss_mb": maxrss_mb,
        "rlimit_applied": rlimit_applied,
    }))
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''


def process_memory_bytes(proc: subprocess.Popen[str]) -> int | None:
    """用 psutil 跨平台读取子进程常驻内存；已退出或不可访问时返回 ``None``。"""
    try:
        return int(psutil.Process(proc.pid).memory_info().rss)
    except psutil.Error:
        return None


def _error_signature(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "RuntimeError"


class SubprocessSandbox:
    """在独立进程中执行已通过静态检查的生成代码。"""

    def __init__(self, runtime: RuntimeSettings) -> None:
        self.runtime = runtime

    def run(self, source: str, check: StaticCheckResult | None = None) -> SandboxResult:
        if check is not None and not check.passed:
            return SandboxResult(
                passed=False,
                stderr="静态检查未通过，拒绝进入沙箱执行",
                error_signature=check.error_signature,
            )
        limit_bytes = self.runtime.memory_limit_mb * 1024 * 1024
        state: dict[str, Any] = {"peak": 0, "exceeded": False}
        with tempfile.TemporaryDirectory(prefix="factory_sandbox_") as tmp:
            workdir = Path(tmp)
            candidate = workdir / "candidate.py"
            runner = workdir / "runner.py"
            candidate.write_text(source, encoding="utf-8")
            runner.write_text(RUNNER_SOURCE, encoding="utf-8")
            env = sandbox_env()
            started = time.monotonic()
            proc = subprocess.Popen(
                [sys.executable, str(runner), str(limit_bytes), str(candidate)],
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            watcher: threading.Thread | None = None
            if os.name == "nt":
                watcher = threading.Thread(target=self._watch_memory,
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
            last_line = stdout.strip().splitlines()[-1]
            payload = json.loads(last_line)
        except (IndexError, ValueError):
            payload = {}
        exceeded = bool(state["exceeded"])
        peak_mb: float | None = None
        if state["peak"]:
            peak_mb = round(state["peak"] / (1024 * 1024), 2)
        elif isinstance(payload.get("maxrss_mb"), (int, float)):
            peak_mb = round(float(payload["maxrss_mb"]), 2)
        memory_applied = bool(payload.get("rlimit_applied")) or (os.name == "nt" and
                                                                  state["peak"] > 0)
        if timed_out:
            signature = "Timeout"
        elif exceeded:
            signature = "MemoryLimitExceeded"
        elif proc.returncode != 0:
            signature = _error_signature(stderr)
        else:
            signature = None
        result = SandboxResult(
            passed=proc.returncode == 0 and not timed_out and not exceeded,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=round(duration, 3),
            peak_memory_mb=peak_mb,
            memory_limit_applied=memory_applied,
            timed_out=timed_out,
            memory_exceeded=exceeded,
            error_signature=signature,
        )
        logger.info("沙箱执行完成：passed=%s 耗时=%.3fs 峰值内存=%sMB",
                    result.passed, result.duration_seconds, result.peak_memory_mb)
        return result

    def _watch_memory(self, proc: subprocess.Popen[str], state: dict[str, Any]) -> None:
        limit_bytes = self.runtime.memory_limit_mb * 1024 * 1024
        while proc.poll() is None:
            usage = process_memory_bytes(proc)
            if usage:
                state["peak"] = max(int(state["peak"]), usage)
                if usage > limit_bytes:
                    state["exceeded"] = True
                    proc.kill()
                    return
            time.sleep(0.05)


__all__ = ["SubprocessSandbox", "process_memory_bytes", "sandbox_env"]
