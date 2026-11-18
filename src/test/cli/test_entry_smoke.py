"""入口冒烟：每个对外入口都能起来、给出正确退出码与帮助文本。

**入口逻辑在本进程里跑**（`runpy` + 重定向），不靠子进程读 stdout：
Windows 上 `subprocess(text=True)` 的编码/管道行为踩过一次坑——控制台是 cp1252、
reader 线程解码失败会把 stdout 变成空串，于是"程序没问题、测试误报"。
只有 shell 薄壳这类必须真起进程的检查才用 subprocess，并且只看退出码。
"""

from __future__ import annotations

import contextlib
import io
import runpy
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable


def call(module: str, argv: list[str]) -> tuple[int, str, str]:
    """在当前进程里执行 `python -m <module> <argv>`，返回 (退出码, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = [module, *argv]
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                runpy.run_module(module, run_name="__main__")
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv = saved
    return code, out.getvalue(), err.getvalue()


def venv_exists() -> bool:
    return (ROOT / ".venv" / "bin" / "python").exists() or (
        ROOT / ".venv" / "Scripts" / "python.exe").exists()


class EntryPoints(unittest.TestCase):
    def test_cli_version(self):
        code, out, err = call("src.python.cli", ["--version"])
        self.assertEqual(code, 0)
        self.assertIn("retype", out + err)

    def test_cli_help(self):
        code, out, err = call("src.python.cli", ["--help"])
        self.assertEqual(code, 0)
        self.assertIn("--map", out + err)

    def test_log_query_help(self):
        code, out, err = call("src.python.cli.log_query", ["--help"])
        self.assertEqual(code, 0)
        self.assertIn("--src", out + err)

    def test_tui_help_does_not_enter_curses(self):
        code, out, err = call("src.python.tui", ["--help"])
        self.assertEqual(code, 0)
        self.assertIn("用法", out + err)

    def test_launch_prints_usage_without_channel(self):
        code, out, err = call("src.python.launch", [])
        self.assertEqual(code, 2)
        self.assertIn("用法", out + err)

    def test_launch_unknown_channel_is_rejected(self):
        code, _out, _err = call("src.python.launch", ["nope"])
        self.assertEqual(code, 2)

    def test_bootstrap_check_is_quiet_and_successful(self):
        if not venv_exists():
            self.skipTest("没有 .venv（CI 用系统解释器装依赖），--check 期望失败")
        code, _out, err = call("src.python.bootstrap", ["--check"])
        self.assertEqual(code, 0, err)

    def test_tool_help_is_readable(self):
        for module in ("check_guards", "check_perf", "check_coverage"):
            with self.subTest(tool=module):
                code, out, err = call(f"src.python.tools.{module}", ["--help"])
                self.assertEqual(code, 0, err)
                self.assertTrue(out.strip(), "工具的 --help 应当打印用法")


class ScriptLaunchers(unittest.TestCase):
    """shell 薄壳只在真进程里有意义：只看语法与退出码，不看输出。"""

    def test_shell_scripts_pass_syntax_check(self):
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            with self.subTest(script=path.name):
                proc = subprocess.run(
                    ["bash", "-n", str(path)], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)

    @unittest.skipUnless(sys.platform != "win32", "POSIX shell 才有 --help 行为")
    def test_cli_shell_help(self):
        proc = subprocess.run(["bash", str(ROOT / "scripts" / "cli.sh"), "--help"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
