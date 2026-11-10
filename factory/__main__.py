"""AlgoCap Factory CLI 入口（Typer）。

``--version`` / ``--check`` 保持零第三方依赖；重依赖只在 ``run`` 分支延迟导入。
``guide`` 与 ``run`` 缺省参数时都走入口引导：先给要素与示例，再收描述。
"""

from __future__ import annotations

import importlib.util
import json
import sys
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
    spec: str = typer.Option(
        "", "--spec",
        help="自然语言能力描述；留空则进入交互引导（非交互环境必须显式传入）",
    ),
    mock: bool = typer.Option(False, "--mock", help="强制使用离线 MockLLM"),
    task_config: str = typer.Option(
        "configs/verify_credit.yaml", "--task-config",
        help="任务级验证配置；换场景只换 yaml，不改代码",
    ),
    run_id: str = typer.Option(
        "demo", "--run-id",
        help="运行变体名（如 demo / lesson_1）；报告与轨迹会带上场景前缀",
    ),
    kg_filename: str = typer.Option(
        "", "--kg-out",
        help="覆盖回写图谱文件名；默认按场景自动取 <scope>_kg_after_run.json",
    ),
    gen_dir: str = typer.Option(
        "", "--gen-dir",
        help="覆盖生成代码子目录；默认按场景自动取 generated/<scope>/",
    ),
    force: bool = typer.Option(
        False, "--force",
        help="跳过入口引导的拦截；描述被判不可执行时仍强制跑完七步",
    ),
) -> None:
    """跑通 a–g 七步闭环。"""
    from factory.workflow import run_from_cli

    if not spec.strip():
        spec = _prompt_for_spec(task_config)
        if not spec.strip():
            raise typer.Exit(2)
    raise typer.Exit(run_from_cli(spec, mock, ROOT, task_config, run_id,
                                  kg_filename, gen_dir, force))


@app.command()
def guide(
    spec: str = typer.Option(
        "", "--spec", help="只体检这一条描述，不跑七步闭环",
    ),
    task_config: str = typer.Option(
        "configs/verify_credit.yaml", "--task-config",
        help="按该任务场景的要素与示例做体检",
    ),
    as_json: bool = typer.Option(False, "--json", help="输出 JSON，便于前端或脚本消费"),
) -> None:
    """打印能力描述引导菜单，或体检一条描述（不消耗运行资源）。"""
    from factory.intake import render_guidance, render_menu

    reviewer = _build_guide(task_config)
    if spec.strip():
        guidance = reviewer.review(spec)
        if as_json:
            print(json.dumps(guidance.model_dump(mode="json"), ensure_ascii=False, indent=2))
        else:
            print(render_guidance(guidance))
        raise typer.Exit(0 if guidance.accepted else 1)
    if as_json:
        print(json.dumps(reviewer.describe(), ensure_ascii=False, indent=2))
    else:
        print(render_menu(reviewer))
    raise typer.Exit()


def _build_guide(task_config: str):
    """构造入口引导器：规则来自 default.yaml 与任务 yaml 的 intake 段。"""
    from factory.artifacts import kg_stem, scene_of
    from factory.config import load_settings, load_task_settings
    from factory.intake import IntakeGuide

    settings = load_settings(ROOT / "configs/default.yaml")
    task = load_task_settings(ROOT / task_config)
    return IntakeGuide(
        settings.intake, task.intake,
        configs_dir=ROOT / "configs",
        task_config=task_config,
        graph_path=(ROOT / settings.paths.kg
                    / f"{kg_stem(scene_of(task_config), 'after_run')}.json"),
    )


def _prompt_for_spec(task_config: str) -> str:
    """交互式引导：先亮菜单与示例，再收一条描述。

    非交互环境（CI / 管道）不进 prompt，直接打印菜单并要求 ``--spec``，
    避免子进程等 stdin 卡住。
    """
    from factory.intake import render_guidance, render_menu

    reviewer = _build_guide(task_config)
    print(render_menu(reviewer))
    if not sys.stdin.isatty():
        print("\n[factory] 非交互环境请用 --spec 传入能力描述", file=sys.stderr)
        return ""
    examples = reviewer.examples()
    default = examples[0] if examples else ""
    prompt = "请粘贴能力描述（直接回车使用示例）："
    try:
        answer = input(prompt).strip()
    except EOFError:
        return ""
    spec = answer or default
    if spec:
        print(render_guidance(reviewer.review(spec)))
    return spec


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
        target = ROOT / settings.paths.reports / "shared_openapi.json"
        path = write_openapi(target, ROOT)
        print(f"[API] OpenAPI 已导出：{path.relative_to(ROOT).as_posix()}")
        raise typer.Exit()
    import uvicorn

    uvicorn.run(create_app(ROOT), host=host, port=port)


if __name__ == "__main__":
    app()
