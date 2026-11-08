"""AlgoCap Factory CLI 入口（Typer）。

``--version`` / ``--check`` 保持零第三方依赖；重依赖只在 ``run`` 分支延迟导入。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import typer

from factory import __version__

CORE_DEPENDENCIES = ["pydantic", "yaml", "pandas", "sklearn", "networkx"]
ROOT = Path(__file__).resolve().parents[1]

app = typer.Typer(help="AlgoCap Factory · 基于 AI Agent 的算法能力工厂",
                  add_completion=False)


def check_dependencies() -> int:
    """检查核心第三方依赖是否就绪，返回进程退出码。"""
    missing = [name for name in CORE_DEPENDENCIES
               if importlib.util.find_spec(name) is None]
    if missing:
        print(f"[factory] 缺少依赖：{', '.join(missing)}")
        print("[factory] 请执行：pip install -r requirements.txt")
        return 1
    print("[factory] 核心依赖就绪")
    return 0


def _version_callback(value: bool) -> None:
    if value:
        print(f"factory {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback,
                                 is_eager=True, help="显示版本号"),
    check: bool = typer.Option(False, "--check", help="检查核心依赖是否安装"),
) -> None:
    if check:
        raise typer.Exit(check_dependencies())


@app.command()
def run(
    spec: str = typer.Option(..., "--spec", help="自然语言能力描述"),
    mock: bool = typer.Option(False, "--mock", help="强制使用离线 MockLLM"),
) -> None:
    """跑通 a–g 七步闭环。"""
    from factory.workflow import run_from_cli
    raise typer.Exit(run_from_cli(spec, mock, ROOT))


if __name__ == "__main__":
    app()
