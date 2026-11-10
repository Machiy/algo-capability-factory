"""入口引导测试：用户「瞎说」时先引导，而不是把噪声灌进七步闭环。

覆盖三层：规则引擎（要素体检 / 跑题拦截 / 场景错配）、工作流前置拦截，
以及 CLI 与 API 两个入口的对外行为。全部离线，不调用任何 LLM。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from factory.config import load_settings, load_task_settings
from factory.contracts.intake import IntakeVerdict
from factory.intake import IntakeGuide, render_guidance, render_menu

ROOT = Path(__file__).resolve().parents[1]
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# README「5 分钟验收路径」里的三条示例必须始终被判为可执行，否则引导会误伤
DEMO_SPECS = [
    ("configs/verify_credit.yaml",
     "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"),
    ("configs/verify_text.yaml",
     "把短信分类为垃圾短信或正常短信，输出准确率与宏平均 F1"),
    ("configs/verify_regression.yaml",
     "根据多期特征预测日需求量，最小化RMSE，输出RMSE/MAE/R2"),
]


def build_guide(task_config: str = "configs/verify_credit.yaml") -> IntakeGuide:
    settings = load_settings(ROOT / "configs/default.yaml")
    task = load_task_settings(ROOT / task_config)
    return IntakeGuide(
        settings.intake, task.intake,
        configs_dir=ROOT / "configs",
        task_config=task_config,
        graph_path=ROOT / "outputs/kg/capabilities_after_run.json",
    )


class IntakeRuleTests(unittest.TestCase):
    """规则引擎：判定、追问、示例与场景错配。"""

    def test_demo_specs_are_accepted(self) -> None:
        """三个场景的官方示例不能被引导误拦。"""
        for task_config, spec in DEMO_SPECS:
            with self.subTest(task_config=task_config):
                guidance = build_guide(task_config).review(spec)
                self.assertIsNot(guidance.verdict, IntakeVerdict.REJECT, guidance)
                self.assertGreaterEqual(guidance.score, 0.6)

    def test_blank_spec_is_rejected_with_examples(self) -> None:
        guidance = build_guide().review("   ")
        self.assertIs(guidance.verdict, IntakeVerdict.REJECT)
        self.assertIn("empty", [item.code for item in guidance.issues])
        # 拒绝时必须给可复制的示例，否则用户不知道怎么写
        self.assertTrue(guidance.examples)
        self.assertIn("输入引导", render_guidance(guidance))

    def test_gibberish_is_rejected_as_too_short(self) -> None:
        guidance = build_guide().review("asdf")
        self.assertIs(guidance.verdict, IntakeVerdict.REJECT)
        self.assertIn("too_short", [item.code for item in guidance.issues])

    def test_off_topic_request_is_rejected(self) -> None:
        guidance = build_guide().review("帮我写一首关于春天的诗")
        self.assertIs(guidance.verdict, IntakeVerdict.REJECT)
        self.assertIn("off_topic", [item.code for item in guidance.issues])

    def test_incomplete_spec_gets_clarify_and_questions(self) -> None:
        """缺「输入数据」时给出针对性的追问，但仍允许继续。"""
        guidance = build_guide().review("我要做一个违约预测的东西")
        self.assertIs(guidance.verdict, IntakeVerdict.CLARIFY)
        self.assertIn("data", guidance.missing_elements)
        self.assertTrue(guidance.questions)
        self.assertIn("missing_data", [item.code for item in guidance.issues])

    def test_scenario_mismatch_points_to_other_config(self) -> None:
        """在信用卡任务里写短信分类，应提示换 --task-config，而不是硬跑。"""
        guidance = build_guide("configs/verify_credit.yaml").review(
            "把短信分类为垃圾短信或正常短信，输出准确率与宏平均 F1"
        )
        codes = [item.code for item in guidance.issues]
        self.assertIn("task_mismatch", codes)
        self.assertIn("configs/verify_text.yaml", guidance.suggestion)
        # 示例要换成用户真正想跑的场景，避免照抄信用卡示例
        self.assertIn("短信", guidance.examples[0])

    def test_capability_id_reference_is_accepted(self) -> None:
        """直接引用图谱能力 id 复刻时，缺字段由图谱补齐，不追问。"""
        guidance = build_guide().review("复刻 cap.data_dictionary.T1")
        self.assertIs(guidance.verdict, IntakeVerdict.OK)
        self.assertIn("capability_ref", [item.code for item in guidance.issues])
        self.assertFalse(guidance.questions)

    def test_describe_lists_elements_and_scenarios(self) -> None:
        info = build_guide().describe()
        self.assertEqual(info["scenario"], "信用卡违约预测")
        self.assertGreaterEqual(len(info["elements"]), 4)
        self.assertTrue(info["examples"])
        configs = {item["task_config"] for item in info["scenarios"]}
        self.assertIn("configs/verify_text.yaml", configs)
        self.assertIn("能力描述引导", render_menu(build_guide()))


class WorkflowGuardTests(unittest.TestCase):
    """工作流前置拦截：不可执行的描述不消耗一次七步闭环。"""

    def _workflow(self):
        from factory.workflow import Workflow

        settings = load_settings(ROOT / "configs/default.yaml")
        task = load_task_settings(ROOT / "configs/verify_credit.yaml")
        settings.llm = settings.llm.model_copy(
            update={"provider": "mock", "role_providers": {}}
        )
        return Workflow(settings, task, ROOT, use_knowledge=False)

    def test_reject_raises_before_running(self) -> None:
        from factory.intake import SpecRejected

        with self.assertRaises(SpecRejected) as ctx:
            self._workflow().run("你好", "unit_intake")
        self.assertIs(ctx.exception.guidance.verdict, IntakeVerdict.REJECT)

    def test_intake_section_renders_in_report(self) -> None:
        from factory.workflow.pipeline import render_intake_section

        guidance = build_guide().review("我要做一个违约预测的东西")
        section = "\n".join(render_intake_section(guidance))
        self.assertIn("## 0. 输入引导", section)
        self.assertIn("CLARIFY", section)


class CliIntakeTests(unittest.TestCase):
    """CLI 入口：menu 子命令、非交互环境不挂起、拒绝时退出码非 0。"""

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        # stdin 显式置空：交互引导只在 tty 下启用，测试环境不能等输入
        return subprocess.run(
            [sys.executable, "-m", "factory", *args],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1",
                 "TERM": "dumb", "COLUMNS": "120"},
            timeout=180,
            check=False,
        )

    def test_guide_prints_menu(self) -> None:
        result = self._run("guide")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = _ANSI_RE.sub("", result.stdout)
        self.assertIn("能力描述引导", text)
        self.assertIn("任务目标", text)
        self.assertIn("configs/verify_text.yaml", text)

    def test_guide_reviews_spec_and_exits_nonzero_when_rejected(self) -> None:
        result = self._run("guide", "--spec", "asdf")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("输入引导", _ANSI_RE.sub("", result.stdout))

    def test_run_without_spec_does_not_hang_in_non_interactive_env(self) -> None:
        result = self._run("run", "--mock")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--spec", _ANSI_RE.sub("", result.stdout + result.stderr))


class ApiIntakeTests(unittest.TestCase):
    """API 入口：引导菜单、只体检不跑、拒绝时返回 422 结构化 detail。"""

    def test_guide_and_review_endpoints(self) -> None:
        from fastapi.testclient import TestClient

        from factory.api.app import create_app

        client = TestClient(create_app(ROOT))
        menu = client.get("/intake/guide")
        self.assertEqual(menu.status_code, 200, menu.text)
        self.assertTrue(menu.json()["examples"])

        review = client.post("/intake/review", json={"spec": "asdf"})
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(review.json()["verdict"], "reject")
        self.assertTrue(review.json()["examples"])

        mismatch = client.post("/intake/review", json={
            "spec": "把短信分类为垃圾短信或正常短信，输出准确率与宏平均 F1",
            "task_config": "configs/verify_credit.yaml",
        })
        codes = [item["code"] for item in mismatch.json()["issues"]]
        self.assertIn("task_mismatch", codes)

    def test_run_rejects_gibberish_with_guidance(self) -> None:
        from fastapi.testclient import TestClient

        from factory.api.app import create_app

        client = TestClient(create_app(ROOT))
        response = client.post("/run", json={"spec": "写一首诗", "run_id": "api.intake"})
        self.assertEqual(response.status_code, 422, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["guidance"]["verdict"], "reject")
        self.assertTrue(detail["guidance"]["examples"])


if __name__ == "__main__":
    unittest.main()
