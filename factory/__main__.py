"""AlgoCap Factory CLI 入口。

``--version`` / ``--check`` 保持零第三方依赖；重依赖只在 ``run`` 分支延迟导入。
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from factory import __version__

CORE_DEPENDENCIES = ["pydantic", "yaml", "pandas", "sklearn", "networkx"]
ROOT = Path(__file__).resolve().parents[1]


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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="factory", description="AlgoCap Factory · 基于 AI Agent 的算法能力工厂"
    )
    parser.add_argument("command", nargs="?", help="子命令：run")
    parser.add_argument("--version", action="version", version=f"factory {__version__}")
    parser.add_argument("--check", action="store_true", help="检查核心依赖是否安装")
    parser.add_argument("--spec", help="自然语言能力描述")
    parser.add_argument("--mock", action="store_true", help="强制使用离线 MockLLM")
    args = parser.parse_args()

    if args.check:
        raise SystemExit(check_dependencies())
    if args.command == "run":
        if not args.spec:
            parser.error("run 需要 --spec \"能力描述\"")
        from factory.workflow import run_from_cli
        raise SystemExit(run_from_cli(args.spec, args.mock, ROOT))
    if args.spec:
        parser.error("请使用 python -m factory run --spec \"能力描述\"")
    parser.print_help()


if __name__ == "__main__":
    main()
