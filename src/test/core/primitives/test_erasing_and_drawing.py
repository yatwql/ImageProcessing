"""擦除与绘制测试：局部擦除、多行绘制、对齐落位、字距与字号估算。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np

from src.python.core import analyze, draw_text, guess_size, ink_size, solve_tracking
from src.python.core.edit import erase
from src.python.core.fonts import FontFace
from src.python.core.render import render_line
from src.test._support import FONT_CJK, FONT_CJK_REG, has_cjk_font, make_text_image


class EraseRegion(unittest.TestCase):
    def setUp(self):
        self.rgb, self.boxes = make_text_image(["第一行文字", "第二行文字"])
        self.info = analyze(np.array(self.rgb), (30, 30, 300, 60))

    def test_full_erase_clears_the_line(self):
        if self.info is None:
            raise AssertionError("analyze 返回 None")
        out = erase(self.rgb, self.info["mask"])
        self.assertLess(out[30:90, 30:320].std(), 12)

    def test_x_range_erase_keeps_the_rest(self):
        if self.info is None:
            raise AssertionError("analyze 返回 None")
        out = erase(self.rgb, self.info["mask"], x_range=(30, 90))
        # 右半部分应保持原样
        self.assertTrue(np.array_equal(self.rgb[30:90, 200:320], out[30:90, 200:320]))

    def test_erase_with_empty_mask_is_noop(self):
        empty = np.zeros(self.rgb.shape[:2], bool)
        self.assertTrue(np.array_equal(erase(self.rgb, empty), self.rgb))


class DrawTextPlacement(unittest.TestCase):
    def setUp(self):
        self.canvas = np.full((120, 400, 3), 255, np.uint8)

    def render(self, text: str, align: str, box=(20.0, 300.0, 20.0, 80.0)):
        return draw_text(self.canvas.copy(), text, FontFace(FONT_CJK, 0), 32, 0.0,
                         (0, 0, 0), box, align)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_left_align_starts_at_box_left(self):
        out = self.render("测试", "left")
        cols = np.nonzero((out < 250).any(axis=(0, 2)))[0]
        self.assertAlmostEqual(float(cols.min()), 20.0, delta=3)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_center_align_is_centred_in_box(self):
        out = self.render("测试", "center")
        cols = np.nonzero((out < 250).any(axis=(0, 2)))[0]
        self.assertAlmostEqual((float(cols.min()) + float(cols.max())) / 2, 160.0, delta=6)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_multi_line_draws_two_rows(self):
        out = self.render("第一行\n第二行", "left")
        rows = np.nonzero((out < 250).any(axis=(1, 2)))[0]
        self.assertGreater(len(rows), 0)
        gaps = np.diff(rows)
        self.assertGreater(gaps.max(), 5)                 # 两行之间确实有间隔

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_draw_outside_canvas_does_not_raise(self):
        out = draw_text(self.canvas.copy(), "超出边界", FontFace(FONT_CJK, 0), 40, 0.0,
                        (0, 0, 0), (390.0, 400.0, 100.0, 120.0), "left")
        self.assertEqual(out.shape, self.canvas.shape)


class TrackingAndSizeEstimates(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_solve_tracking_reaches_target_width(self):
        face = FontFace(FONT_CJK_REG, 0)
        natural = ink_size("宽宽宽", face, 30)[0]
        target = natural + 2 * 6.0                     # 在 ±0.35em 的允许范围内
        tracking = solve_tracking("宽宽宽", face, 30, 0.0, target)
        self.assertAlmostEqual(ink_size("宽宽宽", face, 30, tracking)[0], target, delta=5)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_solve_tracking_is_clamped(self):
        face = FontFace(FONT_CJK_REG, 0)
        tracking = solve_tracking("宽宽宽", face, 30, 0.0, 999)
        self.assertLessEqual(tracking, 1.6 * 30 + 0.01)     # 上限 1.6em，防止拉成不可读

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_solve_tracking_ignores_single_character(self):
        face = FontFace(FONT_CJK_REG, 0)
        self.assertEqual(solve_tracking("字", face, 30, 1.0, 200), 1.0)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_guess_size_matches_rendered_height(self):
        face = FontFace(FONT_CJK, 0)
        arr, box, _pad = render_line("国国", face, 40)
        height = box[3] - box[1]
        self.assertAlmostEqual(guess_size(height, face), 40, delta=3)

    def test_guess_size_has_lower_bound(self):
        self.assertGreaterEqual(guess_size(1.0, FontFace(FONT_CJK, 0)), 6)


if __name__ == "__main__":
    unittest.main()
