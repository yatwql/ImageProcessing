"""绘制与字距的边界：空行、越界裁切、对齐、无墨迹时字距不收敛。"""

from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from src.python.core import fonts, render, style
from src.test._support import (
    FONT_CJK,
    has_cjk_font,
)


class RenderGaps(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 CJK 字体")
    def test_solve_tracking_stops_when_text_has_no_ink(self):
        face = style.FontFace(FONT_CJK, 0) if hasattr(style, "FontFace") else None
        face = face or fonts.FontFace(FONT_CJK, 0)
        with mock.patch.object(render, "ink_size", return_value=(0, 0)):
            tracking = render.solve_tracking("年度", face, 20, 0.0, 200.0)
        self.assertEqual(tracking, 0.0, "没有墨迹时不该继续累加字距")


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


class BlankOnlyText(unittest.TestCase):
    def test_text_with_only_blank_lines_draws_nothing(self):
        canvas = np.full((40, 80, 3), 255, np.uint8)
        before = canvas.copy()
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        out = render.draw_text(
            canvas,
            "\n",
            fonts.FontFace(FONT_CJK, 0),
            20,
            0.0,
            (0, 0, 0),
            (5.0, 75.0, 5.0, 35.0),
            "left",
        )
        self.assertTrue(np.array_equal(out, before), "全是空行时不该画任何东西")
