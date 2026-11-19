"""透明通道场景：带 alpha 的图擦除后不留字形轮廓，重绘后新字不透明。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import os
import tempfile
import unittest

from PIL import Image, ImageDraw

from src.python.core import Options, analyze, build_font_pool, plan_jobs, replace_image
from src.python.core.image import load_image, save_image
from src.test._support import cjk_font, has_cjk_font


def transparent_text_image():
    """透明底 + 半透明白字：最容易暴露 alpha 未修复的问题。"""
    img = Image.new("RGBA", (360, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((30, 40), "年度报告2023", font=cjk_font(36), fill=(255, 255, 255, 255))
    return img


@unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
class AlphaHandling(unittest.TestCase):
    def test_load_splits_alpha_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.png")
            transparent_text_image().save(path)
            rgb, alpha = load_image(path)
            self.assertEqual(rgb.shape[2], 3)
            if alpha is None:
                raise AssertionError("应该带 alpha 通道")
            self.assertEqual(alpha.shape, rgb.shape[:2])

    def test_erase_also_clears_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.png")
            transparent_text_image().save(path)
            rgb, alpha = load_image(path)
            info = analyze(rgb, (28, 38, 300, 50))
            if info is None:
                self.skipTest("透明底上未检测到文字")
            from src.python.core.edit import erase

            if alpha is None:
                raise AssertionError("应该带 alpha 通道")
            alpha_out = erase(alpha, info["mask"])
            inside = alpha_out[45:80, 35:250]
            self.assertEqual(int(inside.max()), 0)  # 原字迹位置的 alpha 被清掉

    def test_replacement_paints_opaque_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.png")
            transparent_text_image().save(path)
            rgb, alpha = load_image(path)
            jobs = plan_jobs(
                [{"text": "年度报告2023", "rect": (28, 38, 300, 50), "score": 1.0}],
                {"2023": "2024"},
                warn=False,
            )
            pool = build_font_pool(["年度报告2023"], None, 6)
            _out, new_alpha, report = replace_image(rgb, alpha, jobs, Options(quiet=True), pool)
            if new_alpha is None:
                raise AssertionError("alpha 丢失")
            self.assertEqual(len(report), 1)
            self.assertGreater(int(new_alpha.max()), 200)

    def test_saving_to_jpeg_flattens_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            rgb, alpha = load_image(_write(transparent_text_image(), tmp))
            dst = os.path.join(tmp, "b.jpg")
            save_image(rgb, alpha, dst)
            with Image.open(dst) as im:
                self.assertEqual(im.mode, "RGB")


def _write(img: Image.Image, tmp: str) -> str:
    path = os.path.join(tmp, "src.png")
    img.save(path)
    return path


if __name__ == "__main__":
    unittest.main()
