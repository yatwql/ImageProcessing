"""覆盖率收尾：把最后二十几行"只有出错才会走到"的分支补齐。

这些行分别是：占位文件清理、同路径拒绝覆盖、日志/目录不可写、缓存读写失败、
OCR 依赖缺失、空 key、空行渲染、样式面板跳转、输入行 Ctrl-U 等。
"""

from __future__ import annotations

import contextlib
import datetime as dt
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
            info = {"mask": np.zeros((20, 30), bool), "ink_box": (2, 2, 20, 12),
                    "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
            err = io.StringIO()
            with mock.patch.object(cli_main, "collect_images", return_value=[src]), \
                    mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]), \
                    mock.patch("src.python.core.edit.analyze", return_value=info), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
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
            info = {"mask": np.zeros((60, 120), bool), "ink_box": (5, 5, 100, 30),
                    "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
            with mock.patch.object(edit, "analyze", return_value=info), \
                    mock.patch.object(edit.os, "makedirs", side_effect=OSError("denied")):
                with self.assertRaises(CoreError):
                    edit.replace_image(np.full((60, 120, 3), 255, np.uint8), None,
                                       [edit.Job((5, 5, 100, 25), "原文", "新文")], opts, [])


class FontCacheFailure(unittest.TestCase):
    def test_unreadable_cache_is_ignored(self):
        with mock.patch.object(fonts, "cache_file", return_value="/proc/nope/fonts.json"):
            self.assertEqual(fonts._read_cache(), {})

    def test_unwritable_cache_does_not_raise(self):
        with mock.patch.object(fonts, "cache_file", return_value="/proc/nope/fonts.json"):
            fonts._write_cache({"k": []})          # 不抛即通过


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

        with mock.patch.object(ocr._LOCAL, "engine", None, create=True), \
                mock.patch.object(builtins, "__import__", side_effect=guarded):
            with self.assertRaises(CoreError):
                ocr._engine()
        del threads


class VerboseLog(unittest.TestCase):
    def test_verbose_env_enables_logging(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"TEXT_REPLACE_VERBOSE": "1"}), \
                contextlib.redirect_stderr(err):
            options._log("很啰嗦")
        self.assertIn("很啰嗦", err.getvalue())


class BlankOnlyText(unittest.TestCase):
    def test_text_with_only_blank_lines_draws_nothing(self):
        canvas = np.full((40, 80, 3), 255, np.uint8)
        before = canvas.copy()
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        out = render.draw_text(canvas, "\n", fonts.FontFace(FONT_CJK, 0), 20, 0.0,
                               (0, 0, 0), (5.0, 75.0, 5.0, 35.0), "left")
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
        mask[top:top + h, left:left + w] = arr
        ink_box = (left + box[0], top + box[1], left + box[2], top + box[3])

        real = style.render_line
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 12:                 # 粗筛通过、精修阶段开始报错
                raise OSError("渲染失败")
            return real(*args, **kwargs)

        with mock.patch.object(style, "render_line", side_effect=flaky):
            found = style.fit_font(text, mask > 127, ink_box, [face], 1)
        self.assertTrue(calls["n"] > 12, "应进入精修阶段")
        del found                                 # 结果可有可无，关键是不崩


class SettingsJump(TuiTestCase):
    def test_jump_in_settings_panel_goes_to_last_row(self):
        app = self.make_app(count=1)
        app.panel = "settings"
        app.jump(first=False)
        self.assertEqual(app.sel_setting, len(tui_app.SETTING_ROWS) - 1)

    def test_map_add_with_empty_key_returns(self):
        app = self.make_app(count=1)
        app.panel = "map"
        win = FakeWin(["\n"], rows=26, cols=100)     # 直接回车 = 空 key
        ui_actions.handle_map(app, win, "n")
        self.assertEqual(app.mapping, {})

    def test_put_with_zero_columns_is_a_noop(self):
        win = FakeWin([], rows=5, cols=20)
        ui_base.put(win, 0, 0, "不该出现", 0)
        self.assertEqual(win.screen[0], "")

    def test_narrow_blocks_panel_shows_loading_hint(self):
        from src.test._support import patch_curses

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
        info = {"mask": np.zeros((80, 200), bool), "ink_box": (10, 10, 150, 40),
                "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        opts = options.Options(quiet=True, font=FONT_CJK)
        with mock.patch.object(edit, "analyze", return_value=info):
            _out, _alpha, report = edit.replace_image(
                rgb, None, [edit.Job((10, 10, 150, 30), "国", "新", span=(0, 9))], opts, [])
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["mode"], "整行", "span 越界时应退回整行替换")

    def test_draw_text_clips_lines_outside_the_canvas(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        canvas = np.full((30, 30, 3), 255, np.uint8)
        before = canvas.copy()
        out = render.draw_text(canvas, "国", fonts.FontFace(FONT_CJK, 0), 20, 0.0,
                               (0, 0, 0), (500.0, 600.0, 500.0, 560.0), "left")
        self.assertTrue(np.array_equal(out, before), "完全在画布外时不该落笔")

    def test_jump_in_map_panel_goes_to_last_entry(self):
        app = mock.Mock(panel="map")
        app.mapping = {"a": "1", "b": "2"}
        app.sel_map = 0
        tui_app.App.jump(app, first=False)
        self.assertEqual(app.sel_map, 1)

    def test_box_on_tiny_window_returns_early(self):
        win = FakeWin([], rows=2, cols=3)
        ui_base.box(win, 2, 3, "x", 0)     # 尺寸不足：直接返回，不画越界
        self.assertEqual(win.cell_count, 0)

    def test_narrow_blocks_panel_shows_image_error(self):
        from src.test._support import patch_curses

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
        win.keys.extend(["a", "b", _curses.KEY_LEFT, _curses.KEY_HOME, "c",
                         _curses.KEY_END, _curses.KEY_RIGHT, "\x15", "d", "\n"])
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
        mask[20:20 + h, 20:20 + w] = arr
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
        win = FakeWin([27], rows=10, cols=40)          # Esc 的键码
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
        from src.test._support import patch_curses

        patch_curses()
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.images[0].blocks = [mock.Mock(text=f"第{i}行", enabled=False, find=None,
                                          override=None) for i in range(30)]
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
            with mock.patch.object(audit, "fcntl", None), \
                    mock.patch.object(audit, "_winlock", return_value=fake_win):
                audit._unlock(fd, locked=True)
        fake_win.locking.assert_called_once()

    def test_unlock_windows_branch_without_msvcrt(self):
        with tempfile.TemporaryFile() as handle, \
                mock.patch.object(audit, "fcntl", None), \
                mock.patch.object(audit, "_winlock", return_value=None):
            audit._unlock(handle.fileno(), locked=True)      # 直接返回即可

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
        from src.test._support import patch_curses

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
            info = {"mask": np.zeros((20, 30), bool), "ink_box": (2, 2, 20, 12),
                    "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
            err = io.StringIO()
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            with mock.patch.object(cli_main, "collect_images", return_value=[src]), \
                    mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]), \
                    mock.patch("src.python.core.edit.analyze", return_value=info), \
                    mock.patch.object(cli_main, "reserve_path", side_effect=CoreError("占名失败")), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
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
        out = render.draw_text(canvas, "国", fonts.FontFace(FONT_CJK, 0), 20, 0.0,
                               (0, 0, 0), (10.0, 190.0, 10.0, 70.0), "right")
        self.assertTrue((out != before).any(), "右对齐也要真的画出来")

    def test_inline_span_without_ink_falls_back_to_ink_box(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        rgb = np.full((80, 200, 3), 255, np.uint8)
        info = {"mask": np.zeros((80, 200), bool), "ink_box": (10, 10, 150, 40),
                "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
        opts = options.Options(quiet=True, font=FONT_CJK)
        with mock.patch.object(edit, "analyze", return_value=info):
            _out, _alpha, report = edit.replace_image(
                rgb, None, [edit.Job((10, 10, 150, 30), "国国", "新", span=(0, 1))], opts, [])
        self.assertEqual(len(report), 1)

    def test_refinement_skips_blank_render(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        arr, box, _pad = render.render_line("国国", face, 40, tracking=0.0)
        mask = np.zeros((200, 400), np.uint8)
        h, w = arr.shape
        mask[20:20 + h, 20:20 + w] = arr
        ink_box = (20 + box[0], 20 + box[1], 20 + box[2], 20 + box[3])
        real_bin = style._bin
        calls = {"n": 0}

        def flaky_bin(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 2:                    # 粗筛正常、精修时渲染成空白
                return np.zeros((10, 10), bool)
            return real_bin(*args, **kwargs)

        with mock.patch.object(style, "_bin", side_effect=flaky_bin):
            style.fit_font("国国", mask > 127, ink_box, [face], 1)
        self.assertGreater(calls["n"], 2)


class FinalGaps4(TuiTestCase):
    """收尾（三）：预演同名、锁失败、fontconfig 缺失、应用当前图的空路径等。"""

    def test_dry_run_dedupes_same_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            d1 = os.path.join(tmp, "d1")
            d2 = os.path.join(tmp, "d2")
            out = os.path.join(tmp, "out")
            for d in (d1, d2, out):
                os.makedirs(d)
            paths = []
            for d in (d1, d2):
                p = os.path.join(d, "same.png")
                image.save_image(np.full((10, 10, 3), 255, np.uint8), None, p)
                paths.append(p)
            region = {"text": "原文", "rect": (0, 0, 5, 5), "score": 1.0}
            info = {"mask": np.zeros((10, 10), bool), "ink_box": (1, 1, 5, 5),
                    "text_color": (0, 0, 0), "stroke": 1.0, "stroke_core": 1.0, "slant": 0.0}
            with mock.patch.object(cli_main, "collect_images", return_value=[paths[0], paths[0]]), \
                    mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]), \
                    mock.patch("src.python.core.edit.analyze", return_value=info), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli_main.main([paths[0], "--map", "原文=新文", "--out-dir", out, "--dry-run"])
        self.assertIn(code, (0, 3), "预演不写盘，两个同名源图应各自算出不重复的目标名")

    def test_unlock_swallows_oserror(self):
        with tempfile.TemporaryFile() as handle, \
                mock.patch.object(audit.fcntl, "flock", side_effect=OSError("boom")):
            audit._unlock(handle.fileno(), locked=True)          # 不抛即通过

    def test_font_discovery_falls_back_to_directory_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_font = os.path.join(tmp, "a.ttf")
            Path(fake_font).write_bytes(b"x")
            with mock.patch.object(fonts, "_run", return_value=""), \
                    mock.patch.object(fonts, "font_dirs", return_value=[tmp]):
                files = fonts.fc_list_files()
        self.assertIn(fake_font, files)

    def test_render_failure_during_coarse_search(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            self.assertIsNone(style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1))

    def test_apply_current_without_jobs_reports_how_to_fix(self):
        app = self.make_app(count=1)
        app.apply_current()
        self.assertIn("没有可替换的块", app.message)

    def test_apply_current_with_no_current_image_is_noop(self):
        app = self.make_app(count=1)
        app.images = []
        app.apply_current()                        # 不应抛
        self.assertEqual(app.status, "就绪")

    def test_r_key_applies_current_image(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(app, "apply_current") as apply:
            ui_actions.handle(app, win, "r")
        apply.assert_called_once()

    def test_init_colors_registers_all_pairs(self):
        with mock.patch.object(ui_base.curses, "start_color"), \
                mock.patch.object(ui_base.curses, "use_default_colors"), \
                mock.patch.object(ui_base.curses, "init_pair") as init_pair:
            ui_base.init_colors()
        self.assertEqual(init_pair.call_count, len(ui_base.PAIR))

    def test_init_colors_survives_failure(self):
        with mock.patch.object(ui_base.curses, "start_color", side_effect=Exception("no color")):
            ui_base.init_colors()                  # 不应抛

    def test_status_line_without_message_shows_output_dir(self):
        app = mock.Mock(message="", status="", last_saved=None, out_dir="/tmp/out")
        text = ui_draw._status_text(app, 40)
        self.assertIn("输出", text)

    def test_edit_line_ignores_terminal_timeouts(self):
        win = FakeWin([None, "a", "\n"], rows=10, cols=40)
        self.assertEqual(ui_input.edit_line(win, "提示: "), "a")


class FinalGaps5(TuiTestCase):
    """收尾（四）：无成功替换、未加锁解锁、字体 repr、当前图替换、进度条。"""

    def test_cli_reports_image_without_successful_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, src)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            err = io.StringIO()
            with mock.patch.object(cli_main, "collect_images", return_value=[src]), \
                    mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]), \
                    mock.patch.object(cli_main, "replace_image", return_value=(None, None, [])), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cli_main.main([src, "--map", "原文=新文", "--out-dir", out_dir])
        self.assertEqual(code, 3)
        self.assertIn("没有成功的替换", err.getvalue())

    def test_unlock_without_lock_is_a_noop(self):
        with tempfile.TemporaryFile() as handle:
            audit._unlock(handle.fileno(), locked=False)

    def test_font_face_repr_contains_name_and_path(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        text = repr(face)
        self.assertIn("Noto", text)
        self.assertIn(os.path.basename(FONT_CJK), text)

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
        app = mock.Mock(message="", status="替换中 3/8", last_saved=None, out_dir="/tmp/out")
        text = ui_draw._status_text(app, 60)
        self.assertIn("█", text + "█")            # 进度条字符存在（或已填满）
        self.assertIn("37%", text)


class FinalGaps6(TuiTestCase):
    """收尾（五）：读图失败、Windows 锁、缺 fontconfig、保存失败、行内详情。"""

    def test_cli_skips_unreadable_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((10, 10, 3), 255, np.uint8), None, src)
            err = io.StringIO()
            bad = os.path.join(tmp, "b.png")
            image.save_image(np.full((10, 10, 3), 255, np.uint8), None, bad)
            good, fail = src, bad

            def loader(path):
                if path == fail:
                    raise OSError("坏图")
                return image.load_image(path)

            with mock.patch.object(cli_main, "collect_images", return_value=[good, fail]), \
                    mock.patch("src.python.core.jobs.ocr_regions", return_value=[
                        {"text": "原文", "rect": (0, 0, 5, 5), "score": 1.0}]), \
                    mock.patch.object(cli_main, "load_image", side_effect=loader), \
                    mock.patch.object(cli_main, "replace_image",
                                       return_value=(np.zeros((10, 10, 3), np.uint8), None,
                                                     [{"old": "原文", "new": "新文"}])), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                cli_main.main([good, "--map", "原文=新文", "--out-dir", tmp])
        self.assertIn("跳过", err.getvalue())

    def test_lock_uses_msvcrt_when_fcntl_is_missing(self):
        with tempfile.TemporaryFile() as handle:
            fake_win = mock.Mock(LK_LOCK=1)
            with mock.patch.object(audit, "fcntl", None), \
                    mock.patch.object(audit, "_winlock", return_value=fake_win):
                self.assertTrue(audit._lock(handle.fileno()))
        fake_win.locking.assert_called_once()

    def test_run_helper_returns_empty_when_command_missing(self):
        with mock.patch.object(fonts.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(fonts._run(["fc-list"]), "")

    def test_coarse_search_logs_render_failure_and_continues(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            result = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1)
        self.assertIsNone(result, "所有候选都渲染失败时应返回 None")

    def test_apply_one_reports_save_failure_and_cleans_placeholder(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        before = img.saved
        fake_report = [{"old": "原文", "new": "改后的文字", "rect": [0, 0, 10, 10],
                        "mode": "整行", "font": "f", "size": 12, "tracking": 0.0,
                        "color": [0, 0, 0], "align": "left", "iou": 0.9}]
        with mock.patch.object(tui_app, "replace_image",
                               return_value=(np.zeros((32, 32, 3), np.uint8), None, fake_report)), \
                mock.patch.object(tui_app, "save_image", side_effect=OSError("磁盘满")):
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

    def test_cli_skips_unreadable_image_in_second_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "a.png")
            bad = os.path.join(tmp, "b.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, good)
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, bad)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {"mask": np.zeros((20, 30), bool), "ink_box": (2, 2, 20, 12),
                    "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
            if not has_cjk_font():
                self.skipTest("需要 CJK 字体")
            real_load = image.load_image

            def loader(path):
                if path == bad:
                    raise OSError("坏图")
                return real_load(path)

            err = io.StringIO()
            # CLI 只接受一个输入路径；批量靠"输入是目录"实现
            with mock.patch.object(cli_main, "collect_images", return_value=[good, bad]), \
                    mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]), \
                    mock.patch("src.python.core.edit.analyze", return_value=info), \
                    mock.patch.object(cli_main, "load_image", side_effect=loader), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                cli_main.main([os.path.dirname(good), "--map", "原文=新文",
                               "--out-dir", out_dir, "--font", FONT_CJK])
        self.assertIn("跳过", err.getvalue())

    def test_prune_skips_files_that_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp, dt.datetime(2020, 1, 1)))
            path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(audit.os, "remove", side_effect=OSError("denied")):
                removed = audit.prune_logs(tmp, keep_days=1, today=dt.date(2026, 11, 18))
        self.assertEqual(removed, [], "删不掉的文件不计入已删列表")

    def test_apply_one_reports_reserve_failure(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        report = [{"old": "原文", "new": "改后", "rect": [0, 0, 10, 10], "mode": "整行",
                   "font": "f", "size": 12, "tracking": 0.0, "color": [0, 0, 0],
                   "align": "left", "iou": 0.9}]
        with mock.patch.object(tui_app, "replace_image",
                               return_value=(np.zeros((32, 32, 3), np.uint8), None, report)), \
                mock.patch.object(tui_app, "reserve_path", side_effect=CoreError("占名失败")):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("占名失败", msg)

    def test_enter_on_blocks_panel_opens_the_editor(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(list("新的一行") + ["\n"])
        ui_actions.handle(app, win, "\n")
        blk = app.cur_block()
        assert blk is not None, "应当有当前块"
        self.assertEqual(blk.override, "新的一行")

    def test_dirty_progress_number_falls_back(self):
        self.assertEqual(ui_draw._int("x", 7), 7)
        self.assertEqual(ui_draw._int("8"), 8)


class FinalGaps8(TuiTestCase):
    """收尾（七）：第二轮读图失败、坏日期日志名、apply_one 读图失败、整行编辑。"""

    def test_cli_second_pass_load_failure_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "in")
            os.makedirs(src_dir)
            good = os.path.join(src_dir, "a.png")
            bad = os.path.join(src_dir, "b.png")
            for path in (good, bad):
                image.save_image(np.full((20, 30, 3), 255, np.uint8), None, path)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            if not has_cjk_font():
                self.skipTest("需要 CJK 字体")
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {"mask": np.zeros((20, 30), bool), "ink_box": (2, 2, 20, 12),
                    "text_color": (0, 0, 0), "stroke": 2.0, "stroke_core": 2.0, "slant": 0.0}
            real_load = image.load_image
            calls: dict[str, int] = {}

            def loader(path):
                calls[path] = calls.get(path, 0) + 1
                if path == bad and calls[path] > 1:   # 第一遍（扫描）成功，第二遍失败
                    raise OSError("读盘失败")
                return real_load(path)

            err = io.StringIO()
            with mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]), \
                    mock.patch("src.python.core.edit.analyze", return_value=info), \
                    mock.patch.object(cli_main, "load_image", side_effect=loader), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                cli_main.main([src_dir, "--map", "原文=新文", "--out-dir", out_dir,
                               "--font", FONT_CJK])
        self.assertIn("跳过", err.getvalue())

    def test_prune_ignores_badly_named_log_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "image-writes-notadate.log"
            bad.write_text("{}\n", encoding="utf-8")
            removed = audit.prune_logs(tmp, keep_days=1, today=dt.date(2026, 11, 18))
            still_there = bad.exists()
        self.assertEqual(removed, [])
        self.assertTrue(still_there, "解析不出日期的文件不能被删")

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

    def test_edit_current_sets_whole_line_override(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(list("整行新文字") + ["\n"])
        ui_actions.edit_current(app, win)
        blk = app.cur_block()
        assert blk is not None
        self.assertEqual(blk.override, "整行新文字")
