"""入口冒烟：每个对外入口都能起来、给出正确退出码（不需要真终端）。

这轮出过的两类事故都靠"入口"暴露：`retype --version` 崩溃、`launch` 找不到渠道。
这里对每个入口跑一次子进程，断言"起得来、用法说明打得出来、错误码正确"。
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable


def run(*args: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    # 子进程强制 UTF-8：Windows runner 的控制台是 cp1252，打印中文会 UnicodeEncodeError，
    # 那会让"入口坏了"和"控制台编码不支持"混为一谈
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run(
        [PY, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def output(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "") + (proc.stderr or "")


class EntryPoints(unittest.TestCase):
    def test_cli_version(self):
        proc = run("-m", "src.python.cli", "--version")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("retype", output(proc))

    def test_cli_help(self):
        proc = run("-m", "src.python.cli", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--map", output(proc))

    def test_log_query_help(self):
        proc = run("-m", "src.python.cli.log_query", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--src", output(proc))

    def test_tui_help_does_not_enter_curses(self):
        proc = run("-m", "src.python.tui", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("用法", output(proc))

    def test_launch_prints_usage_without_channel(self):
        proc = run("-m", "src.python.launch")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("用法", output(proc))

    def test_launch_unknown_channel_is_rejected(self):
        proc = run("-m", "src.python.launch", "nope")
        self.assertEqual(proc.returncode, 2)

    def test_bootstrap_check_is_quiet_and_successful(self):
        if (
            not (ROOT / ".venv" / "bin" / "python").exists()
            and not (ROOT / ".venv" / "Scripts" / "python.exe").exists()
        ):
            self.skipTest("没有 .venv（CI 用系统解释器装依赖），--check 期望失败")
        proc = run("-m", "src.python.bootstrap", "--check")
        self.assertEqual(proc.returncode, 0, output(proc))

    def test_guard_and_perf_tools_are_runnable(self):
        for module in ("check_guards", "check_perf", "check_coverage"):
            with self.subTest(tool=module):
                proc = run("-m", f"src.python.tools.{module}", "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)


class ScriptLaunchers(unittest.TestCase):
    """shell 薄壳也要能起来（Windows 的 .ps1 不在这里跑）。"""

    def test_shell_scripts_pass_syntax_check(self):
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            with self.subTest(script=path.name):
                proc = subprocess.run(
                    ["bash", "-n", str(path)], capture_output=True, text=True, check=False
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)

    @unittest.skipUnless(sys.platform != "win32", "POSIX shell 才有 --help 行为")
    def test_cli_shell_help(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts" / "cli.sh"), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
