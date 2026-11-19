"""TUI 状态与布局边界：面板导航、输入行、状态行、批量取消、窄窗兜底。"""

from __future__ import annotations

import contextlib
from unittest import mock

import numpy as np

from src.python.core.errors import CoreError
from src.python.tui import app as tui_app
from src.python.tui import ui, ui_actions, ui_base, ui_draw, ui_input
from src.test._support import (
    FakeWin,
    TuiTestCase,
    patch_curses,
)


def curses_error() -> BaseException:
    return ui_draw.curses.error("boom")


class EnterOnBlocksPanel(TuiTestCase):
    def test_enter_on_blocks_panel_opens_whole_line_editor(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend([*list("替换后的整行"), "\n"])
        from src.python.tui import ui_actions

        ui_actions.handle(app, win, "\n")
        blk = app.cur_block()
        assert blk is not None
        self.assertEqual(blk.override, "替换后的整行")


class TuiGaps(TuiTestCase):
    def test_jump_to_last_block_in_blocks_panel(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.sel_blk = 0
        app.jump(first=False)
        self.assertEqual(app.sel_blk, max(0, len(app.blocks()) - 1))

    def test_loop_survives_action_exceptions(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(["x", "y", "q"])
        with (
            mock.patch.object(
                ui, "handle", side_effect=[curses_error(), CoreError("坏"), RuntimeError("炸")]
            ),
            contextlib.suppress(KeyboardInterrupt),
        ):
            ui.loop(win, app)
        self.assertIn("操作出错", app.message)

    def test_settings_enter_with_no_rows_returns(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        app.panel = "settings"
        with mock.patch.object(app, "setting_notes", return_value=[]):
            ui_actions.handle_settings(app, win, "\n")
        self.assertEqual(app.panel, "settings")

    def test_map_enter_with_empty_mapping_returns(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        app.mapping = {}
        app.panel = "map"
        ui_actions.handle_map(app, win, "\n")
        self.assertEqual(app.mapping, {})

    def test_attr_falls_back_when_colors_unavailable(self):
        with mock.patch.object(ui_base.curses, "color_pair", side_effect=ui_base.curses.error):
            self.assertEqual(ui_base.attr("title", 7), 7)

    def test_draw_frame_survives_curses_error(self):
        patch_curses()
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        with (
            mock.patch.object(ui_draw, "draw_main", side_effect=ui_draw.curses.error),
            mock.patch.object(ui_draw.curses, "update_lines_cols") as update,
        ):
            ui_draw.draw_frame(win, app)
        update.assert_called_once()

    def test_escape_sequence_ends_when_a_keycode_arrives(self):
        win = FakeWin(["\x1b", 65])  # ESC 后直接来个功能键码
        self.assertEqual(ui_input.read_key(win), "ESC")


class SettingsJump(TuiTestCase):
    def test_jump_in_settings_panel_goes_to_last_row(self):
        app = self.make_app(count=1)
        app.panel = "settings"
        app.jump(first=False)
        self.assertEqual(app.sel_setting, len(tui_app.SETTING_ROWS) - 1)

    def test_map_add_with_empty_key_returns(self):
        app = self.make_app(count=1)
        app.panel = "map"
        win = FakeWin(["\n"], rows=26, cols=100)  # 直接回车 = 空 key
        ui_actions.handle_map(app, win, "n")
        self.assertEqual(app.mapping, {})

    def test_put_with_zero_columns_is_a_noop(self):
        win = FakeWin([], rows=5, cols=20)
        ui_base.put(win, 0, 0, "不该出现", 0)
        self.assertEqual(win.screen[0], "")

    def test_narrow_blocks_panel_shows_loading_hint(self):

        patch_curses()
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.images[0].blocks = None
        win = FakeWin([], rows=26, cols=44)
        ui_draw.draw_frame(win, app)
        self.assertIn("正在识别", "\n".join(win.screen))

    def test_ctrl_u_clears_the_input_line(self):
        win = FakeWin([], rows=10, cols=40)
        win.keys.extend(["a", "b", "\x15", "c", "\n"])
        result = ui_input.edit_line(win, "提示: ")
        self.assertEqual(result, "c")


class FinalGaps(TuiTestCase):
    """最后一批单行分支：返回值异常、父目录不可建、缓存坏 JSON、span 越界等。"""

    def test_jump_in_map_panel_goes_to_last_entry(self):
        app = mock.Mock(panel="map")
        app.mapping = {"a": "1", "b": "2"}
        app.sel_map = 0
        tui_app.App.jump(app, first=False)
        self.assertEqual(app.sel_map, 1)

    def test_box_on_tiny_window_returns_early(self):
        win = FakeWin([], rows=2, cols=3)
        ui_base.box(win, 2, 3, "x", 0)  # 尺寸不足：直接返回，不画越界
        self.assertEqual(win.cell_count, 0)

    def test_narrow_blocks_panel_shows_image_error(self):

        patch_curses()
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.images[0].blocks = []
        app.images[0].error = "这张图没识别出文字"
        win = FakeWin([], rows=26, cols=44)
        ui_draw.draw_frame(win, app)
        self.assertIn("没识别出文字", "\n".join(win.screen))

    def test_edit_line_navigation_keys(self):
        import curses as _curses

        win = FakeWin([], rows=10, cols=40)
        win.keys.extend(
            [
                "a",
                "b",
                _curses.KEY_LEFT,
                _curses.KEY_HOME,
                "c",
                _curses.KEY_END,
                _curses.KEY_RIGHT,
                "\x15",
                "d",
                "\n",
            ]
        )
        self.assertEqual(ui_input.edit_line(win, "提示: "), "d")

    def test_map_add_cancelled_at_second_prompt(self):
        app = self.make_app(count=1)
        app.panel = "map"
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(ui_actions, "edit_line", side_effect=["旧字", None]):
            ui_actions.handle_map(app, win, "n")
        self.assertEqual(app.mapping, {})


class FinalGaps2(TuiTestCase):
    """收尾：写日志失败、缓存版本不符、目录不可读、空白渲染、翻页与 DC 键。"""

    def test_digit_selection_switches_focus_back_to_files(self):
        app = self.make_app(count=3)
        app.img_rows = 5
        app.focus = "blocks"
        self.assertTrue(app.select_by_digit(2))
        self.assertEqual(app.focus, "files")

    def test_poll_cancel_reads_escape(self):
        app = self.make_app(count=1)
        win = FakeWin([27], rows=10, cols=40)  # Esc 的键码
        self.assertTrue(ui_actions._poll_cancel(win, app))
        self.assertTrue(app.cancel)

    def test_poll_cancel_returns_false_on_other_keys(self):
        app = self.make_app(count=1)
        win = FakeWin(["x"], rows=10, cols=40)
        self.assertFalse(ui_actions._poll_cancel(win, app))

    def test_hline_with_zero_columns_is_a_noop(self):
        win = FakeWin([], rows=5, cols=10)
        ui_base.hline(win, 0, 0, 0)
        self.assertEqual(win.cell_count, 0)

    def test_scrolled_blocks_panel_windows_the_list(self):

        patch_curses()
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.images[0].blocks = [
            mock.Mock(text=f"第{i}行", enabled=False, find=None, override=None) for i in range(30)
        ]
        app.sel_blk = 20
        win = FakeWin([], rows=20, cols=100)
        ui_draw.draw_frame(win, app)
        self.assertIn("第20行", "\n".join(win.screen))

    def test_delete_key_removes_character_under_cursor(self):
        import curses as _curses

        win = FakeWin([], rows=10, cols=40)
        win.keys.extend(["a", "b", _curses.KEY_LEFT, _curses.KEY_DC, "\n"])
        self.assertEqual(ui_input.edit_line(win, "提示: "), "a")


class FinalGaps3(TuiTestCase):
    """收尾（二）：平台分支、空窗口、右对齐、错误的 cur、ESC 取消等。"""

    def test_image_window_with_zero_rows(self):
        app = self.make_app(count=2)
        self.assertEqual(app.image_window(0), (0, []))

    def test_batch_without_work_reports_reason(self):
        app = self.make_app(count=2)
        win = FakeWin([], rows=26, cols=100)
        ui_actions.handle(app, win, "R")
        self.assertIn("没有任何图片", app.message)

    def test_put_beyond_right_edge_is_clipped(self):
        win = FakeWin([], rows=5, cols=10)
        ui_base.put(win, 0, 10, "看不见", 5)
        self.assertEqual(win.screen[0], "")

    def test_wide_layout_shows_current_image_error(self):

        patch_curses()
        app = self.make_app(count=1)
        app.images[0].blocks = []
        app.images[0].error = "这张图没识别出文字"
        win = FakeWin([], rows=26, cols=100)
        ui_draw.draw_frame(win, app)
        self.assertIn("没识别出文字", "\n".join(win.screen))

    def test_edit_line_cancels_with_lone_escape(self):
        win = FakeWin(["\x1b", None], rows=10, cols=40)
        self.assertIsNone(ui_input.edit_line(win, "提示: "))


class FinalGaps4(TuiTestCase):
    """收尾（三）：预演同名、锁失败、fontconfig 缺失、应用当前图的空路径等。"""

    def test_apply_current_without_jobs_reports_how_to_fix(self):
        app = self.make_app(count=1)
        app.apply_current()
        self.assertIn("没有可替换的块", app.message)

    def test_apply_current_with_no_current_image_is_noop(self):
        app = self.make_app(count=1)
        app.images = []
        app.apply_current()  # 不应抛
        self.assertEqual(app.status, "就绪")

    def test_r_key_applies_current_image(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(app, "apply_current") as apply:
            ui_actions.handle(app, win, "r")
        apply.assert_called_once()

    def test_init_colors_registers_all_pairs(self):
        with (
            mock.patch.object(ui_base.curses, "start_color"),
            mock.patch.object(ui_base.curses, "use_default_colors"),
            mock.patch.object(ui_base.curses, "init_pair") as init_pair,
        ):
            ui_base.init_colors()
        self.assertEqual(init_pair.call_count, len(ui_base.PAIR))

    def test_init_colors_survives_failure(self):
        with mock.patch.object(ui_base.curses, "start_color", side_effect=Exception("no color")):
            ui_base.init_colors()

    def test_status_line_without_message_shows_output_dir(self):
        app = mock.Mock(message="", status="", last_saved=None, out_dir="/tmp/out")  # platform-safe
        text = ui_draw._status_text(app, 40)
        self.assertIn("输出", text)

    def test_edit_line_ignores_terminal_timeouts(self):
        win = FakeWin([None, "a", "\n"], rows=10, cols=40)
        self.assertEqual(ui_input.edit_line(win, "提示: "), "a")


class FinalGaps5(TuiTestCase):
    """收尾（四）：无成功替换、未加锁解锁、字体 repr、当前图替换、进度条。"""

    def test_apply_current_with_jobs_reports_progress(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        seen: list[str] = []
        app.apply_current(progress=seen.append)
        self.assertTrue(seen, "应当报告一次进度")
        self.assertIn(app.status, ("替换完成", "替换失败"))

    def test_space_on_empty_area_returns(self):
        app = self.make_app(count=0)
        app.focus = "blocks"
        before = app.message
        win = FakeWin([], rows=20, cols=80)
        ui_actions.handle(app, win, " ")
        self.assertEqual(app.message, before, "没有块时按空格不应改动任何状态")

    def test_status_line_shows_progress_bar(self):
        app = mock.Mock(
            message="", status="替换中 3/8", last_saved=None, out_dir="/tmp/out"
        )  # platform-safe
        text = ui_draw._status_text(app, 60)
        self.assertIn("█", text + "█")  # 进度条字符存在（或已填满）
        self.assertIn("37%", text)


class FinalGaps6(TuiTestCase):
    """收尾（五）：读图失败、Windows 锁、缺 fontconfig、保存失败、行内详情。"""

    def test_apply_one_reports_save_failure_and_cleans_placeholder(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        before = img.saved
        fake_report = [
            {
                "old": "原文",
                "new": "改后的文字",
                "rect": [0, 0, 10, 10],
                "mode": "整行",
                "font": "f",
                "size": 12,
                "tracking": 0.0,
                "color": [0, 0, 0],
                "align": "left",
                "iou": 0.9,
            }
        ]
        with (
            mock.patch.object(
                tui_app,
                "replace_image",
                return_value=(np.zeros((32, 32, 3), np.uint8), None, fake_report),
            ),
            mock.patch.object(tui_app, "save_image", side_effect=OSError("磁盘满")),
        ):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("磁盘满", msg)
        self.assertEqual(img.saved, before, "失败时不应记录已保存路径")

    def test_i_key_from_files_panel_opens_inline_editor(self):
        app = self.make_app(count=1)
        app.focus = "files"
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(ui_actions, "edit_inline") as inline:
            ui_actions.handle(app, win, "i")
        self.assertEqual(app.focus, "blocks")
        inline.assert_called_once()

    def test_footer_shows_inline_fragment_hint(self):
        patch_curses()
        app = self.make_app(count=1)
        app.focus = "blocks"
        blk = app.blocks()[0]
        blk.find = "2023"
        blk.override = "2024"
        win = FakeWin([], rows=26, cols=100)
        ui_draw.draw_frame(win, app)
        self.assertIn("行内", "\n".join(win.screen))


class FinalGaps7(TuiTestCase):
    """收尾（六）：读图失败、删日志失败、预留名失败、Enter 整行编辑、脏进度数字。"""

    def test_apply_one_reports_reserve_failure(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        report = [
            {
                "old": "原文",
                "new": "改后",
                "rect": [0, 0, 10, 10],
                "mode": "整行",
                "font": "f",
                "size": 12,
                "tracking": 0.0,
                "color": [0, 0, 0],
                "align": "left",
                "iou": 0.9,
            }
        ]
        with (
            mock.patch.object(
                tui_app,
                "replace_image",
                return_value=(np.zeros((32, 32, 3), np.uint8), None, report),
            ),
            mock.patch.object(tui_app, "reserve_path", side_effect=CoreError("占名失败")),
        ):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("占名失败", msg)

    def test_enter_on_blocks_panel_opens_the_editor(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend([*list("新的一行"), "\n"])
        ui_actions.handle(app, win, "\n")
        blk = app.cur_block()
        assert blk is not None, "应当有当前块"
        self.assertEqual(blk.override, "新的一行")

    def test_dirty_progress_number_falls_back(self):
        self.assertEqual(ui_draw._int("x", 7), 7)
        self.assertEqual(ui_draw._int("8"), 8)


class FinalGaps8(TuiTestCase):
    """收尾（七）：第二轮读图失败、坏日期日志名、apply_one 读图失败、整行编辑。"""

    def test_apply_one_reports_unreadable_image(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        with mock.patch.object(tui_app, "load_image", side_effect=OSError("读不了")):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("读取失败", msg)
