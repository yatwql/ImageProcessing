"""TUI 布局渲染测试：双栏/单栏切换、窄屏提示、异常不外溢。

渲到假窗口上，断言“画得出来、内容对、不抛异常”。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import src.python.tui.ui as ui
from src.test._support import FakeWin, TuiTestCase


class LayoutRendering(TuiTestCase):
    def render(self, app, cols: int, rows: int) -> FakeWin:
        win = FakeWin([], rows=rows, cols=cols)
        ui.draw_frame(win, app)
        return win

    def test_wide_terminal_shows_two_panels(self):
        app = self.make_app()
        win = self.render(app, 100, 30)
        text = "\n".join(win.screen)
        self.assertIn("① 图片", text)
        self.assertIn("② 识别到的文字", text)

    def test_narrow_terminal_switches_to_single_panel(self):
        app = self.make_app()
        win = self.render(app, 50, 24)
        text = "\n".join(win.screen)
        self.assertIn("Tab→文字", text)
        self.assertIn("[50x24]", text)

    def test_narrow_terminal_on_blocks_panel(self):
        app = self.make_app()
        app.focus = "blocks"
        text = "\n".join(self.render(app, 50, 24).screen)
        self.assertIn("Tab→图片", text)

    def test_too_small_terminal_shows_hint_not_crash(self):
        app = self.make_app()
        text = "\n".join(self.render(app, 14, 6).screen)
        self.assertIn("太窄", text)

    def test_long_text_is_truncated_to_width(self):
        app = self.make_app()
        app.blocks()[0].text = "很长的文字" * 40
        win = self.render(app, 60, 20)
        self.assertTrue(all(len(line) <= 60 for line in win.screen))

    def test_render_error_is_contained(self):
        app = self.make_app()
        win = FakeWin([], rows=24, cols=80)

        def boom(*_args, **_kwargs):
            raise RuntimeError("画不动了")

        original = ui.draw_wide
        ui.draw_wide = boom
        try:
            ui.draw_frame(win, app)               # 不应抛出
        finally:
            ui.draw_wide = original
        self.assertIn("界面绘制出错", app.message)


if __name__ == "__main__":
    unittest.main()
