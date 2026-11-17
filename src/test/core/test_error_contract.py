"""错误契约测试：核心层用 CoreError 报可预期失败，不直接退出进程。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import unittest

from src.python.core.errors import CoreError
from src.python.core.fonts import build_font_pool
from src.python.core.jobs import area_jobs
from src.python.core.options import parse_color


class CoreErrorContract(unittest.TestCase):
    def test_color_parser_accepts_hex_and_rgb(self):
        self.assertEqual(parse_color("#ff0000"), (255, 0, 0))
        self.assertEqual(parse_color("255,0,0"), (255, 0, 0))
        self.assertEqual(parse_color("f00"), (255, 0, 0))

    def test_color_parser_rejects_invalid_input(self):
        for bad in ("zzz", "12", "#12345g", "1,2"):
            with self.assertRaises((CoreError, ValueError, IndexError)):
                parse_color(bad)

    def test_bad_area_spec_raises_core_error(self):
        with self.assertRaises(CoreError):
            area_jobs(["没有等号"])
        with self.assertRaises(CoreError):
            area_jobs(["a,b,c=新文字"])

    def test_area_spec_creates_job(self):
        jobs = area_jobs(["10,20,300,60=新标题"])
        self.assertEqual(jobs[0].rect, (10, 20, 300, 60))
        self.assertEqual(jobs[0].new, "新标题")

    def test_missing_font_file_raises_core_error(self):
        with self.assertRaises(CoreError):
            build_font_pool(["测试"], "/no/such/font.ttf", 10)


if __name__ == "__main__":
    unittest.main()
