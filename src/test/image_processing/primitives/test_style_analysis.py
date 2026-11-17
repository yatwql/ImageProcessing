"""版式分析测试：从合成图反解字色、字迹范围、字号与候选字体。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.python.core import analyze, build_font_pool, fit_font
from src.test._support import FONT_CJK, has_cjk_font


def draw_report() -> np.ndarray:
    """一张白底两行中文的合成图（标题行 + 正文行）。"""
    img = Image.new("RGB", (600, 200), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_CJK, 36, index=2)     # SC
    d.text((40, 80), "年度报告2023", font=font, fill=(30, 30, 30))
    d.text((40, 140), "其余文字保持不变", font=font, fill=(30, 30, 30))
    return np.array(img)


class StyleRecovery(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_analyze_recovers_text_color_and_ink_box(self):
        info = analyze(draw_report(), (30, 70, 300, 50))
        if info is None:
            raise AssertionError("analyze 返回 None")
        self.assertEqual(tuple(int(v) for v in info["text_color"]), (30, 30, 30))
        self.assertLessEqual(info["ink_box"][0], 45)
        self.assertGreaterEqual(info["ink_box"][2], 200)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_font_matching_recovers_original_size(self):
        info = analyze(draw_report(), (30, 70, 300, 50))
        if info is None:
            raise AssertionError("analyze 返回 None")
        pool = build_font_pool(["年度报告2023"], None, 160)
        fit = fit_font("年度报告2023", info["mask"], info["ink_box"], pool, 160,
                       a_stroke=info.get("stroke_core"), slant=info.get("slant"))
        if fit is None:
            raise AssertionError("fit_font 返回 None")
        self.assertAlmostEqual(fit[2], 36, delta=3)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_upright_text_never_matches_italic_face(self):
        info = analyze(draw_report(), (30, 70, 300, 50))
        if info is None:
            raise AssertionError("analyze 返回 None")
        pool = build_font_pool(["年度报告2023"], None, 160)
        fit = fit_font("年度报告2023", info["mask"], info["ink_box"], pool, 160,
                       a_stroke=info.get("stroke_core"), slant=info.get("slant"))
        if fit is None:
            raise AssertionError("fit_font 返回 None")
        self.assertNotIn("italic", fit[1].name.lower())
        self.assertNotIn("oblique", fit[1].name.lower())


if __name__ == "__main__":
    unittest.main()
