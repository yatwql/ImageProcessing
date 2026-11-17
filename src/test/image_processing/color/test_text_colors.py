"""文字颜色场景：深色/彩色/浅色文字的取样与还原。

字体匹配依赖的字色必须接近原色，替换后颜色不能偏。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.python.core import Options, analyze, build_font_pool, plan_jobs, replace_image
from src.test._support import FONT_CJK, has_cjk_font


def image_with(color, bg=(255, 255, 255), text: str = "年度报告2023"):
    img = Image.new("RGB", (420, 150), bg)
    d = ImageDraw.Draw(img)
    d.text((30, 45), text, font=ImageFont.truetype(FONT_CJK, 36, index=2), fill=color)
    return np.array(img)


CASES = (
    ("near_black", (25, 25, 25), (255, 255, 255), 40),
    ("brand_red", (200, 30, 40), (255, 255, 255), 40),
    ("muted_gray", (110, 110, 110), (255, 255, 255), 60),
    ("white_on_blue", (250, 250, 250), (25, 55, 110), 40),
)


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class TextColorSampling(unittest.TestCase):
    def test_analyze_returns_color_close_to_source(self):
        for name, fg, bg, tolerance in CASES:
            with self.subTest(case=name):
                info = analyze(image_with(fg, bg), (25, 35, 360, 60))
                if info is None:
                    self.skipTest(f"{name}: 未检测到文字")
                got = np.array(info["text_color"], float)
                self.assertLess(float(np.abs(got - np.array(fg, float)).max()), tolerance)

    def test_replacement_keeps_original_color(self):
        for name, fg, bg, _tolerance in CASES:
            with self.subTest(case=name):
                rgb = image_with(fg, bg)
                info = analyze(rgb, (25, 35, 360, 60))
                if info is None:
                    self.skipTest(f"{name}: 未检测到文字")
                jobs = plan_jobs([{"text": "年度报告2023", "rect": (25, 35, 360, 60), "score": 1.0}],
                                 {"2023": "2024"}, warn=False)
                pool = build_font_pool(["年度报告2023"], None, 6)
                out, _a, report = replace_image(rgb, None, jobs, Options(quiet=True), pool)
                self.assertEqual(len(report), 1)
                painted = out[45:85, 250:360]
                mask = np.abs(painted.astype(int) - np.array(bg, int)).max(axis=2) > 40
                self.assertGreater(int(mask.sum()), 20)
                avg = painted[mask].mean(axis=0)
                self.assertLess(float(np.abs(avg - np.array(fg, float)).max()), 70)


if __name__ == "__main__":
    unittest.main()
