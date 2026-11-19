"""CLI 参数层测试：默认值、参数合并、非法用法与提前报错。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from src.python.cli.main import build_parser, load_mapping
from src.test._support import has_cjk_font, make_text_image, patch_ocr


class ParserDefaults(unittest.TestCase):
    def setUp(self):
        self.args = build_parser().parse_args(["data"])

    def test_default_options(self):
        self.assertEqual(self.args.align, "auto")
        self.assertEqual(self.args.max_fonts, 160)
        self.assertFalse(self.args.dry_run)
        self.assertFalse(self.args.fit_width)
        self.assertEqual(self.args.map, [])

    def test_repeatable_map_collects_all(self):
        args = build_parser().parse_args(["data", "--map", "a=b", "--map", "c=d"])
        self.assertEqual(args.map, ["a=b", "c=d"])

    def test_explicit_overrides(self):
        args = build_parser().parse_args(
            [
                "data",
                "--align",
                "center",
                "--size",
                "48",
                "--color",
                "#ffffff",
                "--fit-width",
                "--tracking",
                "2.5",
                "--max-fonts",
                "20",
            ]
        )
        self.assertEqual(args.align, "center")
        self.assertEqual(args.size, 48)
        self.assertEqual(args.color, "#ffffff")
        self.assertTrue(args.fit_width)
        self.assertAlmostEqual(args.tracking, 2.5, places=3)
        self.assertEqual(args.max_fonts, 20)


class MappingLoading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, payload) -> str:
        path = os.path.join(self.tmp.name, "map.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def test_map_flag_overrides_file_entry(self):
        path = self.write({"2023": "2024", "张三": "李四"})
        mapping = load_mapping(path, ["2023=2030"])
        self.assertEqual(mapping["2023"], "2030")
        self.assertEqual(mapping["张三"], "李四")

    def test_values_are_coerced_to_str(self):
        path = self.write({"count": 3})
        self.assertEqual(load_mapping(path, []), {"count": "3"})

    def test_non_object_json_is_rejected(self):
        path = self.write(["a", "b"])
        with self.assertRaises(SystemExit):
            load_mapping(path, [])

    def test_missing_file_is_rejected(self):
        with self.assertRaises(SystemExit):
            load_mapping(os.path.join(self.tmp.name, "nope.json"), [])

    def test_bad_map_syntax_is_rejected(self):
        with self.assertRaises(SystemExit):
            load_mapping(None, ["没有等号"])


@unittest.skipUnless(has_cjk_font(), "需要 CJK 字体（Debian/Ubuntu 装 fonts-noto-cjk）")
class ArgumentGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rgb, self.boxes = make_text_image(["报告 2023"])

    def write_image(self, name: str = "a.png") -> str:
        from PIL import Image

        path = os.path.join(self.tmp.name, name)
        Image.fromarray(self.rgb).save(path)
        return path

    def test_area_is_rejected_for_directory_input(self):
        from src.python.cli.main import main

        self.write_image()
        with patch_ocr(self.boxes), self.assertRaises(SystemExit):
            main([self.tmp.name, "--area", "0,0,10,10=新"])

    def test_batch_with_file_output_is_rejected(self):
        from src.python.cli.main import main

        self.write_image("a.png")
        self.write_image("b.png")
        with patch_ocr(self.boxes), self.assertRaises(SystemExit):
            main([self.tmp.name, "--map", "2023=2024", "-o", "out.png"])

    def test_invalid_color_fails_before_processing(self):
        from src.python.cli.main import main

        path = self.write_image()
        with patch_ocr(self.boxes), self.assertRaises(SystemExit):
            main([path, "--map", "2023=2024", "--color", "zzz"])

    def test_missing_font_fails_before_processing(self):
        from src.python.cli.main import main

        path = self.write_image()
        with patch_ocr(self.boxes), self.assertRaises(SystemExit):
            main([path, "--map", "2023=2024", "--font", "/no/such.ttf"])

    def test_empty_directory_is_rejected(self):
        from src.python.cli.main import main

        with self.assertRaises(SystemExit):
            main([self.tmp.name, "--map", "2023=2024"])


class VersionFlag(unittest.TestCase):
    """`--version` 是脚本/打包检查的契约，输出里必须带程序名与版本号。"""

    def test_version_flag_prints_name_and_version(self):
        import contextlib
        import io

        from src.python.cli.main import main
        from src.python.version import NAME, VERSION

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(f"{NAME} {VERSION}", out.getvalue())


class WorkerLevels(unittest.TestCase):
    """并发档位：默认 1、`auto` 有上限、非法值当场拒、环境变量排在 CLI 之后。"""

    def test_default_is_single_thread_for_batch(self):
        from src.python.cli import batch

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(batch.WORKERS_ENV, None)
            self.assertEqual(batch.resolve_workers(None, dry_run=False, batch=True), 1)

    def test_dry_run_always_single_thread(self):
        from src.python.cli import batch

        self.assertEqual(batch.resolve_workers("4", dry_run=True, batch=True), 1)
        self.assertEqual(batch.resolve_workers("auto", dry_run=True, batch=True), 1)

    def test_single_image_ignores_workers(self):
        from src.python.cli import batch

        self.assertEqual(batch.resolve_workers("8", dry_run=False, batch=False), 1)

    def test_auto_is_half_the_cores_but_capped(self):
        from src.python.cli import batch

        with mock.patch.object(batch.os, "cpu_count", return_value=32):
            self.assertEqual(batch.workers_value("auto"), batch.WORKERS_AUTO_CAP)
        with mock.patch.object(batch.os, "cpu_count", return_value=2):
            self.assertEqual(batch.workers_value("auto"), 1)

    def test_env_var_is_used_when_cli_says_nothing(self):
        from src.python.cli import batch

        with mock.patch.dict(os.environ, {batch.WORKERS_ENV: "3"}):
            self.assertEqual(batch.resolve_workers(None, dry_run=False, batch=True), 3)
            self.assertEqual(batch.resolve_workers("2", dry_run=False, batch=True), 2)

    def test_invalid_level_exits_instead_of_silently_falling_back(self):
        from src.python.cli import batch

        for bad in ("0", "-1", "fast"):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                batch.workers_value(bad)


if __name__ == "__main__":
    unittest.main()
