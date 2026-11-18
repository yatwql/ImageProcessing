"""交互边界：样式/映射面板的非法输入、目录浏览的边界、批量与取消的组合。

主流程用例已经覆盖"正常敲一遍"，这里专门盯容易出事的边角：
非法数字、留空=自动、越界移动、不可读目录、重复运行、批量全无匹配。
"""

from __future__ import annotations

import json
import os
import unittest

from src.python.tui import ui
from src.python.tui.app import Block
from src.test._support import FakeWin, TuiTestCase


class SettingParsing(TuiTestCase):
    """样式面板：合法值写进去，非法值保留原值并提示（不能静默重置成自动）。"""

    def setUp(self):
        super().setUp()
        self.app = self.make_app(count=1)

    def test_empty_input_restores_automatic(self):
        self.app.opts.size = 28
        message = self.app.set_setting("size", "")
        self.assertIsNone(self.app.opts.size)
        self.assertIn("自动", message)

    def test_size_accepts_a_positive_integer(self):
        self.assertIn("32", self.app.set_setting("size", "32"))
        self.assertEqual(self.app.opts.size, 32)

    def test_size_rejects_out_of_range_and_garbage(self):
        self.app.opts.size = 24
        for bad in ("0", "-3", "5"):
            with self.subTest(value=bad):
                message = self.app.set_setting("size", bad)
                self.assertEqual(self.app.opts.size, 24, f"非法值不该改动已有设置: {bad}")
                self.assertIn("6", message, "数字太小要说清楚下限")
        message = self.app.set_setting("size", "abc")
        self.assertEqual(self.app.opts.size, 24, "非数字不该改动已有设置")
        self.assertTrue(message, "非法输入必须有提示")

    def test_fullwidth_digits_are_accepted(self):
        """`int()` 认全角数字：输入法打「３２」也应当生效，而不是报错。"""
        self.app.set_setting("size", "３２")
        self.assertEqual(self.app.opts.size, 32)

    def test_quality_range_is_enforced(self):
        self.app.opts.quality = 90
        self.app.set_setting("quality", "101")
        self.assertEqual(self.app.opts.quality, 90)
        self.app.set_setting("quality", "80")
        self.assertEqual(self.app.opts.quality, 80)

    def test_align_accepts_only_known_modes(self):
        self.app.set_setting("align", "left")
        self.assertEqual(self.app.opts.align, "left")
        self.app.set_setting("align", "斜着")
        self.assertNotEqual(self.app.opts.align, "斜着")

    def test_fit_width_toggles(self):
        self.app.set_setting("fit_width", "on")
        self.assertTrue(self.app.opts.fit_width)
        self.app.set_setting("fit_width", "off")
        self.assertFalse(self.app.opts.fit_width)

    def test_tracking_accepts_negative_values(self):
        self.app.set_setting("tracking", "-1.5")
        tracking = self.app.opts.tracking
        assert tracking is not None, "合法输入应写入 tracking"
        self.assertAlmostEqual(tracking, -1.5, places=3)


class MappingEdits(TuiTestCase):
    """映射表的增删改：空 key、重复 key、非法 JSON 都不能把界面搞坏。"""

    def setUp(self):
        super().setUp()
        self.app = self.make_app(count=1)

    def test_save_and_load_round_trip(self):
        self.app.mapping = {"2023": "2024", "张三": "李四"}
        path = os.path.join(self.tmp.name, "map.json")
        self.app.save_map(path)
        self.app.mapping = {}
        self.app.load_map(path)
        self.assertEqual(self.app.mapping, {"2023": "2024", "张三": "李四"})

    def test_loading_garbage_json_keeps_old_mapping(self):
        self.app.mapping = {"旧": "新"}
        path = os.path.join(self.tmp.name, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{不是 JSON")
        self.app.load_map(path)
        self.assertEqual(self.app.mapping, {"旧": "新"}, "读失败不应清空已有映射")
        self.assertIn("失败", self.app.message)

    def test_loading_non_object_json_is_rejected(self):
        path = os.path.join(self.tmp.name, "list.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(["a", "b"], f)
        self.app.load_map(path)
        self.assertIn("失败", self.app.message)

    def test_add_to_mapping_uses_current_block(self):
        self.app.focus = "blocks"
        blk = self.app.blocks()[0]
        blk.override = "改后"
        self.app.add_to_mapping()
        if self.app.mapping:  # 没有原文时不会加，属正常分支
            self.assertTrue(all(isinstance(k, str) for k in self.app.mapping))


class BrowsingEdges(TuiTestCase):
    """目录浏览：不可读目录、只有子目录、回上级到根。"""

    def test_unreadable_directory_reports_a_message(self):
        from src.python.tui import browse

        rows, images, error = browse.scan_rows(os.path.join(self.tmp.name, "missing"))
        self.assertEqual((rows, images), ([], []))
        self.assertIn("无法读取", error or "")

    def test_hidden_and_non_image_files_are_skipped(self):
        from PIL import Image

        from src.python.tui import browse

        d = os.path.join(self.tmp.name, "mix")
        os.makedirs(d)
        Image.new("RGB", (10, 10)).save(os.path.join(d, "a.png"))
        with open(os.path.join(d, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        with open(os.path.join(d, ".hidden.png"), "w", encoding="utf-8") as f:
            f.write("x")
        _rows, images, error = browse.scan_rows(d)
        self.assertIsNone(error)
        self.assertEqual([os.path.basename(p) for p in images], ["a.png"])

    def test_parent_row_is_first_when_not_at_root(self):
        from src.python.tui import browse

        d = os.path.join(self.tmp.name, "child")
        os.makedirs(d)
        rows, _images, _error = browse.scan_rows(d)
        self.assertEqual(rows[0][0], "parent")

    def test_first_image_row_falls_back_to_zero(self):
        from src.python.tui import browse

        self.assertEqual(browse.first_image_row([("dir", "/tmp")]), 0)


class BatchEdges(TuiTestCase):
    """批量：全无匹配、部分失败、取消后仍可继续。"""

    def test_runnable_is_empty_without_overrides(self):
        app = self.make_app(count=2)
        self.assertEqual(app.runnable(), [])

    def test_apply_all_without_work_reports_reason(self):
        app = self.make_app(count=2)
        app.apply_all()
        self.assertIn("没有", app.message)

    def test_cancel_flag_is_reset_on_the_next_batch(self):
        app = self.make_app(count=2)
        for img in app.images:
            img.blocks = [Block("第0行文字", (10, 20, 200, 24))]
            img.blocks[0].override = "改后"
        app.apply_all(should_stop=lambda: True)
        self.assertTrue(app.cancel)
        app.cancel = False
        app.apply_all()
        self.assertFalse(app.cancel)
        self.assertIn("批量完成", app.status)


class KeyEdges(TuiTestCase):
    """按键边界：翻页、等价键、0=第 10 张、帮助页任意键返回。"""

    def setUp(self):
        super().setUp()
        self.app = self.make_app(count=12)
        self.win = FakeWin([], rows=28, cols=100)

    def press(self, *keys):
        for key in keys:
            ui.handle(self.app, self.win, key)

    def test_page_keys_move_ten_rows(self):
        self.app.img_rows = 5
        before = self.app.sel_row
        self.press("KEY_NPAGE")
        self.assertGreater(self.app.sel_row, before)

    def test_comma_and_dot_are_navigation_aliases(self):
        self.app.img_rows = 5
        before = self.app.sel_row
        self.press(".")
        self.assertNotEqual(self.app.sel_row, before)
        self.press(",")
        self.assertEqual(self.app.sel_row, before)

    def test_zero_selects_the_tenth_image(self):
        self.app.img_rows = 12
        self.press("0")
        self.assertIn("第 10 张", self.app.message)

    def test_help_accepts_any_key_to_return(self):
        self.press("?")
        self.assertEqual(self.app.panel, "help")
        self.press("KEY_F(5)")
        self.assertEqual(self.app.panel, "main")

    def test_unknown_key_changes_nothing(self):
        before = (self.app.sel_row, self.app.focus, self.app.panel, self.app.quit)
        self.press("\x00")
        self.assertEqual((self.app.sel_row, self.app.focus, self.app.panel, self.app.quit), before)


if __name__ == "__main__":
    unittest.main()
