"""擦除阶段的自适应 inpaint 半径：粗笔画要更大邻域，细笔画不能糊开。

固定半径 4 在大标题/加粗字上会留下模糊边；半径跟笔画宽度走，
同时必须有上下限，避免细字被过度抹平。
"""

from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from src.python.core import edit


def thin_stroke_mask() -> np.ndarray:
    """3px 宽的细横线，模拟常规字重的笔画。"""
    mask = np.zeros((60, 200), bool)
    mask[28:31, 20:180] = True
    return mask


def thick_stroke_mask() -> np.ndarray:
    """24px 宽的粗条，模拟大标题/粗体的笔画。"""
    mask = np.zeros((120, 240), bool)
    mask[40:64, 20:220] = True
    return mask


class InpaintRadius(unittest.TestCase):
    def test_empty_mask_falls_back_to_minimum(self):
        self.assertEqual(edit.inpaint_radius(np.zeros((10, 10), bool)), edit.INPAINT_RADIUS_MIN)

    def test_thin_stroke_stays_at_minimum(self):
        self.assertEqual(edit.inpaint_radius(thin_stroke_mask()), edit.INPAINT_RADIUS_MIN)

    def test_thick_stroke_gets_a_larger_radius(self):
        radius = edit.inpaint_radius(thick_stroke_mask())
        self.assertGreater(radius, edit.INPAINT_RADIUS_MIN)
        self.assertLessEqual(radius, edit.INPAINT_RADIUS_MAX)

    def test_radius_grows_with_stroke_width(self):
        radii = []
        for width in (4, 10, 20, 40):
            mask = np.zeros((160, 240), bool)
            mask[60 : 60 + width, 20:220] = True
            radii.append(edit.inpaint_radius(mask))
        self.assertEqual(radii, sorted(radii), f"笔画越粗半径应越大，实际 {radii}")

    def test_radius_is_clamped_to_maximum(self):
        mask = np.zeros((300, 300), bool)  # 整块都是"字"，笔画宽度远超上限
        mask[10:290, 10:290] = True
        self.assertEqual(edit.inpaint_radius(mask), edit.INPAINT_RADIUS_MAX)

    def test_erase_passes_adaptive_radius_to_inpaint(self):
        """erase 传给 cv2.inpaint 的半径必须跟笔画走，而不是写死的 4。

        erase 会先膨胀再模糊 mask，半径与原始 mask 直算的结果略有差异，
        所以只断言"粗笔画拿到的半径明显大于下限、细笔画就是下限"。
        """
        img = np.full((120, 240, 3), 250, np.uint8)
        with mock.patch.object(edit.cv2, "inpaint", wraps=edit.cv2.inpaint) as spy:
            edit.erase(img, thick_stroke_mask())
        self.assertGreater(spy.call_args.args[2], edit.INPAINT_RADIUS_MIN)

        with mock.patch.object(edit.cv2, "inpaint", wraps=edit.cv2.inpaint) as spy:
            edit.erase(np.full((60, 200, 3), 250, np.uint8), thin_stroke_mask())
        self.assertEqual(spy.call_args.args[2], edit.INPAINT_RADIUS_MIN)


if __name__ == "__main__":
    unittest.main()
