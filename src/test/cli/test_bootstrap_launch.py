"""环境引导与启动器：`bootstrap.py` / `launch.py` 的分支与错误路径。

这两个模块决定"用户能不能把程序跑起来"，但之前覆盖率只有 58% / 72%——
因为正常路径一跑就装依赖、建 venv，用例不敢碰。这里全部打桩：
装依赖只验证"调了哪些命令"，绝不真的联网。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python import bootstrap, launch


class ConfDirResolution(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "Windows 上 /tmp/cfg 不是绝对路径语义")
    def test_explicit_absolute_dir_is_used_as_is(self):
        with mock.patch.dict(os.environ, {"IMG_P_CONFIG_DIR": "/tmp/cfg"}):
            self.assertEqual(bootstrap._conf_dir(), Path("/tmp/cfg"))

    def test_relative_dir_is_anchored_at_repo_root(self):
        with mock.patch.dict(os.environ, {"IMG_P_CONFIG_DIR": "cfg/x"}):
            resolved = bootstrap._conf_dir()
        self.assertTrue(resolved.is_absolute())
        self.assertTrue(resolved.as_posix().endswith("cfg/x"))

    def test_empty_env_falls_back_to_platform_default(self):
        with mock.patch.dict(os.environ, {"IMG_P_CONFIG_DIR": ""}):
            self.assertEqual(bootstrap._conf_dir(), bootstrap.default_conf_dir())


class EnsureVenv(unittest.TestCase):
    def test_existing_venv_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            py = bootstrap.venv_python(root)
            py.parent.mkdir(parents=True, exist_ok=True)
            py.write_text("", encoding="utf-8")
            self.assertEqual(bootstrap.ensure_venv(root), py)

    def test_missing_venv_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            py = bootstrap.venv_python(root)
            with mock.patch.object(bootstrap.venv, "EnvBuilder") as builder:
                bootstrap.ensure_venv(root)
            builder.assert_called_once()
            self.assertFalse(py.exists(), "这里只验证调用，不真的建环境")


class MissingModules(unittest.TestCase):
    def test_absent_interpreter_reports_venv(self):
        self.assertEqual(bootstrap.missing_modules(Path("/no/such/python")), ["venv"])

    def test_real_interpreter_reports_runtime_ready(self):
        py = bootstrap.venv_python()
        if not py.exists():
            self.skipTest("没有 .venv")
        self.assertEqual(bootstrap.missing_modules(py), [])

    def test_dev_probe_mentions_pytest_when_missing(self):
        py = bootstrap.venv_python()
        if not py.exists():
            self.skipTest("没有 .venv")
        missing = bootstrap.missing_modules(py, need_dev=True)
        # 装了 dev 依赖就没有缺项；没装则只缺 pytest
        self.assertTrue(not missing or missing == ["pytest"])


class EnsureDependencies(unittest.TestCase):
    def test_no_missing_modules_is_a_noop(self):
        with (
            mock.patch.object(bootstrap, "missing_modules", return_value=[]),
            mock.patch.object(bootstrap, "pip_install") as pip,
        ):
            self.assertTrue(bootstrap.ensure_dependencies(Path("/x/python")))
        pip.assert_not_called()

    def test_auto_disabled_reports_and_refuses(self):
        with (
            mock.patch.object(bootstrap, "missing_modules", return_value=["PIL"]),
            mock.patch.object(bootstrap, "pip_install") as pip,
            mock.patch("sys.stderr"),
        ):
            self.assertFalse(bootstrap.ensure_dependencies(Path("/x/python"), auto=False))
        pip.assert_not_called()

    def test_auto_enabled_installs_runtime_then_rechecks(self):
        results = [["PIL"], []]
        with (
            mock.patch.object(bootstrap, "missing_modules", side_effect=results),
            mock.patch.object(bootstrap, "ensure_venv", return_value=Path("/x/python")),
            mock.patch.object(bootstrap, "pip_install") as pip,
            mock.patch("sys.stderr"),
        ):
            self.assertTrue(bootstrap.ensure_dependencies(Path("/x/python")))
        installed = [call.args[1:] for call in pip.call_args_list]
        self.assertTrue(any("requirements.txt" in args for args in installed))

    def test_dev_flag_installs_dev_requirements(self):
        results = [["pytest"], []]
        with (
            mock.patch.object(bootstrap, "missing_modules", side_effect=results),
            mock.patch.object(bootstrap, "ensure_venv", return_value=Path("/x/python")),
            mock.patch.object(bootstrap, "pip_install") as pip,
            mock.patch("sys.stderr"),
        ):
            bootstrap.ensure_dependencies(Path("/x/python"), need_dev=True)
        installed = [call.args[1:] for call in pip.call_args_list]
        self.assertTrue(any("requirements-dev.txt" in args for args in installed))


class WriteConfig(unittest.TestCase):
    def test_example_and_default_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            example = Path(tmp) / "retype.example.json"
            config = Path(tmp) / "retype.json"
            with (
                mock.patch.object(bootstrap, "CONF_DIR", Path(tmp)),
                mock.patch.object(bootstrap, "EXAMPLE", example),
                mock.patch.object(bootstrap, "CONFIG", config),
            ):
                bootstrap.write_config()
            self.assertTrue(example.exists())
            self.assertTrue(config.exists())
            self.assertIn("data_dir", config.read_text(encoding="utf-8"))

    def test_existing_config_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            example = Path(tmp) / "retype.example.json"
            config = Path(tmp) / "retype.json"
            config.write_text('{"data_dir": "/mine"}', encoding="utf-8")
            with (
                mock.patch.object(bootstrap, "CONF_DIR", Path(tmp)),
                mock.patch.object(bootstrap, "EXAMPLE", example),
                mock.patch.object(bootstrap, "CONFIG", config),
            ):
                bootstrap.write_config()
            self.assertIn("/mine", config.read_text(encoding="utf-8"))

    def test_unwritable_dir_is_reported_not_raised(self):
        # 用打桩而不是依赖 /proc：Windows 上 /proc 可能真的建得出来
        with (
            mock.patch.object(bootstrap, "CONF_DIR", Path("/nope/config")),
            mock.patch.object(bootstrap, "EXAMPLE", Path("/nope/config/e.json")),
            mock.patch.object(bootstrap, "CONFIG", Path("/nope/config/c.json")),
            mock.patch.object(Path, "mkdir", side_effect=OSError("denied")),
            mock.patch("builtins.print") as fake_print,
        ):
            bootstrap.write_config()
        self.assertTrue(any("无法创建" in str(c) for c in fake_print.call_args_list))


class BootstrapMain(unittest.TestCase):
    def test_check_mode_returns_code_from_ensure_dependencies(self):
        with mock.patch.object(bootstrap, "ensure_dependencies", return_value=False):
            self.assertEqual(bootstrap.main(["--check"]), 1)
        with mock.patch.object(bootstrap, "ensure_dependencies", return_value=True):
            self.assertEqual(bootstrap.main(["--check"]), 0)

    def test_skip_install_only_prepares_venv_and_config(self):
        with (
            mock.patch.object(bootstrap, "ensure_venv", return_value=Path("/x/python")),
            mock.patch.object(bootstrap, "pip_install") as pip,
            mock.patch.object(bootstrap, "write_config") as write,
        ):
            self.assertEqual(bootstrap.main(["--skip-install"]), 0)
        pip.assert_not_called()
        write.assert_called_once()

    def test_dev_flag_passes_dev_requirements(self):
        with (
            mock.patch.object(bootstrap, "ensure_venv", return_value=Path("/x/python")),
            mock.patch.object(bootstrap, "pip_install") as pip,
            mock.patch.object(bootstrap, "write_config"),
        ):
            bootstrap.main(["--dev"])
        installed = [call.args[1:] for call in pip.call_args_list]
        self.assertTrue(any("requirements-dev.txt" in args for args in installed))

    def test_help_prints_usage(self):
        with mock.patch("sys.stdout"), self.assertRaises(SystemExit) as ctx:
            bootstrap.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


class LaunchDispatch(unittest.TestCase):
    def test_channel_table_covers_user_facing_entries(self):
        for name in ("cli", "tui", "test", "log-query", "setup"):
            self.assertIn(name, launch.CHANNELS)

    def test_execv_is_used_with_the_venv_interpreter(self):
        with (
            mock.patch.object(bootstrap, "ensure_dependencies", return_value=True),
            mock.patch.object(launch.os, "chdir"),
            mock.patch.object(launch.os, "execv", side_effect=OSError("boom")) as execv,
            mock.patch("sys.stderr"),
        ):
            code = launch.main(["cli", "--version"])
        self.assertEqual(code, 1, "execv 失败要退化成一句提示 + 非零退出")
        self.assertEqual(execv.call_args.args[0], str(bootstrap.venv_python()))

    def test_disabled_auto_setup_blocks_exec(self):
        with (
            mock.patch.object(bootstrap, "ensure_dependencies", return_value=False),
            mock.patch.dict(os.environ, {"IMG_P_NO_AUTO_SETUP": "1"}),
            mock.patch.object(launch.os, "execv") as execv,
            mock.patch("sys.stderr"),
        ):
            self.assertEqual(launch.main(["cli"]), 1)
        execv.assert_not_called()

    def test_auto_setup_switch_reads_env(self):
        with mock.patch.dict(os.environ, {"IMG_P_NO_AUTO_SETUP": "1"}):
            self.assertFalse(launch.auto_setup_enabled())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(launch.auto_setup_enabled())


class PlatformPaths(unittest.TestCase):
    def test_venv_python_uses_scripts_on_windows(self):
        with mock.patch.object(sys, "platform", "win32"):
            self.assertIn("Scripts", bootstrap.venv_python().parts)

    def test_venv_python_uses_bin_elsewhere(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertIn("bin", bootstrap.venv_python().parts)


if __name__ == "__main__":
    unittest.main()
