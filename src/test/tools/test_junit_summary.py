"""CI 失败摘要工具（`junit_summary`）：把 junit 报告里的红用例列成 `class::name`。

守的原因：这段逻辑原本写在工作流的 heredoc 里，Windows 控制台 cp1252 直接
`UnicodeEncodeError`（摘要步自己红了）。搬进 tools 后既能 `ensure_utf8_stdio()`，
也能在本地写用例。
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from src.python.tools import junit_summary

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3">
    <testcase classname="src.test.a" name="test_ok"/>
    <testcase classname="src.test.b" name="test_fail">
      <failure message="boom">traceback</failure>
    </testcase>
    <testcase classname="src.test.c" name="test_error">
      <error message="kaboom">traceback</error>
    </testcase>
  </testsuite>
</testsuites>
"""


def run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = junit_summary.main(argv)
    return code, out.getvalue()


class FailingCases(unittest.TestCase):
    def test_lists_failures_and_errors_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            path.write_text(JUNIT, encoding="utf-8")
            cases = junit_summary.failing_cases(path)
        self.assertEqual(cases, ["src.test.b::test_fail", "src.test.c::test_error"])

    def test_missing_report_yields_no_cases(self):
        self.assertEqual(junit_summary.failing_cases(Path("/nonexistent/junit.xml")), [])


class CommandLine(unittest.TestCase):
    def test_prints_count_and_each_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            path.write_text(JUNIT, encoding="utf-8")
            code, out = run([str(path)])
        self.assertEqual(code, 0)
        self.assertIn("失败/错误用例：2", out)
        self.assertIn("- src.test.b::test_fail", out)

    def test_missing_report_is_not_an_error(self):
        code, out = run(["/nonexistent/junit.xml"])
        self.assertEqual(code, 0)
        self.assertIn("没有 junit 报告", out)

    def test_usage_without_argument(self):
        code, out = run([])
        self.assertEqual(code, 2)
        self.assertIn("junit_summary", out)


if __name__ == "__main__":
    unittest.main()
