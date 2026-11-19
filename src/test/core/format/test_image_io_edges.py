"""图片读写边界：alpha 保留、格式表、元数据读取失败。"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.python.core import image
from src.python.core.errors import CoreError


class ImageGaps(unittest.TestCase):
    def test_png_with_alpha_keeps_transparency(self):
        with tempfile.TemporaryDirectory() as tmp:
            rgb = np.full((20, 20, 3), 200, np.uint8)
            alpha = np.full((20, 20), 128, np.uint8)
            dst = os.path.join(tmp, "a.png")
            image.save_image(rgb, alpha, dst)
            _rgb, loaded_alpha = image.load_image(dst)
            self.assertIsNotNone(loaded_alpha)
            assert loaded_alpha is not None
            self.assertLess(int(loaded_alpha.min()), 255, "半透明应被保留")


class MetaFailure(unittest.TestCase):
    def test_unreadable_meta_returns_empty(self):
        with mock.patch.object(image.Image, "open", side_effect=OSError("boom")):
            self.assertEqual(image.load_meta("/nope.png"), {})


class ImageFormatTable(unittest.TestCase):
    """格式表与保存行为：不支持的扩展名必须是一句 CoreError，而不是 traceback。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rgb = np.full((20, 30, 3), 200, np.uint8)

    def test_unknown_extension_raises_core_error(self):
        from src.python.core.image import save_image

        with self.assertRaises(CoreError):
            save_image(self.rgb, None, os.path.join(self.tmp.name, "out.xyz"))

    def test_quality_out_of_range_is_rejected(self):
        from src.python.core.image import save_image

        for quality in (0, 101, -5):
            with self.subTest(quality=quality), self.assertRaises(CoreError):
                save_image(self.rgb, None, os.path.join(self.tmp.name, "out.jpg"), quality=quality)

    def test_alpha_is_flattened_for_jpeg(self):
        from src.python.core.image import save_image

        alpha = np.zeros((20, 30), np.uint8)
        alpha[:, :10] = 255
        dst = os.path.join(self.tmp.name, "flat.jpg")
        save_image(self.rgb, alpha, dst)
        self.assertTrue(os.path.exists(dst))
