"""行内替换的报告/日志字段：`old` 是整行、`new` 只是片段，必须再记下命中的子串与区间。

历史遗留（归档 RF-6）：行内替换时报告里 `old` 是整行文字、`new` 只是替换片段，日志照录看起来
不对等。现在报告与写盘日志统一补 `fragment`（命中的原文子串）与 `span`（它在整行里的字符区间），
`old` / `new` / `mode` 三个旧字段语义不变，旧日志（没有新字段）照样能读。
"""

from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np

from src.python.core import audit, edit
from src.python.core.match import Job
from src.python.core.options import Options
from src.test._support import FONT_CJK, has_cjk_font

TEXT_COLOR = (30, 30, 30)
LINE = "年度报告2023"


def fake_info() -> dict:
    """analyze() 的替身：一块 40x200 的实心墨迹。"""
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
class InlineFragmentInReport(unittest.TestCase):
    def setUp(self):
        self.rgb = np.full((200, 320, 3), 255, np.uint8)
        self.opts = Options(quiet=True)
        self.opts.font = FONT_CJK  # 固定字体：不依赖系统字体池的排序
        self._orig_analyze = edit.analyze
        edit.analyze = lambda *_a, **_k: dict(fake_info())
        self.addCleanup(lambda: setattr(edit, "analyze", self._orig_analyze))

    def replace(self, job: Job) -> dict:
        _rgb, _alpha, report = edit.replace_image(self.rgb, None, [job], self.opts, [])
        self.assertEqual(len(report), 1, "一处任务应产出一条报告")
        return report[0]

    def test_inline_job_records_fragment_and_span(self):
        start = LINE.index("2023")
        op = self.replace(Job((10, 20, 200, 24), LINE, "2024", (start, start + 4)))
        self.assertEqual(op["old"], LINE, "old 仍是整行文字，语义不变")
        self.assertEqual(op["new"], "2024")
        self.assertEqual(op["fragment"], "2023", "fragment 是命中的原文子串")
        self.assertEqual(op["span"], [start, start + 4], "span 是子串在整行里的字符区间")
        self.assertEqual(op["mode"], "行内")

    def test_whole_line_job_has_no_fragment(self):
        op = self.replace(Job((10, 20, 200, 24), LINE, "年度财务总结2024"))
        self.assertEqual(op["mode"], "整行")
        self.assertIsNone(op["fragment"], "整行替换没有「命中子串」")
        self.assertIsNone(op["span"])

    def test_fragment_slice_matches_the_span_it_reports(self):
        for sub in ("2023", "年度", "报告"):
            start = LINE.index(sub)
            op = self.replace(Job((10, 20, 200, 24), LINE, "X", (start, start + len(sub))))
            self.assertEqual(op["fragment"], sub)
            self.assertEqual(LINE[op["span"][0] : op["span"][1]], op["fragment"])


class FragmentInWriteLog(unittest.TestCase):
    """日志里的 operations 也要带上 fragment/span，且旧记录（没这两个字段）照样读得出。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dst = os.path.join(self.tmp.name, "out.png")
        np.zeros((8, 8, 3), np.uint8)
        from PIL import Image

        Image.new("RGB", (8, 8), "white").save(self.dst)

    def entry(self, report: list[dict]) -> dict:
        return audit.build_entry(self.dst, self.dst, report, channel="cli", options=None)

    def test_log_operation_keeps_fragment_and_span(self):
        op = {
            "old": LINE,
            "new": "2024",
            "fragment": "2023",
            "span": [4, 8],
            "mode": "行内",
            "rect": [10, 20, 200, 24],
            "font": "X",
            "size": 24,
            "tracking": 0.0,
            "color": [30, 30, 30],
            "align": "center",
            "iou": 0.9,
        }
        logged = self.entry([op])["operations"][0]
        self.assertEqual(logged["fragment"], "2023")
        self.assertEqual(logged["span"], [4, 8])
        self.assertEqual(logged["old"], LINE, "整行文本照旧落进日志")

    def test_old_operation_without_new_fields_reads_as_none(self):
        op = {"old": LINE, "new": "2024", "mode": "行内", "rect": [0, 0, 1, 1]}
        logged = self.entry([op])["operations"][0]
        self.assertIsNone(logged["fragment"], "旧日志没有该字段，取到 None 而不是炸")
        self.assertIsNone(logged["span"])


if __name__ == "__main__":
    unittest.main()
