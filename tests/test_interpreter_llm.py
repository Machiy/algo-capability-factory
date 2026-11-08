"""任务 1 严格口径：能力理解由真实 LLM 录制响应驱动。

用入库的真实 cassette（``source=deepseek_api``）验证 ``Interpreter`` 消费
真实结构化响应，而不是只看一次孤立演示；未命中时显式回退规则模板并
把 ``last_source`` 标为 ``mock``，不冒充真实调用。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from factory.agents import Interpreter
from factory.config import load_settings
from factory.contracts.llm import LLMRequest, LLMResponse
from factory.contracts.models import TaskType
from factory.llm import BaseLLM, RoutedLLM, build_llm
from factory.llm.cassette import cassette_path
from factory.llm.demo import USER_PROMPT

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/default.yaml"


class _StubLLM(BaseLLM):
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(raw=self.tag, source=self.tag)


class RoutedLLMTests(unittest.TestCase):
    def test_routes_by_role_and_keeps_default(self) -> None:
        routed = RoutedLLM({"Interpreter": _StubLLM("cassette")}, _StubLLM("mock"))
        interpreter_hit = routed.complete(
            LLMRequest(role="Interpreter", system="s", user="u")
        )
        coder_hit = routed.complete(LLMRequest(role="Coder", system="s", user="u"))
        self.assertEqual(interpreter_hit.source, "cassette")
        self.assertEqual(coder_hit.source, "mock")


class RealInterpreterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = load_settings(CONFIG)
        cls.path = cassette_path(
            ROOT / cls.settings.llm.cassette.dir, cls.settings.llm.model
        )
        if not cls.path.is_file():
            raise unittest.SkipTest("真实 cassette 尚未录制")

    def _llm_settings(self, **updates):
        base = {"provider": "cassette", "role_providers": {}}
        base.update(updates)
        return self.settings.llm.model_copy(update=base)

    def test_interpreter_consumes_real_recording(self) -> None:
        settings = self._llm_settings()
        interpreter = Interpreter(build_llm(settings, ROOT), settings)
        spec = interpreter.parse(USER_PROMPT)
        self.assertEqual(interpreter.last_source, "cassette")
        self.assertEqual(spec.spec_id, "spec.next_month_default")
        self.assertEqual(spec.task_type, TaskType.TABULAR_BINARY)
        self.assertAlmostEqual(spec.cost_ratio_fn_fp, 5.0)
        self.assertIn("AUC", spec.metrics)
        self.assertIn("default_probability", spec.outputs)
        joined = " ".join(spec.constraints)
        self.assertIn("out_of_time", joined)
        self.assertIn("id", joined)

    def test_role_routing_keeps_other_roles_on_mock(self) -> None:
        settings = self._llm_settings(provider="mock",
                                      role_providers={"Interpreter": "cassette"})
        llm = build_llm(settings, ROOT)
        self.assertIsInstance(llm, RoutedLLM)
        interpreter = Interpreter(llm, settings)
        interpreter.parse(USER_PROMPT)
        self.assertEqual(interpreter.last_source, "cassette")
        other = llm.complete(LLMRequest(role="Coder", system="s", user="u"))
        self.assertEqual(other.source, "mock")

    def test_unmatched_description_falls_back_explicitly(self) -> None:
        settings = self._llm_settings(provider="mock",
                                      role_providers={"Interpreter": "cassette"})
        interpreter = Interpreter(build_llm(settings, ROOT), settings)
        with self.assertLogs("factory.llm.recorded", level="WARNING"):
            spec = interpreter.parse("完全不同的能力描述，不会命中已录制的请求")
        self.assertEqual(interpreter.last_source, "mock")
        self.assertEqual(spec.spec_id, "spec.workflow.v1")


if __name__ == "__main__":
    unittest.main()
