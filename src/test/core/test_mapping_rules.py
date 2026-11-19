"""映射规则测试：映射表与文字块如何变成替换任务（Job）。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

from src.python.core import jobs_from_blocks, norm_map, plan_jobs
from src.test._support import regions


class MappingRules(unittest.TestCase):
    """映射表的 key 与识别出的整行文字怎么匹配。"""

    def test_normalization_ignores_whitespace_and_narrow_forms(self):
        text = "年度 销售 报告"
        norm, idx = norm_map(text)
        self.assertEqual(norm, "年度销售报告")
        self.assertEqual([text[i] for i in idx], list(norm))

    def test_whole_line_key_rewrites_whole_line(self):
        jobs = plan_jobs(
            regions(("负责人：张三", (0, 0, 100, 20))), {"负责人：张三": "负责人：李四"}, warn=False
        )
        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0].span)
        self.assertEqual(jobs[0].new, "负责人：李四")

    def test_fragment_key_only_covers_that_fragment(self):
        text = "年度销售报告2023"
        jobs = plan_jobs(regions((text, (0, 0, 200, 20))), {"2023": "2024"}, warn=False)
        self.assertEqual(len(jobs), 1)
        span = jobs[0].span
        if span is None:
            raise AssertionError("应该是行内替换")
        self.assertEqual(text[span[0] : span[1]], "2023")

    def test_same_key_applies_to_every_occurrence(self):
        regs = regions(("2023 年总结", (0, 0, 100, 20)), ("计划 2023", (0, 30, 100, 20)))
        self.assertEqual(len(plan_jobs(regs, {"2023": "2024"}, warn=False)), 2)

    def test_whole_line_and_fragment_targets_coexist(self):
        regs = regions(("2023", (0, 0, 40, 20)), ("计划 2023", (0, 30, 100, 20)))
        jobs = plan_jobs(regs, {"2023": "2024"}, warn=False)
        self.assertEqual(sorted(j.span is None for j in jobs), [False, True])

    def test_similar_line_falls_back_to_whole_line(self):
        jobs = plan_jobs(
            regions(("年度销售报告2023", (0, 0, 200, 20))),
            {"年度销售报告2033": "新的标题"},
            warn=False,
        )
        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0].span)

    def test_unrelated_key_produces_no_job(self):
        self.assertEqual(
            plan_jobs(regions(("完全无关的一行", (0, 0, 100, 20))), {"电话": "热线"}, warn=False),
            [],
        )

    def test_fullwidth_digits_match_ascii_key(self):
        jobs = plan_jobs(regions(("编号 ２０２３", (0, 0, 120, 20))), {"2023": "2024"}, warn=False)
        self.assertEqual(len(jobs), 1)


class BlockOverrides(unittest.TestCase):
    """TUI 里块级设置（override/find/禁用）与全局映射的优先级。"""

    class Blk:
        def __init__(self, text, override=None, find=None, enabled=True, rect=(0, 0, 10, 10)):
            self.text, self.override, self.find = text, override, find
            self.enabled, self.rect = enabled, rect

    def test_block_override_beats_global_mapping(self):
        jobs = jobs_from_blocks([self.Blk("原文", override="新文")], {"原文": "映射文"}, warn=False)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].new, "新文")

    def test_block_find_field_produces_fragment_span(self):
        jobs = jobs_from_blocks(
            [self.Blk("年度报告2023", override="2024", find="2023")], {}, warn=False
        )
        span = jobs[0].span
        if span is None:
            raise AssertionError("应该是行内替换")
        self.assertEqual("年度报告2023"[span[0] : span[1]], "2023")

    def test_disabled_block_is_skipped(self):
        self.assertEqual(
            jobs_from_blocks([self.Blk("原文", override="新文", enabled=False)], {}, warn=False), []
        )

    def test_global_mapping_covers_blocks_without_override(self):
        blocks = [self.Blk("负责人：张三", override="负责人：李四"), self.Blk("电话 2023")]
        self.assertEqual(len(jobs_from_blocks(blocks, {"2023": "2024"}, warn=False)), 2)


if __name__ == "__main__":
    unittest.main()
