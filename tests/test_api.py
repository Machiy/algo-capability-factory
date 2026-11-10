"""接入层验收：OpenAPI 自动生成、健康检查、/run 契约。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import factory
from factory.api.app import create_app, write_openapi

ROOT = Path(__file__).resolve().parents[1]


class OpenAPITests(unittest.TestCase):
    def test_schema_is_generated_by_framework(self) -> None:
        """schema 由 FastAPI 从路由与模型生成，不手写 spec。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_openapi(Path(tmp) / "openapi.json", ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["openapi"].startswith("3."))
        for route in ("/run", "/health", "/templates"):
            self.assertIn(route, payload["paths"])
        self.assertIn("post", payload["paths"]["/run"])
        schemas = payload["components"]["schemas"]
        for name in ("RunRequest", "RunResponse", "CandidateSummary"):
            self.assertIn(name, schemas)
        # 接口文档的版本号必须跟包版本一致，避免发布后 OpenAPI 还写着旧版本
        self.assertEqual(payload["info"]["version"], factory.__version__)

    def test_health_and_templates(self) -> None:
        client = TestClient(create_app(ROOT))
        self.assertEqual(client.get("/health").json(), {"status": "ok"})
        families = client.get("/templates").json()["templates"]
        self.assertIn("hist_gradient_boosting", families)


class RunEndpointTests(unittest.TestCase):
    def test_run_returns_contract_without_real_workflow(self) -> None:
        fake_trace = SimpleNamespace(
            run_id="api.unit",
            passed=True,
            interpreter_source="cassette",
            kg_mode="with_kg",
            candidates=[
                SimpleNamespace(
                    plan_id="plan.01",
                    model_family="hist_gradient_boosting",
                    passed=True,
                    score=0.7843,
                    repair_rounds=0,
                    metrics={"auc": 0.7843},
                ),
            ],
            repairs=[],
            report_path="outputs/reports/credit_run_api_unit.md",
        )
        with patch("factory.workflow.Workflow") as workflow_cls:
            workflow_cls.return_value.metric_name = "auc"
            workflow_cls.return_value.run.return_value = fake_trace
            client = TestClient(create_app(ROOT))
            response = client.post(
                "/run", json={"spec": "测试能力描述", "run_id": "api.unit"}
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["passed"])
        self.assertEqual(body["interpreter_source"], "cassette")
        self.assertEqual(body["candidate_count"], 1)
        # 指标按任务透出：不再是固定 auc 字段，文本 / 回归场景同样可用
        self.assertEqual(body["candidates"][0]["metrics"]["auc"], 0.7843)
        self.assertEqual(body["candidates"][0]["primary_metric"], "auc")
        self.assertEqual(body["test_metrics"], {})
        self.assertEqual(body["report_path"], "outputs/reports/credit_run_api_unit.md")

    def test_run_rejects_missing_spec(self) -> None:
        client = TestClient(create_app(ROOT))
        self.assertEqual(client.post("/run", json={}).status_code, 422)

    def test_run_rejects_path_traversal_run_id(self) -> None:
        """run_id 会拼进报告/轨迹文件名，接口层必须先挡住路径穿越。"""
        client = TestClient(create_app(ROOT))
        for bad in ("../../evil", "a/b", "", "x" * 65, "空格 id"):
            with self.subTest(run_id=bad):
                response = client.post(
                    "/run", json={"spec": "测试", "run_id": bad}
                )
                self.assertEqual(response.status_code, 422)

    def test_workflow_guard_rejects_illegal_run_id(self) -> None:
        """绕过接口直接调用工作流时，同样在入口被拒（不产生任何产物）。"""
        from factory.workflow import run_from_cli

        code = run_from_cli("预测信用卡客户下月违约概率", mock=True,
                            root=ROOT, run_id="../escape")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
