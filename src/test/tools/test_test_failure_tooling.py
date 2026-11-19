"""顺序依赖定位与失败用例提取：两个排障工具的纯逻辑与入口契约。

- `test_order_dependent`：`parse_collect_order` 解析收集顺序、`minimize_prefix` 二分最短前缀、
  `locate` 用注入的 runner 跑主流程（不打桩就能测）。
- `test_failures`：junit → 节点 ID / 类型 / 消息，以及 `--json`、退出码（0/1/2）。
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.python.tools import test_failures, test_order_dependent

COLLECT_OUTPUT = """\
src/test/cli/test_a.py::Cls::test_one
src/test/cli/test_a.py::Cls::test_two
src/test/core/test_b.py::test_three
src/test/tui/test_c.py::Cls::test_four

4 tests collected in 0.12s
"""


class ParseCollectOrder(unittest.TestCase):
    def test_files_are_deduplicated_in_first_seen_order(self):
        self.assertEqual(
            test_order_dependent.parse_collect_order(COLLECT_OUTPUT),
            ["src/test/cli/test_a.py", "src/test/core/test_b.py", "src/test/tui/test_c.py"],
        )

    def test_summary_lines_are_ignored(self):
        self.assertEqual(test_order_dependent.parse_collect_order("no tests ran in 0.01s"), [])


class MinimizePrefix(unittest.TestCase):
    """二分：只在「前缀够长就复现」的前提下成立（真实污染即如此）。"""

    def test_finds_the_shortest_reproducing_prefix(self):
        candidates = ["a.py", "b.py", "c.py", "d.py"]

        def fails(files):
            return len(files) >= 3  # 需要 a+b+c 才会失败

        self.assertEqual(
            test_order_dependent.minimize_prefix(candidates, fails), ["a.py", "b.py", "c.py"]
        )

    def test_returns_empty_when_never_fails(self):
        self.assertEqual(test_order_dependent.minimize_prefix(["a.py"], lambda _f: False), [])


class Locate(unittest.TestCase):
    """主流程：单跑通过 → 才能谈顺序依赖；否则直接判"不是顺序依赖"。"""

    def test_solo_failure_means_not_order_dependent(self):
        finding, outcome = test_order_dependent.locate(
            "src/test/t.py::Cls::test_x",
            ["a.py"],
            lambda _files, _target: test_order_dependent.Outcome.TARGET_FAILED,
        )
        self.assertIsNone(finding.culprit)
        self.assertIs(outcome, test_order_dependent.Outcome.TARGET_FAILED)

    def test_locates_the_culprit_file(self):
        def run(files, _target):
            # a.py 是污染源：只要它在前缀里，目标就红
            return (
                (
                    test_order_dependent.Outcome.TARGET_FAILED
                    if "b.py" in files
                    else test_order_dependent.Outcome.TARGET_PASSED
                )
                if files
                else test_order_dependent.Outcome.TARGET_PASSED
            )

        finding, outcome = test_order_dependent.locate(
            "t.py::Cls::test_x", ["a.py", "b.py", "c.py"], run
        )
        self.assertIs(outcome, test_order_dependent.Outcome.TARGET_FAILED)
        self.assertEqual(finding.culprit, "b.py")
        self.assertIn("b.py", finding.command("t.py::Cls::test_x"))


class NodeId(unittest.TestCase):
    def test_class_holder_becomes_part_of_the_nodeid(self):
        self.assertEqual(
            test_failures._nodeid("src.test.cli.test_a.Cls", "test_x"),
            "src/test/cli/test_a.py::Cls::test_x",
        )

    def test_module_level_test_has_no_class(self):
        self.assertEqual(
            test_failures._nodeid("src.test.core.test_b", "test_three"),
            "src/test/core/test_b.py::test_three",
        )


def write_junit(path: Path, failures: int) -> None:
    suite = ET.Element("testsuite", {"tests": "3", "failures": str(failures)})
    ok = ET.SubElement(suite, "testcase", {"classname": "src.test.a.Cls", "name": "test_ok"})
    ok.text = None
    for i in range(failures):
        case = ET.SubElement(
            suite, "testcase", {"classname": "src.test.a.Cls", "name": f"test_bad_{i}"}
        )
        bad = ET.SubElement(case, "failure", {"type": "AssertionError", "message": "boom\nline2"})
        bad.text = "traceback"
    ET.ElementTree(suite).write(path, encoding="utf-8")


class TestFailuresCLI(unittest.TestCase):
    def run_main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = test_failures.main(list(args))
        return code, out.getvalue()

    def test_missing_report_is_exit_two(self):
        code, _out = self.run_main("--path", "reports/不存在.xml")
        self.assertEqual(code, 2)

    def test_no_failures_is_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            write_junit(path, failures=0)
            code, out = self.run_main("--path", str(path))
        self.assertEqual(code, 0)
        self.assertIn("没有失败用例", out)

    def test_failures_are_listed_with_a_rerun_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            write_junit(path, failures=2)
            code, out = self.run_main("--path", str(path))
        self.assertEqual(code, 1)
        self.assertIn("src/test/a.py::Cls::test_bad_0", out)
        self.assertIn("单跑复现", out)

    def test_json_mode_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            write_junit(path, failures=1)
            code, out = self.run_main("--path", str(path), "--json")
        payload = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["cases"][0]["type"], "AssertionError")
        self.assertIn("pytest -q", payload["rerun"])

    def test_max_limits_the_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            write_junit(path, failures=3)
            code, out = self.run_main("--path", str(path), "--max", "1")
        self.assertEqual(code, 1)
        self.assertIn("另有 2 个", out)


if __name__ == "__main__":
    unittest.main()
