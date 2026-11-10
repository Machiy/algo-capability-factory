"""外部插件自动发现：新增一个 .py 就能接入模板 / 指标，不改核心包。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory.agents.templates import _REGISTRY as TEMPLATES
from factory.agents.templates import list_templates, render
from factory.plugins import load_plugins
from factory.validation.metrics import _REGISTRY as METRICS
from factory.validation.metrics import compute, list_plugins

PLUGIN_SOURCE = '''\
from factory.agents.templates import register as register_template
from factory.validation.metrics import register as register_metric


@register_template("unit_external_family")
def _render(columns, hyperparams):
    return "FEATURE_COLUMNS = []\\ndef build_pipeline(config):\\n    return None\\n"


@register_metric("unit_external", "unit_metric")
def _metric(**context):
    return 0.75
'''


class ExternalPluginTests(unittest.TestCase):
    def tearDown(self) -> None:
        # 注册表是进程级全局，测试后清理，避免污染其他用例
        TEMPLATES.pop("unit_external_family", None)
        METRICS.pop("unit_external", None)

    def test_one_file_registers_template_and_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plugins").mkdir()
            (root / "plugins" / "unit_ext.py").write_text(
                PLUGIN_SOURCE, encoding="utf-8")
            loaded = load_plugins(root)
            self.assertEqual(loaded, ["unit_ext.py"])
            self.assertIn("unit_external_family", list_templates())
            self.assertIn("build_pipeline", render("unit_external_family", ["a"], {}))
            self.assertIn("unit_metric", list_plugins()["unit_external"])
            self.assertEqual(compute("unit_external", "unit_metric"), 0.75)
            # 重复加载不重复执行插件模块
            self.assertEqual(load_plugins(root), [])

    def test_missing_directory_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_plugins(Path(tmp)), [])

    def test_broken_plugin_does_not_break_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plugins").mkdir()
            (root / "plugins" / "bad.py").write_text("raise RuntimeError('boom')\n",
                                                     encoding="utf-8")
            (root / "plugins" / "unit_ext.py").write_text(PLUGIN_SOURCE,
                                                         encoding="utf-8")
            loaded = load_plugins(root)
            self.assertEqual(loaded, ["unit_ext.py"])
            self.assertIn("unit_external_family", list_templates())


if __name__ == "__main__":
    unittest.main()
