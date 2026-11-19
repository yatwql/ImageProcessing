"""工程工具的入口契约：每个 CLI 都能 `--help`（不炸）、`--ci` 结论可读。

为什么要单独钉一层：`tools/` 下的脚本是"门禁的门禁"——它们坏掉时表现为 CI 莫名红，
而不是某个业务用例失败。这里只测入口面（解析参数、退出码、输出不刷屏），
实现细节由各自的用例负责。
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from src.python.tools import (
    check_coverage,
    check_import_surface,
    check_workflows,
    make_constraints,
    probe_ci_env,
    release,
    test_coverage_report,
    test_runner,
)

MODULES = [
    check_coverage,
    check_import_surface,
    check_workflows,
    probe_ci_env,
    test_coverage_report,
    release,
    test_runner,
    make_constraints,
]


def run_help(module) -> str:
    """跑一次 `--help`，返回打印内容；入口自己 `sys.exit(0)` 也算通过。"""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            module.main(["--help"])
        except SystemExit as exc:
            assert exc.code == 0, f"{module.__name__} --help 退出码应为 0"
    return buffer.getvalue()


class HelpExit(unittest.TestCase):
    """`--help` 一律正常结束，且确实打印了说明（不是静默返回）。"""

    def test_every_tool_prints_help(self):
        for module in MODULES:
            with self.subTest(tool=module.__name__):
                self.assertTrue(run_help(module).strip(), f"{module.__name__} --help 没有输出")


class HelpHasNoSideEffects(unittest.TestCase):
    """`--help` 只打印说明：不许建目录、不许清报告（曾经的现场事故见下）。"""

    def test_runner_help_does_not_touch_reports(self):
        # 旧实现先 prepare_report_dir() 再解析参数：看帮助会把 reports/coverage.xml
        # 清掉，而门禁的覆盖率步骤紧接着就要读它 → 全量门禁恒红。
        with (
            mock.patch.object(test_runner, "prepare_report_dir") as prepare,
            mock.patch.object(test_runner, "prepare_tmp") as make_tmp,
        ):
            self.assertEqual(test_runner.main(["--help"]), 0)
        prepare.assert_not_called()
        make_tmp.assert_not_called()


class CIMode(unittest.TestCase):
    """`--ci` 是门禁形态：只输出结论，不逐条刷屏。"""

    def test_check_import_surface_ci_is_silent_when_clean(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(check_import_surface, "violations", return_value=[]),
            contextlib.redirect_stdout(buffer),
        ):
            self.assertEqual(check_import_surface.main(["--ci"]), 0)
        self.assertEqual(buffer.getvalue(), "", "干净时 --ci 不该刷屏")

    def test_check_workflows_ci_prints_one_conclusion_on_failure(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(check_workflows, "CI") as fake_ci,
            mock.patch.object(check_workflows, "load_yaml", return_value={"jobs": {}}),
            contextlib.redirect_stdout(buffer),
        ):
            fake_ci.is_file.return_value = True
            fake_ci.relative_to.return_value = "ci.yml"
            code = check_workflows.main(["--ci"])
        self.assertEqual(code, 1)
        self.assertIn("工作流自检", buffer.getvalue())

    def test_check_coverage_ci_reports_missing_report(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = check_coverage.main(["reports/不存在的覆盖率.xml", "--ci"])
        self.assertEqual(code, 1)
        self.assertIn("找不到覆盖率报告", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
