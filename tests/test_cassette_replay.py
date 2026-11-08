"""真实 cassette 的离线回放验收：全程不联网、不需要 key。

只读取已入库的脱敏产物，逐条验证来源、回放一致性与脱敏结果；若 cassette
缺失则跳过，保证干净环境也能跑测试。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from factory.config import load_settings
from factory.llm import build_llm
from factory.llm.cassette import cassette_path, compute_key, load_cassette
from factory.llm.demo import RECHECK_USER_PROMPT, build_demo_request

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"


class RealCassetteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG)
        cls.path = cassette_path(
            ROOT / cls.settings.llm.cassette.dir, cls.settings.llm.model
        )
        if not cls.path.is_file():
            raise unittest.SkipTest("真实 cassette 尚未录制")

    def test_cassette_is_from_real_api(self) -> None:
        cassette = load_cassette(self.path)
        self.assertIsNotNone(cassette)
        self.assertEqual(cassette.source, "deepseek_api")
        self.assertEqual(cassette.provider, "deepseek")
        self.assertTrue(cassette.recorded_at)
        self.assertGreaterEqual(len(cassette.entries), 2)

    def test_first_recording_replays(self) -> None:
        """首次真实调用在 provider=cassette 下断网回放，输出与录制逐字一致。"""
        llm_settings = self.settings.llm.model_copy(update={"provider": "cassette"})
        request = build_demo_request(llm_settings)
        result = build_llm(llm_settings, ROOT).complete(request)
        self.assertEqual(result.source, "cassette")
        self.assertTrue(result.cached)
        cassette = load_cassette(self.path)
        key = compute_key(request, llm_settings.cassette.key_fields)
        entry = cassette.find(key)
        self.assertIsNotNone(entry)
        self.assertEqual(result.raw, entry.response["raw"])
        self.assertGreater(len(result.raw), 0)

    def test_recheck_recording_replays_after_library_replacement(self) -> None:
        """替换现成库后的第二次真实调用，同样可断网回放。"""
        llm_settings = self.settings.llm.model_copy(update={"provider": "cassette"})
        request = build_demo_request(llm_settings, RECHECK_USER_PROMPT)
        result = build_llm(llm_settings, ROOT).complete(request)
        self.assertEqual(result.source, "cassette")
        self.assertTrue(result.cached)
        cassette = load_cassette(self.path)
        key = compute_key(request, llm_settings.cassette.key_fields)
        entry = cassette.find(key)
        self.assertIsNotNone(entry)
        self.assertEqual(result.raw, entry.response["raw"])
        self.assertTrue(entry.recorded_at)

    def test_cassette_contains_no_credentials(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("authorization", "api_key", "set-cookie", "api.deepseek.com"):
            self.assertNotIn(forbidden, lowered)
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_\-]{16,}", text))


if __name__ == "__main__":
    unittest.main()
