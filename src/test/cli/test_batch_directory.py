"""CLI 目录批量测试：逐图处理、汇总统计、输出命名、dry-run 与过滤规则。

OCR 用桩替换，验证的是批量的编排、命名与汇总行为。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest

from PIL import Image

from src.python.cli.main import main
from src.test._support import make_text_image, patch_ocr


class BatchDirectoryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.src_dir = os.path.join(self.tmp.name, "in")
        self.out_dir = os.path.join(self.tmp.name, "out")
        os.makedirs(self.src_dir)
        self.rgb, self.boxes = make_text_image(["年度报告2023"])

    def make_image(self, name: str) -> str:
        path = os.path.join(self.src_dir, name)
        Image.fromarray(self.rgb).save(path)
        return path

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with patch_ocr(self.boxes), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_every_image_produces_output(self):
        self.make_image("a.png")
        self.make_image("b.png")
        code, text, _err = self.run_cli(self.src_dir, "--map", "2023=2024",
                                        "--out-dir", self.out_dir)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(self.out_dir)), ["a.png", "b.png"])
        self.assertIn("成功 2 张", text)
        self.assertIn("共 2 处替换", text)

    def test_dry_run_writes_no_files(self):
        self.make_image("a.png")
        code, text, _err = self.run_cli(self.src_dir, "--map", "2023=2024",
                                        "--out-dir", self.out_dir, "--dry-run")
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(self.out_dir))
        self.assertIn("批量完成", text)

    def test_non_image_files_are_ignored(self):
        self.make_image("a.png")
        with open(os.path.join(self.src_dir, "note.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        code, _text, _err = self.run_cli(self.src_dir, "--map", "2023=2024",
                                         "--out-dir", self.out_dir)
        self.assertEqual(code, 0)
        self.assertEqual(os.listdir(self.out_dir), ["a.png"])

    def test_same_stem_different_extension_gets_numbered(self):
        self.make_image("report.png")
        Image.fromarray(self.rgb).save(os.path.join(self.src_dir, "report.jpg"))
        code, _text, _err = self.run_cli(self.src_dir, "--map", "2023=2024",
                                         "--out-dir", self.out_dir)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(self.out_dir)), ["report-1.png", "report.png"])

    def test_images_without_match_exit_with_reason(self):
        self.make_image("a.png")
        with patch_ocr(self.boxes), self.assertRaises(SystemExit):
            main([self.src_dir, "--map", "完全没有的字=新", "--out-dir", self.out_dir])
        self.assertFalse(os.path.exists(self.out_dir))

    def test_quiet_keeps_summary_only(self):
        self.make_image("a.png")
        code, text, _err = self.run_cli(self.src_dir, "--map", "2023=2024",
                                        "--out-dir", self.out_dir, "--quiet")
        self.assertEqual(code, 0)
        self.assertIn("批量完成", text)
        self.assertNotIn("→", text.split("批量完成")[0])   # 不打印逐图明细

    def test_default_out_dir_is_output_sibling(self):
        from src.python.config import DEFAULT_OUT_DIR

        self.make_image("a.png")
        code, _text, _err = self.run_cli(self.src_dir, "--map", "2023=2024", "--quiet")
        self.assertEqual(code, 0)
        produced = os.path.join(DEFAULT_OUT_DIR, "a.png")
        self.assertTrue(os.path.exists(produced))
        with contextlib.suppress(OSError):
            os.remove(produced)

    def test_out_dir_equal_to_larger_tree_is_allowed_but_refuses_source_file(self):
        src = self.make_image("a.png")
        code, _text, err = self.run_cli(self.src_dir, "--map", "2023=2024",
                                        "--out-dir", self.src_dir)
        self.assertNotEqual(code, 0)
        self.assertIn("拒绝覆盖", err)
        self.assertTrue(os.path.exists(src))


if __name__ == "__main__":
    unittest.main()
