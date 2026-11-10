"""发布脚本的纯逻辑测试：不联网、不创建真实 tag / Release。"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "tag_release", ROOT / "scripts" / "tag_release.py")
assert _spec is not None and _spec.loader is not None
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


class ReleaseScriptTests(unittest.TestCase):
    def test_release_notes_come_from_changelog(self) -> None:
        notes = release._release_notes("1.4.3")
        self.assertIn("## [1.4.3]", notes)
        self.assertIn("路径规范化", notes)
        self.assertNotIn("## [1.4.2]", notes)

    def test_release_notes_fallback(self) -> None:
        notes = release._release_notes("9.9.9")
        self.assertIn("详见 CHANGELOG.md", notes)

    def test_remote_slug_supports_https_and_ssh(self) -> None:
        for url in ("https://github.com/Machiy/algo-capability-factory.git",
                    "git@github.com:Machiy/algo-capability-factory.git"):
            with self.subTest(url=url), patch.object(release, "_git", return_value=url):
                self.assertEqual(release._remote_slug(),
                                 "Machiy/algo-capability-factory")

    def test_existing_release_is_skipped(self) -> None:
        with patch.object(release, "_remote_slug",
                          return_value="Machiy/algo-capability-factory"), \
             patch.object(release, "_github_api", return_value=(200, {})) as api:
            self.assertTrue(release._ensure_release("v1.4.3", "1.4.3", "token"))
            self.assertEqual(api.call_args.args[0], "GET")

    def test_release_is_created_when_missing(self) -> None:
        calls = []

        def fake_api(method: str, path: str, token: str, payload=None):
            calls.append(method)
            if method == "GET":
                return 404, None
            return 201, {"html_url": "https://github.com/example/releases/tag/v9.9.9"}

        with patch.object(release, "_remote_slug",
                          return_value="Machiy/algo-capability-factory"), \
             patch.object(release, "_github_api", side_effect=fake_api):
            self.assertTrue(release._ensure_release("v9.9.9", "9.9.9", "token"))
        self.assertEqual(calls, ["GET", "POST"])


if __name__ == "__main__":
    unittest.main()
