"""功能边界：映射规则、颜色解析、任务构造、日志轮转等容易漏的输入。

这些用例盯的是"用户真会这么用，但主流程用例没覆盖"的角落：
空值、极值、非法值、重复键、多行文字、行内区间越界。
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile
import unittest

import numpy as np

from src.python.core import audit, jobs, match, options
from src.python.core.errors import CoreError


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


class AreaJobs(unittest.TestCase):
    def test_area_spec_without_equal_is_rejected(self):
        from src.python.core.errors import CoreError

        with self.assertRaises(CoreError):
            jobs.area_jobs(["10,10,100,30"])

    def test_area_spec_with_bad_numbers_is_rejected(self):
        from src.python.core.errors import CoreError

        with self.assertRaises(CoreError):
            jobs.area_jobs(["a,b,c,d=新文字"])

    def test_area_spec_parses_rect_and_text(self):
        out = jobs.area_jobs(["10,20,100,30=新文字"])
        self.assertEqual(out[0].rect, (10, 20, 100, 30))
        self.assertEqual(out[0].new, "新文字")


class ColorParsing(unittest.TestCase):
    def test_hex_and_rgb_forms_agree(self):
        self.assertEqual(options.parse_color("#C00000"), (192, 0, 0))
        self.assertEqual(options.parse_color("192,0,0"), (192, 0, 0))
        self.assertEqual(options.parse_color("#c00"), (204, 0, 0))

    def test_garbage_is_rejected_with_core_error(self):
        for bad in ("zzz", "#12345", "1,2", ""):
            with self.subTest(spec=bad):
                with self.assertRaises(CoreError):
                    options.parse_color(bad)


class LogRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)

    def write_log(self, day: dt.date) -> str:
        path = audit.log_path(self.tmp.name, dt.datetime.combine(day, dt.time()))
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}\n")
        return path

    def test_old_days_are_pruned_and_recent_kept(self):
        today = dt.date(2026, 11, 18)
        old = self.write_log(today - dt.timedelta(days=40))
        fresh = self.write_log(today - dt.timedelta(days=1))
        removed = audit.prune_logs(self.tmp.name, keep_days=30, today=today)
        self.assertEqual([os.path.basename(old)], removed)
        self.assertTrue(os.path.exists(fresh))

    def test_unrelated_files_are_never_touched(self):
        keep = os.path.join(self.tmp.name, "notes.txt")
        with open(keep, "w", encoding="utf-8") as f:
            f.write("keep me")
        audit.prune_logs(self.tmp.name, keep_days=1, today=dt.date(2026, 11, 18))
        self.assertTrue(os.path.exists(keep))

    def test_missing_directory_is_not_an_error(self):
        self.assertEqual(audit.prune_logs(os.path.join(self.tmp.name, "nope")), [])


class OptionsSummary(unittest.TestCase):
    def test_defaults_are_omitted(self):
        self.assertEqual(audit.options_summary(options.Options()), {})

    def test_explicit_values_are_recorded(self):
        summary = audit.options_summary(options.Options(font="/tmp/a.ttf", size=28))  # platform-safe
        self.assertEqual(summary.get("size"), 28)
        self.assertIn("font", summary)

    def test_none_options_yield_empty_summary(self):
        self.assertEqual(audit.options_summary(None), {})


class ImageFormatTable(unittest.TestCase):
    """格式表与保存行为：不支持的扩展名必须是一句 CoreError，而不是 traceback。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.rgb = np.full((20, 30, 3), 200, np.uint8)

    def test_unknown_extension_raises_core_error(self):
        from src.python.core.errors import CoreError
        from src.python.core.image import save_image

        with self.assertRaises(CoreError):
            save_image(self.rgb, None, os.path.join(self.tmp.name, "out.xyz"))

    def test_quality_out_of_range_is_rejected(self):
        from src.python.core.errors import CoreError
        from src.python.core.image import save_image

        for quality in (0, 101, -5):
            with self.subTest(quality=quality):
                with self.assertRaises(CoreError):
                    save_image(
                        self.rgb, None, os.path.join(self.tmp.name, "out.jpg"), quality=quality
                    )

    def test_alpha_is_flattened_for_jpeg(self):
        from src.python.core.image import save_image

        alpha = np.zeros((20, 30), np.uint8)
        alpha[:, :10] = 255
        dst = os.path.join(self.tmp.name, "flat.jpg")
        save_image(self.rgb, alpha, dst)
        self.assertTrue(os.path.exists(dst))


if __name__ == "__main__":
    unittest.main()
