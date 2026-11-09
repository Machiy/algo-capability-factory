"""进程级接线测试：CLI 入口与 API 真实闭环（P1-8）。

此前的接口测试用 ``SimpleNamespace`` 替身，只验证了响应字段映射，没有证明
``/run`` 真的能跑完七步闭环。这里用子进程跑 CLI、用临时工作区跑一次真实
工作流，避免污染仓库内已入库的示例产物。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factory.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]
# Typer / Rich 在带颜色的终端上会把选项拆成 "-\x1b[0m\x1b[1;36m-spec"，
# 断言前统一剥离 ANSI 序列，并同时用 NO_COLOR 关掉着色，避免平台差异
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


class CliProcessTests(unittest.TestCase):
    """CLI 走真实进程，验证入口可执行、退出码与输出正确。"""

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "factory", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ,
                 "PYTHONIOENCODING": "utf-8",
                 "NO_COLOR": "1",
                 "TERM": "dumb",
                 "COLUMNS": "120"},
            timeout=180,
            check=False,
        )

    def test_version_flag(self) -> None:
        import factory

        result = self._run("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"factory {factory.__version__}", _plain(result.stdout))

    def test_check_flag_reports_dependencies(self) -> None:
        result = self._run("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("核心依赖就绪", _plain(result.stdout))

    def test_run_help_lists_task_config_option(self) -> None:
        """换场景的入口参数必须存在，否则跨场景迁移只能靠改代码。"""
        result = self._run("run", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        help_text = _plain(result.stdout)
        for option in ("--spec", "--task-config", "--run-id", "--kg-out", "--gen-dir"):
            self.assertIn(option, help_text)


class ApiWorkflowTests(unittest.TestCase):
    """``POST /run`` 真跑一次七步闭环，而不是替身。"""

    def test_run_endpoint_executes_real_workflow(self) -> None:
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory(prefix="factory_api_ws_") as tmp:
            root = Path(tmp)
            for name in ("configs", "assets"):
                shutil.copytree(ROOT / name, root / name,
                                ignore=shutil.ignore_patterns("repo", "*.arff"))
            for sub in ("generated", "reports", "kg", "runs"):
                (root / "outputs" / sub).mkdir(parents=True, exist_ok=True)
            # 只跑一个候选（HGB，AUC 达标）把耗时压到 10s 内；
            # 配置读取路径与线上完全一致，只是候选数与算法族不同
            config_path = root / "configs/default.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "beam_width: 3", "beam_width: 1"
                ),
                encoding="utf-8",
            )
            credit = root / "configs/verify_credit.yaml"
            credit.write_text(
                credit.read_text(encoding="utf-8").replace(
                    "model_families: [logistic_regression, random_forest, "
                    "hist_gradient_boosting]",
                    "model_families: [hist_gradient_boosting]",
                ),
                encoding="utf-8",
            )
            response = TestClient(create_app(root)).post("/run", json={
                "spec": "预测信用卡客户下月违约概率，时间外划分，禁止 ID 入模",
                "run_id": "api.real",
                "mock": True,
            })
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertTrue(body["passed"], body)
            self.assertEqual(body["candidate_count"], 1)
            candidate = body["candidates"][0]
            self.assertEqual(candidate["primary_metric"], "auc")
            self.assertIsNotNone(candidate["metrics"].get("auc"))
            # 终评确实执行过：test 段指标非空
            self.assertIn("auc", body["test_metrics"])
            self.assertTrue((root / body["report_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
