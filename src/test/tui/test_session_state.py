"""TUI 会话状态测试：样式选项校验、映射表读写（不涉及 curses 界面）。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import tempfile
import unittest

from src.test._support import TuiTestCase


class TuiSessionState(TuiTestCase):
    def test_invalid_color_only_reports_message(self):
        app = self.make_app()
        msg = app.set_setting("color", "zzz")
        self.assertIn("颜色", msg)
        self.assertIsNone(app.opts.color)

    def test_style_options_accept_numbers_and_keywords(self):
        app = self.make_app()
        app.set_setting("size", "40")
        app.set_setting("align", "center")
        app.set_setting("fit_width", "on")
        self.assertEqual(app.opts.size, 40)
        self.assertEqual(app.opts.align, "center")
        self.assertTrue(app.opts.fit_width)
        app.set_setting("size", "自动")
        self.assertIsNone(app.opts.size)

    def test_setting_rows_expose_title_and_value(self):
        notes = self.make_app().setting_notes()
        self.assertGreaterEqual(len(notes), 6)
        self.assertTrue(all(len(n) == 3 for n in notes))
        self.assertEqual(notes[1][2], "自动")

    def test_mapping_file_roundtrip(self):
        app = self.make_app()
        app.mapping["2023"] = "2024"
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/m.json"
            app.save_map(path)
            other = self.make_app()
            other.load_map(path)
            self.assertEqual(other.mapping["2023"], "2024")


if __name__ == "__main__":
    unittest.main()
