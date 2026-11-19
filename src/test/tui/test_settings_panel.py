"""TUI 样式选项面板（c 键）：逐项编辑、非法值只提示、Esc 返回。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

from src.test._support import FONT_CJK, TuiTestCase, has_cjk_font


class SettingsPanel(TuiTestCase):
    def test_escape_closes_panel_back_to_main(self):
        app = self.make_app()
        self.drive(app, ["c", "\x1b", None, "q"])
        self.assertEqual(app.panel, "main")

    def test_size_edit_accepts_number(self):
        app = self.make_app()
        self.drive(app, ["c", "j", "\n", *list("40"), "\n", "q", "q"])
        self.assertEqual(app.opts.size, 40)
        self.assertIn("size", app.message)

    def test_size_edit_rejects_text(self):
        app = self.make_app()
        self.drive(app, ["c", "j", "\n", *list("abc"), "\n", "q", "q"])
        self.assertIsNone(app.opts.size)
        self.assertIn("不是合法数值", app.message)

    def test_quality_edit_accepts_range_and_rejects_outside(self):
        app = self.make_app()
        self.assertIn("quality", app.set_setting("quality", "80"))
        self.assertEqual(app.opts.quality, 80)
        self.assertIn("1-100", app.set_setting("quality", "0"))
        self.assertEqual(app.opts.quality, 80)  # 非法值不破坏已设置的值
        self.assertIn("自动", app.set_setting("quality", ""))
        self.assertIsNone(app.opts.quality)

    def test_align_and_fit_width_edit(self):
        app = self.make_app()
        self.drive(app, ["c", "j", "j", "j", "\n", *list("right"), "\n", "q"])
        self.assertEqual(app.opts.align, "right")
        app2 = self.make_app()
        self.drive(app2, ["c", "j", "j", "j", "j", "\n", *list("on"), "\n", "q", "q"])
        self.assertTrue(app2.opts.fit_width)

    def test_color_edit_rejects_bad_value(self):
        app = self.make_app()
        self.drive(app, ["c", "j", "j", "\n", *list("zzz"), "\n", "q", "q"])
        self.assertIsNone(app.opts.color)
        self.assertIn("颜色格式错误", app.message)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_font_edit_requires_existing_file(self):
        app = self.make_app()
        self.drive(app, ["c", "\n", *list("/no/such.ttf"), "\n", "q", "q"])
        self.assertIsNone(app.opts.font)
        self.assertIn("找不到字体文件", app.message)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_font_edit_accepts_existing_file(self):
        app = self.make_app()
        self.drive(app, ["c", "\n", *list(FONT_CJK), "\n", "q", "q"])
        self.assertEqual(app.opts.font, FONT_CJK)

    def test_tracking_and_max_fonts_edit(self):
        app = self.make_app()
        self.drive(app, ["c", "j", "j", "j", "j", "j", "\n", *list("1.5"), "\n", "q"])
        self.assertAlmostEqual(app.opts.tracking or 0.0, 1.5, places=3)
        app2 = self.make_app()
        self.drive(app2, ["c"] + ["j"] * 6 + ["\n"] + list("32") + ["\n", "q", "q"])
        self.assertEqual(app2.opts.max_fonts, 32)


if __name__ == "__main__":
    unittest.main()
