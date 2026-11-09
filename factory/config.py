"""配置加载：路径、检索权重、沙箱上限、指标门槛与 LLM 参数一律来自 YAML。

配置模型允许存在未使用的段，因此用 ``extra="ignore"``；运行时契约则严格
``extra="forbid"``，两者用途不同。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from factory.contracts.validation import MetricSpec, SplitSpec


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RetrievalSettings(_ConfigModel):
    """``knowledge.retrieval`` 段：Top-K 与可解释打分权重。"""

    top_k: int = 5
    weights: dict[str, float] = Field(default_factory=dict)


class KnowledgeSettings(_ConfigModel):
    """``configs/default.yaml`` 的 knowledge 段。"""

    graph_path: str
    sqlite_path: str
    extraction_results: list[str] = Field(default_factory=list)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)

    @property
    def top_k(self) -> int:
        return self.retrieval.top_k

    @property
    def weights(self) -> dict[str, float]:
        return self.retrieval.weights


class PathsSettings(_ConfigModel):
    """``configs/default.yaml`` 的 paths 段。"""

    data: str
    docs: str
    legacy: str
    generated: str
    reports: str
    kg: str
    runs: str


class RuntimeSettings(_ConfigModel):
    """``configs/default.yaml`` 的 runtime 段：沙箱资源与 AST 白名单。"""

    timeout_seconds: int = 60
    memory_limit_mb: int = 2048
    allowed_imports: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)


class CassetteSettings(_ConfigModel):
    """``llm.cassette`` 段：录制回放的命中键、脱敏字段与未命中策略。"""

    dir: str = "assets/llm_cassettes"
    version: int = 1
    record: bool = False
    on_miss: str = "error"
    key_fields: list[str] = Field(default_factory=list)
    strip: list[str] = Field(default_factory=list)


class LLMSettings(_ConfigModel):
    """``configs/default.yaml`` 的 llm 段；凭据只存环境变量名。"""

    provider: str = "mock"
    base_url: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 8192
    context_budget_tokens: int = 32000
    timeout_seconds: int = 180
    reasoning_effort: str = "high"
    thinking: str = "enabled"
    role_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)
    role_providers: dict[str, str] = Field(default_factory=dict)
    api_key_env: str = "LLM_API_KEY"
    cassette: CassetteSettings = Field(default_factory=CassetteSettings)


class DatasetSettings(_ConfigModel):
    """``verify_*.yaml`` 的 dataset 段：禁入模字段、标签与文本列。

    ``text_column`` 非空即表示该任务以原始文本为输入（文本分类），
    此时核心流程不再按表格列名选特征，改由模板声明 ``TEXT_COLUMN``。
    """

    path: str = ""
    target: str = ""
    id_column: str = "ID"
    text_column: str = ""
    forbidden_features: list[str] = Field(default_factory=list)


class CandidateSettings(_ConfigModel):
    """``verify_*.yaml`` 的 candidates 段：可用算法族，供 Planner 按任务裁剪。"""

    model_families: list[str] = Field(default_factory=list)


class KnowledgeSourceSettings(_ConfigModel):
    """``verify_*.yaml`` 的 knowledge 段：该场景的能力材料目录。

    留空表示沿用 ``default.yaml`` 的全局路径；指定后该任务从自己的材料
    抽取独立子图，避免跨领域检索把无关约束注入 prompt。
    """

    docs: str = ""
    legacy: str = ""


class TaskSettings(_ConfigModel):
    """任务级验证配置：换任务只改 ``verify_*.yaml``，不改核心验证器。"""

    task_type: str = "tabular_binary_classification"
    dataset: DatasetSettings = Field(default_factory=DatasetSettings)
    split: SplitSpec = Field(default_factory=SplitSpec)
    metrics: list[MetricSpec] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    candidates: CandidateSettings = Field(default_factory=CandidateSettings)
    knowledge: KnowledgeSourceSettings = Field(default_factory=KnowledgeSourceSettings)

    @property
    def sensitive_features(self) -> list[str]:
        value = self.constraints.get("sensitive_features", [])
        return list(value) if isinstance(value, list) else []

    @property
    def cost_ratio_fn_fp(self) -> float:
        return float(self.constraints.get("cost_ratio_fn_fp", 5.0))


class Settings(_ConfigModel):
    """配置契约的总入口。"""

    knowledge: KnowledgeSettings
    paths: PathsSettings
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)


def _read_mapping(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"配置文件顶层必须是映射：{path}")
    return payload


def load_settings(config_path: str | Path) -> Settings:
    """读取全局配置，返回强类型配置契约。"""
    payload = _read_mapping(Path(config_path))
    for section in ("knowledge", "paths"):
        if section not in payload:
            raise ValueError(f"配置缺少 {section} 段：{config_path}")
    return Settings(
        knowledge=KnowledgeSettings(**payload["knowledge"]),
        paths=PathsSettings(**payload["paths"]),
        runtime=RuntimeSettings(**payload.get("runtime", {})),
        llm=LLMSettings(**payload.get("llm", {})),
    )


def load_task_settings(task_config_path: str | Path) -> TaskSettings:
    """读取任务级验证配置，门槛与约束不在代码里硬编码。"""
    return TaskSettings(**_read_mapping(Path(task_config_path)))


__all__ = [
    "CandidateSettings",
    "CassetteSettings",
    "DatasetSettings",
    "KnowledgeSettings",
    "LLMSettings",
    "PathsSettings",
    "RetrievalSettings",
    "RuntimeSettings",
    "Settings",
    "TaskSettings",
    "load_settings",
    "load_task_settings",
]
