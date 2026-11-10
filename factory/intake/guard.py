"""入口输入引导：把「用户可能瞎说」挡在七步闭环之前。

三条规则，全部离线、确定、可单测：

1. **空白 / 过短 / 跑题** → ``REJECT``，直接给出可复制的合格示例；
2. **缺关键要素**（目标 / 数据 / 指标 / 约束）→ ``CLARIFY``，给追问，允许继续；
3. **描述的是另一个场景**（例如在信用卡任务里写短信分类）→ ``CLARIFY``，附上
   应使用的 ``--task-config``。

规则来自 ``configs/default.yaml`` 的 ``intake`` 段与各任务 ``verify_*.yaml``
的 ``intake`` 段，换场景只改 yaml。判定不调用 LLM，保证断网可复现、结论稳定。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from factory.config import IntakeSettings, TaskIntakeSettings
from factory.contracts.intake import IntakeGuidance, IntakeIssue, IntakeVerdict

logger = logging.getLogger(__name__)

# 用户可以直接引用图谱里已沉淀的能力 id，例如「复刻 cap.credit.default.v1」
_CAPABILITY_ID = re.compile(r"cap\.[a-z0-9._-]+")

# 一个中文/英文词都算有效信息；只有符号或空白的描述一定不可执行
_MEANINGFUL = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


class SpecRejected(ValueError):
    """描述被判定不可执行；异常携带完整引导，入口层据此打印建议。"""

    def __init__(self, guidance: IntakeGuidance) -> None:
        self.guidance = guidance
        codes = ", ".join(issue.code for issue in guidance.issues) or "reject"
        super().__init__(f"能力描述不可执行（{codes}）；{render_guidance(guidance)}")


def _hits(text: str, keywords: list[str]) -> list[str]:
    """返回命中的关键词（去重、保序），统一小写做包含匹配。"""
    matched: list[str] = []
    for keyword in keywords:
        item = keyword.strip().lower()
        if item and item in text and item not in matched:
            matched.append(item)
    return matched


class IntakeGuide:
    """按配置体检自然语言描述，并给出「菜单式」引导内容。

    ``configs_dir`` 用于扫描其余 ``verify_*.yaml``，从而发现场景错配；
    ``graph_path`` 用于列出图谱里已沉淀的能力 id，方便用户直接引用。
    """

    def __init__(self, intake: IntakeSettings, task_intake: TaskIntakeSettings,
                 configs_dir: Path | None = None,
                 task_config: str = "configs/verify_credit.yaml",
                 graph_path: Path | None = None) -> None:
        self.intake = intake
        self.task_intake = task_intake
        self.configs_dir = configs_dir
        self.task_config = task_config
        self.graph_path = graph_path
        self.scenarios = self._scan_scenarios()

    # ------------------------------------------------------------------ 体检
    def review(self, spec: str) -> IntakeGuidance:
        """对一条描述给出结论、缺失要素、追问与示例。"""
        text = (spec or "").strip()
        scenario = self.task_intake.scenario
        matched_elements, missing_elements = self._match_elements(text)
        score = self._score(matched_elements)
        issues: list[IntakeIssue] = []
        verdict = IntakeVerdict.OK

        scenario_hits = _hits(text.lower(), self.task_intake.keywords)
        capability_ref = _CAPABILITY_ID.search(text)

        # 1) 空白 / 过短：没有可解析的信息，直接拒
        if not text:
            issues.append(IntakeIssue(code="empty", message="未提供任何能力描述",
                                      hint="用一句话说明要预测/分类什么、用什么数据"))
            verdict = IntakeVerdict.REJECT
        elif len(text) < self.intake.min_chars or not _MEANINGFUL.search(text):
            issues.append(IntakeIssue(
                code="too_short",
                message=f"描述只有 {len(text)} 个字符，信息不足以规划方案",
                hint=f"至少写清目标、数据与评价方式（建议 ≥ {self.intake.min_chars} 字）",
            ))
            verdict = IntakeVerdict.REJECT

        # 2) 跑题：命中闲聊/创作类模式且完全不沾当前场景
        off_topic = _hits(text.lower(), self.intake.off_topic_patterns)
        if off_topic and verdict is not IntakeVerdict.REJECT:
            if scenario_hits or capability_ref:
                issues.append(IntakeIssue(
                    code="off_topic_suspect",
                    message=f"描述含「{off_topic[0]}」等非算法表述，可能是误输入",
                    hint="确认是在描述可执行的建模任务，而不是创作或咨询类需求",
                ))
                verdict = IntakeVerdict.CLARIFY
            else:
                issues.append(IntakeIssue(
                    code="off_topic",
                    message=f"{self.intake.off_topic_message}（命中：{', '.join(off_topic)}）",
                    hint="本工厂只承接预测 / 分类 / 回归 / 复刻类算法能力需求",
                ))
                verdict = IntakeVerdict.REJECT

        # 3) 场景错配：另一个任务的场景关键词命中更多时，直接给出切换命令
        other = self._best_other_scenario(text.lower())
        if other is not None and (other["hits"] > len(scenario_hits)
                                  or not scenario_hits):
            issues.append(IntakeIssue(
                code="task_mismatch",
                message=(f"描述更像「{other['scenario']}」场景，"
                         f"而当前任务配置是「{scenario or '未命名'}」"),
                hint=f"改用该场景重跑：--task-config {other['task_config']}",
            ))
            if verdict is IntakeVerdict.OK:
                verdict = IntakeVerdict.CLARIFY

        # 4) 缺必填要素：可继续，但把追问列出来
        required_missing = [key for key in missing_elements if key in self.intake.required_keys]
        capability_note = ""
        if required_missing and verdict is not IntakeVerdict.REJECT:
            if capability_ref:
                # 直接引用已沉淀能力 id 时，缺字段由图谱补齐，不算问题，
                # 但要在结论里说明，避免「完备度低却判 OK」看起来自相矛盾
                missing_elements = [key for key in missing_elements
                                    if key not in required_missing]
                required_missing = []
                capability_note = (f"已引用能力 id {capability_ref.group(0)}，"
                                   "未描述的字段沿用图谱与本任务配置")
                issues.append(IntakeIssue(code="capability_ref",
                                          message=capability_note))
            else:
                verdict = IntakeVerdict.CLARIFY
                for key in required_missing:
                    issues.append(IntakeIssue(
                        code=f"missing_{key}",
                        message=f"缺少「{self._label(key)}」",
                        hint=self._hint(key),
                    ))

        # 结论 OK 时不再追问，避免「要素齐全」与「请补充」同时出现
        questions: list[str] = []
        if verdict is not IntakeVerdict.OK:
            questions = [self._question(key) for key in missing_elements][:3]
            questions = [item for item in questions if item]
        return IntakeGuidance(
            verdict=verdict,
            score=score,
            scenario=scenario,
            matched_elements=matched_elements,
            missing_elements=missing_elements,
            issues=issues,
            questions=questions,
            examples=self.examples(extra=other["examples"] if other else None),
            elements=self._element_lines(),
            suggestion=capability_note or self._suggestion(verdict, other),
        )

    # ------------------------------------------------------------ 引导内容
    def examples(self, extra: list[str] | None = None) -> list[str]:
        """示例优先级：错配场景（如果有）> 当前场景 > 全局，去重后截断。"""
        merged: list[str] = []
        for item in [*(extra or []), *self.task_intake.examples, *self.intake.examples]:
            text = item.strip()
            if text and text not in merged:
                merged.append(text)
        return merged[: self.intake.max_examples]

    def describe(self) -> dict[str, Any]:
        """菜单式引导内容，供 ``factory guide`` 与 ``GET /intake/guide`` 复用。"""
        return {
            "scenario": self.task_intake.scenario,
            "task_config": self.task_config,
            "dataset_hint": self.task_intake.dataset_hint,
            "min_chars": self.intake.min_chars,
            "elements": [
                {"key": item.key, "label": self._label(item.key),
                 "required": item.required, "hint": item.hint}
                for item in self.intake.elements
            ],
            "questions": [self._question(item.key) for item in self.intake.elements],
            "examples": self.examples(),
            "scenarios": self.scenarios,
            "capabilities": self._capabilities(),
        }

    # -------------------------------------------------------------- 内部实现
    def _match_elements(self, text: str) -> tuple[list[str], list[str]]:
        lowered = text.lower()
        matched: list[str] = []
        missing: list[str] = []
        for element in self.intake.elements:
            if _hits(lowered, element.keywords):
                matched.append(element.key)
            else:
                missing.append(element.key)
        return matched, missing

    def _score(self, matched: list[str]) -> float:
        total = 0.0
        earned = 0.0
        for element in self.intake.elements:
            weight = 2.0 if element.required else 1.0
            total += weight
            if element.key in matched:
                earned += weight
        return round(earned / total, 3) if total else 1.0

    def _label(self, key: str) -> str:
        for element in self.intake.elements:
            if element.key == key:
                return element.label or element.key
        return key

    def _hint(self, key: str) -> str:
        for element in self.intake.elements:
            if element.key == key:
                return element.hint
        return ""

    def _question(self, key: str) -> str:
        return self.intake.questions.get(key, self._hint(key))

    def _element_lines(self) -> list[str]:
        lines: list[str] = []
        for element in self.intake.elements:
            tag = "必填" if element.required else "建议"
            lines.append(f"[{tag}] {self._label(element.key)}：{element.hint}")
        return lines

    def _suggestion(self, verdict: IntakeVerdict, other: dict[str, Any] | None) -> str:
        if other is not None and verdict is not IntakeVerdict.REJECT:
            return f"若确实要跑「{other['scenario']}」，加 --task-config {other['task_config']}"
        if verdict is IntakeVerdict.REJECT:
            return "按下方示例改写后重试；确认无误可加 --force 跳过引导"
        if verdict is IntakeVerdict.CLARIFY:
            return "补齐缺失要素会更稳；也可直接继续，Agent 按任务配置补全缺省约束"
        return "描述要素齐全，可直接进入七步闭环"

    def _scan_scenarios(self) -> list[dict[str, Any]]:
        """扫描 ``configs/verify_*.yaml``，供菜单展示与错配检测。"""
        if self.configs_dir is None or not self.configs_dir.is_dir():
            return []
        found: list[dict[str, Any]] = []
        for path in sorted(self.configs_dir.glob("verify_*.yaml")):
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:  # 单个坏配置不该拖垮引导
                logger.warning("读取场景配置失败：%s（%s）", path.name, exc)
                continue
            intake = payload.get("intake") or {}
            if not isinstance(intake, dict):
                continue
            config = f"configs/{path.name}"
            found.append({
                "scenario": str(intake.get("scenario") or path.stem),
                "task_config": config,
                "task_type": str(payload.get("task_type", "")),
                "keywords": [str(item) for item in intake.get("keywords") or []],
                "examples": [str(item) for item in intake.get("examples") or []],
            })
        return found

    def _best_other_scenario(self, lowered: str) -> dict[str, Any] | None:
        """当前场景之外命中关键词最多的场景；命中数相同则不提示。"""
        current = Path(self.task_config).name
        best: dict[str, Any] | None = None
        for item in self.scenarios:
            if Path(item["task_config"]).name == current:
                continue
            count = len(_hits(lowered, item["keywords"]))
            if count >= 2 and (best is None or count > best["hits"]):
                best = {**item, "hits": count}
        return best

    def _capabilities(self) -> list[dict[str, Any]]:
        """从回写图谱里列出已沉淀能力，让用户可以直接引用 id 复刻。

        图谱里能力节点数量多（数据陷阱、实验结论各自成节点），逐条列出会淹没
        引导信息；这里按 ``cap.<来源>`` 前缀归组，只展示组名、条数与一条样例。
        """
        if self.graph_path is None or not self.graph_path.is_file():
            return []
        try:
            payload = json.loads(self.graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取图谱失败，引导菜单不含能力清单：%s", exc)
            return []
        grouped: dict[str, dict[str, Any]] = {}
        for node in payload.get("nodes", []):
            if node.get("node_type") != "Capability":
                continue
            node_id = str(node.get("node_id", ""))
            head = node_id.split(".")
            group_key = ".".join(head[:2]) if len(head) > 2 else node_id
            group = grouped.setdefault(
                group_key, {"node_id": group_key, "name": "", "count": 0}
            )
            group["count"] += 1
            if not group["name"]:
                group["name"] = str(node.get("name", ""))
        return list(grouped.values())[:6]


def render_guidance(guidance: IntakeGuidance) -> str:
    """把体检结论渲染成终端可读文本（CLI 与异常信息共用）。"""
    head = {
        IntakeVerdict.OK: "描述要素齐全",
        IntakeVerdict.CLARIFY: "描述可继续，但建议补充",
        IntakeVerdict.REJECT: "描述不可执行，已拦在闭环之前",
    }[guidance.verdict]
    lines = [f"[输入引导] {head}（完备度 {guidance.score:.2f}）"]
    if guidance.matched_elements:
        lines.append(f"  - 已表达：{'、'.join(guidance.matched_elements)}")
    if guidance.missing_elements:
        lines.append(f"  - 未提及：{'、'.join(guidance.missing_elements)}")
    for issue in guidance.issues:
        hint = f"；建议：{issue.hint}" if issue.hint else ""
        lines.append(f"  - {issue.message}{hint}")
    if guidance.questions:
        lines.append("  - 请补充：")
        lines.extend(f"      {index}) {question}"
                     for index, question in enumerate(guidance.questions, start=1))
    if guidance.examples:
        lines.append("  - 可直接复制的示例：")
        lines.extend(f"      {index}) {example}"
                     for index, example in enumerate(guidance.examples, start=1))
    if guidance.suggestion:
        lines.append(f"  - {guidance.suggestion}")
    return "\n".join(lines)


def render_menu(guide: IntakeGuide) -> str:
    """渲染「输入引导菜单」：要素、示例、可用场景与已沉淀能力。"""
    info = guide.describe()
    lines = ["AlgoCap Factory · 能力描述引导", ""]
    lines.append(f"当前场景：{info['scenario'] or '未命名'}（{info['task_config']}）")
    if info["dataset_hint"]:
        lines.append(f"数据集：{info['dataset_hint']}")
    lines.extend(["", "一条可执行的描述建议覆盖以下要素："])
    for item in info["elements"]:
        tag = "必填" if item["required"] else "建议"
        lines.append(f"  [{tag}] {item['label']}：{item['hint']}")
    if info["examples"]:
        lines.extend(["", "合格示例（可直接复制）："])
        lines.extend(f"  - {example}" for example in info["examples"])
    if len(info["scenarios"]) > 1:
        lines.extend(["", "可用场景（换 --task-config 即可迁移）："])
        for item in info["scenarios"]:
            lines.append(f"  - {item['task_config']}  {item['scenario']}")
            for example in item["examples"][:1]:
                lines.append(f"      示例：{example}")
    if info["capabilities"]:
        lines.extend(["", "图谱里已沉淀的能力（可在描述中直接引用 id 复刻）："])
        lines.extend(
            f"  - {item['node_id']}（{item['count']} 条）样例：{item['name']}"
            for item in info["capabilities"]
        )
    if info["questions"]:
        lines.extend(["", "描述时可参考这些提问："])
        lines.extend(f"  - {question}" for question in info["questions"])
    lines.extend(["", "非交互环境请直接用 --spec 传入描述。"])
    return "\n".join(lines)


__all__ = ["IntakeGuide", "SpecRejected", "render_guidance", "render_menu"]
