"""文字渲染测试：单行渲染、字符横向区间、字距求解、模糊 IoU。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np

from src.python.core import char_spans, ink_size, render_line, solve_tracking
from src.python.core.fonts import FontFace
from src.python.core.style import soft_iou
from src.test._support import FONT_CJK, FONT_CJK_REG, has_cjk_font


class TextRendering(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_rendered_line_reports_ink_box(self):
        face = FontFace(FONT_CJK, 0)
        arr, box, _pad = render_line("测试", face, 40)
        self.assertEqual(arr.ndim, 2)
        self.assertGreater(box[2] - box[0], 10)
        self.assertGreater(box[3] - box[1], 10)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_character_spans_are_ordered(self):
        face = FontFace(FONT_CJK_REG, 0)
        spans = char_spans("年度报告", face, 30, 0.0, 100.0)
        self.assertEqual(len(spans), 4)
        self.assertTrue(all(spans[i][1] <= spans[i + 1][0] + 0.01 for i in range(3)))
        self.assertAlmostEqual(spans[0][0], 100.0, delta=3.0)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_tracking_solver_matches_target_width(self):
        face = FontFace(FONT_CJK_REG, 0)
        tracking = solve_tracking("测试文字", face, 30, 0.0, 200)
        self.assertAlmostEqual(ink_size("测试文字", face, 30, tracking)[0], 200, delta=4)

    def test_soft_iou_scores_identical_masks_high(self):
        a = np.zeros((20, 40), np.uint8)
        a[5:15, 8:30] = 255
        self.assertGreater(soft_iou(a.astype(bool), a.astype(bool)), 0.99)
        shifted = np.roll(a, 3, axis=1)
        self.assertGreater(soft_iou(a.astype(bool), shifted.astype(bool)), 0.5)


if __name__ == "__main__":
    unittest.main()
