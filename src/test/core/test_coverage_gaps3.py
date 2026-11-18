"""覆盖率收尾：把最后二十几行"只有出错才会走到"的分支补齐。

这些行分别是：占位文件清理、同路径拒绝覆盖、日志/目录不可写、缓存读写失败、
OCR 依赖缺失、空 key、空行渲染、样式面板跳转、输入行 Ctrl-U 等。
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.python import bootstrap, config
from src.python.cli import main as cli_main
from src.python.core import audit, edit, fonts, image, match, ocr, options, render, style
from src.python.core.errors import CoreError
from src.python.tui import app as tui_app
from src.python.tui import ui_actions, ui_base, ui_draw, ui_input
from src.test._support import FONT_CJK, FakeWin, TuiTestCase, has_cjk_font, patch_curses


class ProbeOserror(unittest.TestCase):
    def test_probe_failure_on_existing_interpreter_reports_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_py = Path(tmp) / "python"
            fake_py.write_text("", encoding="utf-8")
            with mock.patch.object(bootstrap.subprocess, "run", side_effect=OSError("boom")):
                self.assertEqual(bootstrap.missing_modules(fake_py), ["venv"])


class ConfigAlign(unittest.TestCase):
    def test_align_default_applied_when_auto(self):
        # Options() 的默认 align 就是 "auto"，正好命中"还没显式设置过"的分支
        opts = options.Options()
        with mock.patch.object(config, "option_defaults", return_value={"align": "left"}):
            config.apply_to_options(opts)
        self.assertEqual(opts.align, "left")


class SameFileRefusal(unittest.TestCase):
    def test_output_equal_to_input_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, src)
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            err = io.StringIO()
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[src]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli_main.main([src, "--map", "原文=新文", "-o", src])
        self.assertEqual(code, 3)
        self.assertIn("拒绝覆盖", err.getvalue())


class AuditWriteFailure(unittest.TestCase):
    def test_oserror_while_opening_log_becomes_core_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(audit.os, "open", side_effect=OSError("denied")):
                with self.assertRaises(CoreError):
                    audit.record_write("a.png", "b.png", (), log_dir=tmp)


class DebugDirFailure(unittest.TestCase):
    def test_uncreatable_debug_dir_raises_core_error(self):
        from src.test._support import has_cjk_font

        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "blocker"
            blocker.write_text("not a dir", encoding="utf-8")
            opts = options.Options(debug=str(blocker / "sub"), quiet=True, font=FONT_CJK)
            info = {
                "mask": np.zeros((60, 120), bool),
                "ink_box": (5, 5, 100, 30),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            with (
                mock.patch.object(edit, "analyze", return_value=info),
                mock.patch.object(edit.os, "makedirs", side_effect=OSError("denied")),
            ):
                with self.assertRaises(CoreError):
                    edit.replace_image(
                        np.full((60, 120, 3), 255, np.uint8),
                        None,
                        [edit.Job((5, 5, 100, 25), "原文", "新文")],
                        opts,
                        [],
                    )


class FontCacheFailure(unittest.TestCase):
    def test_unreadable_cache_is_ignored(self):
        with mock.patch.object(fonts, "cache_file", return_value="/proc/nope/fonts.json"):
            self.assertEqual(fonts._read_cache(), {})

    def test_unwritable_cache_does_not_raise(self):
        with mock.patch.object(fonts, "cache_file", return_value="/proc/nope/fonts.json"):
            fonts._write_cache({"k": []})  # 不抛即通过


class ReserveFailure(unittest.TestCase):
    def test_oserror_on_reserve_is_a_core_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(image.os, "open", side_effect=OSError("denied")):
                with self.assertRaises(CoreError):
                    image.reserve_path(os.path.join(tmp, "x.png"))


class EmptyMappingKey(unittest.TestCase):
    def test_empty_key_is_skipped(self):
        regions = [{"text": "年度报告", "rect": (0, 0, 100, 30), "score": 1.0}]
        self.assertEqual(match.plan_jobs(regions, {"": "新"}, warn=False), [])


class OcrImportFailure(unittest.TestCase):
    def test_missing_ocr_package_raises_core_error(self):
        import builtins
        import threading

        saved = threads = threading.local()
        del saved
        original_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name.startswith("rapidocr"):
                raise ImportError("no rapidocr")
            return original_import(name, *args, **kwargs)

        with (
            mock.patch.object(ocr._LOCAL, "engine", None, create=True),
            mock.patch.object(builtins, "__import__", side_effect=guarded),
        ):
            with self.assertRaises(CoreError):
                ocr._engine()
        del threads


class VerboseLog(unittest.TestCase):
    def test_verbose_env_enables_logging(self):
        err = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"TEXT_REPLACE_VERBOSE": "1"}),
            contextlib.redirect_stderr(err),
        ):
            options._log("很啰嗦")
        self.assertIn("很啰嗦", err.getvalue())


class BlankOnlyText(unittest.TestCase):
    def test_text_with_only_blank_lines_draws_nothing(self):
        canvas = np.full((40, 80, 3), 255, np.uint8)
        before = canvas.copy()
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        out = render.draw_text(
            canvas,
            "\n",
            fonts.FontFace(FONT_CJK, 0),
            20,
            0.0,
            (0, 0, 0),
            (5.0, 75.0, 5.0, 35.0),
            "left",
        )
        self.assertTrue(np.array_equal(out, before), "全是空行时不该画任何东西")


class RefineRenderFailure(unittest.TestCase):
    def test_render_failure_during_refinement_is_skipped(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        text = "国国"
        arr, box, _pad = render.render_line(text, face, 40, tracking=0.0)
        mask = np.zeros((200, 400), np.uint8)
        top, left = 20, 20
        h, w = arr.shape
        mask[top : top + h, left : left + w] = arr
        ink_box = (left + box[0], top + box[1], left + box[2], top + box[3])

        real = style.render_line
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 12:  # 粗筛通过、精修阶段开始报错
                raise OSError("渲染失败")
            return real(*args, **kwargs)

        with mock.patch.object(style, "render_line", side_effect=flaky):
            found = style.fit_font(text, mask > 127, ink_box, [face], 1)
        self.assertTrue(calls["n"] > 12, "应进入精修阶段")
        del found  # 结果可有可无，关键是不崩


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


if __name__ == "__main__":
    unittest.main()


class FinalGaps(TuiTestCase):
    """最后一批单行分支：返回值异常、父目录不可建、缓存坏 JSON、span 越界等。"""

    def test_probe_nonzero_returncode_reports_venv(self):
        fake = mock.Mock(returncode=1, stdout="")
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "python"
            py.write_text("", encoding="utf-8")
            with mock.patch.object(bootstrap.subprocess, "run", return_value=fake):
                self.assertEqual(bootstrap.missing_modules(py), ["venv"])

    def test_reserve_reports_uncreatable_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "no", "such", "dir", "x.png")
            with mock.patch.object(image.os, "makedirs", side_effect=OSError("denied")):
                with self.assertRaises(CoreError):
                    image.reserve_path(target)

    def test_bad_cache_json_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fonts.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{坏的")
            with mock.patch.object(fonts, "cache_file", return_value=path):
                self.assertEqual(fonts._read_cache(), {})

    def test_span_beyond_text_falls_back_to_whole_line(self):
        rgb = np.full((80, 200, 3), 255, np.uint8)
        info = {
            "mask": np.zeros((80, 200), bool),
            "ink_box": (10, 10, 150, 40),
            "text_color": (0, 0, 0),
            "stroke": 2.0,
            "stroke_core": 2.0,
            "slant": 0.0,
        }
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        opts = options.Options(quiet=True, font=FONT_CJK)
        with mock.patch.object(edit, "analyze", return_value=info):
            _out, _alpha, report = edit.replace_image(
                rgb, None, [edit.Job((10, 10, 150, 30), "国", "新", span=(0, 9))], opts, []
            )
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["mode"], "整行", "span 越界时应退回整行替换")

    def test_draw_text_clips_lines_outside_the_canvas(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        canvas = np.full((30, 30, 3), 255, np.uint8)
        before = canvas.copy()
        out = render.draw_text(
            canvas,
            "国",
            fonts.FontFace(FONT_CJK, 0),
            20,
            0.0,
            (0, 0, 0),
            (500.0, 600.0, 500.0, 560.0),
            "left",
        )
        self.assertTrue(np.array_equal(out, before), "完全在画布外时不该落笔")

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

    def test_log_write_failure_becomes_core_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(audit.os, "write", side_effect=OSError("disk full")):
                with self.assertRaises(CoreError):
                    audit.record_write("a.png", "b.png", (), log_dir=tmp)

    def test_cache_with_other_version_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fonts.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"version": 0, "entries": {}}')
            with mock.patch.object(fonts, "cache_file", return_value=path):
                self.assertEqual(fonts._read_cache(), {})

    def test_collect_images_reports_unreadable_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(image.os, "listdir", side_effect=OSError("denied")):
                with self.assertRaises(CoreError):
                    image.collect_images(tmp)

    def test_blank_render_in_refinement_is_skipped(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        arr, box, _pad = render.render_line("国国", face, 40, tracking=0.0)
        mask = np.zeros((200, 400), np.uint8)
        h, w = arr.shape
        mask[20 : 20 + h, 20 : 20 + w] = arr
        ink_box = (20 + box[0], 20 + box[1], 20 + box[2], 20 + box[3])
        with mock.patch.object(style, "_bin", return_value=np.zeros((10, 10), bool)):
            result = style.fit_font("国国", mask > 127, ink_box, [face], 1)
        self.assertIsNone(result, "所有候选都渲染成空白时应返回 None")

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

    def test_unlock_windows_branch(self):
        # 用真实临时文件描述符：git 钩子里 fd 3 是 git 自己的管道，
        # lseek 会失败，测试会误红（这类"写死 fd"的用例本身就是隐患）
        with tempfile.TemporaryFile() as handle:
            fd = handle.fileno()
            fake_win = mock.Mock(LK_UNLCK=1)
            with (
                mock.patch.object(audit, "fcntl", None),
                mock.patch.object(audit, "_winlock", return_value=fake_win),
            ):
                audit._unlock(fd, locked=True)
        fake_win.locking.assert_called_once()

    def test_unlock_windows_branch_without_msvcrt(self):
        with (
            tempfile.TemporaryFile() as handle,
            mock.patch.object(audit, "fcntl", None),
            mock.patch.object(audit, "_winlock", return_value=None),
        ):
            audit._unlock(handle.fileno(), locked=True)  # 直接返回即可

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

    def test_reserve_failure_in_cli_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, src)
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            err = io.StringIO()
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[src]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                mock.patch.object(cli_main, "reserve_path", side_effect=CoreError("占名失败")),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli_main.main([src, "--map", "原文=新文", "--out-dir", out_dir])
        self.assertEqual(code, 3)
        self.assertIn("占名失败", err.getvalue())

    def test_font_signature_tolerates_unreadable_file(self):
        with mock.patch.object(fonts.os, "stat", side_effect=OSError("denied")):
            signature = fonts._file_signature(["/no/such/font.ttf"])
        self.assertTrue(signature, "读不到字体时也要给出一个签名，而不是崩")

    def test_draw_text_right_alignment(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        canvas = np.full((80, 200, 3), 255, np.uint8)
        before = canvas.copy()
        out = render.draw_text(
            canvas,
            "国",
            fonts.FontFace(FONT_CJK, 0),
            20,
            0.0,
            (0, 0, 0),
            (10.0, 190.0, 10.0, 70.0),
            "right",
        )
        self.assertTrue((out != before).any(), "右对齐也要真的画出来")

    def test_inline_span_without_ink_falls_back_to_ink_box(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        rgb = np.full((80, 200, 3), 255, np.uint8)
        info = {
            "mask": np.zeros((80, 200), bool),
            "ink_box": (10, 10, 150, 40),
            "text_color": (0, 0, 0),
            "stroke": 2.0,
            "stroke_core": 2.0,
            "slant": 0.0,
        }
        opts = options.Options(quiet=True, font=FONT_CJK)
        with mock.patch.object(edit, "analyze", return_value=info):
            _out, _alpha, report = edit.replace_image(
                rgb, None, [edit.Job((10, 10, 150, 30), "国国", "新", span=(0, 1))], opts, []
            )
        self.assertEqual(len(report), 1)

    def test_refinement_skips_blank_render(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        arr, box, _pad = render.render_line("国国", face, 40, tracking=0.0)
        mask = np.zeros((200, 400), np.uint8)
        h, w = arr.shape
        mask[20 : 20 + h, 20 : 20 + w] = arr
        ink_box = (20 + box[0], 20 + box[1], 20 + box[2], 20 + box[3])
        real_bin = style._bin
        calls = {"n": 0}

        def flaky_bin(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 2:  # 粗筛正常、精修时渲染成空白
                return np.zeros((10, 10), bool)
            return real_bin(*args, **kwargs)

        with mock.patch.object(style, "_bin", side_effect=flaky_bin):
            style.fit_font("国国", mask > 127, ink_box, [face], 1)
        self.assertGreater(calls["n"], 2)


class LockWithoutAnyBackend(unittest.TestCase):
    """既没有 fcntl 也没有 msvcrt（极端环境）：`_lock` 返回 False，写日志照常进行。"""

    def test_lock_returns_false_without_any_backend(self):
        with (
            tempfile.TemporaryFile() as handle,
            mock.patch.object(audit, "fcntl", None),
            mock.patch.object(audit, "_winlock", return_value=None),
        ):
            self.assertFalse(audit._lock(handle.fileno()))


if __name__ == "__main__":
    unittest.main()
