"""TUI 执行流程测试：替换当前图、批量确认、重名与覆盖保护。

用合成图 + 预置文字块，跳过 OCR。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.python.tui.app import App, Block, ImageItem
from src.test._support import TuiTestCase, has_cjk_font, make_text_image


class ApplyFlow(TuiTestCase):
    def build_app(self, out_sub: str = "out") -> App:
        tmp = tempfile.TemporaryDirectory()  # noqa: SIM115
        self.addCleanup(tmp.cleanup)
        rgb, boxes = make_text_image(["年度报告2023", "其余文字不动"])
        path = os.path.join(tmp.name, "report.png")
        Image.fromarray(rgb).save(path)
        app = App([tmp.name])
        app.out_dir = os.path.join(tmp.name, out_sub)
        self.current(app).blocks = [Block(text, rect) for text, rect in boxes]
        return app

    def current(self, app: App) -> ImageItem:
        """当前图片（build_app 一定造出了图，这里收窄 Optional）。"""
        img = app.cur
        assert img is not None
        return img

    def blocks_of(self, app: App) -> list[Block]:
        blocks = self.current(app).blocks
        assert blocks
        return blocks

    def saved_of(self, img: ImageItem) -> str:
        assert img.saved is not None
        return img.saved

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_apply_writes_output_and_marks_done(self):
        app = self.build_app()
        img = self.current(app)
        self.blocks_of(app)[0].override = "年度总结2024"
        ok, msg = app.apply_one(img)
        self.assertTrue(ok, msg)
        self.assertTrue(os.path.exists(self.saved_of(img)))
        self.assertTrue(img.done)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_reapply_reuses_same_output_file(self):
        app = self.build_app()
        img = self.current(app)
        self.blocks_of(app)[0].override = "年度总结2024"
        app.apply_one(img)
        first = self.saved_of(img)
        app.apply_one(img)
        self.assertEqual(img.saved, first)
        self.assertEqual(len(os.listdir(os.path.dirname(first))), 1)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_output_dir_inside_input_dir_is_refused(self):
        app = self.build_app(out_sub=".")  # 输出到输入目录 = 会覆盖原图
        img = self.current(app)
        self.blocks_of(app)[0].override = "年度总结2024"
        ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("覆盖原图", msg)

    def test_no_override_reports_reason(self):
        app = self.build_app()
        ok, msg = app.apply_one(self.current(app))
        self.assertFalse(ok)
        self.assertIn("没有启用", msg)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_batch_confirm_no_cancels(self):
        app = self.build_app()
        self.blocks_of(app)[0].override = "年度总结2024"
        self.drive(app, ["R"] + list("n") + ["\n", "q"])
        self.assertIn("已取消", app.message)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_batch_confirm_yes_runs_and_counts(self):
        app = self.build_app()
        self.blocks_of(app)[0].override = "年度总结2024"
        self.drive(app, ["R"] + list("y") + ["\n", "q"])
        self.assertIn("批量完成", app.status)
        self.assertTrue(self.current(app).done)

    def test_core_warnings_are_routed_to_the_message_hook(self):
        app = self.build_app()
        self.assertTrue(callable(app.opts.warn))  # 不再让核心层 print 冲花 curses
        app.on_core_warning("字体不可靠")
        self.assertEqual(app.warned[-1], "字体不可靠")

    def test_warnings_are_cleared_before_each_apply(self):
        app = self.build_app()
        app.warned.append("上一张图的旧提示")
        app.apply_one(self.current(app))  # 没有新文字 → 提前返回
        self.assertTrue(any("旧提示" in w for w in app.warned))  # 提前返回时不清理
        self.blocks_of(app)[0].override = "年度总结2024"
        app.apply_one(self.current(app))
        self.assertFalse(any("旧提示" in w for w in app.warned))

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_batch_progress_reports_index_and_name(self):
        app = self.build_app()
        self.blocks_of(app)[0].override = "年度总结2024"
        seen: list[str] = []
        app.apply_all(progress=seen.append)
        self.assertTrue(
            any("1/1" in msg and "report.png" in msg for msg in seen),
            f"进度信息应含序号与图名，实际：{seen}",
        )

    def test_batch_stops_before_first_image_when_should_stop_is_true(self):
        app = self.build_app()
        self.blocks_of(app)[0].override = "年度总结2024"
        app.images = app.images * 2  # 两张待处理，便于看"完成 0/2"
        app.apply_all(should_stop=lambda: True)
        self.assertTrue(app.cancel)
        self.assertIn("已取消", app.status)
        self.assertIn("0/2", app.status)

    def test_batch_runs_to_the_end_when_should_stop_is_false(self):
        app = self.build_app()
        self.blocks_of(app)[0].override = "年度总结2024"
        app.apply_all(should_stop=lambda: False)
        self.assertFalse(app.cancel)
        self.assertIn("批量完成", app.status)

    def test_pixel_outside_target_stays_identical(self):
        app = self.build_app()
        img = self.current(app)
        self.blocks_of(app)[0].override = "年度总结2024"
        before = np.array(Image.open(img.path))
        app.apply_one(img)
        after = np.array(Image.open(self.saved_of(img)))
        self.assertTrue(np.array_equal(before[120:180, 30:300], after[120:180, 30:300]))


if __name__ == "__main__":
    unittest.main()
