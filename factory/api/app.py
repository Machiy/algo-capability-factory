"""L5 接入层：FastAPI 服务与 OpenAPI 导出。

重依赖按需导入：核心闭环与 CLI 不依赖 ``fastapi`` / ``uvicorn``，只有真正
启动服务或导出文档时才加载。OpenAPI schema 由 FastAPI 从 Pydantic 模型与
路由自动生成，不手写 spec。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


class RunRequest(BaseModel):
    """``POST /run`` 请求体。"""

    spec: str = Field(description="自然语言能力描述")
    mock: bool = Field(default=False, description="强制规则模板路径")
    # run_id 会拼进报告 / 轨迹文件名，必须限制字符集，避免路径穿越
    run_id: str = Field(
        default="api",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="运行标识，用于产物命名（字母/数字/./_/-，1–64 位，禁止 ..）",
    )

    @field_validator("run_id")
    @classmethod
    def _reject_traversal(cls, value: str) -> str:
        if ".." in value:
            raise ValueError("run_id 不能包含 ..")
        return value


class CandidateSummary(BaseModel):
    """单个候选的摘要，指标只保留主指标避免响应过长。"""

    plan_id: str
    model_family: str
    passed: bool
    auc: float | None = None
    repair_rounds: int = 0


class RunResponse(BaseModel):
    """``POST /run`` 响应体，字段取自 ``RunTrace``。"""

    run_id: str
    passed: bool
    interpreter_source: str
    kg_mode: str
    candidate_count: int
    repair_count: int
    candidates: list[CandidateSummary]
    report_path: str


def create_app(root: Path | None = None) -> Any:
    """构造 FastAPI 应用；``root`` 为仓库根目录。"""
    from fastapi import FastAPI, HTTPException

    from factory import __version__

    base = Path(root) if root is not None else ROOT
    app = FastAPI(
        title="AlgoCap Factory API",
        version=__version__,
        description=(
            "基于 AI Agent 的算法能力工厂：提交自然语言能力描述，"
            "返回生成代码、四层验证结论与图谱沉淀。"
        ),
    )

    @app.get("/health", summary="健康检查")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/templates", summary="已注册算法模板")
    def templates() -> dict[str, list[str]]:
        from factory.agents import list_templates
        return {"templates": list_templates()}

    @app.post("/run", response_model=RunResponse, summary="跑通 a–g 七步闭环")
    def run(payload: RunRequest) -> RunResponse:
        from factory.config import load_settings, load_task_settings
        from factory.workflow import Workflow

        settings = load_settings(base / "configs/default.yaml")
        task = load_task_settings(base / "configs/verify_credit.yaml")
        if payload.mock:
            settings.llm = settings.llm.model_copy(
                update={"provider": "mock", "role_providers": {}}
            )
        try:
            trace = Workflow(settings, task, base).run(payload.spec, payload.run_id)
        except (FileNotFoundError, ValueError) as exc:
            # 配置 / 数据 / 标识非法属于调用方问题，回 400 并给出可读原因
            logger.warning("运行请求被拒绝：%s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # 接口层兜底，避免把堆栈直接暴露给调用方
            logger.exception("运行失败：%s", type(exc).__name__)
            raise HTTPException(
                status_code=500, detail=f"运行失败：{type(exc).__name__}"
            ) from exc
        candidates = [
            CandidateSummary(
                plan_id=item.plan_id,
                model_family=item.model_family,
                passed=item.passed,
                auc=item.metrics.get("auc"),
                repair_rounds=item.repair_rounds,
            )
            for item in sorted(trace.candidates, key=lambda c: -c.score)
        ]
        return RunResponse(
            run_id=trace.run_id,
            passed=trace.passed,
            interpreter_source=trace.interpreter_source,
            kg_mode=trace.kg_mode,
            candidate_count=len(trace.candidates),
            repair_count=len(trace.repairs),
            candidates=candidates,
            report_path=trace.report_path,
        )

    return app


def write_openapi(path: Path, root: Path | None = None) -> Path:
    """把 FastAPI 自动生成的 schema 落盘为交付物，不手写 spec。"""
    app = create_app(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    logger.info("OpenAPI 已导出：%s", path)
    return path


__all__ = [
    "CandidateSummary",
    "RunRequest",
    "RunResponse",
    "create_app",
    "write_openapi",
]
