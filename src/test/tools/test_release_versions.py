"""版本号与分支策略（`-dev` 开发版 / 正式版）：`release.py` 的定版与切版。

规则（见 `docs/managements/releasing.md`）：
- 日常开发在 `dev` 分支，`VERSION` 带 `-dev`（如 `0.3-dev`）；
- 正式发布去掉后缀（`0.3`），打标签 `v0.3`，再合并进 `master`；
- 发布后回到 `dev` 切下一个开发版（`devbump`）；开发版不允许打标签。
"""

from __future__ import annotations

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python.tools import release

VERSION_TEMPLATE = '''"""程序名称与版本号。"""

from __future__ import annotations

NAME = "retype"
TITLE = "图片文字替换"
VERSION = "{version}"
UPDATED = "2026-11-18"
'''


def write_version_file(path: Path, version: str) -> None:
    path.write_text(VERSION_TEMPLATE.format(version=version), encoding="utf-8")


def run(func, *args) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = func(*args)
    return code, out.getvalue()


class VersionForm(unittest.TestCase):
    def test_base_version_strips_dev_suffix(self):
        self.assertEqual(release.base_version("0.2-dev"), "0.2")
        self.assertEqual(release.base_version("0.2"), "0.2")

    def test_is_dev(self):
        self.assertTrue(release.is_dev("0.2-dev"))
        self.assertFalse(release.is_dev("0.2"))


class Prepare(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.version_file = root / "version.py"
        self.changelog = root / "changelog.md"

    def patch(self):
        return (
            mock.patch.object(release, "VERSION_FILE", self.version_file),
            mock.patch.object(release, "CHANGELOG", self.changelog),
        )

    def test_dev_to_release_drops_suffix_and_adds_changelog_head(self):
        write_version_file(self.version_file, "0.2-dev")
        self.changelog.write_text("# 变更记录\n\n## 归档\n", encoding="utf-8")
        p1, p2 = self.patch()
        with p1, p2:
            code, _out = run(release.cmd_prepare, "0.2")
        self.assertEqual(code, 0)
        text = self.version_file.read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.2"', text)
        self.assertNotIn("-dev", text)
        changelog = self.changelog.read_text(encoding="utf-8")
        self.assertRegex(changelog, r"## v0\.2 — \d{4}-\d{2}-\d{2}")

    def test_cross_version_prepare_is_refused(self):
        write_version_file(self.version_file, "0.2-dev")
        self.changelog.write_text("# 变更记录\n", encoding="utf-8")
        p1, p2 = self.patch()
        with p1, p2:
            code, out = run(release.cmd_prepare, "0.9")
        self.assertEqual(code, 2)
        self.assertIn("跨版本发布", out)
        self.assertIn('VERSION = "0.2-dev"', self.version_file.read_text(encoding="utf-8"))

    def test_bad_format_is_refused(self):
        write_version_file(self.version_file, "0.2-dev")
        p1, p2 = self.patch()
        with p1, p2:
            code, out = run(release.cmd_prepare, "v0.2")
        self.assertEqual(code, 2)
        self.assertIn("MAJOR.MINOR", out)


class DevBump(unittest.TestCase):
    def test_bumps_to_next_dev_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_file = Path(tmp) / "version.py"
            write_version_file(version_file, "0.2")
            with mock.patch.object(release, "VERSION_FILE", version_file):
                code, out = run(release.cmd_devbump, "0.3")
            self.assertEqual(code, 0)
            text = version_file.read_text(encoding="utf-8")
            self.assertIn('VERSION = "0.3-dev"', text)
            self.assertIn("0.3-dev", out)

    def test_rejects_non_minor_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_file = Path(tmp) / "version.py"
            write_version_file(version_file, "0.2")
            code, out = run(release.cmd_devbump, "0.3.1", version_file)
            self.assertEqual(code, 2)
            self.assertIn("MAJOR.MINOR", out)


class Tag(unittest.TestCase):
    def test_dev_version_cannot_be_tagged(self):
        code, out = run(release.cmd_tag, "0.3-dev", False)
        self.assertEqual(code, 2)
        self.assertIn("开发版", out)

    def test_tag_name_has_no_dev_suffix(self):
        # 不能真去问 git（发过 v0.3 之后这条就会红）：把"标签是否存在"桩掉，
        # 用例只验"标签名里不该出现 -dev"这条规则本身。
        with mock.patch.object(release, "sh") as fake_sh:
            fake_sh.return_value.stdout = ""
            code, out = run(release.cmd_tag, "0.3", False)
        self.assertEqual(code, 0)
        self.assertIn("git tag -a v0.3", out)
        self.assertFalse(re.search(r"v0\.3-dev", out))

    def test_existing_tag_is_refused(self):
        """同名标签已存在就拒绝：重复打标签会让"这个版本发布了什么"变得不可考。"""
        with mock.patch.object(release, "sh") as fake_sh:
            fake_sh.return_value.stdout = "v0.3\n"
            code, out = run(release.cmd_tag, "0.3", False)
        self.assertEqual(code, 2)
        self.assertIn("已存在", out)


if __name__ == "__main__":
    unittest.main()
