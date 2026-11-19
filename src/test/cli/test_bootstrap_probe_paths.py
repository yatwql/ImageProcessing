"""环境引导与入口壳：探测失败、缺 pip、入口 shim、外部命令缺失。"""

from __future__ import annotations

import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python import bootstrap, launch
from src.python.core import fonts
from src.test._support import (
    TuiTestCase,
)


class BootstrapGaps(unittest.TestCase):
    def test_pip_install_calls_pip_in_repo_root(self):
        # `str(Path)` 在 Windows 上给反斜杠，期望值也用 Path 算，不能写死 "/x/python"
        expected_py = str(Path("/x/python"))
        with mock.patch.object(bootstrap.subprocess, "run") as run:
            bootstrap.pip_install(Path("/x/python"), "-r", "requirements.txt")
        args, kwargs = run.call_args
        self.assertEqual(args[0][:4], [expected_py, "-m", "pip", "install"])
        self.assertEqual(kwargs["cwd"], str(bootstrap.ROOT))
        self.assertTrue(kwargs["check"])


class EntryShimGaps(unittest.TestCase):
    """`python -m` 薄壳：`if __name__` 块只在被当脚本执行时跑。"""

    def run_shim(self, module: str, patch_target: str) -> None:
        with mock.patch(patch_target, return_value=0), self.assertRaises(SystemExit) as ctx:
            runpy.run_module(module, run_name="__main__")
        self.assertEqual(ctx.exception.code, 0)

    def test_cli_main_shim(self):
        self.run_shim("src.python.cli", "src.python.cli.main.main")

    def test_tui_main_shim(self):
        self.run_shim("src.python.tui", "src.python.tui.ui.main")


class LaunchGaps(unittest.TestCase):
    def test_repo_root_is_added_to_sys_path_on_import(self):
        saved = list(sys.path)
        try:
            sys.path = [p for p in sys.path if p != str(launch.ROOT)]
            import importlib

            importlib.reload(launch)
            self.assertIn(str(launch.ROOT), sys.path)
        finally:
            sys.path = saved


class BootstrapProbe(unittest.TestCase):
    def test_probe_oserror_reports_venv(self):
        py = Path("/tmp/python")  # platform-safe
        with mock.patch.object(bootstrap.subprocess, "run", side_effect=OSError("boom")):
            self.assertEqual(bootstrap.missing_modules(py), ["venv"])


class ProbeOserror(unittest.TestCase):
    def test_probe_failure_on_existing_interpreter_reports_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_py = Path(tmp) / "python"
            fake_py.write_text("", encoding="utf-8")
            with mock.patch.object(bootstrap.subprocess, "run", side_effect=OSError("boom")):
                self.assertEqual(bootstrap.missing_modules(fake_py), ["venv"])


class FinalGaps(TuiTestCase):
    """最后一批单行分支：返回值异常、父目录不可建、缓存坏 JSON、span 越界等。"""

    def test_probe_nonzero_returncode_reports_venv(self):
        fake = mock.Mock(returncode=1, stdout="")
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "python"
            py.write_text("", encoding="utf-8")
            with mock.patch.object(bootstrap.subprocess, "run", return_value=fake):
                self.assertEqual(bootstrap.missing_modules(py), ["venv"])


class FinalGaps6(TuiTestCase):
    """收尾（五）：读图失败、Windows 锁、缺 fontconfig、保存失败、行内详情。"""

    def test_run_helper_returns_empty_when_command_missing(self):
        with mock.patch.object(fonts.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(fonts._run(["fc-list"]), "")


class VenvHint(unittest.TestCase):
    """裸系统解释器跑入口时给一句"用 .venv"的提示；已在 venv / CI 里就不吵。"""

    def test_hint_is_silent_inside_a_venv(self):
        with (
            mock.patch.object(bootstrap.sys, "prefix", "/venv/inside"),
            mock.patch.object(bootstrap.sys, "base_prefix", "/usr", create=True),
        ):
            self.assertTrue(bootstrap.in_venv())
            self.assertIsNone(bootstrap.venv_hint())

    def test_hint_mentions_the_launcher_when_run_outside(self):
        with (
            mock.patch.object(bootstrap.sys, "prefix", "/usr"),
            mock.patch.object(bootstrap.sys, "base_prefix", "/usr", create=True),
            mock.patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("CI", None)
            os.environ.pop("GITHUB_ACTIONS", None)
            hint = bootstrap.venv_hint()
        self.assertIsNotNone(hint)
        self.assertIn(".venv", hint or "")

    def test_hint_stays_quiet_on_ci(self):
        with (
            mock.patch.object(bootstrap.sys, "prefix", "/usr"),
            mock.patch.object(bootstrap.sys, "base_prefix", "/usr", create=True),
            mock.patch.dict(os.environ, {"CI": "1"}),
        ):
            self.assertIsNone(bootstrap.venv_hint())
