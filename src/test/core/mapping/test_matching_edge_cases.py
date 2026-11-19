"""映射规则的边界：归一化、整行/行内/模糊命中、冲突与低置信过滤。"""

from __future__ import annotations

import contextlib
import io
import unittest

from src.python.core import match


class MatchGaps(unittest.TestCase):
    def test_unmatched_key_is_reported_to_sink(self):
        seen: list[str] = []
        regions = [{"text": "完全无关的一行", "rect": (0, 0, 100, 30), "score": 1.0}]
        match.plan_jobs(regions, {"2023": "2024"}, warn=True, sink=seen.append)
        self.assertTrue(any("未找到待替换文字" in item for item in seen))


class MatchFuzzyPrint(unittest.TestCase):
    def test_fuzzy_match_warns_on_stderr_without_sink(self):
        regions = [{"text": "年度报告2O23", "rect": (0, 0, 100, 30), "score": 1.0}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            jobs = match.plan_jobs(regions, {"年度报告2023": "新"}, warn=True)
        self.assertEqual(len(jobs), 1)
        self.assertIn("模糊匹配", err.getvalue())


class EmptyMappingKey(unittest.TestCase):
    def test_empty_key_is_skipped(self):
        regions = [{"text": "年度报告", "rect": (0, 0, 100, 30), "score": 1.0}]
        self.assertEqual(match.plan_jobs(regions, {"": "新"}, warn=False), [])


class NormMap(unittest.TestCase):
    def test_whitespace_and_fullwidth_are_normalized(self):
        text, index = match.norm_map("年度 报告２０２３")
        self.assertEqual(text, "年度报告2023")
        self.assertEqual(len(index), len(text))

    def test_index_maps_back_to_original_characters(self):
        raw = "第 1 期２０２３"
        text, index = match.norm_map(raw)
        start = text.index("2023")
        self.assertEqual(raw[index[start]], "２")

    def test_empty_text_yields_empty_result(self):
        self.assertEqual(match.norm_map(""), ("", []))


class PlanJobs(unittest.TestCase):
    def regions(self, *texts):
        return [
            {"text": t, "rect": (0, i * 40, 200, 30), "score": 1.0} for i, t in enumerate(texts)
        ]

    def test_whole_line_match_produces_one_job(self):
        out = match.plan_jobs(
            self.regions("年度报告2023"), {"年度报告2023": "年度总结2024"}, warn=False
        )
        self.assertEqual(len(out), 1)
        self.assertIsNone(out[0].span)

    def test_inline_fragment_produces_span(self):
        out = match.plan_jobs(self.regions("负责人：2023"), {"2023": "2024"}, warn=False)
        self.assertEqual(len(out), 1)
        span = out[0].span
        assert span is not None, "行内替换必须给出 span"
        start, end = span
        self.assertEqual("负责人：2023"[start:end], "2023")

    def test_all_occurrences_of_a_fragment_become_jobs(self):
        out = match.plan_jobs(self.regions("2023 到 2023"), {"2023": "2024"}, warn=False)
        self.assertEqual(len(out), 2)

    def test_unmatched_text_produces_nothing(self):
        self.assertEqual(
            match.plan_jobs(self.regions("无关文字"), {"2023": "2024"}, warn=False), []
        )

    def test_empty_mapping_produces_nothing(self):
        self.assertEqual(match.plan_jobs(self.regions("年度报告2023"), {}, warn=False), [])

    def test_warning_sink_receives_fuzzy_hint(self):
        seen: list[str] = []
        match.plan_jobs(
            self.regions("年度报告2O23"), {"年度报告2023": "新"}, warn=True, sink=seen.append
        )
        self.assertTrue(seen, "模糊匹配时应通过 sink 提示，而不是 print")
