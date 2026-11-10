"""外部插件发现：只放一个 ``.py`` 就能接入新模板 / 新指标。

装饰器注册表（``agents.templates.register`` / ``validation.metrics.register``）
本身已支持运行时注册，但此前外部文件必须被包内显式 import 才生效，等于
「新增插件还得改核心包」。这里用标准库 ``importlib`` 扫描 ``plugins/``，
在运行时把文件加载进来，让「新增一个文件即可」真正成立：

```python
# plugins/my_metric.py
from factory.validation.metrics import register

@register("my_metrics", "my_score")
def my_score(**context):
    return 0.5
```

扫描结果按绝对路径去重，单个插件出错只记 warning，不阻断主流程。
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DIRECTORY = "plugins"
_LOADED: set[Path] = set()


def load_plugins(root: Path, directory: str = DEFAULT_DIRECTORY) -> list[str]:
    """加载 ``root/<directory>/*.py``，返回本次真正加载的文件名（幂等）。"""
    folder = root / directory
    if not folder.is_dir():
        return []
    loaded: list[str] = []
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        resolved = path.resolve()
        if resolved in _LOADED:
            continue
        digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:10]
        module_name = f"factory_external_plugin_{path.stem}_{digest}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, resolved)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - 外部插件失败不能让服务起不来
            sys.modules.pop(module_name, None)
            logger.warning("外部插件加载失败：%s（%s）", path.name, exc)
            continue
        _LOADED.add(resolved)
        loaded.append(path.name)
    if loaded:
        logger.info("已加载外部插件：%s", ", ".join(loaded))
    return loaded


__all__ = ["DEFAULT_DIRECTORY", "load_plugins"]
