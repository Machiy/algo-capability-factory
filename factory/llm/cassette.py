"""Cassette 命中键、脱敏与读写。

落盘前一律清除 header / 完整 endpoint / key / token；命中键包含所有影响
输出的参数，避免不同思考强度下错配回放。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from factory.config import CassetteSettings
from factory.contracts.llm import Cassette, CassetteEntry, LLMRequest, LLMResponse

REDACTED = "[REDACTED]"
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+\S+"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*\S+"),
)
_DEFAULT_KEY_FIELDS = ["role", "system", "user", "model", "temperature", "max_tokens"]


def compute_key(request: LLMRequest, key_fields: list[str]) -> str:
    """按配置列出的字段计算稳定命中键。"""
    fields = key_fields or _DEFAULT_KEY_FIELDS
    payload = request.model_dump(include=set(fields))
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sanitize(value: Any, strip_fields: list[str], api_key: str | None = None) -> Any:
    """递归脱敏：删禁用字段、替换疑似凭据与当前真实 key。"""
    if isinstance(value, str):
        text = value
        for pattern in _SECRET_PATTERNS:
            text = pattern.sub(REDACTED, text)
        if api_key:
            text = text.replace(api_key, REDACTED)
        return text
    if isinstance(value, dict):
        blocked = {item.lower().replace("-", "_") for item in strip_fields}
        return {
            key: sanitize(item, strip_fields, api_key)
            for key, item in value.items()
            if key.lower().replace("-", "_") not in blocked
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item, strip_fields, api_key) for item in value]
    return value


def cassette_path(directory: Path, model: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", model) or "model"
    return directory / f"deepseek_{slug}.json"


def load_cassette(path: Path) -> Cassette | None:
    if not path.is_file():
        return None
    return Cassette(**json.loads(path.read_text(encoding="utf-8")))


def save_cassette(path: Path, cassette: Cassette, settings: CassetteSettings,
                  api_key: str | None = None) -> Path:
    payload = sanitize(cassette.model_dump(mode="json"), settings.strip, api_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def make_entry(request: LLMRequest, response: LLMResponse,
               settings: CassetteSettings, api_key: str | None = None,
               recorded_at: str | None = None) -> CassetteEntry:
    """把一次调用转为脱敏后的 cassette 条目，并记录该条的录制时刻。

    键字段与 ``RecordedLLM`` 保持一致：认知角色用 ``role_key_fields``（去掉动态
    user），否则用全局 ``key_fields``——否则录制键与回放键不一致，永远 miss。
    """
    key_fields = settings.role_key_fields.get(request.role) or settings.key_fields
    prompt = f"{request.system}\n{request.user}".encode()
    request_payload = sanitize(request.model_dump(), settings.strip, api_key)
    response_payload = sanitize({
        "raw": response.raw,
        "parsed": response.parsed,
        "usage": response.usage.model_dump(),
    }, settings.strip, api_key)
    return CassetteEntry(
        key=compute_key(request, key_fields),
        role=request.role,
        prompt_sha256=hashlib.sha256(prompt).hexdigest(),
        request=request_payload,
        response=response_payload,
        model=response.model,
        recorded_at=recorded_at or datetime.now().isoformat(timespec="seconds"),
    )


__all__ = [
    "REDACTED",
    "cassette_path",
    "compute_key",
    "load_cassette",
    "make_entry",
    "sanitize",
    "save_cassette",
]
