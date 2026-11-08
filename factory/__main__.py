"""最小 CLI 占位。

P0 阶段提供 --version 与 --check；P3/P5 完成后由 cli/app.py 的 Typer 应用接管
`factory run --spec ...`。保持零第三方依赖，便于干净环境验证仓库骨架。
"""

from __future__ import annotations

import argparse
import importlib.util

from factory import __version__

CORE_DEPENDENCIES = ["pydantic", "yaml", "pandas", "sklearn", "networkx"]


def check_dependencies() -> int:
    """检查核心第三方依赖是否就绪，返回进程退出码。"""
    missing = [name for name in CORE_DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        print(f"[factory] 缺少依赖：{', '.join(missing)}")
        print("[factory] 请执行：pip install -r requirements.txt")
        print("[factory] 数据准备脚本 scripts/download_data.py 不依赖这些包，可直接运行")
        return 1
    print("[factory] 核心依赖就绪")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="factory", description="AlgoCap Factory · 基于 AI Agent 的算法能力工厂"
    )
    parser.add_argument("--version", action="version", version=f"factory {__version__}")
    parser.add_argument("--check", action="store_true", help="检查核心依赖是否安装")
    parser.add_argument("--spec", help="自然语言能力描述（P3 起支持）")
    parser.add_argument("--mock", action="store_true", help="使用离线 MockLLM（P3 起支持）")
    args = parser.parse_args()

    if args.check:
        raise SystemExit(check_dependencies())
    if args.spec:
        print("[factory] Agent 工作流尚未实现，见 PLAN.md 的 P3 阶段")
        raise SystemExit(2)
    parser.print_help()


if __name__ == "__main__":
    main()
