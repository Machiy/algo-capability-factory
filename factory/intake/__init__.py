"""入口输入引导层：体检自然语言描述，给出可执行的改写建议。

不依赖任何第三方库（除 PyYAML），因此 CLI 的 ``guide`` 子命令在最小环境下
也能运行；规则全部来自 ``configs/*.yaml`` 的 ``intake`` 段。
"""

from factory.intake.guard import IntakeGuide, SpecRejected, render_guidance, render_menu

__all__ = ["IntakeGuide", "SpecRejected", "render_guidance", "render_menu"]
