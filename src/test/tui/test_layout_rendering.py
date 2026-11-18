"""TUI 布局渲染测试：双栏/单栏切换、窄屏提示、异常不外溢。

渲到假窗口上，断言“画得出来、内容对、不抛异常”。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import src.python.tui.ui as ui
import src.python.tui.ui_draw as ui_draw
from src.python.tui.ui_base import dwidth
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

        original = ui_draw.draw_wide
        ui_draw.draw_wide = boom
        try:
            ui.draw_frame(win, app)  # 不应抛出
        finally:
            ui_draw.draw_wide = original
        self.assertIn("界面绘制出错", app.message)


class RefreshFlush(TuiTestCase):
    """每一帧都必须 refresh：漏掉就是用户看到的"一片黑屏"。

    curses 的 erase/draw 只改缓冲区，不刷新等于什么都没画。
    """

    def counting_win(self, rows: int = 28, cols: int = 100) -> FakeWin:
        """FakeWin 自带 refresh_count：只改缓冲区不刷新（真机黑屏）会被抓到。"""
        return FakeWin([], rows=rows, cols=cols)

    def test_main_view_flushes_every_frame(self):
        app = self.make_app()
        win = self.counting_win()
        ui.draw_frame(win, app)
        self.assertGreaterEqual(win.refresh_count, 1, "主界面必须 refresh，否则黑屏")

    def test_every_panel_flushes(self):
        app = self.make_app()
        for panel in ("main", "map", "settings", "help"):
            with self.subTest(panel=panel):
                app.panel = panel
                win = self.counting_win()
                ui.draw_frame(win, app)
                self.assertGreaterEqual(win.refresh_count, 1, f"{panel} 面板没有 refresh")

    def test_too_small_screen_also_flushes(self):
        app = self.make_app()
        win = self.counting_win(rows=6, cols=14)
        ui.draw_frame(win, app)
        self.assertGreaterEqual(win.refresh_count, 1)


class BorderDrawing(TuiTestCase):
    """线框必须走 addch：ACS_* 在某些构建里是 int，传给 addstr 会 TypeError → 整帧黑屏。"""

    def test_border_cells_are_drawn(self):
        app = self.make_app()
        win = FakeWin([], rows=26, cols=100)
        ui.draw_frame(win, app)
        self.assertGreater(win.cell_count, 20, "边框/分隔线一格格都没画出来")

    def test_fake_window_rejects_non_str_to_addstr(self):
        win = FakeWin([], rows=4, cols=20)
        with self.assertRaises(TypeError):
            win.addstr(0, 0, 104)          # curses 的 ACS int 码不能进 addstr

    def test_fake_window_accepts_acs_int_in_addch(self):
        win = FakeWin([], rows=4, cols=20)
        win.addch(0, 0, 104, 0)            # 真 curses 允许 addch 收 ACS int
        self.assertEqual(win.cell_count, 1)


class ResponsiveLayout(TuiTestCase):
    """宽屏（电脑）与窄屏（手机）都要排得下：不溢出、不丢关键信息。"""

    DESKTOP = [(100, 30), (130, 40), (80, 24)]
    PHONE = [(44, 22), (36, 20), (32, 18)]

    def render(self, app, cols: int, rows: int) -> FakeWin:
        win = FakeWin([], rows=rows, cols=cols)
        ui.draw_frame(win, app)
        return win

    def test_no_line_exceeds_the_window_width(self):
        app = self.make_app()
        for cols, rows in self.DESKTOP + self.PHONE:
            with self.subTest(size=f"{cols}x{rows}"):
                win = self.render(app, cols, rows)
                for line in win.screen:
                    self.assertLessEqual(dwidth(line), cols, f"{cols} 列下溢出: {line!r}")

    def test_desktop_shows_both_panels_and_page_position(self):
        app = self.make_app()
        text = "\n".join(self.render(app, 100, 30).screen)
        self.assertIn("① 图片", text)
        self.assertIn("② 识别到的文字", text)
        self.assertIn("张", text)                     # 右上角的 "N/M 张"

    def test_phone_shows_single_panel_with_size_marker(self):
        app = self.make_app()
        text = "\n".join(self.render(app, 44, 22).screen)
        self.assertIn("Tab→文字", text)
        self.assertIn("[44x22]", text)
        self.assertNotIn("② 识别到的文字", text, "窄屏只画当前一栏")

    def test_very_narrow_phone_uses_compact_header(self):
        app = self.make_app()
        text = "\n".join(self.render(app, 36, 20).screen)
        self.assertIn("图片 1/", text)
        self.assertNotIn("Tab→文字", text, "32~43 列放不下切换提示，只留计数")

    def test_phone_keeps_key_hints_short_enough(self):
        app = self.make_app()
        for cols, rows in self.PHONE:
            with self.subTest(size=f"{cols}x{rows}"):
                text = "\n".join(self.render(app, cols, rows).screen)
                self.assertIn("替换", text, "最常用的替换键必须在提示里")

    def test_wide_screen_key_hints_are_complete(self):
        app = self.make_app()
        text = "\n".join(self.render(app, 120, 30).screen)
        for hint in ("R 全部", "Ctrl-R", "? 帮助"):
            self.assertIn(hint, text)

    def test_selected_row_is_marked_in_both_layouts(self):
        app = self.make_app()
        for cols, rows in ((100, 30), (44, 22)):
            with self.subTest(size=f"{cols}x{rows}"):
                text = "\n".join(self.render(app, cols, rows).screen)
                self.assertIn("第0行文字", text, "当前块内容要能看到")
                self.assertIn("选：", text, "详情行必须存在")


if __name__ == "__main__":
    unittest.main()
