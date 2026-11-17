"""TUI 按键测试：转义序列解码、方向键与别名键导航、数字跳图、Esc 语义。

不依赖真终端：用 _support.FakeWin 喂按键，直接驱动 ui.loop / ui.read_key。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import curses
import os
import tempfile
import unittest

import src.python.tui.ui as ui
from src.test._support import FakeWin, TuiTestCase


class CliLikeArguments(unittest.TestCase):
    """TUI 启动参数：--quality / --log-dir 与主流程一致。"""

    def test_quality_and_log_dir_are_parsed(self):
        log_dir = os.path.join(tempfile.gettempdir(), "img-p-logs")
        _inputs, _out, _map, opts = ui.parse_args(
            ["--quality", "80", "--log-dir", log_dir])
        self.assertEqual(opts.quality, 80)
        self.assertEqual(opts.log_dir, log_dir)

    def test_out_of_range_quality_exits(self):
        with self.assertRaises(SystemExit):
            ui.parse_args(["--quality", "0"])


class KeySequenceDecoding(unittest.TestCase):
    """各种终端吐出来的按键字节怎么归一。"""

    def test_escape_sequences_decode_to_arrows(self):
        for seq, token in ((["\x1b", "[", "A"], "KEY_UP"),
                           (["\x1b", "O", "B"], "KEY_DOWN"),
                           (["\x1b", "[", "5", "~"], "KEY_PPAGE")):
            self.assertEqual(ui.read_key(FakeWin(seq)), token)

    def test_single_escape_stays_escape_key(self):
        self.assertEqual(ui.read_key(FakeWin(["\x1b"])), "ESC")

    def test_plain_character_passes_through(self):
        self.assertEqual(ui.read_key(FakeWin(["j"])), "j")

    def test_unknown_escape_sequence_is_ignored(self):
        self.assertEqual(ui.read_key(FakeWin(["\x1b", "[", "9", "9", "~"])), "")


class ListNavigation(TuiTestCase):
    """列表移动、面板切换与数字跳图。"""

    def test_down_arrow_moves_image_selection(self):
        app = self.make_app()
        self.drive(app, ["\x1b", "[", "B", None, "q"])
        self.assertEqual(app.image_position(), 2)

    def test_curses_keycodes_navigate(self):
        app = self.make_app()
        self.drive(app, [curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_UP, "q"])
        self.assertEqual(app.image_position(), 2)

    def test_comma_and_dot_alias_arrows(self):
        app = self.make_app()
        self.drive(app, [".", ".", ",", "q"])
        self.assertEqual(app.image_position(), 2)

    def test_escape_returns_instead_of_quitting(self):
        app = self.make_app()
        self.drive(app, ["\x1b", None, "q"])
        self.assertTrue(app.quit)                     # 退出是后面的 q 干的
        self.assertIn("按 q 退出", app.message)

    def test_t_key_toggles_panel_focus(self):
        app = self.make_app()
        self.drive(app, ["t", "q"])
        self.assertEqual(app.focus, "blocks")

    def test_down_arrow_moves_block_selection(self):
        app = self.make_app()
        self.drive(app, ["t", curses.KEY_DOWN, "q"])
        self.assertEqual(app.sel_blk, 1)

    def test_digit_key_selects_image(self):
        app = self.make_app()
        self.drive(app, ["2", "q"])
        self.assertEqual(app.image_position(), 2)
        self.assertEqual(app.focus, "files")

    def test_zero_key_selects_tenth_image(self):
        app = self.make_app(count=10)
        app.img_rows = 12                             # 一屏能看到第 10 张
        app.sel_row = app.first_image_row()
        self.assertTrue(app.select_by_digit(10))
        self.assertEqual(app.image_position(), 10)

    def test_visible_rows_are_numbered(self):
        self.assertEqual(ui.digit_of(0).strip(), "1")
        self.assertEqual(ui.digit_of(8).strip(), "9")
        self.assertEqual(ui.digit_of(9).strip(), "0")
        self.assertEqual(ui.digit_of(10).strip(), "")

    def test_out_of_range_digit_is_ignored(self):
        app = self.make_app()
        before = app.sel_row
        self.assertFalse(app.select_by_digit(9))
        self.assertEqual(app.sel_row, before)

    def test_list_window_follows_selection(self):
        app = self.make_app(count=10)
        app.img_rows = 4
        app.sel_row = 8
        start, visible = app.image_window(4)
        self.assertEqual(len(visible), 4)
        self.assertLessEqual(start, 8)
        self.assertGreaterEqual(start + len(visible) - 1, 8)
        app.img_rows = 12
        app.select_by_digit(1)
        self.assertEqual(app.sel_row, app.first_image_row())


if __name__ == "__main__":
    unittest.main()
