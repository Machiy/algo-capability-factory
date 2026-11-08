"""实时 LLM 路径的零费用回归（模拟 HTTP 层，不发真实请求）。

替换现成库（structlog / psutil / LangGraph / ...）后，验证 ``scripts/record_llm.py``
的调用链仍完整：``configure_logging`` → ``OpenAICompatLLM.complete`` → 请求参数
组装 → 响应解析 → 脱敏录制 → ``RecordedLLM`` 回放。

本测试不产生 API 费用，也不写入 ``assets/llm_cassettes/`` 的真实交付文件；
真实调用证据仍只有 ``deepseek_deepseek-flash.json`` 中那 1 次录制，二者不可混淆。
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from factory.config import load_settings
from factory.llm.cassette import cassette_path, compute_key, load_cassette
from factory.llm.demo import build_demo_request
from factory.llm.openai_compat import OpenAICompatLLM
from factory.llm.recorded import RecordedLLM
from factory.logging_setup import configure_logging

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"


def _fake_completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20),
    )


class RealtimePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG).llm
        cls.request = build_demo_request(cls.settings)

    def test_realtime_request_parse_record_and_replay(self) -> None:
        raw = '{"spec_id": "spec.realtime.regression"}'
        client = MagicMock()
        client.chat.completions.create.return_value = _fake_completion(raw)
        placeholder = "unit-test-placeholder-key"
        with tempfile.TemporaryDirectory() as tmp:
            settings = self.settings.model_copy(update={
                "cassette": self.settings.cassette.model_copy(
                    update={"dir": tmp, "record": True}
                ),
            })
            with (
                patch("openai.OpenAI", return_value=client),
                patch.dict(os.environ, {"LLM_API_KEY": placeholder}),
            ):
                configure_logging()
                response = OpenAICompatLLM(settings, ROOT).complete(self.request)

            kwargs = client.chat.completions.create.call_args.kwargs
            self.assertEqual(kwargs["model"], settings.model)
            self.assertEqual(kwargs["temperature"], settings.temperature)
            self.assertEqual(kwargs["max_tokens"], settings.max_tokens)
            self.assertEqual(kwargs["extra_body"]["thinking"],
                             {"type": settings.thinking})
            # Interpreter 的 role_overrides 必须真正生效
            self.assertEqual(kwargs["extra_body"]["reasoning_effort"], "low")
            self.assertEqual(kwargs["messages"][0]["role"], "system")
            self.assertEqual(response.source, "deepseek_api")
            self.assertFalse(response.cached)
            self.assertEqual(response.parsed["spec_id"], "spec.realtime.regression")
            self.assertEqual(response.usage.total_tokens, 20)

            path = cassette_path(Path(tmp), settings.model)
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            self.assertNotIn(placeholder, text)
            for forbidden in ("authorization", "api_key", "set-cookie",
                              "api.deepseek.com"):
                self.assertNotIn(forbidden, lowered)

            cassette = load_cassette(path)
            self.assertIsNotNone(cassette)
            self.assertEqual(cassette.source, "deepseek_api")
            key = compute_key(self.request, settings.cassette.key_fields)
            self.assertIsNotNone(cassette.find(key))

            replay_settings = settings.model_copy(update={
                "provider": "cassette",
                "cassette": settings.cassette.model_copy(update={"record": False}),
            })
            replayed = RecordedLLM(cassette, replay_settings).complete(self.request)
            self.assertEqual(replayed.source, "cassette")
            self.assertTrue(replayed.cached)
            self.assertEqual(replayed.raw, response.raw)
            self.assertEqual(replayed.parsed, response.parsed)

    def test_realtime_path_does_not_touch_delivery_cassette(self) -> None:
        """交付 cassette 仍只有 1 条真实录制，不被零费用回归改写。"""
        delivery = (ROOT / self.settings.cassette.dir /
                    "deepseek_deepseek-flash.json")
        if not delivery.is_file():
            self.skipTest("真实 cassette 尚未录制")
        cassette = load_cassette(delivery)
        self.assertEqual(cassette.source, "deepseek_api")
        self.assertEqual(len(cassette.entries), 1)


if __name__ == "__main__":
    unittest.main()
