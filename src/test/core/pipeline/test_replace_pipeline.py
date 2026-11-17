"""替换流水线测试：行内替换只动目标片段、重复执行结果一致、拒绝覆盖原图。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.python.cli.main import main as cli_main
from src.python.core import Job, Options, build_font_pool, plan_jobs, replace_image
from src.test._support import FONT_CJK, has_cjk_font, regions


def draw_two_lines() -> np.ndarray:
    img = Image.new("RGB", (600, 200), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_CJK, 36, index=2)
    d.text((40, 80), "年度报告2023", font=font, fill=(30, 30, 30))
    d.text((40, 140), "其余文字保持不变", font=font, fill=(30, 30, 30))
    return np.array(img)


class InlineReplacement(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_fragment_replacement_keeps_other_pixels(self):
        rgb = draw_two_lines()
        jobs = plan_jobs(regions(("年度报告2023", (30, 70, 300, 50))),
                         {"2023": "2024"}, warn=False)
        pool = build_font_pool(["年度报告2023"], None, 160)
        out, alpha, report = replace_image(rgb, None, jobs, Options(quiet=True), pool)
        self.assertIsNone(alpha)
        self.assertEqual(len(report), 1)
        # 第二行完全没被碰过
        self.assertTrue(np.array_equal(rgb[130:180, 30:400], out[130:180, 30:400]))
        # 左侧文字也基本不变
        diff = np.abs(rgb[70:110, 30:120].astype(int) - out[70:110, 30:120].astype(int)).mean()
        self.assertLess(diff, 3.0)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_memoized_rerun_is_identical(self):
        rgb = draw_two_lines()
        jobs = [Job((30, 70, 300, 50), "年度报告2023", "年度总结2024")]
        pool = build_font_pool(["年度报告2023"], None, 160)
        memo: dict = {}
        out1, _a, _r = replace_image(rgb, None, jobs, Options(quiet=True), pool, memo=memo)
        out2, _a, _r = replace_image(rgb, None, jobs, Options(quiet=True), pool, memo=memo)
        self.assertTrue(np.array_equal(out1, out2))
        self.assertGreaterEqual(len(memo), 2)


class OverwriteGuard(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_cli_refuses_to_overwrite_source_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.png")
            im = Image.new("RGB", (300, 100), (255, 255, 255))
            d = ImageDraw.Draw(im)
            d.text((20, 30), "2023", font=ImageFont.truetype(FONT_CJK, 34, index=2),
                   fill=(20, 20, 20))
            im.save(path)
            with open(path, "rb") as f:
                before = f.read()
            rc = cli_main([path, "-o", path, "--map", "2023=2024", "--quiet"])
            self.assertNotEqual(rc, 0)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), before)


if __name__ == "__main__":
    unittest.main()
