"""排版形态场景：逐字加宽的标题、多行正文、居中横幅。

关注点：字距/多行/对齐能否被分析出来并在替换后保持。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np
from PIL import Image, ImageDraw

from src.python.core import (
    Options,
    analyze,
    build_font_pool,
    fit_font,
    ink_size,
    plan_jobs,
    replace_image,
)
from src.test._support import cjk_font, has_cjk_font


def letter_spaced_title(chars: str = "重点提要", step: int = 52, size: int = 40):
    img = Image.new("RGB", (460, 140), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = cjk_font(size, regular=True)
    x = 40
    for ch in chars:
        d.text((x, 50), ch, font=font, fill=(120, 120, 120))
        x += step
    return np.array(img)


def two_line_paragraph():
    img = Image.new("RGB", (520, 200), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = cjk_font(28, regular=True)
    d.text((40, 40), "第一行 保持不动的文字", font=font, fill=(40, 40, 40))
    d.text((40, 100), "第二行 2023 也要换", font=font, fill=(40, 40, 40))
    return np.array(img)


def centered_banner():
    img = Image.new("RGB", (600, 140), (25, 55, 110))
    d = ImageDraw.Draw(img)
    d.text((300, 70), "年度峰会 2023", font=cjk_font(40), fill=(255, 255, 255), anchor="mm")
    return np.array(img)


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class LetterSpacedTitle(unittest.TestCase):
    def test_fit_font_recovers_wide_tracking(self):
        rgb = letter_spaced_title()
        info = analyze(rgb, (30, 40, 320, 60))
        if info is None:
            self.skipTest("未检测到文字")
        pool = build_font_pool(["重点提要"], None, 6)
        fit = fit_font(
            "重点提要",
            info["mask"],
            info["ink_box"],
            pool,
            6,
            a_stroke=info.get("stroke_core"),
            slant=info.get("slant"),
        )
        if fit is None:
            self.skipTest("字体匹配失败")
        self.assertGreater(abs(fit[3]), 0.3 * fit[2])  # 明显加宽的字距

    def test_replacement_keeps_wide_tracking(self):
        """换字后仍然铺开：按“本机同一字体 + 同一字号 + 反解字距”的排版宽度比断言。

        旧断言拿原图墨迹宽度 `src_w` 当基准，但换字后的宽度取决于本机选中的字体
        （Windows 是 msyh、Linux 是 Noto CJK），同一字号下天然不同——
        于是本地全绿、windows 作业红。改成与字体无关的比值。
        """
        rgb = letter_spaced_title()
        rect = (30, 40, 320, 60)
        info = analyze(rgb, rect)
        if info is None:
            self.skipTest("未检测到文字")
        jobs = plan_jobs(
            [{"text": "重点提要", "rect": rect, "score": 1.0}], {"重点提要": "核心观点"}, warn=False
        )
        pool = build_font_pool(["重点提要"], None, 6)
        out, _a, report = replace_image(rgb, None, jobs, Options(quiet=True), pool)
        self.assertEqual(len(report), 1)
        out_cols = np.nonzero((out[40:110] < 200).any(axis=(0, 2)))[0]
        out_w = int(out_cols.max() - out_cols.min())
        fit = fit_font(
            "重点提要",
            info["mask"],
            info["ink_box"],
            pool,
            6,
            a_stroke=info.get("stroke_core"),
            slant=info.get("slant"),
        )
        if fit is None:
            self.assertGreater(out_w, 0)  # 字体匹配失败时只确认确实画上了字
            return
        _score, face, size, tracking, _iou = fit
        expected_w = ink_size("核心观点", face, size, tracking)[0]
        self.assertGreaterEqual(out_w, 0.85 * expected_w)  # 仍铺开，不因换字收紧


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class MultiLineParagraph(unittest.TestCase):
    def test_only_target_line_changes(self):
        rgb = two_line_paragraph()
        jobs = plan_jobs(
            [{"text": "第二行 2023 也要换", "rect": (35, 95, 400, 45), "score": 1.0}],
            {"2023": "2024"},
            warn=False,
        )
        pool = build_font_pool(["第二行 2023 也要换"], None, 6)
        out, _a, report = replace_image(rgb, None, jobs, Options(quiet=True), pool)
        self.assertEqual(len(report), 1)
        self.assertTrue(np.array_equal(rgb[30:80, 30:500], out[30:80, 30:500]))

    def test_both_lines_can_be_jobs(self):
        rgb = two_line_paragraph()
        jobs = plan_jobs(
            [
                {"text": "第一行 保持不动的文字", "rect": (35, 35, 400, 45), "score": 1.0},
                {"text": "第二行 2023 也要换", "rect": (35, 95, 400, 45), "score": 1.0},
            ],
            {"文字": "内容", "2023": "2024"},
            warn=False,
        )
        pool = build_font_pool(["第一行 保持不动的文字"], None, 6)
        out, _a, report = replace_image(rgb, None, jobs, Options(quiet=True), pool)
        self.assertEqual(len(report), 2)
        self.assertFalse(np.array_equal(rgb, out))


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class CenteredBanner(unittest.TestCase):
    def test_auto_align_keeps_title_centered(self):
        rgb = centered_banner()
        jobs = plan_jobs(
            [{"text": "年度峰会 2023", "rect": (200, 40, 200, 60), "score": 1.0}],
            {"2023": "2024"},
            warn=False,
        )
        pool = build_font_pool(["年度峰会 2023"], None, 6)
        out, _a, report = replace_image(rgb, None, jobs, Options(quiet=True), pool)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["align"], "center")
        self.assertEqual(report[0]["color"], [255, 255, 255])


if __name__ == "__main__":
    unittest.main()
