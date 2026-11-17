"""CLI 单图流程测试：--list、输出位置、dry-run、样式覆盖、失败提示。

OCR 用桩替换，验证的是命令行编排与写盘行为。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.python.cli.main import main
from src.test._support import has_cjk_font, make_text_image, patch_ocr


class SingleImageRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.rgb, self.boxes = make_text_image(["年度报告2023", "其余文字不动"])
        self.path = os.path.join(self.tmp.name, "report.png")
        Image.fromarray(self.rgb).save(self.path)

    def run_cli(self, *argv: str):
        out = io.StringIO()
        with patch_ocr(self.boxes), contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_list_prints_each_block(self):
        code, text = self.run_cli(self.path, "--list")
        self.assertEqual(code, 0)
        self.assertIn("年度报告2023", text)
        self.assertIn("(40", text)

    def test_output_path_is_honoured(self):
        dst = os.path.join(self.tmp.name, "out.png")
        code, text = self.run_cli(self.path, "-o", dst, "--map", "2023=2024")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(dst))
        self.assertIn("已保存", text)

    def test_default_output_goes_to_data_output(self):
        from src.python.config import DEFAULT_OUT_DIR

        before = set(os.listdir(DEFAULT_OUT_DIR)) if os.path.isdir(DEFAULT_OUT_DIR) else set()
        try:
            code, _text = self.run_cli(self.path, "--map", "2023=2024", "--quiet")
            self.assertEqual(code, 0)
            produced = set(os.listdir(DEFAULT_OUT_DIR)) - before
            self.assertEqual(len(produced), 1)             # 默认目录里只多出这一张
            self.assertTrue(next(iter(produced)).startswith("report"))
        finally:                                           # 用例不把产物留在仓库里
            if os.path.isdir(DEFAULT_OUT_DIR):
                for name in set(os.listdir(DEFAULT_OUT_DIR)) - before:
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(DEFAULT_OUT_DIR, name))

    def test_dry_run_writes_nothing(self):
        dst = os.path.join(self.tmp.name, "dry.png")
        code, text = self.run_cli(self.path, "-o", dst, "--map", "2023=2024", "--dry-run")
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(dst))
        self.assertIn("预演", text)

    def test_explicit_output_is_overwritten(self):
        dst = os.path.join(self.tmp.name, "out.png")
        self.run_cli(self.path, "-o", dst, "--map", "2023=2024")
        first = os.path.getmtime(dst)
        self.run_cli(self.path, "-o", dst, "--map", "2023=2024")
        self.assertEqual(os.listdir(self.tmp.name).count("out.png"), 1)
        self.assertGreaterEqual(os.path.getmtime(dst), first)

    def test_out_dir_run_twice_numbers_the_second_output(self):
        out_dir = os.path.join(self.tmp.name, "out")
        self.run_cli(self.path, "--out-dir", out_dir, "--map", "2023=2024")
        self.run_cli(self.path, "--out-dir", out_dir, "--map", "2023=2024")
        self.assertEqual(sorted(os.listdir(out_dir)), ["report-1.png", "report.png"])

    def test_style_overrides_are_accepted(self):
        dst = os.path.join(self.tmp.name, "styled.png")
        code, text = self.run_cli(
            self.path, "-o", dst, "--map", "2023=2024",
            "--align", "center", "--color", "#ff0000", "--size", "30", "--fit-width")
        self.assertEqual(code, 0)
        self.assertIn("center", text)
        self.assertIn("30px", text)

    def test_unknown_key_still_succeeds_when_other_key_matches(self):
        dst = os.path.join(self.tmp.name, "mixed.png")
        code, _text = self.run_cli(self.path, "-o", dst,
                                   "--map", "不存在的文字=新", "--map", "2023=2024")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(dst))

    def test_unsupported_output_extension_is_refused_with_a_message(self):
        dst = os.path.join(self.tmp.name, "out.xyz")
        err = io.StringIO()
        with patch_ocr(self.boxes), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            code = main([self.path, "-o", dst, "--map", "2023=2024"])
        self.assertNotEqual(code, 0)
        self.assertIn("不支持的输出格式", err.getvalue())
        self.assertFalse(os.path.exists(dst))

    def test_report_file_summarises_the_run(self):
        dst = os.path.join(self.tmp.name, "out.png")
        report = os.path.join(self.tmp.name, "report.json")
        code, _text = self.run_cli(self.path, "-o", dst, "--map", "2023=2024",
                                   "--report", report, "--quiet")
        self.assertEqual(code, 0)
        with open(report, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["succeeded"], 1)
        self.assertEqual(data["replaced"], 1)
        self.assertEqual(data["items"][0]["operations"][0]["new"], "2024")
        self.assertEqual(data["items"][0]["dst"], os.path.abspath(dst))

    def test_quality_out_of_range_is_rejected(self):
        with patch_ocr(self.boxes), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as ctx:
            main([self.path, "--map", "2023=2024", "--quality", "0"])
        self.assertIn("1-100", str(ctx.exception))

    def test_no_task_at_all_exits(self):
        with patch_ocr(self.boxes), self.assertRaises(SystemExit):
            main([self.path])

    def test_area_mode_uses_region_ocr(self):
        dst = os.path.join(self.tmp.name, "area.png")
        code, text = self.run_cli(self.path, "-o", dst, "--area", "20,20,300,60=新的标题")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(dst))
        self.assertIn("新的标题", text)


class SingleImageOutputPixels(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_replacement_changes_only_target_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            rgb, boxes = make_text_image(["年度报告2023", "其余文字不动"])
            src = os.path.join(tmp, "a.png")
            dst = os.path.join(tmp, "b.png")
            Image.fromarray(rgb).save(src)
            with patch_ocr(boxes), contextlib.redirect_stdout(io.StringIO()):
                main([src, "-o", dst, "--map", "2023=2024", "--quiet"])
            before = np.array(Image.open(src))
            after = np.array(Image.open(dst))
            self.assertTrue(np.array_equal(before[100:150, 30:400], after[100:150, 30:400]))
            self.assertFalse(np.array_equal(before[30:80, 30:400], after[30:80, 30:400]))


if __name__ == "__main__":
    unittest.main()
