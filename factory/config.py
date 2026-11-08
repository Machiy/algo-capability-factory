"""配置加载：路径、检索权重、沙箱资源上限一律来自 ``configs/*.yaml``。

配置模型允许存在未使用的段（llm / workflow / 任务专属字段），因此用
``extra="ignore"``；运行时契约则严格 ``extra="forbid"``，两者用途不同。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RetrievalSettings(_ConfigModel):
    """``knowledge.retrieval`` 段：Top-K 与可解释打分权重。"""

    top_k: int = 5
    weights: dict[str, float] = Field(default_factory=dict)


class KnowledgeSettings(_ConfigModel):
    """``configs/default.yaml`` 的 knowledge 段。

    YAML 中 Top-K 与权重嵌套在 ``retrieval`` 下；``top_k`` / ``weights``
    作为只读属性提供，避免调用方绕过配置而误用默认值。
    """

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


class DatasetSettings(_ConfigModel):
    """``verify_credit.yaml`` 的 dataset 段：禁入模字段与标签。"""

    target: str = ""
    id_column: str = "ID"
    forbidden_features: list[str] = Field(default_factory=list)


class TaskSettings(_ConfigModel):
    """任务级验证配置的最小子集，门槛与约束不在代码里硬编码。"""

    task_type: str = "tabular_binary_classification"
    dataset: DatasetSettings = Field(default_factory=DatasetSettings)


class Settings(_ConfigModel):
    """P1 / P2 阶段需要的配置子集。"""

    knowledge: KnowledgeSettings
    paths: PathsSettings
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)


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
    )


def load_task_settings(task_config_path: str | Path) -> TaskSettings:
    """读取任务级验证配置，供静态检查与指标插件使用。"""
    return TaskSettings(**_read_mapping(Path(task_config_path)))


__all__ = [
    "DatasetSettings",
    "KnowledgeSettings",
    "PathsSettings",
    "RetrievalSettings",
    "RuntimeSettings",
    "Settings",
    "TaskSettings",
    "load_settings",
    "load_task_settings",
]
