"""图片读写与输出路径测试：格式支持、alpha 处理、目录扫描、重名编号、同文件判定。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.python.core.errors import CoreError
from src.python.core.image import (
    FMT_BY_EXT,
    collect_images,
    load_image,
    load_meta,
    reserve_path,
    same_file,
    save_image,
    unique_path,
)


class ImageReadWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()      # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)

    def test_png_roundtrip_preserves_pixels(self):
        rgb = np.full((20, 30, 3), 128, np.uint8)
        dst = os.path.join(self.tmp.name, "a.png")
        save_image(rgb, None, dst)
        back, alpha = load_image(dst)
        self.assertEqual(back.shape, (20, 30, 3))
        self.assertIsNone(alpha)
        self.assertTrue(np.all(back == 128))

    def test_jpeg_output_flattens_alpha(self):
        rgb = np.full((10, 10, 3), 200, np.uint8)
        alpha = np.full((10, 10), 128, np.uint8)
        dst = os.path.join(self.tmp.name, "b.jpg")
        save_image(rgb, alpha, dst)
        with Image.open(dst) as im:
            self.assertEqual(im.mode, "RGB")

    def test_supported_output_formats_cover_common_extensions(self):
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif"):
            self.assertIn(ext, FMT_BY_EXT)

    def test_unsupported_output_extension_raises_core_error(self):
        dst = os.path.join(self.tmp.name, "out.xyz")
        with self.assertRaises(CoreError) as ctx:
            save_image(np.zeros((4, 4, 3), np.uint8), None, dst)
        self.assertIn("不支持的输出格式", str(ctx.exception))
        self.assertFalse(os.path.exists(dst))

    def test_palette_png_transparency_is_returned_as_alpha(self):
        path = os.path.join(self.tmp.name, "palette.png")
        im = Image.new("P", (8, 8), 1)
        im.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
        im.paste(0, (0, 0, 4, 4))                       # 左上角画成透明索引色
        im.save(path, transparency=0)

        rgb, alpha = load_image(path)

        self.assertIsNotNone(alpha)
        assert alpha is not None
        self.assertEqual(int(alpha[0, 0]), 0)           # 透明区保留下来
        self.assertEqual(int(alpha[-1, -1]), 255)
        self.assertEqual(rgb.shape, (8, 8, 3))

    def test_load_meta_reads_dpi_and_icc(self):
        path = os.path.join(self.tmp.name, "meta.jpg")
        Image.new("RGB", (8, 8), (1, 2, 3)).save(path, dpi=(144, 144),
                                                icc_profile=b"fake-icc")
        meta = load_meta(path)
        dpi = meta.get("dpi")
        assert isinstance(dpi, tuple)
        self.assertAlmostEqual(float(dpi[0]), 144, delta=1)
        self.assertEqual(meta.get("icc_profile"), b"fake-icc")

    def test_save_image_carries_meta_to_output(self):
        rgb = np.full((8, 8, 3), 90, np.uint8)
        dst = os.path.join(self.tmp.name, "out.png")
        save_image(rgb, None, dst, meta={"icc_profile": b"fake-icc", "dpi": (72, 72)})
        back = load_meta(dst)
        self.assertEqual(back.get("icc_profile"), b"fake-icc")

    def test_jpeg_quality_option_changes_file_size(self):
        rng = np.random.default_rng(7)
        rgb = rng.integers(0, 256, (60, 60, 3), dtype=np.uint8)
        best = os.path.join(self.tmp.name, "best.jpg")
        small = os.path.join(self.tmp.name, "small.jpg")
        save_image(rgb, None, best, quality=95)
        save_image(rgb, None, small, quality=30)
        self.assertLess(os.path.getsize(small), os.path.getsize(best))

    def test_webp_quality_option_is_applied(self):
        rng = np.random.default_rng(11)
        rgb = rng.integers(0, 256, (80, 80, 3), dtype=np.uint8)
        best = os.path.join(self.tmp.name, "best.webp")
        small = os.path.join(self.tmp.name, "small.webp")
        save_image(rgb, None, best, quality=95)
        save_image(rgb, None, small, quality=20)
        self.assertLess(os.path.getsize(small), os.path.getsize(best))

    def test_invalid_quality_raises_core_error(self):
        dst = os.path.join(self.tmp.name, "q.jpg")
        with self.assertRaises(CoreError) as ctx:
            save_image(np.zeros((4, 4, 3), np.uint8), None, dst, quality=0)
        self.assertIn("1-100", str(ctx.exception))
        self.assertFalse(os.path.exists(dst))

    def test_fully_opaque_rgba_image_returns_no_alpha(self):
        path = os.path.join(self.tmp.name, "opaque.png")
        Image.new("RGBA", (6, 6), (10, 20, 30, 255)).save(path)
        _rgb, alpha = load_image(path)
        self.assertIsNone(alpha)                        # 不必要地带 alpha 会改变输出模式

    def test_directory_scan_keeps_images_and_sorts(self):
        for name in ("b.PNG", "a.jpg"):
            Image.new("RGB", (4, 4)).save(os.path.join(self.tmp.name, name))
        with open(os.path.join(self.tmp.name, "note.txt"), "w", encoding="utf-8") as f:
            f.write("ignore me")
        found = collect_images(self.tmp.name)
        self.assertEqual([os.path.basename(p) for p in found], ["a.jpg", "b.PNG"])
        single = os.path.join(self.tmp.name, "a.jpg")
        self.assertEqual(collect_images(single), [single])


class OutputPaths(unittest.TestCase):
    def test_reserve_path_never_reuses_an_existing_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = reserve_path(os.path.join(tmp, "a.png"))
            second = reserve_path(os.path.join(tmp, "a.png"))
            self.assertEqual(os.path.basename(first), "a.png")
            self.assertEqual(os.path.basename(second), "a-1.png")
            self.assertTrue(os.path.exists(first))       # 占位文件已创建
            self.assertTrue(os.path.exists(second))

    def test_reserve_path_creates_missing_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = reserve_path(os.path.join(tmp, "deep", "out.png"))
            self.assertTrue(os.path.isfile(path))

    def test_duplicate_output_name_gets_numbered_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = os.path.join(tmp, "a.png")
            self.assertEqual(unique_path(first), first)          # 不存在就用原名
            open(first, "wb").close()
            second = unique_path(first)
            self.assertEqual(os.path.basename(second), "a-1.png")
            open(second, "wb").close()
            self.assertEqual(os.path.basename(unique_path(first)), "a-2.png")
            self.assertEqual(os.path.splitext(unique_path(first))[1], ".png")

    def test_same_path_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.png")
            b = os.path.join(tmp, "b.png")
            dotted = os.path.join(tmp, ".", "a.png")
            self.assertTrue(same_file(a, a))
            self.assertTrue(same_file(a, dotted))
            self.assertFalse(same_file(a, b))


if __name__ == "__main__":
    unittest.main()
