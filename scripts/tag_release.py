"""发布动作：push 之后按 ``factory.__version__`` 打 annotated tag 并推送。

固化在 `.codebuddy/rules/git-commit.md` 的「版本标签」一节：每次
`git push origin main` 成功后立即执行本脚本，让 CHANGELOG 的每个版本都能在
Git 上定位到一个不可变的提交。

    python scripts/tag_release.py                 # 给当前 HEAD 打 v<__version__>
    python scripts/tag_release.py --dry-run      # 只检查、不创建
    python scripts/tag_release.py --version 1.2.0 --target 1ef44d9   # 补历史标签

安全约束：

- 工作区必须干净，HEAD 必须已在 ``origin/main``（不允许给未推送的提交打 tag）；
- 本地 / 远端已存在同名 tag 时直接跳过，绝不 force 覆盖；
- ``--target`` 只用于补历史标签，此时跳过 HEAD 一致性检查。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory import __version__


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{result.stderr.strip()}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="按版本号创建并推送 Git 标签")
    parser.add_argument("--version", default="", help="覆盖版本号（补历史标签时用）")
    parser.add_argument("--target", default="", help="标签指向的提交；默认当前 HEAD")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不创建 / 推送")
    args = parser.parse_args()

    version = args.version or __version__
    tag = f"v{version}"
    target = args.target or "HEAD"

    dirty = _git("status", "--porcelain")
    if dirty:
        print(f"[tag] 工作区不干净，先提交：\n{dirty}")
        return 1

    if not args.target:
        head = _git("rev-parse", "HEAD")
        remote = _git("rev-parse", "origin/main", check=False)
        if remote != head:
            print(f"[tag] HEAD {head[:8]} 尚未推送到 origin/main（{remote[:8] or '无'}），先 push")
            return 1

    if _git("tag", "--list", tag):
        print(f"[tag] 本地已存在 {tag}，跳过（不覆盖）")
        return 0
    if _git("ls-remote", "--tags", "origin", f"refs/tags/{tag}", check=False):
        print(f"[tag] 远端已存在 {tag}，跳过（不覆盖）")
        return 0

    message = (f"AlgoCap Factory {tag}\n\n"
               f"版本说明见 CHANGELOG.md；由 scripts/tag_release.py 创建。")
    if args.dry_run:
        print(f"[tag] dry-run：将创建 {tag} -> {target}，并推送到 origin")
        return 0

    _git("tag", "-a", tag, "-m", message, target)
    _git("push", "origin", tag)
    print(f"[tag] 已创建并推送 {tag} -> {_git('rev-parse', '--short', tag)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
