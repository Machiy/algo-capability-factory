"""L5 接入层：FastAPI 服务与 OpenAPI 导出。

重依赖按需导入：核心闭环与 CLI 不依赖 ``fastapi`` / ``uvicorn``，只有真正
启动服务或导出文档时才加载。OpenAPI schema 由 FastAPI 从 Pydantic 模型与
路由自动生成，不手写 spec。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from factory.artifacts import kg_stem, scene_of
from factory.contracts.intake import IntakeGuidance

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

# 任务配置只允许引用 configs 下已存在的 verify_*.yaml，避免路径穿越读任意文件
_TASK_CONFIG_PATTERN = re.compile(r"^configs/verify_[a-z0-9_]+\.yaml$")


class RunRequest(BaseModel):
    """``POST /run`` 请求体。"""

    spec: str = Field(description="自然语言能力描述")
    mock: bool = Field(default=False, description="强制规则模板路径")
    force: bool = Field(
        default=False,
        description="跳过入口引导拦截；描述被判不可执行时仍强制跑完七步",
    )
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
    """单个候选的摘要：指标按任务透出，分类 / 文本 / 回归都适用。

    早期版本固定返回 ``auc``，换成文本或回归任务时该字段恒为 ``null``；
    现在给出完整 ``metrics``，并用 ``primary_metric`` 指明当前任务的主指标。
    """

    plan_id: str
    model_family: str
    passed: bool
    metrics: dict[str, float | None] = Field(default_factory=dict)
    primary_metric: str = ""
    primary_value: float | None = None
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
    # 终评结果（test 段一次性评估）；未启用终评时为空
    test_metrics: dict[str, float | None] = Field(default_factory=dict)
    report_path: str
    # 入口体检结论：调用方据此提示用户「哪一项没写清楚」
    intake: IntakeGuidance | None = None


class IntakeReviewRequest(BaseModel):
    """``POST /intake/review`` 请求体：只体检描述，不触发运行。"""

    spec: str = Field(description="待体检的自然语言能力描述")
    task_config: str = Field(
        default="configs/verify_credit.yaml",
        description="按该任务的要素与示例体检，如 configs/verify_text.yaml",
    )

    @field_validator("task_config")
    @classmethod
    def _check_task_config(cls, value: str) -> str:
        if not _TASK_CONFIG_PATTERN.match(value):
            raise ValueError("task_config 只能是 configs/verify_*.yaml")
        return value


def _build_guide(base: Path, task_config: str) -> Any:
    """构造入口引导器：规则来自 default.yaml 与任务 yaml 的 intake 段。"""
    from factory.config import load_settings, load_task_settings
    from factory.intake import IntakeGuide

    settings = load_settings(base / "configs/default.yaml")
    task = load_task_settings(base / task_config)
    return IntakeGuide(
        settings.intake, task.intake,
        configs_dir=base / "configs",
        task_config=task_config,
        graph_path=(base / settings.paths.kg
                    / f"{kg_stem(scene_of(task_config), 'after_run')}.json"),
    )


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

    @app.get("/intake/guide", summary="能力描述引导菜单")
    def intake_guide(task_config: str = "configs/verify_credit.yaml") -> dict[str, Any]:
        """要素清单、可复制示例、可用场景与已沉淀能力，供前端做输入引导。"""
        if not _TASK_CONFIG_PATTERN.match(task_config) or not (base / task_config).is_file():
            raise HTTPException(status_code=400,
                                detail="task_config 只能是已存在的 configs/verify_*.yaml")
        return _build_guide(base, task_config).describe()

    @app.post("/intake/review", response_model=IntakeGuidance,
              summary="体检一条能力描述（不触发运行）")
    def intake_review(payload: IntakeReviewRequest) -> IntakeGuidance:
        if not (base / payload.task_config).is_file():
            raise HTTPException(status_code=400,
                                detail=f"任务配置不存在：{payload.task_config}")
        return _build_guide(base, payload.task_config).review(payload.spec)

    @app.post("/run", response_model=RunResponse, summary="跑通 a–g 七步闭环")
    def run(payload: RunRequest) -> RunResponse:
        from factory.config import load_settings, load_task_settings
        from factory.intake import SpecRejected
        from factory.workflow import Workflow

        settings = load_settings(base / "configs/default.yaml",
                                 apply_env=not payload.mock)
        task = load_task_settings(base / "configs/verify_credit.yaml")
        if payload.mock:
            settings.llm = settings.llm.model_copy(
                update={"provider": "mock", "role_providers": {}}
            )
        try:
            workflow = Workflow(settings, task, base)
            trace = workflow.run(payload.spec, payload.run_id, force=payload.force)
        except SpecRejected as exc:
            # 描述不可执行：422 返回结构化引导，调用方据此提示用户改写
            logger.warning("输入被入口引导拦下：%s",
                           [item.code for item in exc.guidance.issues])
            raise HTTPException(status_code=422, detail={
                "message": "能力描述不可执行，请按引导改写后重试",
                "guidance": exc.guidance.model_dump(mode="json"),
            }) from exc
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
                metrics=dict(item.metrics),
                primary_metric=workflow.metric_name,
                primary_value=item.metrics.get(workflow.metric_name),
                repair_rounds=item.repair_rounds,
            )
            for item in sorted(trace.candidates, key=lambda c: -c.score)
        ]
        test_eval = getattr(trace, "test_evaluation", None)
        return RunResponse(
            run_id=trace.run_id,
            passed=trace.passed,
            interpreter_source=trace.interpreter_source,
            kg_mode=trace.kg_mode,
            candidate_count=len(trace.candidates),
            repair_count=len(trace.repairs),
            candidates=candidates,
            test_metrics=dict(test_eval.metrics) if test_eval is not None else {},
            report_path=trace.report_path,
            intake=getattr(trace, "intake", None),
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
    "IntakeReviewRequest",
    "RunRequest",
    "RunResponse",
    "create_app",
    "write_openapi",
]
