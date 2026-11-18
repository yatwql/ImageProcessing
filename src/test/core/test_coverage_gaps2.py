"""覆盖率收尾（core / cli 侧）：把最后几十行"错误分支与空输入"补齐。

每条都对准一步具体代码：`except` 分支、空结果分支、占位文件清理、
模糊匹配提示、无 sink 时的 stderr 提示。
"""

from __future__ import annotations

import contextlib
import io
import json
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


class BootstrapProbe(unittest.TestCase):
    def test_probe_oserror_reports_venv(self):
        py = Path("/tmp/python")
        with mock.patch.object(bootstrap.subprocess, "run", side_effect=OSError("boom")):
            self.assertEqual(bootstrap.missing_modules(py), ["venv"])


class ConfigFitWidth(unittest.TestCase):
    def test_fit_width_default_is_applied_when_unset(self):
        opts = options.Options()
        opts.fit_width = False
        with mock.patch.object(config, "option_defaults", return_value={"fit_width": True}):
            config.apply_to_options(opts)
        self.assertTrue(opts.fit_width)


class AuditBadLine(unittest.TestCase):
    def test_non_object_json_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp))
            path.write_text('[1, 2]\n\n{"src_file": "a.png"}\n', encoding="utf-8")
            entries = audit.read_entries(tmp)
        self.assertEqual(len(entries), 1, "数组行与空行都应被跳过")


class MatchFuzzyPrint(unittest.TestCase):
    def test_fuzzy_match_warns_on_stderr_without_sink(self):
        regions = [{"text": "年度报告2O23", "rect": (0, 0, 100, 30), "score": 1.0}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            jobs = match.plan_jobs(regions, {"年度报告2023": "新"}, warn=True)
        self.assertEqual(len(jobs), 1)
        self.assertIn("模糊匹配", err.getvalue())


class WarnOutput(unittest.TestCase):
    def test_warn_prints_when_no_sink(self):
        opts = options.Options()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            options.warn(opts, "字体不可靠")
        self.assertIn("字体不可靠", err.getvalue())


class OcrEmptyResult(unittest.TestCase):
    def test_empty_engine_result_returns_none(self):
        rgb = np.zeros((10, 10, 3), np.uint8)
        fake = mock.Mock(return_value=([], None))
        with mock.patch.object(ocr, "_engine", return_value=fake):
            self.assertIsNone(ocr.ocr_crop(rgb, (0, 0, 10, 10)))


class MetaFailure(unittest.TestCase):
    def test_unreadable_meta_returns_empty(self):
        with mock.patch.object(image.Image, "open", side_effect=OSError("boom")):
            self.assertEqual(image.load_meta("/nope.png"), {})


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
            ):
                with self.assertRaises(CoreError):
                    edit.replace_image(
                        rgb, None, [edit.Job((5, 5, 100, 25), "原文", "新文")], opts, []
                    )


class FontRowParsing(unittest.TestCase):
    def test_bad_rows_return_none(self):
        self.assertIsNone(fonts._faces_from_rows([("a.ttf", "not-an-int", "n")]))
        self.assertIsNone(fonts._faces_from_rows("not-a-list"))


class RenderEmptyLine(unittest.TestCase):
    def test_blank_line_in_multiline_text_is_skipped(self):
        from src.test._support import FONT_CJK, has_cjk_font

        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        canvas = np.full((120, 240, 3), 255, np.uint8)
        before = canvas.copy()
        face = fonts.FontFace(FONT_CJK, 0)
        out = render.draw_text(
            canvas, "第一行\n\n第三行", face, 20, 0.0, (0, 0, 0), (10.0, 230.0, 10.0, 110.0), "left"
        )
        self.assertTrue((out != before).any(), "有空行时其余文字仍要画出来")


class StyleRenderFailure(unittest.TestCase):
    def test_render_failure_is_logged_and_skipped(self):
        from src.test._support import FONT_CJK, has_cjk_font

        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            found = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 2)
        self.assertIsNone(found)


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
                mock.patch.object(cli_main, "save_image", side_effect=OSError("磁盘满")),
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


class AuditJsonError(unittest.TestCase):
    def test_broken_json_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp))
            path.write_text("{坏的\n", encoding="utf-8")
            self.assertEqual(audit.read_entries(tmp), [])
            self.assertTrue(json.dumps({"a": 1}))  # 保持 json 导入被使用


if __name__ == "__main__":
    unittest.main()
