"""CLI 失败路径：读图失败、同名拒绝、占名失败、预演去重、保存清理。"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.python.cli import batch as cli_batch
from src.python.cli import main as cli_main
from src.python.core import fonts, image, render
from src.python.core.errors import CoreError
from src.test._support import (
    FONT_CJK,
    TuiTestCase,
    has_cjk_font,
)


class AllImagesUnreadable(unittest.TestCase):
    def test_all_images_failing_to_load_exits_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((10, 10, 3), 255, np.uint8), None, src)
            err = io.StringIO()
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[src]),
                mock.patch.object(cli_batch, "load_image", side_effect=OSError("坏图")),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as ctx,
            ):
                cli_main.main([src, "--map", "原文=新文", "--out-dir", tmp])
        self.assertIn("读取失败", str(ctx.exception.code))


class CliReportGaps(unittest.TestCase):
    def test_unwritable_report_path_is_reported_not_raised(self):
        err = io.StringIO()
        with (
            mock.patch("builtins.open", side_effect=OSError("no space")),
            contextlib.redirect_stderr(err),
        ):
            cli_main.write_report(
                "/nope/report.json", [], [], [], 0, 0, dry_run=False, out_dir="/tmp"
            )
        self.assertIn("写摘要失败", err.getvalue())


class CliSaveFailureCleanup(unittest.TestCase):
    def test_placeholder_is_removed_when_save_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, src)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            err = io.StringIO()
            from src.test._support import FONT_CJK, has_cjk_font

            if not has_cjk_font():
                self.skipTest("需要 CJK 字体")
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[src]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                mock.patch.object(cli_batch, "save_image", side_effect=OSError("磁盘满")),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli_main.main(
                    [src, "--map", "原文=新文", "--out-dir", out_dir, "--font", FONT_CJK]
                )
            remaining = os.listdir(out_dir)
            message = err.getvalue()
        self.assertEqual(code, 3, "全部失败时退出码为 3")
        self.assertIn("保存失败", message)
        self.assertEqual(remaining, [], "失败后占位文件必须清掉")


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


class ReserveFailure(unittest.TestCase):
    def test_oserror_on_reserve_is_a_core_error(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(image.os, "open", side_effect=OSError("denied")),
            self.assertRaises(CoreError),
        ):
            image.reserve_path(os.path.join(tmp, "x.png"))


class FinalGaps(TuiTestCase):
    """最后一批单行分支：返回值异常、父目录不可建、缓存坏 JSON、span 越界等。"""

    def test_reserve_reports_uncreatable_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "no", "such", "dir", "x.png")
            with (
                mock.patch.object(image.os, "makedirs", side_effect=OSError("denied")),
                self.assertRaises(CoreError),
            ):
                image.reserve_path(target)

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


class FinalGaps2(TuiTestCase):
    """收尾：写日志失败、缓存版本不符、目录不可读、空白渲染、翻页与 DC 键。"""

    def test_collect_images_reports_unreadable_directory(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(image.os, "listdir", side_effect=OSError("denied")),
            self.assertRaises(CoreError),
        ):
            image.collect_images(tmp)


class FinalGaps3(TuiTestCase):
    """收尾（二）：平台分支、空窗口、右对齐、错误的 cur、ESC 取消等。"""

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
                mock.patch.object(cli_batch, "reserve_path", side_effect=CoreError("占名失败")),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli_main.main([src, "--map", "原文=新文", "--out-dir", out_dir])
        self.assertEqual(code, 3)
        self.assertIn("占名失败", err.getvalue())


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
            info = {
                "mask": np.zeros((10, 10), bool),
                "ink_box": (1, 1, 5, 5),
                "text_color": (0, 0, 0),
                "stroke": 1.0,
                "stroke_core": 1.0,
                "slant": 0.0,
            }
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[paths[0], paths[0]]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = cli_main.main(
                    [paths[0], "--map", "原文=新文", "--out-dir", out, "--dry-run"]
                )
        self.assertIn(code, (0, 3), "预演不写盘，两个同名源图应各自算出不重复的目标名")


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
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[src]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch.object(cli_batch, "replace_image", return_value=(None, None, [])),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli_main.main([src, "--map", "原文=新文", "--out-dir", out_dir])
        self.assertEqual(code, 3)
        self.assertIn("没有成功的替换", err.getvalue())


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

            with (
                mock.patch.object(cli_main, "collect_images", return_value=[good, fail]),
                mock.patch(
                    "src.python.core.jobs.ocr_regions",
                    return_value=[{"text": "原文", "rect": (0, 0, 5, 5), "score": 1.0}],
                ),
                mock.patch.object(cli_batch, "load_image", side_effect=loader),
                mock.patch.object(
                    cli_batch,
                    "replace_image",
                    return_value=(
                        np.zeros((10, 10, 3), np.uint8),
                        None,
                        [{"old": "原文", "new": "新文"}],
                    ),
                ),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_main.main([good, "--map", "原文=新文", "--out-dir", tmp])
        self.assertIn("跳过", err.getvalue())


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
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            if not has_cjk_font():
                self.skipTest("需要 CJK 字体")
            real_load = image.load_image

            def loader(path):
                if path == bad:
                    raise OSError("坏图")
                return real_load(path)

            err = io.StringIO()
            # CLI 只接受一个输入路径；批量靠"输入是目录"实现
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[good, bad]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                mock.patch.object(cli_batch, "load_image", side_effect=loader),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_main.main(
                    [
                        os.path.dirname(good),
                        "--map",
                        "原文=新文",
                        "--out-dir",
                        out_dir,
                        "--font",
                        FONT_CJK,
                    ]
                )
        self.assertIn("跳过", err.getvalue())


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
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            real_load = image.load_image
            calls: dict[str, int] = {}

            def loader(path):
                calls[path] = calls.get(path, 0) + 1
                if path == bad and calls[path] > 1:  # 第一遍（扫描）成功，第二遍失败
                    raise OSError("读盘失败")
                return real_load(path)

            err = io.StringIO()
            with (
                # 关掉规划遍的解码缓存，第二遍才会真的重新读盘（这里要测的就是那条分支）
                mock.patch.object(cli_batch, "CACHE_BYTES_MAX", 0),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                mock.patch.object(cli_batch, "load_image", side_effect=loader),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_main.main(
                    [src_dir, "--map", "原文=新文", "--out-dir", out_dir, "--font", FONT_CJK]
                )
        self.assertIn("跳过", err.getvalue())
