"""P2 执行层测试：M2 前置的注入反例、超时与静态门禁。

故意构造危险 import、禁用调用、``ID`` / 标签入模、缺失契约签名与超时代码，
验证必被拦截；这些反例即 M2「能否抓出人为注入的泄漏与危险 import」的判据。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from factory.config import RuntimeSettings, load_settings, load_task_settings
from factory.runtime import StaticChecker, SubprocessSandbox

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/default.yaml"
TASK_CONFIG = ROOT / "configs/verify_credit.yaml"

SAFE_SOURCE = '''
def build_pipeline(config):
    return {"name": "stub", "features": ["LIMIT_BAL"]}
'''

DROP_ID_SOURCE = '''
def build_pipeline(config):
    frame = load_frame()
    return frame.drop(columns=["ID"])
'''

DANGEROUS_IMPORT_SOURCE = '''
import subprocess

def build_pipeline(config):
    subprocess.run(["echo", "hi"])
    return {}
'''

FORBIDDEN_CALL_SOURCE = '''
def build_pipeline(config):
    return open("assets/data/UCI_Credit_Card.csv")
'''

ID_FEATURE_SOURCE = '''
def build_pipeline(config):
    frame = load_frame()
    return frame["ID"]
'''

TARGET_FEATURE_SOURCE = '''
def build_pipeline(config):
    frame = load_frame()
    return frame["default.payment.next.month"]
'''

MISSING_CONTRACT_SOURCE = '''
def other_function(config):
    return {}
'''

SLOW_SOURCE = '''
def build_pipeline(config):
    total = 0
    for index in range(200000000):
        total += index
    return total
'''


class StaticCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = load_settings(DEFAULT_CONFIG)
        task = load_task_settings(TASK_CONFIG)
        cls.checker = StaticChecker(settings.runtime, task.dataset)

    def test_safe_code_passes(self) -> None:
        result = self.checker.check(SAFE_SOURCE)
        self.assertTrue(result.passed, result.violations)
        self.assertEqual(result.failed_checks(), [])
        self.assertEqual(len(result.source_sha256), 64)

    def test_dropping_id_is_allowed(self) -> None:
        result = self.checker.check(DROP_ID_SOURCE)
        self.assertTrue(result.passed, result.violations)

    def test_rejects_dangerous_import(self) -> None:
        result = self.checker.check(DANGEROUS_IMPORT_SOURCE)
        self.assertFalse(result.passed)
        self.assertFalse(result.checks["import_whitelist"])
        self.assertEqual(result.error_signature, "ImportError")

    def test_rejects_forbidden_call(self) -> None:
        result = self.checker.check(FORBIDDEN_CALL_SOURCE)
        self.assertFalse(result.passed)
        self.assertFalse(result.checks["forbidden_calls"])

    def test_rejects_id_as_feature(self) -> None:
        result = self.checker.check(ID_FEATURE_SOURCE)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_signature, "LeakageDetected")

    def test_rejects_target_as_feature(self) -> None:
        result = self.checker.check(TARGET_FEATURE_SOURCE)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_signature, "LeakageDetected")

    def test_rejects_missing_build_pipeline(self) -> None:
        result = self.checker.check(MISSING_CONTRACT_SOURCE)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_signature, "ContractError")

    def test_rejects_syntax_error(self) -> None:
        result = self.checker.check("def build_pipeline(:")
        self.assertFalse(result.passed)
        self.assertEqual(result.error_signature, "SyntaxError")

    def test_rules_come_from_config(self) -> None:
        described = self.checker.describe()
        self.assertIn("numpy", described["allowed_imports"])
        self.assertIn("ID", described["forbidden_features"])
        self.assertEqual(described["target"], "default.payment.next.month")


class SandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = load_settings(DEFAULT_CONFIG)
        task = load_task_settings(TASK_CONFIG)
        cls.runtime = settings.runtime
        cls.checker = StaticChecker(settings.runtime, task.dataset)

    def test_legal_code_runs(self) -> None:
        check = self.checker.check(SAFE_SOURCE)
        self.assertTrue(check.passed)
        result = SubprocessSandbox(self.runtime).run(SAFE_SOURCE, check)
        self.assertTrue(result.passed, result.stderr)
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(result.error_signature)
        self.assertGreater(result.duration_seconds, 0)

    def test_static_failure_blocks_execution(self) -> None:
        check = self.checker.check(DANGEROUS_IMPORT_SOURCE)
        result = SubprocessSandbox(self.runtime).run(DANGEROUS_IMPORT_SOURCE, check)
        self.assertFalse(result.passed)
        self.assertEqual(result.returncode, -1)
        self.assertEqual(result.error_signature, check.error_signature)

    def test_timeout_is_enforced(self) -> None:
        runtime = RuntimeSettings(**{**self.runtime.model_dump(), "timeout_seconds": 2})
        check = self.checker.check(SLOW_SOURCE)
        self.assertTrue(check.passed)
        result = SubprocessSandbox(runtime).run(SLOW_SOURCE, check)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_signature, "Timeout")

    def test_runtime_settings_from_yaml(self) -> None:
        self.assertEqual(self.runtime.timeout_seconds, 60)
        self.assertEqual(self.runtime.memory_limit_mb, 2048)
        self.assertIn("sklearn", self.runtime.allowed_imports)


if __name__ == "__main__":
    unittest.main()
