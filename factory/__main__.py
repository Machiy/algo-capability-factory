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
    task_config: str = typer.Option(
        "configs/verify_credit.yaml", "--task-config",
        help="任务级验证配置；换场景只换 yaml，不改代码",
    ),
    run_id: str = typer.Option("demo", "--run-id", help="运行标识，决定报告与轨迹文件名"),
    kg_filename: str = typer.Option(
        "capabilities_after_run.json", "--kg-out",
        help="回写图谱文件名；不同场景各用一份，避免指标互相污染",
    ),
    gen_dir: str = typer.Option(
        "", "--gen-dir",
        help="生成代码子目录；不同场景分开存放，避免互相覆盖",
    ),
) -> None:
    """跑通 a–g 七步闭环。"""
    from factory.workflow import run_from_cli
    raise typer.Exit(run_from_cli(spec, mock, ROOT, task_config, run_id,
                                  kg_filename, gen_dir))


@app.command()
def api(
    host: str = typer.Option("127.0.0.1", help="监听地址"),
    port: int = typer.Option(8000, help="监听端口"),
    export_openapi: bool = typer.Option(
        False, "--export-openapi", help="只导出 OpenAPI 文档到 outputs/reports/"
    ),
) -> None:
    """启动 FastAPI 服务，或导出 OpenAPI 文档。"""
    from factory.api.app import create_app, write_openapi

    if export_openapi:
        from factory.config import load_settings
        settings = load_settings(ROOT / "configs/default.yaml")
        target = ROOT / settings.paths.reports / "openapi.json"
        path = write_openapi(target, ROOT)
        print(f"[API] OpenAPI 已导出：{path.relative_to(ROOT).as_posix()}")
        raise typer.Exit()
    import uvicorn

    uvicorn.run(create_app(ROOT), host=host, port=port)


if __name__ == "__main__":
    app()
