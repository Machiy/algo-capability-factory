"""规则模板 LLM：离线默认路径，输出确定、不联网、不需要凭据。

明确标注 ``source="mock"``，绝不冒充真实模型输出；Coder 模板生成的
``build_pipeline()`` 满足 AST 白名单与「预处理置于 Pipeline 内」约束。
"""

from __future__ import annotations

import json

from factory.config import LLMSettings
from factory.contracts.llm import LLMRequest, LLMResponse
from factory.llm.base import BaseLLM

CODE_TEMPLATE = '''\
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

def build_pipeline(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=42)),
    ])
'''


class MockLLM(BaseLLM):
    """按角色返回规则模板内容，供离线闭环与测试使用。"""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings()

    def complete(self, request: LLMRequest) -> LLMResponse:
        raw, parsed = self._render(request)
        return LLMResponse(raw=raw, parsed=parsed, model="mock", source="mock")

    def _render(self, request: LLMRequest) -> tuple[str, dict]:
        role = request.role
        if role == "Interpreter":
            parsed = {
                "spec_id": "spec.mock.credit.v1",
                "description": request.user,
                "task_type": "tabular_binary_classification",
                "constraints": ["时间外划分", "敏感字段不入模", "ID 禁止入模"],
            }
        elif role == "Planner":
            parsed = {"candidates": [
                {"plan_id": "plan.lr", "model_family": "logistic_regression"},
                {"plan_id": "plan.woe", "model_family": "logistic_regression",
                 "operators": ["WOEBinner"]},
                {"plan_id": "plan.hgb", "model_family": "hist_gradient_boosting"},
            ]}
        elif role == "Coder":
            return CODE_TEMPLATE, {"contract": "build_pipeline"}
        elif role == "Repairer":
            parsed = {"strategy": "按错误签名查表定向修复", "applied": False}
        elif role == "Curator":
            parsed = {"sink": "ValidationRun + FailureCase", "version": "v1"}
        else:
            parsed = {"role": role, "summary": "规则模板输出"}
        return json.dumps(parsed, ensure_ascii=False), parsed


__all__ = ["CODE_TEMPLATE", "MockLLM"]
