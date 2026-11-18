"""TUI 外壳：参数解析、入口分支、主循环异常处理与基础绘制件。

`tui/ui.py` 之前只有 60% 覆盖——它的分支（路径不存在、空目录、键盘中断、
`KEY_RESIZE`、终端不响应）恰恰是用户最可能撞上的路径。
"""

from __future__ import annotations

import contextlib
import curses
import io
import os
import unittest
from unittest import mock

from src.python.core.errors import CoreError
from src.python.tui import ui, ui_base, ui_draw, ui_input
from src.test._support import FakeWin, TuiTestCase, patch_curses


class ParseArgs(unittest.TestCase):
    def test_defaults(self):
        inputs, out_dir, map_file, opts = ui.parse_args([])
        self.assertEqual(len(inputs), 1)          # 默认输入目录
        self.assertIsNone(out_dir)
        self.assertIsNone(map_file)
        self.assertEqual(opts.align, "auto")

    def test_all_value_flags_are_parsed(self):
        _in, out_dir, map_file, opts = ui.parse_args([
            "data", "-o", "/tmp/out", "-m", "map.json", "-f", "/tmp/a.ttf",
            "--color", "#102030", "--align", "left", "--size", "28",
            "--tracking", "-1.5", "--max-fonts", "40", "--quality", "80",
            "--log-dir", "/tmp/logs", "--fit-width",
        ])
        self.assertEqual(out_dir, "/tmp/out")
        self.assertEqual(map_file, "map.json")
        self.assertEqual(opts.font, "/tmp/a.ttf")
        self.assertEqual(opts.color, "#102030")
        self.assertEqual(opts.align, "left")
        self.assertEqual(opts.size, 28)
        tracking = opts.tracking
        assert tracking is not None, "--tracking 应写入浮点值"
        self.assertAlmostEqual(tracking, -1.5, places=3)
        self.assertEqual(opts.max_fonts, 40)
        self.assertEqual(opts.quality, 80)
        self.assertEqual(opts.log_dir, "/tmp/logs")
        self.assertTrue(opts.fit_width)

    def test_non_numeric_value_exits_with_2(self):
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit) as ctx:
                ui.parse_args(["data", "--size", "abc"])
        self.assertEqual(ctx.exception.code, 2)

    def test_quality_out_of_range_exits_with_2(self):
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit) as ctx:
                ui.parse_args(["data", "--quality", "999"])
        self.assertEqual(ctx.exception.code, 2)

    def test_help_prints_usage_and_exits_0(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                ui.parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("用法", out.getvalue())

    def test_unknown_flag_is_treated_as_input_path(self):
        inputs, _out, _map, _opts = ui.parse_args(["--nope"])
        self.assertIn("--nope", inputs)


class MainEntry(TuiTestCase):
    def run_main(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ui.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_missing_path_exits_with_2(self):
        code, _out, err = self.run_main([os.path.join(self.tmp.name, "nope")])
        self.assertEqual(code, 2)
        self.assertIn("路径不存在", err)

    def test_empty_directory_starts_with_a_hint(self):
        empty = os.path.join(self.tmp.name, "empty")
        os.makedirs(empty)
        with mock.patch.object(ui.curses, "wrapper") as wrapper:
            code, _out, _err = self.run_main([empty])
        self.assertEqual(code, 0)
        app = wrapper.call_args.args[1]
        self.assertIn("还没有图片", app.message)
        self.assertIn("Ctrl-R", app.message)

    def test_core_error_during_startup_exits_with_2(self):
        with mock.patch.object(ui, "App", side_effect=CoreError("映射表坏了")):
            code, _out, err = self.run_main(["data/demo"])
        self.assertEqual(code, 2)
        self.assertIn("映射表坏了", err)

    def test_keyboard_interrupt_maps_to_130(self):
        with mock.patch.object(ui.curses, "wrapper", side_effect=KeyboardInterrupt):
            code, _out, _err = self.run_main(["data/demo"])
        self.assertEqual(code, 130)

    def test_version_banner_is_printed_before_curses(self):
        with mock.patch.object(ui.curses, "wrapper"):
            _code, out, _err = self.run_main(["data/demo"])
        self.assertIn("retype", out)


class LoopBehaviour(TuiTestCase):
    def make(self):
        app = self.make_app(count=2)
        return app, FakeWin([], rows=26, cols=100)

    def run_loop(self, app, win):
        with contextlib.suppress(KeyboardInterrupt):
            ui.loop(win, app)
        return win

    def test_escape_is_mapped_to_the_escape_key_for_actions(self):
        app, win = self.make()
        app.focus = "blocks"
        # ESC 后面紧跟 None：表示"没有后续字节"，read_key 才会把它当独立的 Esc
        win.keys.extend(["\x1b", None, "q"])
        self.run_loop(app, win)
        self.assertEqual(app.focus, "files", "Esc 应当当作返回上一层")

    def test_resize_is_handled_without_quitting(self):
        app, win = self.make()
        win.keys.extend(["KEY_RESIZE", "q"])
        self.run_loop(app, win)
        self.assertTrue(app.quit)

    def test_persistent_terminal_errors_end_the_loop(self):
        """终端彻底不响应（读键直接抛错）时要主动退出，而不是空转到天荒地老。"""
        app, win = self.make()
        with mock.patch.object(ui, "read_key", side_effect=curses.error("boom")):
            self.run_loop(app, win)
        self.assertIn("终端没有响应", app.message)
        self.assertFalse(app.quit, "这是被动退出，不是用户按 q")

    def test_two_consecutive_interrupts_quit(self):
        app, win = self.make()
        win.get_wch = mock.Mock(side_effect=[KeyboardInterrupt, KeyboardInterrupt])
        self.run_loop(app, win)
        self.assertTrue(app.quit)

    def test_single_interrupt_does_not_quit(self):
        app, win = self.make()
        win.get_wch = mock.Mock(side_effect=[KeyboardInterrupt, "q"])
        self.run_loop(app, win)
        self.assertTrue(app.quit, "第二次拿到 q 才退出；单次 Ctrl-C 只是忽略")


class ReadKey(unittest.TestCase):
    def test_plain_character(self):
        self.assertEqual(ui_input.read_key(FakeWin(["a"])), "a")

    def test_int_key_uses_the_keymap(self):
        self.assertEqual(ui_input.read_key(FakeWin([curses.KEY_UP])), "KEY_UP")

    def test_unknown_int_returns_empty(self):
        self.assertEqual(ui_input.read_key(FakeWin([9999])), "")

    def test_lone_escape_returns_escape(self):
        self.assertEqual(ui_input.read_key(FakeWin(["\x1b", None])), "ESC")

    def test_escape_sequence_is_translated(self):
        self.assertEqual(ui_input.read_key(FakeWin(["\x1b", "[", "A"])), "KEY_UP")
        self.assertEqual(ui_input.read_key(FakeWin(["\x1b", "[", "6", "~"])), "KEY_NPAGE")

    def test_shift_tab_sequence_is_translated(self):
        self.assertEqual(ui_input.read_key(FakeWin(["\x1b", "[", "Z"])), "BTAB")

    def test_unknown_sequence_returns_empty(self):
        self.assertEqual(ui_input.read_key(FakeWin(["\x1b", "[", "9", "9"])), "")

    def test_timeout_restores_blocking_mode(self):
        win = FakeWin([None])
        self.assertEqual(ui_input.read_key(win, timeout_ms=5), "")
        self.assertEqual(win.timeout_ms, -1)


class BaseWidgets(unittest.TestCase):
    def test_progress_bar_edges(self):
        self.assertEqual(ui_base.progress_bar(0.0, 10), "░" * 10)
        self.assertEqual(ui_base.progress_bar(1.0, 10), "█" * 10)
        self.assertEqual(ui_base.progress_bar(-1.0, 10), "░" * 10, "负值要夹到 0")
        self.assertEqual(ui_base.progress_bar(2.0, 10), "█" * 10, "超过 1 要夹到满")

    def test_cut_and_pad_on_tiny_budgets(self):
        self.assertEqual(ui_base.cut("年度报告", 0), "")
        self.assertEqual(ui_base.pad("", 3), "   ")
        self.assertLessEqual(ui_base.dwidth(ui_base.cut("abc中", 4)), 4)

    def test_box_and_divider_survive_tiny_windows(self):
        patch_curses()
        win = FakeWin([], rows=3, cols=4)
        ui_base.box(win, 3, 4, "x", 0)          # 不抛即可
        ui_base.divider(win, 1, 0, 4, 0)

    def test_help_mentions_every_top_level_key(self):
        for key in ("Enter", "Tab", "Esc", "q", "Ctrl-R", "?"):
            with self.subTest(key=key):
                self.assertIn(key, ui_base.HELP)

    def test_usage_lists_the_main_flags(self):
        for flag in ("--out-dir", "--map-file", "--font", "--quality", "--log-dir"):
            with self.subTest(flag=flag):
                self.assertIn(flag, ui_base.USAGE)


class DrawEntry(unittest.TestCase):
    def test_too_small_screen_has_a_hint(self):
        patch_curses()
        win = FakeWin([], rows=6, cols=14)
        ui_draw.draw_frame(win, mock.Mock(panel="main", images=[], message="", status="",
                                          focus="files", out_dir="/x", last_saved=None,
                                          cur=None, blocks=lambda: [], image_position=lambda: 0))
        self.assertIn("太窄", "\n".join(win.screen))


if __name__ == "__main__":
    unittest.main()
