"""P3 LLM 层测试：回放一致性、未命中策略、脱敏与来源诚实标注。

测试用 cassette 一律标记 ``source="test_fixture"``，明确不是真实 API 响应；
真实录制在 P3 尾、key 到位后由 scripts/record_llm.py 执行。
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factory.config import load_settings, load_task_settings
from factory.contracts.llm import Cassette, LLMRequest, LLMResponse, LLMUsage
from factory.llm import (
    CassetteMiss,
    MissingCredentialError,
    MockLLM,
    OpenAICompatLLM,
    RecordedLLM,
    build_llm,
)
from factory.llm.cassette import (
    REDACTED,
    compute_key,
    load_cassette,
    make_entry,
    sanitize,
    save_cassette,
)
from factory.llm.mock import CODE_TEMPLATE
from factory.runtime import StaticChecker

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"
TASK_CONFIG = ROOT / "configs/verify_credit.yaml"


def _request(**overrides: object) -> LLMRequest:
    payload = {
        "role": "Interpreter",
        "system": "解析能力描述",
        "user": "预测信用卡客户下月违约概率",
        "model": "deepseek-flash",
    }
    payload.update(overrides)
    return LLMRequest(**payload)


def _response(raw: str = '{"ok": true}') -> LLMResponse:
    return LLMResponse(
        raw=raw,
        parsed=json.loads(raw),
        model="deepseek-flash",
        usage=LLMUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        source="deepseek_api",
    )


class MockLLMTests(unittest.TestCase):
    def test_interpreter_returns_parsable_contract(self) -> None:
        response = MockLLM().complete(_request())
        self.assertEqual(response.source, "mock")
        self.assertFalse(response.cached)
        self.assertEqual(response.parsed["task_type"], "tabular_binary_classification")

    def test_coder_template_passes_static_check(self) -> None:
        settings = load_settings(CONFIG)
        task = load_task_settings(TASK_CONFIG)
        result = StaticChecker(settings.runtime, task.dataset).check(CODE_TEMPLATE)
        self.assertTrue(result.passed, result.violations)

    def test_planner_produces_three_candidates(self) -> None:
        response = MockLLM().complete(_request(role="Planner"))
        self.assertEqual(len(response.parsed["candidates"]), 3)


class CassetteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG).llm
        cls.request = _request()
        cls.response = _response()

    def _fixture(self) -> Cassette:
        return Cassette(
            cassette_version=1,
            model=self.settings.model,
            params={"temperature": 0.0},
            source="test_fixture",
            entries=[make_entry(self.request, self.response, self.settings.cassette)],
        )

    def test_key_is_stable_and_sensitive_to_params(self) -> None:
        fields = self.settings.cassette.key_fields
        first = compute_key(self.request, fields)
        self.assertEqual(first, compute_key(_request(), fields))
        changed = self.request.model_copy(update={"reasoning_effort": "low"})
        self.assertNotEqual(first, compute_key(changed, fields))

    def test_replay_is_identical_and_marked_as_cached(self) -> None:
        llm = RecordedLLM(self._fixture(), self.settings)
        first = llm.complete(self.request)
        second = llm.complete(self.request)
        self.assertEqual(first.raw, self.response.raw)
        self.assertEqual(first.parsed, second.parsed)
        self.assertEqual(first.source, "cassette")
        self.assertTrue(first.cached)

    def test_miss_raises_instead_of_fabricating(self) -> None:
        empty = Cassette(model=self.settings.model, source="test_fixture")
        with self.assertRaises(CassetteMiss):
            RecordedLLM(empty, self.settings).complete(self.request)

    def test_fallback_mock_is_explicitly_marked(self) -> None:
        settings = self.settings.model_copy(update={
            "cassette": self.settings.cassette.model_copy(update={"on_miss": "fallback_mock"}),
        })
        llm = RecordedLLM(Cassette(model=settings.model, source="test_fixture"),
                          settings, fallback=MockLLM(settings))
        with self.assertLogs("factory.llm.recorded", level="WARNING"):
            result = llm.complete(self.request)
        self.assertEqual(result.source, "mock")
        self.assertFalse(result.cached)

    def test_build_llm_reports_missing_cassette(self) -> None:
        settings = self.settings.model_copy(update={"provider": "cassette"})
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(CassetteMiss):
            settings = settings.model_copy(update={
                "cassette": settings.cassette.model_copy(update={"dir": tmp}),
            })
            build_llm(settings, ROOT)

    def test_sanitize_removes_secrets_and_forbidden_keys(self) -> None:
        cleaned = sanitize({
            "raw": "Authorization: Bearer sk-fake-secret-abcdef123",
            "Authorization": "Bearer something",
            "api_key": "secret",
            "base_url": "https://api.deepseek.com",
            "set-cookie": "sid=1",
        }, self.settings.cassette.strip, "REALKEY123")
        self.assertNotIn("sk-fake-secret", json.dumps(cleaned, ensure_ascii=False))
        for forbidden in ("Authorization", "api_key", "base_url", "set_cookie"):
            self.assertNotIn(forbidden, cleaned)
        self.assertIn(REDACTED, cleaned["raw"])

    def test_sanitize_replaces_real_key_value(self) -> None:
        cleaned = sanitize({"raw": "key=REALKEY123"}, [], "REALKEY123")
        self.assertNotIn("REALKEY123", cleaned["raw"])

    def test_save_load_roundtrip_is_deterministic(self) -> None:
        fixture = self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cassette.json"
            save_cassette(path, fixture, self.settings.cassette)
            first = path.read_bytes()
            save_cassette(path, fixture, self.settings.cassette)
            self.assertEqual(first, path.read_bytes())
            loaded = load_cassette(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.source, "test_fixture")


class ProviderTests(unittest.TestCase):
    def test_config_values_come_from_yaml(self) -> None:
        settings = load_settings(CONFIG).llm
        self.assertEqual(settings.provider, "mock")
        self.assertEqual(settings.base_url, "https://api.deepseek.com")
        self.assertEqual(settings.model, "deepseek-flash")
        self.assertEqual(settings.api_key_env, "LLM_API_KEY")
        self.assertIn("reasoning_effort", settings.cassette.key_fields)
        self.assertEqual(settings.cassette.on_miss, "error")

    def test_missing_credential_is_explicit(self) -> None:
        settings = load_settings(CONFIG).llm
        with (
            patch.dict(os.environ, {"LLM_API_KEY": ""}),
            self.assertRaises(MissingCredentialError),
        ):
            OpenAICompatLLM(settings, ROOT)

    def test_mock_provider_builds_without_key(self) -> None:
        settings = load_settings(CONFIG).llm
        self.assertIsInstance(build_llm(settings, ROOT), MockLLM)

    def test_unknown_provider_rejected(self) -> None:
        settings = load_settings(CONFIG).llm.model_copy(update={"provider": "unknown"})
        with self.assertRaises(ValueError):
            build_llm(settings, ROOT)


if __name__ == "__main__":
    unittest.main()
