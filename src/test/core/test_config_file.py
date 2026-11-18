"""配置文件（<配置目录>/retype.json，兼容旧 img-p.json）：读取、容错与优先级。

优先级：环境变量 > 配置文件 > 内置默认；命令行/界面里显式设置的值不被覆盖。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from src.python import config
from src.python.core.options import Options


class ConfigFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "img-p.json")
        self.env = mock.patch.dict(os.environ, {"IMG_P_CONFIG": self.path})
        self.env.start()
        self.addCleanup(self.env.stop)

    def write(self, data) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))

    def test_missing_file_means_empty_config(self):
        self.assertEqual(config.load_config(), {})

    def test_unknown_keys_are_ignored(self):
        self.write({"out_dir": "/data/out", "unknown": 1})
        self.assertEqual(config.load_config(), {"out_dir": "/data/out"})

    def test_broken_json_is_ignored_with_a_message(self):
        self.write("{not json")
        self.assertEqual(config.load_config(), {})

    def test_non_object_json_is_ignored(self):
        self.write("[1, 2, 3]")
        self.assertEqual(config.load_config(), {})

    def test_paths_follow_config_when_env_is_absent(self):
        self.write({"data_dir": "/data/pics", "out_dir": "/data/out", "log_dir": "/data/logs"})
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in ("IMG_P_DATA_DIR", "IMG_P_OUT_DIR", "IMG_P_LOG_DIR"):
                os.environ.pop(key, None)
            self.assertEqual(config.default_input(), "/data/pics")
            self.assertEqual(config.default_out_dir(), "/data/out")
            self.assertEqual(config.log_dir(), "/data/logs")

    def test_environment_beats_config(self):
        self.write({"data_dir": "/data/pics", "out_dir": "/data/out", "log_dir": "/data/logs"})
        with mock.patch.dict(os.environ, {"IMG_P_DATA_DIR": "/mnt/a",
                                          "IMG_P_OUT_DIR": "/mnt/b",
                                          "IMG_P_LOG_DIR": "/mnt/c"}):
            self.assertEqual(config.default_input(), "/mnt/a")
            self.assertEqual(config.default_out_dir(), "/mnt/b")
            self.assertEqual(config.log_dir(), "/mnt/c")

    def test_option_defaults_filter_bad_types(self):
        self.write({"quality": 80, "tracking": -1.5, "max_fonts": "many",
                    "align": "center", "fit_width": True})
        defaults = config.option_defaults()
        self.assertEqual(defaults, {"quality": 80, "tracking": -1.5,
                                    "align": "center", "fit_width": True})

    def test_apply_to_options_only_fills_unset_values(self):
        self.write({"quality": 80, "align": "center", "max_fonts": 20})
        opts = Options(quality=40, align="left")
        config.apply_to_options(opts)
        self.assertEqual(opts.quality, 40)             # 已设置的不被覆盖
        self.assertEqual(opts.align, "left")
        self.assertEqual(opts.max_fonts, 20)           # 默认 160 视为未设置

    def test_apply_to_options_leaves_automatic_align(self):
        opts = Options()
        config.apply_to_options(opts)
        self.assertEqual(opts.align, "auto")           # 没有配置时保持自动


if __name__ == "__main__":
    unittest.main()
