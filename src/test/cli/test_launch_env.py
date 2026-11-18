"""启动器与环境引导：首次运行自动装依赖，设 `IMG_P_NO_AUTO_SETUP=1` 才退回手动。

这些用例不真的装依赖（那会拖慢并依赖网络），只固定"怎么判断、怎么分派"这部分逻辑：
渠道表、参数校验、自动安装开关、缺依赖时的探测结果。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python import bootstrap, launch


class LaunchChannels(unittest.TestCase):
    def test_every_documented_channel_is_routable(self):
        for name in ("cli", "tui", "test", "log-query", "setup"):
            with self.subTest(channel=name):
                self.assertIn(name, launch.CHANNELS)
                need_dev, entry = launch.CHANNELS[name]
                self.assertTrue(entry, "每个渠道都要有入口参数")
                self.assertIsInstance(need_dev, bool)

    def test_only_test_channel_pulls_dev_dependencies(self):
        dev = [name for name, (need_dev, _) in launch.CHANNELS.items() if need_dev]
        self.assertEqual(dev, ["test"], "只有跑用例需要 dev 依赖")

    def test_no_channel_prints_usage_and_fails(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(launch.main([]), 2)

    def test_unknown_channel_prints_usage_and_fails(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(launch.main(["nope"]), 2)


class AutoSetupSwitch(unittest.TestCase):
    def test_enabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMG_P_NO_AUTO_SETUP", None)
            self.assertTrue(launch.auto_setup_enabled())

    def test_disabled_by_env(self):
        with mock.patch.dict(os.environ, {"IMG_P_NO_AUTO_SETUP": "1"}):
            self.assertFalse(launch.auto_setup_enabled())

    def test_refuses_to_exec_when_setup_disabled_and_env_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-python"
            with mock.patch.object(bootstrap, "venv_python", return_value=missing), \
                    mock.patch.dict(os.environ, {"IMG_P_NO_AUTO_SETUP": "1"}), \
                    mock.patch("sys.stderr"):
                self.assertEqual(launch.main(["cli", "--version"]), 1)


class MissingModules(unittest.TestCase):
    def test_absent_interpreter_reports_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(bootstrap.missing_modules(Path(tmp) / "python"), ["venv"])

    def test_real_interpreter_reports_nothing_for_runtime_deps(self):
        venv_py = bootstrap.venv_python()
        if not venv_py.exists():
            self.skipTest("没有 .venv，跳过（这是开发机/CI 才有的东西）")
        self.assertEqual(bootstrap.missing_modules(venv_py), [])

    def test_dev_probe_asks_for_pytest(self):
        venv_py = bootstrap.venv_python()
        if not venv_py.exists():
            self.skipTest("没有 .venv，跳过")
        # 装了 dev 依赖（pytest）时不应报缺；没装则恰好报 pytest
        missing = bootstrap.missing_modules(venv_py, need_dev=True)
        self.assertNotIn("PIL", missing)
        self.assertTrue(not missing or missing == ["pytest"])


class BootstrapEntry(unittest.TestCase):
    def test_venv_python_path_matches_platform(self):
        path = bootstrap.venv_python()
        expected = "Scripts" if sys.platform == "win32" else "bin"
        self.assertIn(expected, path.parts)

    def test_check_mode_never_installs_when_disabled(self):
        with mock.patch.dict(os.environ, {"IMG_P_NO_AUTO_SETUP": "1"}), \
                mock.patch.object(bootstrap, "ensure_dependencies", return_value=False) as spy, \
                mock.patch("sys.stderr"):
            self.assertEqual(bootstrap.main(["--check"]), 1)
        self.assertFalse(spy.call_args.kwargs["auto"])


if __name__ == "__main__":
    unittest.main()
