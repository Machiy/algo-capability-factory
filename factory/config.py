"""配置加载：路径、检索权重等一律来自 ``configs/*.yaml``，不在代码里硬编码。

配置模型允许存在未使用的段（llm / workflow / runtime），因此这里用
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


class Settings(_ConfigModel):
    """P1 阶段需要的配置子集。"""

    knowledge: KnowledgeSettings
    paths: PathsSettings


def load_settings(config_path: str | Path) -> Settings:
    """读取并校验 YAML 配置，返回强类型配置契约。

    Raises:
        FileNotFoundError: 配置文件不存在。
        TypeError: 配置文件顶层不是映射。
        ValueError: 缺少必需的配置段。
    """
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"配置文件顶层必须是映射：{path}")
    for section in ("knowledge", "paths"):
        if section not in payload:
            raise ValueError(f"配置缺少 {section} 段：{path}")
    return Settings(
        knowledge=KnowledgeSettings(**payload["knowledge"]),
        paths=PathsSettings(**payload["paths"]),
    )


__all__ = [
    "KnowledgeSettings",
    "PathsSettings",
    "RetrievalSettings",
    "Settings",
    "load_settings",
]
