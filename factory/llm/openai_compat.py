"""DeepSeek OpenAI 兼容实时调用，可选录制脱敏 cassette。

凭据只从环境变量 / ``.env`` 读取；未配置时明确报错，不静默回退到 mock。
"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from factory.config import LLMSettings
from factory.contracts.llm import Cassette, LLMRequest, LLMResponse, LLMUsage
from factory.llm.base import BaseLLM
from factory.llm.cassette import cassette_path, load_cassette, make_entry, save_cassette

logger = logging.getLogger(__name__)

# 模型常把结构化输出包在 ```json ... ``` 里；剥离后再 json.loads
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class MissingCredentialError(RuntimeError):
    """缺少 LLM API 凭据。"""


class OpenAICompatLLM(BaseLLM):
    """真实 API 路径；``cassette.record=true`` 时把响应脱敏后入库。"""

    def __init__(self, settings: LLMSettings, root: Path | None = None) -> None:
        with suppress(ImportError):
            from dotenv import load_dotenv
            load_dotenv()
        self.settings = settings
        self.root = root or Path.cwd()
        api_key = os.environ.get(settings.api_key_env, "").strip()
        if not api_key:
            raise MissingCredentialError(
                f"未设置环境变量 {settings.api_key_env}；请在 .env 或环境变量中配置，"
                "切勿写入仓库、日志或 cassette"
            )
        from openai import OpenAI
        self._api_key = api_key
        self._client = OpenAI(
            api_key=api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        override = self.settings.role_overrides.get(request.role, {})
        effort = override.get("reasoning_effort", request.reasoning_effort)
        completion = self._client.chat.completions.create(
            model=request.model or self.settings.model,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            extra_body={
                "thinking": {"type": request.thinking},
                "reasoning_effort": effort,
            },
        )
        raw = completion.choices[0].message.content or ""
        usage = completion.usage
        result = LLMResponse(
            raw=raw,
            parsed=self._parse(raw),
            model=request.model or self.settings.model,
            usage=LLMUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage, "total_tokens", 0) or 0,
            ),
            source="deepseek_api",
        )
        if self.settings.cassette.record:
            self._record(request, result)
        logger.info("DeepSeek 实时调用完成：role=%s model=%s", request.role, result.model)
        return result

    @staticmethod
    def _parse(raw: str) -> dict[str, Any]:
        """解析模型输出。

        真实模型常把 JSON 包在 ```` ```json ```` 里，或前後带一句解释；
        只认纯 JSON 会让下游拿到空 payload（实测 Planner 返回空候选，
        工作流在 generate 节点 IndexError）。这里先剥离代码块再解析。
        """
        text = (raw or "").strip()
        fenced = _JSON_FENCE_RE.search(text)
        if fenced:
            text = fenced.group(1).strip()
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return {"text": raw}
        return parsed if isinstance(parsed, dict) else {"items": parsed}

    def _record(self, request: LLMRequest, response: LLMResponse) -> None:
        path = cassette_path(self.root / self.settings.cassette.dir, self.settings.model)
        cassette = load_cassette(path) or Cassette(
            cassette_version=self.settings.cassette.version,
            model=self.settings.model,
            params={
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "reasoning_effort": self.settings.reasoning_effort,
                "thinking": self.settings.thinking,
            },
            source="deepseek_api",
            recorded_at=datetime.now().isoformat(timespec="seconds"),
        )
        entry = make_entry(request, response, self.settings.cassette, self._api_key)
        cassette.entries = [item for item in cassette.entries if item.key != entry.key]
        cassette.entries.append(entry)
        save_cassette(path, cassette, self.settings.cassette, self._api_key)
        logger.info("已录制脱敏 cassette：%s", path)


__all__ = ["MissingCredentialError", "OpenAICompatLLM"]
