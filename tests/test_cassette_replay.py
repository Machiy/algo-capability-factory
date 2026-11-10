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


class RoleRequestTests(unittest.TestCase):
    """方案 0.3：按角色构造录制请求（不联网、不依赖真实 cassette）。"""

    def test_build_role_request_uses_given_fields(self) -> None:
        from factory.agents.roles import SYSTEM_PROMPTS
        from factory.llm.demo import build_role_request

        settings = load_settings(CONFIG)
        request = build_role_request(
            settings.llm, "Planner", SYSTEM_PROMPTS["Planner"], "示例输入"
        )
        self.assertEqual(request.role, "Planner")
        self.assertEqual(request.system, SYSTEM_PROMPTS["Planner"])
        self.assertEqual(request.user, "示例输入")
        self.assertEqual(request.model, settings.llm.model)
        self.assertEqual(request.temperature, settings.llm.temperature)

    def test_build_demo_request_delegates_to_role_request(self) -> None:
        from factory.llm.demo import build_demo_request, build_role_request

        settings = load_settings(CONFIG)
        demo = build_demo_request(settings.llm)
        role = build_role_request(settings.llm, "Interpreter", demo.system, demo.user)
        self.assertEqual(demo.model_dump(), role.model_dump())

    def test_all_known_roles_have_system_prompt(self) -> None:
        from factory.agents.roles import SYSTEM_PROMPTS

        for role in ("Interpreter", "Planner", "Coder", "Repairer", "Curator"):
            with self.subTest(role=role):
                self.assertIn(role, SYSTEM_PROMPTS)
                self.assertTrue(SYSTEM_PROMPTS[role].strip())

    def test_role_key_fields_stabilize_cognitive_roles(self) -> None:
        """Planner/Coder 按键退化为「角色 + 场景」，Repairer 必须绑当前失败。"""
        from factory.contracts.llm import LLMRequest
        from factory.llm.cassette import compute_key

        settings = load_settings(CONFIG)
        fields = settings.llm.cassette.role_key_fields.get("Planner")
        self.assertEqual(fields, ["role", "system", "scene"])  # Planner/Coder 含 scene
        self.assertNotIn("user", fields)
        request_a = LLMRequest(role="Planner", system="SYS", user="动态A")
        request_b = LLMRequest(role="Planner", system="SYS", user="动态B")
        self.assertEqual(compute_key(request_a, fields), compute_key(request_b, fields))
        # 不同 scene 的 Planner 键不同（跨场景不串扰）
        request_c = LLMRequest(role="Planner", system="SYS", user="x",
                               scene="text_classification")
        self.assertNotEqual(compute_key(request_a, fields), compute_key(request_c, fields))

    def test_repairer_key_binds_error_signature(self) -> None:
        """修复补丁会改源码：键必须含 user，避免把别的错误签名的补丁回放到本次失败上。"""
        from factory.contracts.llm import LLMRequest
        from factory.llm.cassette import compute_key

        settings = load_settings(CONFIG)
        fields = settings.llm.cassette.role_key_fields.get("Repairer")
        self.assertEqual(fields, ["role", "system", "user"])
        key_error = LLMRequest(role="Repairer", system="SYS",
                               user="错误签名：KeyError: PAY_1")
        metric_error = LLMRequest(role="Repairer", system="SYS",
                                  user="错误签名：MetricBelowThreshold")
        self.assertNotEqual(compute_key(key_error, fields),
                            compute_key(metric_error, fields))


if __name__ == "__main__":
    unittest.main()
