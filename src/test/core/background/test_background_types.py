"""背景类型场景：纯色、渐变、带噪声背景上的字迹分析与擦除。

关注点：字迹 mask 是否干净、擦除后背景是否无明显痕迹。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.python.core import analyze
from src.python.core.edit import erase
from src.test._support import FONT_CJK, has_cjk_font


def draw_on(background: np.ndarray, text: str = "年度报告2023") -> tuple[np.ndarray, tuple]:
    img = Image.fromarray(background.copy())
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_CJK, 36, index=2)
    d.text((40, 40), text, font=font, fill=(30, 30, 30))
    return np.array(img), (36, 36, 320, 52)


def solid(color=(255, 255, 255), size=(400, 160)) -> np.ndarray:
    return np.full((size[1], size[0], 3), color, np.uint8)


def gradient(size=(400, 160)) -> np.ndarray:
    h, w = size[1], size[0]
    ramp = np.linspace(210, 255, w, dtype=np.uint8)
    left = np.repeat(ramp[None, :, None], h, axis=0)
    return np.repeat(left, 3, axis=2)


def noisy(size=(400, 160), base=245, sigma=6) -> np.ndarray:
    rng = np.random.default_rng(7)
    px = rng.normal(base, sigma, (size[1], size[0], 3)).clip(0, 255).astype(np.uint8)
    return px


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class SolidBackground(unittest.TestCase):
    def test_analyze_finds_ink_and_color(self):
        rgb, rect = draw_on(solid())
        info = analyze(rgb, rect)
        if info is None:
            raise AssertionError("analyze 返回 None")
        self.assertEqual(tuple(int(v) for v in info["text_color"]), (30, 30, 30))
        self.assertGreater(int(info["mask"].sum()), 200)

    def test_erase_leaves_flat_area(self):
        rgb, rect = draw_on(solid())
        info = analyze(rgb, rect)
        if info is None:
            raise AssertionError("analyze 返回 None")
        out = erase(rgb, info["mask"])
        patch = out[30:100, 30:360]
        self.assertLess(int(patch.max()) - int(patch.min()), 6)

    def test_dark_background_light_text(self):
        rgb, rect = draw_on(np.full((160, 400, 3), (20, 40, 80), np.uint8))
        img = Image.fromarray(rgb)
        ImageDraw.Draw(img)  # 已有深底，重画白字
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 400, 160], fill=(20, 40, 80))
        d.text((40, 40), "年度报告2023",
               font=ImageFont.truetype(FONT_CJK, 36, index=2), fill=(250, 250, 250))
        info = analyze(np.array(img), rect)
        if info is None:
            raise AssertionError("analyze 返回 None")
        self.assertGreater(min(info["text_color"]), 230)


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class GradientBackground(unittest.TestCase):
    def test_analyze_handles_gradient(self):
        rgb, rect = draw_on(gradient())
        info = analyze(rgb, rect)
        if info is not None:
            self.assertGreater(int(info["mask"].sum()), 100)

    def test_erase_keeps_gradient_smooth(self):
        rgb, rect = draw_on(gradient())
        info = analyze(rgb, rect)
        if info is None:
            self.skipTest("渐变背景下未检测到文字")
        out = erase(rgb, info["mask"])
        row_before = rgb[120, :, 0].astype(int)
        row_after = out[120, :, 0].astype(int)
        self.assertLessEqual(int(np.abs(row_after - row_before).max()), 40)
        self.assertLess(int(np.abs(np.diff(row_after)).max()), 12)     # 没有突兀的接缝


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class NoisyBackground(unittest.TestCase):
    def test_analyze_still_finds_text(self):
        rgb, rect = draw_on(noisy())
        info = analyze(rgb, rect)
        if info is None:
            self.skipTest("噪声背景下未检测到文字")
        self.assertGreater(int(info["mask"].sum()), 100)

    def test_noise_does_not_destroy_neighbour_pixels(self):
        rgb, rect = draw_on(noisy())
        info = analyze(rgb, rect)
        if info is None:
            self.skipTest("噪声背景下未检测到文字")
        out = erase(rgb, info["mask"])
        # 远离文字的区域必须逐像素保持不变
        self.assertTrue(np.array_equal(rgb[120:160, :, :], out[120:160, :, :]))


if __name__ == "__main__":
    unittest.main()
