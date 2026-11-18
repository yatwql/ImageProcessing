"""工作流自检（`check_workflows`）：bash 语法检查要在"没有真 bash"时优雅跳过。

守的原因：windows-latest 上的 `bash` 是 WSL 存根（退 1、stderr 为空），
不探测就逐条报"bash 语法错误"——守护在别的平台上假红，正是这轮 CI 的一类。
另外 `run:` 块里禁止内联 python（heredoc）：那段代码没有 `ensure_utf8_stdio()`，
Windows 控制台 cp1252 打印中文会自己先崩，也写不了用例。
"""

from __future__ import annotations

import unittest
from unittest import mock

from src.python.tools import check_workflows


def workflow(*steps: dict) -> dict:
    return {"jobs": {"demo": {"steps": list(steps)}}}


class ShellSyntax(unittest.TestCase):
    def test_bash_syntax_error_is_reported_when_bash_runs(self):
        bad = workflow({"name": "坏脚本", "run": "if then fi\n"})
        with (
            mock.patch.object(check_workflows, "BASH_OK", True),
            mock.patch.object(check_workflows, "bash_syntax_error", return_value="syntax error"),
        ):
            problems = check_workflows.check_run_blocks(bad)
        self.assertTrue(problems)
        self.assertIn("bash 语法错误", problems[0])

    def test_bash_checks_skipped_without_usable_bash(self):
        bad = workflow({"name": "坏脚本", "run": "if then fi\n"})
        with mock.patch.object(check_workflows, "BASH_OK", False):
            self.assertEqual(check_workflows.check_run_blocks(bad), [])

    def test_valid_script_passes(self):
        good = workflow({"name": "正常", "run": "echo ok\n"})
        with (
            mock.patch.object(check_workflows, "BASH_OK", True),
            mock.patch.object(check_workflows, "bash_syntax_error", return_value=None),
        ):
            self.assertEqual(check_workflows.check_run_blocks(good), [])


class InlinePythonBan(unittest.TestCase):
    def test_python_heredoc_is_rejected(self):
        step = {"name": "摘要", "run": "python - <<'PY'\nprint('x')\nPY\n"}
        with (
            mock.patch.object(check_workflows, "BASH_OK", True),
            mock.patch.object(check_workflows, "bash_syntax_error", return_value=None),
        ):
            problems = check_workflows.check_run_blocks(workflow(step))
        self.assertTrue(problems)
        self.assertIn("heredoc", problems[0])

    def test_tool_invocation_is_allowed(self):
        step = {"name": "摘要", "run": "python -m src.python.tools.junit_summary a.xml\n"}
        with (
            mock.patch.object(check_workflows, "BASH_OK", True),
            mock.patch.object(check_workflows, "bash_syntax_error", return_value=None),
        ):
            self.assertEqual(check_workflows.check_run_blocks(workflow(step)), [])


if __name__ == "__main__":
    unittest.main()
