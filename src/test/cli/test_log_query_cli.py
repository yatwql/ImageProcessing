"""日志查询入口（`src/python/cli/log_query.py`）：过滤、`--json`、坏参数。

以前只有 core.audit 的回读用例，这个模块在覆盖率报告里是 0%——
意味着"用户真按的那条命令"没有任何用例覆盖。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import unittest

from src.python.cli import log_query
from src.python.core import audit


class LogQueryCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.logs = os.path.join(self.tmp.name, "logs")
        audit.record_write(
            src="报告.png", dst="报告-1.png", report=[{"old": "2023", "new": "2024"}],
            log_dir=self.logs, channel="cli", when=dt.datetime(2026, 11, 18, 10, 0),
        )
        audit.record_write(
            src="通知.png", dst="通知-1.png", report=[{"old": "A", "new": "B"}] * 2,
            log_dir=self.logs, channel="tui", when=dt.datetime(2026, 11, 18, 11, 0),
        )

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = log_query.main(["--log-dir", self.logs, *args])
        return code, out.getvalue(), err.getvalue()

    def test_lists_all_entries_with_summary(self):
        code, out, _err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("写盘 2 次", out)
        self.assertIn("替换操作 3 处", out)
        self.assertIn("报告.png", out)

    def test_filters_by_source(self):
        _code, out, _err = self.run_cli("--src", "报告")
        self.assertIn("报告.png", out)
        self.assertNotIn("通知.png", out)

    def test_filters_by_channel(self):
        _code, out, _err = self.run_cli("--channel", "tui")
        self.assertIn("通知.png", out)
        self.assertNotIn("报告.png", out)

    def test_filters_by_date(self):
        _code, out, _err = self.run_cli("--date", "20261118")
        self.assertIn("写盘 2 次", out)
        code, out, _err = self.run_cli("--date", "20260101")
        self.assertEqual(code, 0)
        self.assertIn("没有匹配", out)

    def test_json_output_is_parseable(self):
        _code, out, _err = self.run_cli("--json")
        payload = json.loads(out)
        self.assertEqual(len(payload["reports"]), 2)
        self.assertEqual(payload["summary"]["writes"], 2)

    def test_bad_date_is_rejected(self):
        code, _out, err = self.run_cli("--date", "2026-11-18")
        self.assertEqual(code, 2)
        self.assertIn("YYYYMMDD", err)

    def test_missing_directory_reports_no_match(self):
        code, out, _err = self.run_cli("--src", "不存在的图")
        self.assertEqual(code, 0)
        self.assertIn("没有匹配", out)

    def test_help_prints_usage(self):
        out, _err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            log_query.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("--src", out.getvalue())


if __name__ == "__main__":
    unittest.main()
