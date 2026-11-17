"""OCR 封装测试：结果结构、区域裁剪、引擎缺失时的错误契约。

不加载真实模型：直接喂假结果给 `_ocr`，或用桩替换引擎。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

import numpy as np

from src.python.core import ocr
from src.python.core.errors import CoreError


class OcrResultParsing(unittest.TestCase):
    def test_box_is_converted_to_axis_aligned_rect(self):
        result = [([[10.4, 20.6], [110.2, 20.6], [110.2, 60.1], [10.4, 60.1]], "标题", 0.9)]
        got = ocr._ocr(result)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["text"], "标题")
        self.assertEqual(got[0]["rect"], (10, 20, 100, 40))
        self.assertAlmostEqual(got[0]["score"], 0.9, places=3)

    def test_blank_text_is_dropped(self):
        result = [([[0, 0], [10, 0], [10, 10], [0, 10]], "   ", 0.5)]
        self.assertEqual(ocr._ocr(result), [])

    def test_empty_result_is_empty_list(self):
        self.assertEqual(ocr._ocr(None), [])
        self.assertEqual(ocr._ocr([]), [])


class OcrRegionCalls(unittest.TestCase):
    class Engine:
        def __init__(self, result):
            self.result = result
            self.seen = []

        def __call__(self, image):
            self.seen.append(image.shape)
            return self.result, 0.01

    def setUp(self):
        self.original = ocr._engine
        self.addCleanup(setattr, ocr, "_engine", self.original)

    def patch_engine(self, result):
        engine = self.Engine(result)
        ocr._engine = lambda: engine
        return engine

    def test_regions_uses_bgr_conversion(self):
        rgb = np.zeros((30, 40, 3), np.uint8)
        engine = self.patch_engine([([[5, 5], [25, 5], [25, 20], [5, 20]], "文字", 0.8)])
        got = ocr.ocr_regions(rgb)
        self.assertEqual(got[0]["text"], "文字")
        self.assertEqual(engine.seen[0], (30, 40, 3))

    def test_crop_merges_blocks_in_reading_order(self):
        rgb = np.zeros((80, 120, 3), np.uint8)
        self.patch_engine([
            ([[10, 30], [60, 30], [60, 50], [10, 50]], "第二", 0.9),
            ([[10, 5], [50, 5], [50, 25], [10, 25]], "第一", 0.9),
        ])
        self.assertEqual(ocr.ocr_crop(rgb, (0, 0, 120, 80)), "第一 第二")

    def test_crop_outside_image_returns_none(self):
        rgb = np.zeros((10, 10, 3), np.uint8)
        self.assertIsNone(ocr.ocr_crop(rgb, (50, 50, 10, 10)))

    def test_missing_dependency_raises_core_error(self):
        ocr._LOCAL.engine = None
        original_import = ocr.__dict__.get("RapidOCR", None)
        self.assertIsNone(original_import)          # 未真正加载过模型
        probe = np.zeros((8, 8, 3), np.uint8)
        try:
            ocr.ocr_regions(probe)
        except CoreError:
            self.skipTest("环境未安装 OCR 依赖，错误契约符合预期")
        finally:
            ocr._LOCAL.engine = None


if __name__ == "__main__":
    unittest.main()
