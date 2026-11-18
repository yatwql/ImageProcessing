"""覆盖率收尾：把最后 4 行"看起来难、其实只是没构造对场景"的分支补齐。

- `core/style.py`：粗筛阶段 `ink_size` 抛错 → 走 `except` 记日志（此前只 patch 了 render_line，
  而异常其实发生在更早的 ink_size 上，所以那两行永远进不去）；
- `core/audit.py`：`_winlock()` 在非 Windows 上 `import msvcrt` 失败 → 返回 None；
- `tui/ui_actions.py`：右栏按 Enter 进入 `edit_current`；
- `cli/main.py`：第一遍就全部读图失败 → `sys.exit("所有图片都读取失败")`。
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.python.cli import main as cli_main
from src.python.core import audit, image, style
from src.test._support import FONT_CJK, FakeWin, TuiTestCase, has_cjk_font


class StyleInkSizeFailure(unittest.TestCase):
    def test_ink_size_failure_is_logged_and_skipped(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        from src.python.core import fonts

        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        logged: list[str] = []
        with mock.patch.object(style, "ink_size", side_effect=OSError("渲染不出")), \
                mock.patch.object(style, "_log", side_effect=logged.append):
            result = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1)
        self.assertIsNone(result)
        self.assertTrue(any("渲染失败" in item for item in logged), f"应记录失败：{logged}")


class WinLockImportFailure(unittest.TestCase):
    def test_winlock_returns_none_without_msvcrt(self):
        with mock.patch.object(audit.importlib, "import_module", side_effect=ImportError("no msvcrt")):
            self.assertIsNone(audit._winlock())


class EnterOnBlocksPanel(TuiTestCase):
    def test_enter_on_blocks_panel_opens_whole_line_editor(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(list("替换后的整行") + ["\n"])
        from src.python.tui import ui_actions

        ui_actions.handle(app, win, "\n")
        blk = app.cur_block()
        assert blk is not None
        self.assertEqual(blk.override, "替换后的整行")


class AllImagesUnreadable(unittest.TestCase):
    def test_all_images_failing_to_load_exits_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((10, 10, 3), 255, np.uint8), None, src)
            err = io.StringIO()
            with mock.patch.object(cli_main, "collect_images", return_value=[src]), \
                    mock.patch.object(cli_main, "load_image", side_effect=OSError("坏图")), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main.main([src, "--map", "原文=新文", "--out-dir", tmp])
        self.assertIn("读取失败", str(ctx.exception.code))


if __name__ == "__main__":
    unittest.main()
