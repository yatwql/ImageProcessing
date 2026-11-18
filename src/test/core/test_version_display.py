"""版本号：唯一来源、界面可见、每次运行都报、写盘日志记录、文档开头一致。

一条链上任何一处不一致，都会让人拿着「v0.1」的行为去对照「v0.2」的文档，
所以这里逐段固定：version.py → CLI 启动横幅 → TUI 标题/帮助 → 日志字段 → 文档开头。
"""

from __future__ import annotations

import contextlib
import io
import re
import unittest
from pathlib import Path

from src.python import __version__
from src.python import version as version_mod
from src.python.cli import main as cli_main
from src.python.core import audit
from src.test._support import FakeWin, TuiTestCase, ocr_available

ROOT = Path(__file__).resolve().parents[3]


class VersionSource(unittest.TestCase):
    def test_version_module_is_the_single_source(self):
        self.assertEqual(__version__, version_mod.VERSION)
        self.assertRegex(version_mod.VERSION, r"^\d+\.\d+")

    def test_pyproject_reads_the_version_from_that_module(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = { attr = "src.python.version.VERSION" }', text)


class VersionIsPrinted(TuiTestCase):
    def test_cli_prints_version_before_work(self):
        out, err = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
            contextlib.suppress(SystemExit),
        ):
            cli_main.main(["--version"])
        self.assertIn(f"{version_mod.NAME} {version_mod.VERSION}", out.getvalue() + err.getvalue())

    @unittest.skipUnless(ocr_available(), "需要可用的 OCR 依赖（onnxruntime）")
    def test_cli_banner_goes_to_stderr_so_listing_stays_clean(self):
        out, err = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
            contextlib.suppress(SystemExit),
        ):
            cli_main.main(["--list", "data/demo"])
        self.assertIn(f"{version_mod.NAME} {version_mod.VERSION}", err.getvalue())
        self.assertTrue(out.getvalue().startswith("== "), "stdout 只能是清单内容")

    def test_tui_title_bar_shows_version(self):
        from src.python.tui import ui_draw

        app = self.make_app(count=1)
        win = FakeWin([], rows=28, cols=100)
        ui_draw.draw_frame(win, app)
        self.assertIn(f"v{version_mod.VERSION}", win.screen[0])

    def test_tui_help_page_shows_version(self):
        from src.python.tui import ui_base

        self.assertIn(f"v{version_mod.VERSION}", ui_base.HELP)


class VersionIsLogged(TuiTestCase):
    def test_write_log_entry_carries_the_version(self):
        entry = audit.build_entry("a.png", "b.png", ())
        self.assertEqual(entry["app_version"], version_mod.VERSION)


class CodeUpdatedDate(TuiTestCase):
    """代码更新日期要出现在 TUI 标题、帮助页与写盘日志里（反馈问题时一眼看出是哪天的代码）。"""

    def test_title_bar_shows_the_update_date(self):
        from src.python.tui import ui_draw

        app = self.make_app(count=1)
        win = FakeWin([], rows=28, cols=120)
        ui_draw.draw_frame(win, app)
        self.assertIn(version_mod.UPDATED, win.screen[0])

    def test_help_page_shows_the_update_date(self):
        from src.python.tui import ui_base

        self.assertIn(version_mod.UPDATED, ui_base.HELP)

    def test_write_log_entry_records_the_update_date(self):
        entry = audit.build_entry("a.png", "b.png", ())
        self.assertEqual(entry["app_updated"], version_mod.UPDATED)

    def test_cli_version_prints_the_update_date(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                contextlib.suppress(SystemExit):
            cli_main.main(["--version"])
        self.assertIn(version_mod.UPDATED, out.getvalue() + err.getvalue())

    def test_update_date_looks_like_a_date(self):
        self.assertRegex(version_mod.UPDATED, r"^\d{4}-\d{2}-\d{2}$")


class VersionInDocs(unittest.TestCase):
    def test_every_doc_starts_with_the_current_version(self):
        docs = [
            "README.md",
            "CLAUDE.md",
            "docs/managements/requirements.md",
            "docs/managements/technical.md",
            "docs/managements/plan.md",
            "docs/managements/changelog.md",
            "docs/managements/review-findings.md",
            "docs/manuals/how-to-use.md",
        ]
        pattern = re.compile(rf"^>\s*版本：v{re.escape(version_mod.VERSION)}\s*$", re.MULTILINE)
        for rel in docs:
            with self.subTest(doc=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertRegex(text, pattern, f"{rel} 开头缺少版本行")


if __name__ == "__main__":
    unittest.main()
