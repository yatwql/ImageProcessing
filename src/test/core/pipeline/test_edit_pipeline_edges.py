"""替换流水线边界：调试图写失败、span 越界、行内区间无墨迹时的回退。"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.python.cli import log_query
from src.python.core import edit, fonts, jobs, options, render, style
from src.python.core.errors import CoreError
from src.python.tui import ui_actions
from src.test._support import (
    FONT_CJK,
    FakeWin,
    TuiTestCase,
    has_cjk_font,
)


class LogQueryGaps(unittest.TestCase):
    def test_core_error_from_reader_is_reported(self):
        err = io.StringIO()
        with (
            mock.patch.object(log_query, "read_entries", side_effect=CoreError("读不了")),
            contextlib.redirect_stderr(err),
        ):
            code = log_query.main(["--log-dir", "/tmp/x"])  # platform-safe
        self.assertEqual(code, 2)
        self.assertIn("读不了", err.getvalue())


class EditGaps(unittest.TestCase):
    def test_debug_log_failure_only_warns(self):
        rgb = np.full((80, 160, 3), 255, np.uint8)
        info = {
            "mask": np.zeros((80, 160), bool),
            "ink_box": (5, 5, 100, 30),
            "text_color": (0, 0, 0),
            "stroke": 2.0,
            "stroke_core": 2.0,
            "slant": 0.0,
        }
        warnings: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            opts = options.Options(debug=tmp, log_dir=tmp, quiet=True, font=FONT_CJK)
            opts.warn = warnings.append
            with (
                mock.patch.object(edit, "analyze", return_value=info),
                mock.patch.object(edit, "record_write", side_effect=CoreError("日志满了")),
            ):
                _out, _alpha, report = edit.replace_image(
                    rgb, None, [edit.Job((5, 5, 100, 25), "原文", "新文")], opts, []
                )
        self.assertEqual(len(report), 1, "记日志失败不该影响替换结果")
        self.assertTrue(any("日志满了" in w for w in warnings))


class DebugMaskWriteFailure(unittest.TestCase):
    def test_imwrite_false_raises_core_error(self):
        from src.test._support import FONT_CJK, has_cjk_font

        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        rgb = np.full((60, 120, 3), 255, np.uint8)
        info = {
            "mask": np.zeros((60, 120), bool),
            "ink_box": (5, 5, 100, 30),
            "text_color": (0, 0, 0),
            "stroke": 2.0,
            "stroke_core": 2.0,
            "slant": 0.0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            opts = options.Options(debug=tmp, quiet=True, font=FONT_CJK)
            with (
                mock.patch.object(edit, "analyze", return_value=info),
                mock.patch.object(edit.cv2, "imwrite", return_value=False),
                self.assertRaises(CoreError),
            ):
                edit.replace_image(rgb, None, [edit.Job((5, 5, 100, 25), "原文", "新文")], opts, [])


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
                self.assertRaises(CoreError),
            ):
                edit.replace_image(
                    np.full((60, 120, 3), 255, np.uint8),
                    None,
                    [edit.Job((5, 5, 100, 25), "原文", "新文")],
                    opts,
                    [],
                )


class FinalGaps(TuiTestCase):
    """最后一批单行分支：返回值异常、父目录不可建、缓存坏 JSON、span 越界等。"""

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


class FinalGaps2(TuiTestCase):
    """收尾：写日志失败、缓存版本不符、目录不可读、空白渲染、翻页与 DC 键。"""

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


class FinalGaps3(TuiTestCase):
    """收尾（二）：平台分支、空窗口、右对齐、错误的 cur、ESC 取消等。"""

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


class FinalGaps4(TuiTestCase):
    """收尾（三）：预演同名、锁失败、fontconfig 缺失、应用当前图的空路径等。"""

    def test_render_failure_during_coarse_search(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            self.assertIsNone(style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1))


class FinalGaps6(TuiTestCase):
    """收尾（五）：读图失败、Windows 锁、缺 fontconfig、保存失败、行内详情。"""

    def test_coarse_search_logs_render_failure_and_continues(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            result = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1)
        self.assertIsNone(result, "所有候选都渲染失败时应返回 None")


class FinalGaps8(TuiTestCase):
    """收尾（七）：第二轮读图失败、坏日期日志名、apply_one 读图失败、整行编辑。"""

    def test_edit_current_sets_whole_line_override(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend([*list("整行新文字"), "\n"])
        ui_actions.edit_current(app, win)
        blk = app.cur_block()
        assert blk is not None
        self.assertEqual(blk.override, "整行新文字")


class AreaJobs(unittest.TestCase):
    def test_area_spec_without_equal_is_rejected(self):
        from src.python.core.errors import CoreError

        with self.assertRaises(CoreError):
            jobs.area_jobs(["10,10,100,30"])

    def test_area_spec_with_bad_numbers_is_rejected(self):
        from src.python.core.errors import CoreError

        with self.assertRaises(CoreError):
            jobs.area_jobs(["a,b,c,d=新文字"])

    def test_area_spec_parses_rect_and_text(self):
        out = jobs.area_jobs(["10,20,100,30=新文字"])
        self.assertEqual(out[0].rect, (10, 20, 100, 30))
        self.assertEqual(out[0].new, "新文字")


class ColorParsing(unittest.TestCase):
    def test_hex_and_rgb_forms_agree(self):
        self.assertEqual(options.parse_color("#C00000"), (192, 0, 0))
        self.assertEqual(options.parse_color("192,0,0"), (192, 0, 0))
        self.assertEqual(options.parse_color("#c00"), (204, 0, 0))

    def test_garbage_is_rejected_with_core_error(self):
        for bad in ("zzz", "#12345", "1,2", ""):
            with self.subTest(spec=bad), self.assertRaises(CoreError):
                options.parse_color(bad)
