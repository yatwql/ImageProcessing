"""替换过程中的中断：`replace_image(should_stop=...)` 要在块与块之间能停手。

TUI 的批量取消以前只在"两张图之间"生效，单张图里 OCR + 字体匹配卡住时按 Esc 没反应。
现在每处理一块之前问一次回调，停手时保留已完成的块，调用方据此提示「已取消，完成 x/y」。
"""

from __future__ import annotations

import unittest

import numpy as np

from src.python.core import edit
from src.python.core.match import Job
from src.python.core.options import Options
from src.test._support import FONT_CJK, has_cjk_font

TEXT_COLOR = (30, 30, 30)


def fake_info() -> dict:
    """analyze() 的替身：一块 40x30 的实心墨迹。"""
    mask = np.zeros((200, 320), bool)
    mask[20:50, 10:210] = True
    return {
        "mask": mask,
        "ink_box": (10, 20, 210, 50),
        "text_color": TEXT_COLOR,
        "stroke": 3.0,
        "stroke_core": 3.0,
        "slant": 0.0,
    }


@unittest.skipUnless(has_cjk_font(), "需要 CJK 字体（Debian/Ubuntu 装 fonts-noto-cjk）")
class ReplacementCancel(unittest.TestCase):
    def setUp(self):
        self.rgb = np.full((200, 320, 3), 255, np.uint8)
        self.jobs = [Job((10, 20 + i * 30, 200, 24), "原文", f"新文{i}") for i in range(3)]
        self.opts = Options(quiet=True)
        self.opts.font = FONT_CJK          # 固定字体：不依赖系统字体池的排序
        self._orig_analyze = edit.analyze
        edit.analyze = lambda *_a, **_k: dict(fake_info())
        self.addCleanup(lambda: setattr(edit, "analyze", self._orig_analyze))

    def run_replace(self, should_stop=None):
        return edit.replace_image(
            self.rgb, None, self.jobs, self.opts, [],
            should_stop=should_stop,
        )

    def test_stops_before_first_block_when_already_cancelled(self):
        _out, _alpha, report = self.run_replace(should_stop=lambda: True)
        self.assertEqual(report, [], "还未开始就取消，不应有任何替换")

    def test_stops_after_the_first_block_and_keeps_it(self):
        calls = {"n": 0}

        def stop_after_first() -> bool:
            calls["n"] += 1
            return calls["n"] > 1          # 第一块放行，第二块之前叫停

        _out, _alpha, report = self.run_replace(should_stop=stop_after_first)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["new"], "新文0")

    def test_runs_all_blocks_without_a_callback(self):
        _out, _alpha, report = self.run_replace()
        self.assertEqual([r["new"] for r in report], ["新文0", "新文1", "新文2"])

    def test_keeps_going_when_callback_says_no(self):
        _out, _alpha, report = self.run_replace(should_stop=lambda: False)
        self.assertEqual(len(report), 3)


if __name__ == "__main__":
    unittest.main()
