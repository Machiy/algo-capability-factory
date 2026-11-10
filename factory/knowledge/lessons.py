"""系统级教训：把「运行记录」提炼成「跨运行成立的知识」。

沉淀失败的典型形态是把日志当知识：写下一串 `run_id + 指标 + 报错`，下次
运行时既检索不到、也用不上。本模块定义知识的判定标准与提炼路径：

- **一条教训必须回答五个问题**：什么条件下（``applies_to``）、什么现象
  （``symptom``）、为什么（``root_cause``）、怎么处置（``action``）、怎么预防
  （``prevention``）。缺根因或缺处置的条目只是记录，不提升为教训。
- **教训按系统层面分类**（``LessonScope``），因为只有系统层判断才可迁移：
  沙箱内存口径、跨平台编码、LLM 输出契约这类结论换场景依然成立。

两类来源：``assets/docs/engineering_lessons.md`` 的工程事故种子（人工确认过
的真实教训），以及失败案例按错误签名累积到达阈值后的自动提升（实测教训）。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass

from factory.contracts.knowledge import (
    EdgeType,
    KGEdge,
    KGNode,
    KnowledgeGraph,
    LessonRecord,
    LessonScope,
    NodeType,
)

logger = logging.getLogger(__name__)

# 单条教训的置信度：出现次数越多越可信，实测出现 4 次即可超过人工种子
_CONFIDENCE_BASE = 0.5
_CONFIDENCE_STEP = 0.15
_CONFIDENCE_CAP = 0.95
# 种子教训由工程事故复盘确认，但未在本任务实测，因此略低于满置信
_SEEDED_CONFIDENCE = 0.90

# 种子材料的中文表头 → 标准属性键；两边统一键名，检索与报告才能共用一套读取逻辑
LESSON_HEADER_MAP: dict[str, str] = {
    "编号": "source_id",
    "类别": "scope",
    "现象": "symptom",
    "根因": "root_cause",
    "处置": "action",
    "预防": "prevention",
    "适用面": "applies_to",
    "出现次数": "occurrences",
}

# 材料里的中文类别 → 标准 scope；未知类别归到 workflow，避免静默丢弃
SCOPE_BY_LABEL: dict[str, LessonScope] = {
    "运行环境": LessonScope.RUNTIME,
    "沙箱": LessonScope.RUNTIME,
    "数据": LessonScope.DATA,
    "LLM": LessonScope.LLM,
    "验证": LessonScope.VALIDATION,
    "图谱": LessonScope.KNOWLEDGE,
    "检索": LessonScope.KNOWLEDGE,
    "平台": LessonScope.PLATFORM,
    "编排": LessonScope.WORKFLOW,
    "流程": LessonScope.WORKFLOW,
}


@dataclass(frozen=True)
class _SignatureRule:
    """错误签名 → 系统层教训的确定性映射。

    规则只描述「这类错误的根因与处置」，不涉及具体业务结论，因此不属于把
    业务知识写死在代码里；业务知识仍然来自 ``assets/`` 的源材料。
    """

    keyword: str
    scope: LessonScope
    root_cause: str
    action: str
    prevention: str
    applies_to: str = "跨场景通用"


_SIGNATURE_RULES: tuple[_SignatureRule, ...] = (
    _SignatureRule(
        "KeyError", LessonScope.DATA,
        "生成代码按直觉命名列名（如 PAY_1），与数据字典的实际列名不一致",
        "按数据字典做列名映射后再生成代码，禁止按直觉推断列名",
        "生成前列名以 Dataset 字段表为准，必要时在沙箱内先做一次 schema 断言",
        "同一 schema 的数据集",
    ),
    _SignatureRule(
        "SchemaError", LessonScope.DATA,
        "类别枚举或字段类型与数据实际取值不符（存在未文档化类别）",
        "对未文档化取值统一归入「其他」，并在预处理器内固化映射",
        "先扫描各列取值域，再决定映射规则，不按文档假设枚举完整",
        "同一 schema 的数据集",
    ),
    _SignatureRule(
        "LeakageDetected", LessonScope.DATA,
        "预处理在训练集之外 fit，或目标编码引入了标签信息",
        "所有预处理器置于 Pipeline 内且只在训练集 fit",
        "静态检查类名是否以 ``_`` 开头、是否在 fit 中读取 y",
        "跨场景通用",
    ),
    _SignatureRule(
        "MetricSuspiciouslyHigh", LessonScope.VALIDATION,
        "指标异常高通常意味着标签泄漏或评估口径错误，而不是模型真的更好",
        "先查泄漏与划分，再谈调参",
        "指标超过理论上限的 95% 时强制人工复核",
        "跨场景通用",
    ),
    _SignatureRule(
        "MetricBelowThreshold", LessonScope.WORKFLOW,
        "单一模型族在既有特征下达不到门槛，继续调参的边际收益低于换族或换阈值口径",
        "切换模型族或按成本比重选阈值，而不是在同一个族上反复调参",
        "候选方案至少覆盖三个算法族，阈值按业务成本比选择",
        "跨场景通用",
    ),
    _SignatureRule(
        "Nondeterminism", LessonScope.RUNTIME,
        "未固定随机种子，或同一进程内多次 fit 造成状态污染",
        "显式固定 random_state，并在干净进程内重复 fit 对比",
        "沙箱以 repeat>=2 实测方差，而不是只声明 deterministic",
        "跨场景通用",
    ),
    _SignatureRule(
        "Timeout", LessonScope.RUNTIME,
        "数据规模或模型复杂度超出沙箱超时上限",
        "降复杂度（更小的树、更少迭代）或分块处理，不抬高超时上限",
        "先用 10× 数据做一次资源基准，再决定模型族",
        "跨场景通用",
    ),
    _SignatureRule(
        "Memory", LessonScope.RUNTIME,
        "内存上限按单进程 RSS 计量会失真，超限后触发 OOM 或看门狗误判",
        "按整棵进程树求峰值内存，并在超限时终止子进程",
        "资源基准与验证共用同一套内存口径",
        "跨场景通用",
    ),
    _SignatureRule(
        "ImportError", LessonScope.PLATFORM,
        "依赖不在沙箱 import 白名单内，或环境未安装",
        "改用白名单内实现（sklearn / numpy / pandas），不绕过 AST 检查",
        "生成代码只允许白名单内的库，新增依赖先改白名单与 requirements",
        "跨场景通用",
    ),
    _SignatureRule(
        "UnicodeDecode", LessonScope.PLATFORM,
        "Windows 默认编码是 GBK，读取 UTF-8 材料或产物会失败",
        "读写文件显式声明 ``encoding='utf-8'``",
        "测试在 Windows 与 Linux 双平台跑同一批断言",
        "跨场景通用",
    ),
    _SignatureRule(
        "Connection", LessonScope.LLM,
        "真实 LLM 不可达或额度耗尽，闭环不能因此中断",
        "回退 mock 或 cassette 回放，并在 trace 里标注真实来源",
        "默认路径必须是离线可跑的，真实调用只作增强",
        "跨场景通用",
    ),
    _SignatureRule(
        "JSONDecode", LessonScope.LLM,
        "LLM 返回夹带代码块或自然语言，直接 json.loads 会失败",
        "先提取首个 JSON 对象 / 代码块，再做 schema 校验",
        "prompt 里明确输出契约，解析失败要记录 reject_reason",
        "跨场景通用",
    ),
)

# 签名没命中规则时的兜底：仍然沉淀，但明确标注「未归类」，避免伪造根因
_FALLBACK_ROOT_CAUSE = "尚未归类：需要人工补充根因（当前只有现象与处置）"


def match_signature(signature: str) -> _SignatureRule | None:
    """按关键字匹配签名规则；匹配顺序固定，保证同一签名得到同一结论。"""
    lowered = (signature or "").lower()
    for rule in _SIGNATURE_RULES:
        if rule.keyword.lower() in lowered:
            return rule
    return None


def confidence_for(occurrences: int) -> float:
    """出现次数 → 置信度：出现越多越可信，但不超过人工确认的种子教训。"""
    return min(_CONFIDENCE_CAP, _CONFIDENCE_BASE + _CONFIDENCE_STEP * (max(1, occurrences) - 1))


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.lower())
    return "_".join(part for part in cleaned.split("_") if part)[:48] or "unknown"


def lesson_from_failure(failure: KGNode, threshold: int = 2) -> LessonRecord | None:
    """把累积够次数的失败案例提升为教训；未达阈值返回 ``None``。

    ``occurrences`` 由 Curator 维护为「独立 run 数」，因此同一 run 重跑不会
    让一条偶发失败变成教训，满足幂等要求。
    """
    occurrences = int(failure.attributes.get("occurrences") or 1)
    if occurrences < threshold:
        return None
    signature = str(failure.attributes.get("error_signature") or "Unknown")
    rule = match_signature(signature)
    fix = str(failure.attributes.get("fix_strategy") or "")
    scope = rule.scope if rule else LessonScope.WORKFLOW
    record = LessonRecord(
        lesson_id=f"lesson.{scope.value}.{_slug(signature)}",
        scope=scope,
        symptom=signature,
        root_cause=rule.root_cause if rule else _FALLBACK_ROOT_CAUSE,
        action=rule.action if rule else (fix or "保留失败记录供人工分析"),
        prevention=(rule.prevention if rule else
                    "把该签名补进 lessons.py 的规则表，明确根因后再复用"),
        signatures=[signature],
        applies_to=rule.applies_to if rule else "跨场景通用",
        occurrences=occurrences,
        run_ids=[str(item) for item in failure.attributes.get("run_ids") or []],
        confidence=confidence_for(occurrences),
        source="measured",
    )
    return record


def promote_failures(graph: KnowledgeGraph, threshold: int = 2
                     ) -> tuple[list[LessonRecord], list[KGNode], list[KGEdge]]:
    """从图中失败案例提炼教训，返回（新教训, 新节点, 新边）。

    已存在的教训按 ``signatures`` 去重：同一根因只沉淀一条，累积次数体现在
    ``occurrences`` 上，避免图谱被同义教训淹没。
    """
    existing_lessons = graph.by_type(NodeType.LESSON)
    covered = {
        str(signature)
        for node in existing_lessons
        for signature in node.attributes.get("signatures") or []
    }
    records: list[LessonRecord] = []
    nodes: list[KGNode] = []
    edges: list[KGEdge] = []
    for failure in graph.by_type(NodeType.FAILURE_CASE):
        signature = str(failure.attributes.get("error_signature") or "")
        if signature and signature in covered:
            continue
        record = lesson_from_failure(failure, threshold)
        if record is None:
            continue
        covered.update(record.signatures)
        records.append(record)
        nodes.append(KGNode(
            node_id=record.lesson_id,
            node_type=NodeType.LESSON,
            name=f"教训 {record.scope.value}：{record.symptom}",
            attributes=record.to_attributes(),
        ))
        edges.append(KGEdge(source=record.lesson_id, target=failure.node_id,
                            edge_type=EdgeType.DERIVED_FROM))
    if records:
        logger.info("教训提升：%d 条（阈值 %d 次独立运行）", len(records), threshold)
    return records, nodes, edges


def seed_lesson_attributes(headers: tuple[str, ...], cells: tuple[str, ...],
                           section: str) -> dict[str, object]:
    """把工程教训材料的表格行规范化为标准属性键。

    材料用中文表头便于人读，图谱与检索用英文键便于代码读；这一步只做键名
    与 scope 枚举的规范化，不改写任何内容。
    """
    attributes: dict[str, object] = {}
    for header, value in zip(headers, cells):
        key = LESSON_HEADER_MAP.get(header.strip(), header.strip())
        text = value.strip()
        if not text:
            continue
        if key == "scope":
            scope = SCOPE_BY_LABEL.get(text)
            attributes["scope"] = (scope or LessonScope.WORKFLOW).value
            attributes["scope_label"] = text
        elif key == "occurrences":
            digits = "".join(ch for ch in text if ch.isdigit())
            attributes["occurrences"] = int(digits) if digits else 1
        else:
            attributes[key] = text
    attributes["section"] = section
    attributes["record_kind"] = "knowledge"
    attributes.setdefault("applies_to", "跨场景通用")
    attributes.setdefault("occurrences", 1)
    attributes.setdefault("run_ids", [])
    attributes.setdefault("signatures", [])
    attributes["confidence"] = _SEEDED_CONFIDENCE
    attributes["source"] = "seeded"
    return attributes


def lesson_records(graph: KnowledgeGraph) -> list[LessonRecord]:
    """把图里的教训节点读回契约对象，供检索与报告排序。"""
    records: list[LessonRecord] = []
    for node in graph.by_type(NodeType.LESSON):
        attributes = node.attributes
        records.append(LessonRecord(
            lesson_id=node.node_id,
            scope=LessonScope(str(attributes.get("scope", "workflow"))),
            symptom=str(attributes.get("symptom", node.name)),
            root_cause=str(attributes.get("root_cause", "")),
            action=str(attributes.get("action", "")),
            prevention=str(attributes.get("prevention", "")),
            signatures=[str(item) for item in attributes.get("signatures") or []],
            applies_to=str(attributes.get("applies_to", "")),
            occurrences=int(attributes.get("occurrences") or 1),
            run_ids=[str(item) for item in attributes.get("run_ids") or []],
            confidence=float(attributes.get("confidence") or 0.5),
            source=str(attributes.get("source", "measured")),
        ))
    return records


def _natural_key(value: str) -> tuple[tuple[int, object], ...]:
    """LE2 排在 LE10 之前的自然序：避免 lesson_id 字典序把重要条目挤出 Top-N。"""
    return tuple((0, int(part)) if part.isdigit() else (1, part)
                 for part in re.split(r"(\d+)", value))


def rank_lessons(graph: KnowledgeGraph, scopes: Iterable[LessonScope] | None = None,
                 limit: int = 5) -> list[LessonRecord]:
    """排序口径：本任务实测教训优先 → 出现次数 → 置信度 → 编号自然序。

    实测优先的理由很直接：它说明「这个系统在这个任务上真的踩过」，比通用
    工程教训更该指导本轮生成代码；种子教训仍在图谱与报告中，不会消失。

    可选按 scope 过滤：``data`` 类教训只在同 schema 场景有效，跨场景检索时
    由调用方决定是否排除。
    """
    allowed = set(scopes) if scopes is not None else None
    records = [record for record in lesson_records(graph)
               if allowed is None or record.scope in allowed]
    records.sort(key=lambda item: (item.source != "measured", -item.occurrences,
                                   -item.confidence, _natural_key(item.lesson_id)))
    return records[:limit]


__all__ = [
    "LESSON_HEADER_MAP",
    "SCOPE_BY_LABEL",
    "confidence_for",
    "lesson_from_failure",
    "lesson_records",
    "match_signature",
    "promote_failures",
    "rank_lessons",
    "seed_lesson_attributes",
]
