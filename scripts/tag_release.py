"""发布动作：push 之后按 ``factory.__version__`` 打 tag 并创建 GitHub Release。

固化在 `.codebuddy/rules/git-commit.md` 的「版本标签与 Release」一节：每次
`git push origin main` 成功后立即执行本脚本，完成 **tag + Release** 两步，
让 CHANGELOG 的每个版本在 Git 与 GitHub 上都可定位。

    python scripts/tag_release.py                              # 当前版本：tag + Release
    python scripts/tag_release.py --dry-run                    # 只检查、不创建
    python scripts/tag_release.py --version 1.2.0 --target 1ef44d9   # 补历史版本
    python scripts/tag_release.py --no-release                 # 只打 tag

安全约束：

- 工作区干净、HEAD 已在 ``origin/main``（``--target`` 补历史时跳过后者）；
- 同名 tag / Release 已存在时跳过，绝不 force 覆盖；
- token 只从 ``GITHUB_TOKEN`` / ``GH_TOKEN`` / git 凭据读取，不打印、不落盘；
- 无凭据或 API 失败时返回非 0，如实提示待补，不声称已完成。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory import __version__

API_ROOT = "https://api.github.com"


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{result.stderr.strip()}")
    return result.stdout.strip()


def _remote_slug() -> str:
    """从 origin 解析 ``owner/repo``，支持 https 与 SSH 两种写法。"""
    url = _git("remote", "get-url", "origin").strip().removesuffix(".git")
    for separator in ("github.com/", "github.com:"):
        if separator in url:
            return url.split(separator, 1)[1].strip("/")
    raise RuntimeError("无法从 origin 解析 GitHub 仓库（非 github.com 远端）")


def _github_token() -> str:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    result = subprocess.run(
        ["git", "credential", "fill"], cwd=ROOT,
        input="protocol=https\nhost=github.com\n\n",
        text=True, capture_output=True, check=False,
    )
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def _github_api(method: str, path: str, token: str,
                payload: dict | None = None) -> tuple[int, dict | None]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    request = urllib.request.Request(
        f"{API_ROOT}{path}", data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "algocap-factory-release-script",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (OSError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub API 请求失败：{exc}") from exc


def _release_notes(version: str) -> str:
    """把 CHANGELOG 中该版本的段落直接作为 Release 说明。"""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    marker = f"## [{version}]"
    start = text.find(marker)
    if start < 0:
        return f"AlgoCap Factory v{version}\n\n详见 CHANGELOG.md。"
    end = text.find("\n## [", start + len(marker))
    section = text[start:end if end > 0 else None].strip()
    return f"{section}\n\n> 由 scripts/tag_release.py 从 CHANGELOG.md 自动生成。"


def _ensure_release(tag: str, version: str, token: str,
                    dry_run: bool = False) -> bool:
    """Release 与 tag 一样幂等：已存在就跳过，不存在才创建。"""
    if not token:
        print("[release] 未找到 GITHUB_TOKEN / GH_TOKEN / git 凭据，需人工补建 Release")
        return False
    slug = _remote_slug()
    if dry_run:
        print(f"[release] dry-run：将检查 / 创建 {slug} 的 {tag} Release")
        return True
    status, _ = _github_api("GET", f"/repos/{slug}/releases/tags/{tag}", token)
    if status == 200:
        print(f"[release] {tag} 已存在，跳过（不覆盖）")
        return True
    if status != 404:
        print(f"[release] 查询 Release 失败：HTTP {status}")
        return False
    status, data = _github_api("POST", f"/repos/{slug}/releases", token, {
        "tag_name": tag,
        "name": f"AlgoCap Factory {tag}",
        "body": _release_notes(version),
        "draft": False,
        "prerelease": False,
    })
    if status in (200, 201):
        print(f"[release] 已创建 {tag}：{(data or {}).get('html_url', '')}")
        return True
    print(f"[release] 创建 Release 失败：HTTP {status}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="按版本号创建 tag 与 GitHub Release")
    parser.add_argument("--version", default="", help="覆盖版本号（补历史版本时用）")
    parser.add_argument("--target", default="", help="标签指向的提交；默认当前 HEAD")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不创建 / 推送")
    parser.add_argument("--no-release", action="store_true", help="只打 tag，不创建 Release")
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

    tag_exists = bool(_git("tag", "--list", tag)) or bool(
        _git("ls-remote", "--tags", "origin", f"refs/tags/{tag}", check=False))
    if tag_exists:
        print(f"[tag] {tag} 已存在，跳过（不覆盖）")
    elif args.dry_run:
        print(f"[tag] dry-run：将创建 {tag} -> {target}，并推送到 origin")
    else:
        message = (f"AlgoCap Factory {tag}\n\n"
                   f"版本说明见 CHANGELOG.md；由 scripts/tag_release.py 创建。")
        _git("tag", "-a", tag, "-m", message, target)
        _git("push", "origin", tag)
        # annotated tag 是独立对象，解引用到提交后打印才有意义
        commit = _git("rev-parse", "--short", f"{tag}^{{}}")
        print(f"[tag] 已创建并推送 {tag} -> {commit}")

    if args.no_release:
        return 0
    token = _github_token()
    ok = _ensure_release(tag, version, token, dry_run=args.dry_run)
    if args.dry_run:
        return 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
