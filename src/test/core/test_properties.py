"""属性测试（hypothesis）：用生成的大量输入验证"永远成立的性质"。

手写用例只能覆盖我想到的输入；这里把纯函数的契约写成性质，让 hypothesis 去撞边界：
- `norm_map` 的下标必须能映射回原文（否则行内替换会切错字）
- `cut`/`pad` 的结果宽度必须 ≤ 请求宽度（否则界面会溢出）
- `parse_color` 只允许两种结果：合法三元组，或 `CoreError`
- `unique_path` 不能吞掉扩展名、不能返回已存在的路径
- `plan_jobs` 产出的 span 切出来必须真的是那个片段
"""

from __future__ import annotations

import os
import tempfile
import unittest

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.python.core import match
from src.python.core.errors import CoreError
from src.python.core.image import unique_path
from src.python.core.options import parse_color
from src.python.tui.ui_base import cut, dwidth, pad

SETTINGS = settings(
    max_examples=120, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


class NormMapProperties(unittest.TestCase):
    @SETTINGS
    @given(st.text(max_size=40))
    def test_index_covers_every_normalized_character(self, raw: str):
        text, index = match.norm_map(raw)
        self.assertEqual(len(text), len(index))
        for original in index:
            self.assertGreaterEqual(original, 0)
            self.assertLess(original, max(1, len(raw)))

    @SETTINGS
    @given(st.text(max_size=40))
    def test_normalization_is_idempotent(self, raw: str):
        once, _ = match.norm_map(raw)
        twice, _ = match.norm_map(once)
        self.assertEqual(once, twice)

    @SETTINGS
    @given(st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), max_size=30))
    def test_ascii_without_spaces_maps_one_to_one(self, raw: str):
        _text, index = match.norm_map(raw)
        if any(ch.isspace() for ch in raw):
            return
        self.assertEqual(index, list(range(len(raw))))


class WidthProperties(unittest.TestCase):
    @SETTINGS
    @given(st.text(max_size=40), st.integers(min_value=0, max_value=40))
    def test_cut_never_exceeds_the_budget(self, text: str, cols: int):
        self.assertLessEqual(dwidth(cut(text, cols)), cols)

    @SETTINGS
    @given(st.text(max_size=20), st.integers(min_value=0, max_value=30))
    def test_pad_fills_exactly_the_budget(self, text: str, cols: int):
        filled = pad(text, cols)
        self.assertEqual(dwidth(filled), cols)
        self.assertTrue(filled.startswith(cut(filled, cols)))


class ColorProperties(unittest.TestCase):
    @SETTINGS
    @given(st.text(max_size=12))
    def test_only_valid_triples_or_core_error(self, spec: str):
        try:
            rgb = parse_color(spec)
        except CoreError:
            return
        self.assertEqual(len(rgb), 3)
        for value in rgb:
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 255)

    @SETTINGS
    @given(st.integers(0, 255), st.integers(0, 255), st.integers(0, 255))
    def test_rgb_form_round_trips(self, r: int, g: int, b: int):
        self.assertEqual(parse_color(f"{r},{g},{b}"), (r, g, b))


class UniquePathProperties(unittest.TestCase):
    @SETTINGS
    @given(st.text(alphabet="abc-_", min_size=1, max_size=8))
    def test_numbering_keeps_extension_and_directory(self, stem: str):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, f"{stem}.png")
            open(base, "w", encoding="utf-8").close()
            candidate = unique_path(base)
            self.assertEqual(os.path.dirname(candidate), tmp)
            self.assertTrue(candidate.endswith(".png"))
            self.assertFalse(os.path.exists(candidate), "不能返回一个已存在的路径")


class PlanJobsProperties(unittest.TestCase):
    @SETTINGS
    @given(st.text(alphabet="2023年度报告负责人：", min_size=1, max_size=12))
    def test_span_slices_back_to_the_fragment(self, text: str):
        regions = [{"text": text, "rect": (0, 0, 100, 30), "score": 1.0}]
        jobs = match.plan_jobs(regions, {"2023": "2024"}, warn=False)
        for job in jobs:
            if job.span is None:
                continue
            start, end = job.span
            fragment, _ = match.norm_map(text[start:end])
            self.assertEqual(fragment, "2023", f"span 切到了别的字：{text!r}")


if __name__ == "__main__":
    unittest.main()
