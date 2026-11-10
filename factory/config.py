"""配置加载：路径、检索权重、沙箱上限、指标门槛与 LLM 参数一律来自 YAML。

配置模型允许存在未使用的段，因此用 ``extra="ignore"``；运行时契约则严格
``extra="forbid"``，两者用途不同。
"""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from factory.contracts.knowledge import ExtractionProfile
from factory.contracts.validation import MetricSpec, SplitSpec

logger = logging.getLogger(__name__)

# ``.env`` / 环境变量可覆盖的 LLM 字段：键为环境变量名，值为 (字段名, 解析函数)。
# ``.env.example`` 一直在文档里承诺这些开关，但此前只有 ``LLM_API_KEY`` 被真正读取，
# 改 ``LLM_PROVIDER`` 不会切换后端，容易出现「填了 key 却没有请求」的错觉。
_ENV_LLM_FIELDS: dict[str, tuple[str, Any]] = {
    "LLM_PROVIDER": ("provider", str),
    "LLM_BASE_URL": ("base_url", str),
    "LLM_MODEL": ("model", str),
    "LLM_TEMPERATURE": ("temperature", float),
    "LLM_MAX_TOKENS": ("max_tokens", int),
    "LLM_TIMEOUT_SECONDS": ("timeout_seconds", float),
    "LLM_REASONING_EFFORT": ("reasoning_effort", str),
    "LLM_THINKING": ("thinking", str),
    "LLM_CONTEXT_BUDGET_TOKENS": ("context_budget_tokens", int),
}


def _load_dotenv() -> None:
    """可选加载 ``.env``；未安装 ``python-dotenv`` 时静默跳过。"""
    with suppress(ImportError):
        from dotenv import load_dotenv
        load_dotenv()


def _env_llm_overrides() -> dict[str, Any]:
    """读取环境变量中的 LLM 覆盖项；无法解析的项记 warning 后忽略。"""
    overrides: dict[str, Any] = {}
    for env_key, (field, cast) in _ENV_LLM_FIELDS.items():
        raw = os.environ.get(env_key, "").strip()
        if not raw:
            continue
        try:
            overrides[field] = cast(raw)
        except (TypeError, ValueError):
            logger.warning("环境变量 %s=%r 无法解析，已忽略", env_key, raw)
    return overrides


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RetrievalSettings(_ConfigModel):
    """``knowledge.retrieval`` 段：Top-K、打分权重与历史证据口径。"""

    top_k: int = 5
    weights: dict[str, float] = Field(default_factory=dict)
    # 历史实验记录里的主指标列名：打分只取这一列，不再把所有数值（耗时、编号、
    # 样本量）混在一起取最大值——否则任何带数字的节点都拿到满分，信号退化。
    historical_metric_key: str = "验证集 AUC"
    # 历史记录的作废标记：命中即不进入「历史高分方案」推荐，避免把随机划分
    # 造成的虚高指标（如 EXP-08）当成可复用经验
    invalid_markers: list[str] = Field(default_factory=list)


class KnowledgeSettings(_ConfigModel):
    """``configs/default.yaml`` 的 knowledge 段。

    产物路径不在这里配置：统一由 :mod:`factory.artifacts` 按场景推导，
    避免「配置里写一份、代码里拼一份」的两套命名来源。
    """

    # 跨场景共享的材料：工程教训库这类系统级知识，换任务也要继续生效
    shared_docs: list[str] = Field(default_factory=list)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    # 同一错误签名在多少个独立 run 中出现后，才允许提升为跨运行的教训；
    # 阈值设在配置里，避免把「偶发一次失败」直接写成知识
    lesson_promote_threshold: int = Field(default=2, ge=1)
    # 注入 prompt 的教训条数上限：教训要生效，不能把上下文挤爆
    lesson_prompt_limit: int = Field(default=5, ge=0)
    # 抽取画像：文件名 → 材料类型、章节 → 节点类型。新增材料类型只改 yaml，
    # 不改 extractor；缺段时由 extractor.DEFAULT_EXTRACTION 兜底
    extraction: ExtractionProfile | None = None

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
    # 按角色定制的命中键字段：认知角色（Planner / Coder / Repairer / Curator）的
    # user prompt 含动态检索证据 / 方案 / 错误签名，每次 run 都不同，照搬全局
    # key_fields（含 user）必然 miss。为它们配置不含 user 的字段，让键退化为
    # 「角色 + system 模板」，录制一次后同一角色的调用稳定命中（B1 键策略）。
    role_key_fields: dict[str, list[str]] = Field(default_factory=dict)
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
    # 列名别名：错误列名 → 真实列名（如 PAY_1 → PAY_0，T1 陷阱）。Repairer 据此
    # 做定向修复，换数据集只需改配置，不在代码里写死某个列名。
    column_aliases: dict[str, str] = Field(default_factory=dict)


class CandidateSettings(_ConfigModel):
    """``verify_*.yaml`` 的 candidates 段：可用算法族与搜索维度，供 Planner 按任务裁剪。

    ``binnings / samplers / thresholds`` 此前只在 yaml 声明、因 ``extra="ignore"``
    在加载时被静默丢弃，导致搜索空间只有 ``model_families`` 一个自由度。补声明后
    进入候选装配：``samplers`` / ``thresholds`` 直接写入 ``CandidatePlan``（替换
    pipeline 里硬编码的 ``threshold=0.5`` / ``sampler="none"``），``binnings`` 为
    搜索扩展（A1/A2）预留，本轮不强制应用（模板暂无 WOE 渲染）。
    """

    model_families: list[str] = Field(default_factory=list)
    binnings: list[str] = Field(default_factory=list)
    samplers: list[str] = Field(default_factory=list)
    # 数值阈值（0.30/0.50）与语义值（cost_optimal）并存，语义值由 pipeline 解析
    thresholds: list[float | str] = Field(default_factory=list)
    # 历史实验记录里的模型名 → 本任务的算法族（如 ``histgb`` → hist_gradient_boosting）。
    # 图谱里的记录写的是人类可读模型名，检索要把它映射回可渲染的族；
    # 映射放在任务配置里，换数据集 / 换命名习惯只改 yaml，不在检索器写死。
    family_aliases: dict[str, list[str]] = Field(default_factory=dict)


class KnowledgeSourceSettings(_ConfigModel):
    """``verify_*.yaml`` 的 knowledge 段：该场景的能力材料目录。

    留空表示沿用 ``default.yaml`` 的全局路径；指定后该任务从自己的材料
    抽取独立子图，避免跨领域检索把无关约束注入 prompt。
    """

    docs: str = ""
    legacy: str = ""
    # 场景可额外声明共享材料；留空则沿用 default.yaml 的 knowledge.shared_docs
    shared: list[str] = Field(default_factory=list)


class IntakeElementSettings(_ConfigModel):
    """输入体检的一个要素：命中任一 ``keywords`` 即视为用户表达了该要素。"""

    key: str
    label: str = ""
    keywords: list[str] = Field(default_factory=list)
    required: bool = False
    hint: str = ""


class IntakeSettings(_ConfigModel):
    """``default.yaml`` 的 intake 段：输入引导的通用规则。

    规则全部是纯字符串匹配，不调用 LLM——入口引导必须离线、确定、可测试。
    """

    min_chars: int = Field(default=8, ge=1)
    max_examples: int = Field(default=3, ge=0)
    # 明显跑题的请求直接拦在闭环之前，不浪费一次七步运行
    off_topic_patterns: list[str] = Field(default_factory=list)
    off_topic_message: str = "这条描述看起来不是算法能力需求"
    elements: list[IntakeElementSettings] = Field(default_factory=list)
    questions: dict[str, str] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)

    @property
    def required_keys(self) -> list[str]:
        return [item.key for item in self.elements if item.required]


class TaskIntakeSettings(_ConfigModel):
    """``verify_*.yaml`` 的 intake 段：场景名、场景关键词与可直接复制的示例。

    场景关键词有两个用途：判断描述是否属于本场景，以及发现「用户其实想跑
    另一个场景」时给出 `--task-config` 建议。
    """

    scenario: str = ""
    keywords: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    dataset_hint: str = ""


class TaskSettings(_ConfigModel):
    """任务级验证配置：换任务只改 ``verify_*.yaml``，不改核心验证器。"""

    task_type: str = "tabular_binary_classification"
    dataset: DatasetSettings = Field(default_factory=DatasetSettings)
    split: SplitSpec = Field(default_factory=SplitSpec)
    metrics: list[MetricSpec] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    candidates: CandidateSettings = Field(default_factory=CandidateSettings)
    knowledge: KnowledgeSourceSettings = Field(default_factory=KnowledgeSourceSettings)
    intake: TaskIntakeSettings = Field(default_factory=TaskIntakeSettings)

    @property
    def sensitive_features(self) -> list[str]:
        value = self.constraints.get("sensitive_features", [])
        return list(value) if isinstance(value, list) else []

    @property
    def cost_ratio_fn_fp(self) -> float:
        return float(self.constraints.get("cost_ratio_fn_fp", 5.0))

    @property
    def dataset_profile(self) -> dict[str, Any]:
        """抽取器消费的数据集画像。

        标签名、敏感列与划分策略都来自本任务配置，抽取器不再内嵌某个
        数据集的这些常量；换场景只改 ``verify_*.yaml``。
        """
        name = Path(self.dataset.path).stem if self.dataset.path else ""
        return {
            "name": name,
            "target": self.dataset.target,
            "forbidden_features": list(self.dataset.forbidden_features),
            "sensitive_features": self.sensitive_features,
            "split_policy": self.split.strategy,
        }


class WorkflowSettings(_ConfigModel):
    """``configs/default.yaml`` 的 workflow 段：候选宽度与修复上限。

    这两个数值原先只写在 YAML 里、代码里另有一份硬编码，改配置不生效；
    现在由这里统一读取，缺省时退回默认值，保证旧配置仍可加载。
    """

    beam_width: int = Field(default=3, ge=1, le=10)
    max_repair_rounds: int = Field(default=3, ge=0, le=10)
    # Reviewer 语义评审否决后，Coder 带意见重生成的最大轮次：防「否决→重生成→再否决」
    # 死循环；超限后接受当前代码继续，不无限协商
    max_review_rounds: int = Field(default=1, ge=0, le=3)
    # 同一候选在 valid 段重复 fit 的次数：>=2 才有确定性证据，1 表示跳过该项
    determinism_repeat: int = Field(default=2, ge=1, le=3)
    # 是否在全部候选比较完后对最佳候选跑一次 test 终评（只报告，不参与排序）
    evaluate_on_test: bool = True
    roles: list[str] = Field(default_factory=list)


class SearchSettings(_ConfigModel):
    """``configs/default.yaml`` 的 search 段：方案 A1 的 Successive Halving 参数。

    关闭时（``halving_enabled=False``）保持「一次生成 beam_width 个候选」；
    开启时按候选预算扩空间（model_family × sampler × threshold），逐轮加预算淘汰：
    第 1 轮用 ``smoke_train_ratio`` 比例的训练行粗评全部候选，之后每轮把训练预算
    抬到全量、候选数减半，因此「进下一轮」本身是一次资源递增，而不只是重复测量。
    """

    halving_enabled: bool = False
    candidate_budget: int = Field(default=12, ge=2, le=64)
    smoke_determinism_repeat: int = Field(default=1, ge=1, le=3)
    # 粗评轮数：1 表示只有低预算粗评（旧行为），2 表示低预算→全量预算两轮淘汰
    halving_rounds: int = Field(default=2, ge=1, le=3)
    # 第 1 轮使用的训练行比例；后续轮次固定升到 1.0（全量）
    smoke_train_ratio: float = Field(default=0.4, gt=0.05, le=1.0)


class Settings(_ConfigModel):
    """配置契约的总入口。"""

    knowledge: KnowledgeSettings
    paths: PathsSettings
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)
    intake: IntakeSettings = Field(default_factory=IntakeSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)


def _read_mapping(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"配置文件顶层必须是映射：{path}")
    return payload


def load_settings(config_path: str | Path, apply_env: bool = False) -> Settings:
    """读取全局配置，返回强类型配置契约。

    ``apply_env=True`` 时再用 ``.env`` / 环境变量覆盖 LLM 段。默认关闭，
    保证单测与 CI 不被开发者本地的真实后端配置影响——否则本地填了 key 的
    开发者一跑测试就会产生真实请求与费用。
    """
    payload = _read_mapping(Path(config_path))
    for section in ("knowledge", "paths"):
        if section not in payload:
            raise ValueError(f"配置缺少 {section} 段：{config_path}")
    llm_payload = dict(payload.get("llm", {}))
    if apply_env:
        _load_dotenv()
        llm_payload.update(_env_llm_overrides())
        cassette = dict(llm_payload.get("cassette", {}))
        record = os.environ.get("FACTORY_LLM_RECORD", "").strip().lower()
        if record:
            cassette["record"] = record in {"1", "true", "yes", "on"}
        cassette_dir = os.environ.get("FACTORY_LLM_CASSETTE_DIR", "").strip()
        if cassette_dir:
            cassette["dir"] = cassette_dir
        llm_payload["cassette"] = cassette
    return Settings(
        knowledge=KnowledgeSettings(**payload["knowledge"]),
        paths=PathsSettings(**payload["paths"]),
        runtime=RuntimeSettings(**payload.get("runtime", {})),
        llm=LLMSettings(**llm_payload),
        workflow=WorkflowSettings(**payload.get("workflow", {})),
        intake=IntakeSettings(**payload.get("intake", {})),
        search=SearchSettings(**payload.get("search", {})),
    )


def load_task_settings(task_config_path: str | Path) -> TaskSettings:
    """读取任务级验证配置，门槛与约束不在代码里硬编码。"""
    return TaskSettings(**_read_mapping(Path(task_config_path)))


__all__ = [
    "CandidateSettings",
    "CassetteSettings",
    "DatasetSettings",
    "IntakeElementSettings",
    "IntakeSettings",
    "KnowledgeSettings",
    "KnowledgeSourceSettings",
    "LLMSettings",
    "PathsSettings",
    "RetrievalSettings",
    "RuntimeSettings",
    "SearchSettings",
    "Settings",
    "TaskIntakeSettings",
    "TaskSettings",
    "WorkflowSettings",
    "load_settings",
    "load_task_settings",
]
