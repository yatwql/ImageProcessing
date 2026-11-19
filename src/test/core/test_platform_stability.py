"""跨平台兼容与稳定性：路径/配置/环境变量、异常契约、幂等与规模。

平台差异部分用 `sys.platform` 打桩在任意系统上验证（Windows 分支不必真在 Windows 上跑），
稳定性部分盯"异常不外溢、重复执行结果一致、规模上去不炸"。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.python import bootstrap, config, version
from src.python.core import edit, image
from src.python.core.errors import CoreError
from src.python.core.match import Job
from src.python.core.options import Options
from src.test._support import FONT_CJK, has_cjk_font


class PlatformDefaults(unittest.TestCase):
    """配置目录/解释器路径按平台取默认值（Windows 没有 /data）。"""

    def test_posix_default_conf_dir_is_slash_data(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(
                bootstrap.default_conf_dir().as_posix(), "/data/config"
            )  # platform-safe

    def test_windows_default_conf_dir_is_inside_repo(self):
        with mock.patch.object(sys, "platform", "win32"):
            path = bootstrap.default_conf_dir()
        self.assertIn("data", path.parts)
        self.assertIn("config", path.parts)
        self.assertNotEqual(path.as_posix(), "/data/config")  # platform-safe

    def test_relative_env_config_dir_is_resolved_against_repo(self):
        with mock.patch.dict(os.environ, {"IMG_P_CONFIG_DIR": "cfg/here"}):
            resolved = bootstrap._conf_dir()
        self.assertTrue(resolved.is_absolute())
        self.assertTrue(resolved.as_posix().endswith("cfg/here"))

    def test_venv_python_matches_platform_layout(self):
        with mock.patch.object(sys, "platform", "win32"):
            self.assertIn("Scripts", bootstrap.venv_python().parts)
        with mock.patch.object(sys, "platform", "linux"):
            self.assertIn("bin", bootstrap.venv_python().parts)


class ConfigResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = mock.patch.object(config, "CONFIG_DIR", self.tmp.name)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, name: str, payload: dict) -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return path

    def test_new_name_is_preferred(self):
        self.assertEqual(os.path.basename(config.config_file()), "retype.json")

    def test_legacy_file_is_used_when_new_one_is_missing(self):
        self.write("img-p.json", {"data_dir": "/old"})
        self.assertEqual(os.path.basename(config.config_file()), "img-p.json")

    def test_explicit_env_wins(self):
        with mock.patch.dict(os.environ, {"IMG_P_CONFIG": "/tmp/x.json"}):  # platform-safe
            self.assertEqual(config.config_file(), "/tmp/x.json")  # platform-safe
        with mock.patch.dict(os.environ, {"RETYPE_CONFIG": "/tmp/y.json"}):  # platform-safe
            self.assertEqual(config.config_file(), "/tmp/y.json")  # platform-safe

    def test_chinese_values_survive_a_round_trip(self):
        self.write("retype.json", {"data_dir": "/数据/图片", "font": "/字体/思源.ttf"})
        conf = config.load_config()
        self.assertEqual(conf.get("data_dir"), "/数据/图片")
        self.assertEqual(conf.get("font"), "/字体/思源.ttf")

    def test_broken_json_falls_back_to_defaults(self):
        with open(os.path.join(self.tmp.name, "retype.json"), "w", encoding="utf-8") as f:
            f.write("{坏的")
        self.assertEqual(config.load_config(), {}, "读不出来就当没有配置，不能崩")


class EnvOverrides(unittest.TestCase):
    def test_data_out_and_log_dirs_honor_env(self):
        with mock.patch.dict(
            os.environ,
            {"IMG_P_DATA_DIR": "/t/in", "IMG_P_OUT_DIR": "/t/out", "IMG_P_LOG_DIR": "/t/logs"},
        ):
            self.assertEqual(config.default_input(), "/t/in")
            self.assertEqual(config.default_out_dir(), "/t/out")
            self.assertEqual(config.log_dir(), "/t/logs")


class VersionMeta(unittest.TestCase):
    def test_fields_have_the_expected_shape(self):
        self.assertRegex(version.VERSION, r"^\d+\.\d+")
        self.assertRegex(version.UPDATED, r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(version.NAME.isascii(), "程序名用于命令行，保持 ASCII")

    def test_name_matches_console_script(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn(f'name = "{version.NAME}"', text)
        self.assertIn(f'{version.NAME} = "src.python.cli.main:main"', text)


class PathHandling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_same_file_accepts_relative_and_absolute(self):
        path = os.path.join(self.tmp.name, "a.png")
        image.save_image(np.zeros((4, 4, 3), np.uint8), None, path)
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            self.assertTrue(image.same_file("a.png", path))
        finally:
            os.chdir(cwd)

    def test_different_files_are_not_same(self):
        self.assertFalse(
            image.same_file(
                os.path.join(self.tmp.name, "a.png"), os.path.join(self.tmp.name, "b.png")
            )
        )

    def test_unique_path_numbers_without_touching_extension(self):
        """编号来自 reserve_path/unique_path；扩展名保持不变。"""
        base = os.path.join(self.tmp.name, "out.png")
        first = image.reserve_path(base)
        second = image.reserve_path(base)
        self.assertEqual(os.path.basename(first), "out.png")
        self.assertEqual(os.path.basename(second), "out-1.png")
        self.assertTrue(second.endswith(".png"), "编号不能吃掉扩展名")
        self.assertEqual(os.path.basename(image.unique_path(base)), "out-2.png")

    def test_reserve_path_creates_the_file_atomically(self):
        target = os.path.join(self.tmp.name, "keep.png")
        reserved = image.reserve_path(target)
        self.assertTrue(os.path.exists(reserved))
        self.assertEqual(reserved, target)

    def test_trailing_slash_is_tolerated_for_directories(self):
        from src.python.tui import browse

        rows, images, error = browse.scan_rows(self.tmp.name + os.sep)
        self.assertIsNone(error)
        self.assertEqual(images, [])
        self.assertTrue(all(kind in ("parent", "dir", "img") for kind, _p in rows))


class ErrorContract(unittest.TestCase):
    """核心层只抛 CoreError：渠道拿一句话就能提示，不会看到 traceback。"""

    def test_missing_font_pool_is_a_core_error_not_index_error(self):
        rgb = np.full((60, 120, 3), 255, np.uint8)
        jobs = [Job((10, 10, 80, 20), "原文", "新文")]
        with (
            mock.patch.object(
                edit,
                "analyze",
                return_value={
                    "mask": np.zeros((60, 120), bool),
                    "ink_box": (10, 10, 90, 30),
                    "text_color": (0, 0, 0),
                    "stroke": 2.0,
                    "stroke_core": 2.0,
                    "slant": 0.0,
                },
            ),
            self.assertRaises(CoreError),
        ):
            edit.replace_image(rgb, None, jobs, Options(), [])

    def test_empty_job_list_is_a_noop(self):
        rgb = np.full((20, 20, 3), 128, np.uint8)
        out, alpha, report = edit.replace_image(rgb, None, [], Options(), [])
        self.assertTrue(np.array_equal(out, rgb))
        self.assertIsNone(alpha)
        self.assertEqual(report, [])


class ScaleAndIdempotence(unittest.TestCase):
    def setUp(self):
        self.rgb = np.full((240, 480, 3), 255, np.uint8)
        self.info = {
            "mask": np.zeros((240, 480), bool),
            "ink_box": (10, 10, 200, 40),
            "text_color": (20, 20, 20),
            "stroke": 3.0,
            "stroke_core": 3.0,
            "slant": 0.0,
        }
        patcher = mock.patch.object(edit, "analyze", return_value=self.info)
        patcher.start()
        self.addCleanup(patcher.stop)

    @unittest.skipUnless(has_cjk_font(), "需要 CJK 字体")
    def test_many_jobs_complete_and_report_every_block(self):
        jobs = [Job((10, 10, 200, 30), "原文", f"新{i}") for i in range(40)]
        opts = Options(quiet=True, font=FONT_CJK)
        _out, _alpha, report = edit.replace_image(self.rgb, None, jobs, opts, [])
        self.assertEqual(len(report), 40)

    @unittest.skipUnless(has_cjk_font(), "需要 CJK 字体")
    def test_repeated_run_is_byte_identical(self):
        jobs = [Job((10, 10, 200, 30), "原文", "新文字")]
        opts = Options(quiet=True, font=FONT_CJK)
        first, _a1, _r1 = edit.replace_image(self.rgb, None, jobs, opts, [])
        second, _a2, _r2 = edit.replace_image(self.rgb, None, jobs, opts, [])
        self.assertTrue(np.array_equal(first, second), "同输入同参数必须字节一致")

    def test_tiny_image_does_not_crash(self):
        tiny = np.zeros((1, 1, 3), np.uint8)
        out, _alpha, report = edit.replace_image(tiny, None, [], Options(), [])
        self.assertEqual(out.shape, (1, 1, 3))
        self.assertEqual(report, [])


if __name__ == "__main__":
    unittest.main()
