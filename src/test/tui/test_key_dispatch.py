"""按键分发：每个键都要落到明确的状态变化，且不越界、不崩。

这里覆盖 `ui_actions.handle` 的三块面板（主界面 / 全局映射 / 样式选项）与
`ui.loop` 的收尾路径；图片内容不是重点（替换流程另有用例），所以不去动像素。
"""

from __future__ import annotations

import os
import unittest

from src.python.tui import ui
from src.python.tui.app import Block
from src.test._support import FakeWin, TuiTestCase


class MainPanelKeys(TuiTestCase):
    def setUp(self):
        super().setUp()
        self.app = self.make_app(count=2)
        self.win = FakeWin([], rows=28, cols=100)

    def press(self, *keys: str) -> None:
        for key in keys:
            ui.handle(self.app, self.win, key)

    def focus_blocks(self) -> None:
        """直接切到右栏：Enter 会打开输入行，需要预先排好按键，单独用例再测。"""
        self.app.focus = "blocks"
        self.app.ensure_blocks()

    def edit_line(self, *keys: str) -> None:
        self.win.keys.extend(list(keys) + ["\n"])

    def test_tab_and_t_switch_between_panels(self):
        self.assertEqual(self.app.focus, "files")
        self.press("\t")
        self.assertEqual(self.app.focus, "blocks")
        self.press("t")
        self.assertEqual(self.app.focus, "files")

    def test_enter_on_files_enters_block_panel_and_loads_blocks(self):
        self.press("\n")
        self.assertEqual(self.app.focus, "blocks")
        self.assertTrue(self.app.blocks(), "进入右栏应确保文字块已就绪")

    def test_escape_goes_back_instead_of_quitting(self):
        self.press("\t")
        self.press("\x1b")
        self.assertEqual(self.app.focus, "files")
        self.assertFalse(self.app.quit, "Esc 只返回，不能退出")

    def test_q_quits(self):
        self.press("q")
        self.assertTrue(self.app.quit)

    def test_escape_at_top_level_only_hints(self):
        self.press("\x1b")
        self.assertIn("按 q 退出", self.app.message)
        self.assertFalse(self.app.quit)

    def test_navigation_keys_move_the_selection(self):
        first = self.app.sel_row                       # 初始停在第一张图上
        self.press("j")
        self.assertEqual(self.app.sel_row, first + 1)
        self.press("k")
        self.assertEqual(self.app.sel_row, first)
        self.press("G")
        self.assertEqual(self.app.sel_row, len(self.app.rows) - 1, "G 应跳到末行")
        self.press("g")
        self.assertEqual(self.app.sel_row, 0, "g 应回到首行（父目录行）")

    def test_digit_selects_an_image(self):
        self.app.img_rows = 10                   # 数字跳图只看当前可见窗口
        self.press("2")
        self.assertIn("第 2 张", self.app.message)

    def test_enter_on_block_opens_the_input_line_and_sets_new_text(self):
        self.focus_blocks()
        self.edit_line("新的一整行")
        self.press("\n")
        blk = self.app.cur_block()
        assert blk is not None
        self.assertEqual(blk.override, "新的一整行")

    def test_space_toggles_the_current_block(self):
        self.focus_blocks()
        blk = self.app.cur_block()
        assert blk is not None
        blk.override = "新文字"
        before = blk.enabled
        self.press(" ")
        self.assertNotEqual(blk.enabled, before)

    def test_space_on_block_without_new_text_hints(self):
        self.focus_blocks()
        blk = self.app.cur_block()
        assert blk is not None
        blk.override = None
        self.press(" ")
        self.assertIn("先按 Enter", self.app.message)

    def test_a_and_n_toggle_all_blocks(self):
        self.focus_blocks()
        self.press("a")
        self.assertTrue(all(b.enabled for b in self.app.blocks()))
        self.press("n")
        self.assertFalse(any(b.enabled for b in self.app.blocks()))

    def test_u_clears_the_current_override(self):
        self.focus_blocks()
        blk = self.app.cur_block()
        assert blk is not None
        blk.override = "临时"
        self.press("u")
        self.assertIsNone(blk.override)

    def test_m_adds_current_block_to_global_mapping(self):
        self.focus_blocks()
        blk = self.app.cur_block()
        assert blk is not None
        blk.override = "新文字"
        self.press("m")
        self.assertTrue(self.app.mapping)

    def test_help_panel_opens_and_closes(self):
        self.press("?")
        self.assertEqual(self.app.panel, "help")
        self.press("x")                                  # 帮助面板任意键返回
        self.assertEqual(self.app.panel, "main")

    def test_l_relearns_the_current_image(self):
        img = self.app.cur
        assert img is not None
        img.error = "旧的错误"
        img.blocks = [Block("占位", (0, 0, 10, 10))]
        self.press("l")
        self.assertNotEqual(img.error, "旧的错误", "旧错误必须被清掉")
        self.assertIn("没识别出文字", img.error or "", "这里没有 OCR 桩，重新识别应给提示")

    def test_o_edits_output_dir(self):
        self.win.keys.extend(list("/tmp/out") + ["\n"])
        self.press("o")
        self.assertTrue(self.app.out_dir.endswith("/tmp/out"))

    def test_w_exports_mapping_to_json(self):
        self.app.mapping = {"旧": "新"}
        self.win.keys.extend(list("map.json") + ["\n"])
        self.press("w")
        self.assertTrue(os.path.exists("map.json"))
        self.addCleanup(lambda: os.path.exists("map.json") and os.remove("map.json"))


class MapPanelKeys(TuiTestCase):
    def setUp(self):
        super().setUp()
        self.app = self.make_app(count=1)
        self.win = FakeWin([], rows=28, cols=100)
        self.app.panel = "map"

    def press(self, *keys: str) -> None:
        for key in keys:
            ui.handle(self.app, self.win, key)

    def focus_blocks(self) -> None:
        """直接切到右栏：Enter 会打开输入行，需要预先排好按键，单独用例再测。"""
        self.app.focus = "blocks"
        self.app.ensure_blocks()

    def edit_line(self, *keys: str) -> None:
        self.win.keys.extend(list(keys) + ["\n"])

    def test_escape_returns_to_main(self):
        self.press("\x1b")
        self.assertEqual(self.app.panel, "main")

    def test_n_adds_a_pair(self):
        self.win.keys.extend(list("旧") + ["\n"] + list("新") + ["\n"])
        self.press("n")
        self.assertEqual(self.app.mapping, {"旧": "新"})

    def test_enter_edits_the_selected_pair(self):
        self.app.mapping = {"旧": "新"}
        self.app.sel_map = 0
        self.win.keys.extend(list("改后") + ["\n"])
        self.press("\n")
        self.assertEqual(self.app.mapping, {"旧": "改后"})

    def test_d_deletes_the_selected_pair(self):
        self.app.mapping = {"甲": "1", "乙": "2"}
        self.app.sel_map = 0
        self.press("d")
        self.assertNotIn("甲", self.app.mapping)

    def test_j_and_k_move_the_selection(self):
        self.app.mapping = {"甲": "1", "乙": "2"}
        self.app.sel_map = 0
        self.press("j")
        self.assertEqual(self.app.sel_map, 1)
        self.press("k")
        self.assertEqual(self.app.sel_map, 0)


class SettingsPanelKeys(TuiTestCase):
    def setUp(self):
        super().setUp()
        self.app = self.make_app(count=1)
        self.win = FakeWin([], rows=28, cols=100)
        self.app.panel = "settings"

    def press(self, *keys: str) -> None:
        for key in keys:
            ui.handle(self.app, self.win, key)

    def focus_blocks(self) -> None:
        """直接切到右栏：Enter 会打开输入行，需要预先排好按键，单独用例再测。"""
        self.app.focus = "blocks"
        self.app.ensure_blocks()

    def edit_line(self, *keys: str) -> None:
        self.win.keys.extend(list(keys) + ["\n"])

    def test_escape_returns_to_main(self):
        self.press("\x1b")
        self.assertEqual(self.app.panel, "main")

    def test_j_and_k_move_within_bounds(self):
        self.press("j")
        self.assertEqual(self.app.sel_setting, 1)
        self.press("k", "k", "k")
        self.assertEqual(self.app.sel_setting, 0, "已在首行，不能越界")

    def test_enter_sets_a_value(self):
        self.app.sel_setting = 1                      # 字号
        self.win.keys.extend(list("28") + ["\n"])
        self.press("\n")
        self.assertEqual(self.app.opts.size, 28)

    def test_invalid_quality_keeps_previous_value(self):
        rows = self.app.setting_notes()
        index = next(i for i, row in enumerate(rows) if row[0] == "quality")
        self.app.opts.quality = 90
        self.app.sel_setting = index
        self.win.keys.extend(list("999") + ["\n"])
        self.press("\n")
        self.assertEqual(self.app.opts.quality, 90, "非法输入应保留原值")
        self.assertIn("100", self.app.message)


class BatchInterrupt(TuiTestCase):
    """批量替换途中按 Esc：已完成保留，状态行显示"已取消，完成 x/n"。"""

    def test_escape_during_batch_sets_cancel_and_partial_status(self):
        app = self.make_app(count=2)
        for img in app.images:
            img.blocks = [Block("第0行文字", (10, 20, 200, 24))]
            img.blocks[0].override = "改过的文字"
        app.cancel = False

        app.apply_all(should_stop=lambda: True)
        self.assertTrue(app.cancel)
        self.assertIn("已取消", app.status)
        self.assertIn("0/2", app.status)

    def test_apply_one_refuses_immediately_when_cancelled(self):
        app = self.make_app(count=1)
        img = app.cur
        assert img is not None
        img.blocks = [Block("第0行文字", (10, 20, 200, 24))]
        img.blocks[0].override = "改过的文字"
        app.cancel = True
        ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertEqual(msg, "已取消")


if __name__ == "__main__":
    unittest.main()
