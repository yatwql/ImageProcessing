"""「跨平台」守护的规则自检：规则本身也要有用例，否则它会悄悄失效。

守的是三类「本机绿、Windows 红」的写法（`check_platform_safety._check_test_hygiene`）：
断言里写死字体家族、直接用裸 `bash`/`sh`、无平台守卫地碰 `fcntl`。
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python.tools import check_platform_safety as cps
from src.test import _support


def hits(lines: list[str]) -> list[str]:
    return cps._check_test_hygiene("src/test/demo_case.py", lines)


class FontFamilyRule(unittest.TestCase):
    def test_hardcoded_family_is_flagged(self):
        problems = hits(
            ['self.assertIn("NotoSansCJK", repr(face))']
        )  # platform-safe：这是被测样本文本
        self.assertTrue(problems)
        self.assertIn("字体家族", problems[0])

    def test_neutral_text_is_not_flagged(self):
        self.assertEqual(hits(['self.assertIn("示例字体", repr(face))']), [])

    def test_platform_safe_marker_exempts(self):
        self.assertEqual(hits(['self.assertIn("Noto", repr(face))  # platform-safe']), [])


class BareShellRule(unittest.TestCase):
    def test_bare_bash_is_flagged(self):
        problems = hits(['subprocess.run(["bash", "-n", path])'])
        self.assertTrue(problems)
        self.assertIn("bash_exe", problems[0])

    def test_helper_based_usage_is_allowed(self):
        lines = ["BASH = bash_exe()", 'subprocess.run([BASH, "-n", path])']
        self.assertEqual(hits(lines), [])


class FcntlRule(unittest.TestCase):
    def test_direct_fcntl_without_guard_is_flagged(self):
        problems = hits(["mock.patch.object(audit.fcntl, 'flock')"])
        self.assertTrue(problems)
        self.assertIn("fcntl", problems[0])

    def test_guarded_fcntl_is_allowed(self):
        lines = [
            '@unittest.skipIf(getattr(audit, "fcntl", None) is None, "POSIX only")',
            "mock.patch.object(audit.fcntl, 'flock')",
        ]
        self.assertEqual(hits(lines), [])


class AbsoluteThresholdRule(unittest.TestCase):
    def test_bare_pixel_threshold_is_flagged(self):
        problems = hits(["self.assertGreaterEqual(out_w, 111)"])
        self.assertTrue(problems)
        self.assertIn("绝对像素", problems[0])

    def test_ratio_of_two_measurements_is_allowed(self):
        self.assertEqual(hits(["self.assertGreaterEqual(out_w, 0.85 * expected_w)"]), [])


class RawRuntimeRule(unittest.TestCase):
    def test_asserting_on_sys_executable_is_flagged(self):
        problems = hits(["self.assertEqual(cmd[0], sys.executable)"])
        self.assertTrue(problems)
        self.assertIn("sys.executable", problems[0])

    def test_path_derived_expectation_is_allowed(self):
        self.assertEqual(hits(['self.assertEqual(cmd[0], str(Path("/x/python")))']), [])


class FontModeSelections(unittest.TestCase):
    """`IMG_P_TEST_FONT` 的候选顺序：默认 / alt（换字族）/ 指定文件名。"""

    def test_default_mode_uses_same_weight(self):
        bold = _support.font_candidates(False, "")
        regular = _support.font_candidates(True, "")
        self.assertIn("bold", bold[0].lower())
        self.assertIn("regular", regular[0].lower())

    def test_alt_mode_swaps_weight(self):
        self.assertIn("regular", _support.font_candidates(False, "alt")[0].lower())
        self.assertIn("bold", _support.font_candidates(True, "alt")[0].lower())

    def test_named_mode_only_keeps_that_file(self):
        picked = _support.font_candidates(False, "msyh.ttc")
        self.assertTrue(picked)
        self.assertTrue(all(p.lower().endswith("msyh.ttc") for p in picked))

    def test_unknown_named_font_yields_no_candidate(self):
        self.assertEqual(_support.font_candidates(False, "不存在的字体.ttf"), ())


class ToolStdioRule(unittest.TestCase):
    """`tools/*.py` 里有 main() 就必须调 ensure_utf8_stdio()（Windows 控制台 cp1252）。"""

    def test_tool_without_stdio_call_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/python/tools").mkdir(parents=True)
            (root / "src/python/tools/bad.py").write_text(
                'def main() -> int:\n    print("中文")\n    return 0\n', encoding="utf-8"
            )
            problems = cps.check_tool_stdio(root)
        self.assertTrue(problems)
        self.assertIn("ensure_utf8_stdio", problems[0])

    def test_tool_with_stdio_call_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/python/tools").mkdir(parents=True)
            (root / "src/python/tools/good.py").write_text(
                "def main() -> int:\n    ensure_utf8_stdio()\n    return 0\n", encoding="utf-8"
            )
            self.assertEqual(cps.check_tool_stdio(root), [])

    def test_module_without_main_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/python/tools").mkdir(parents=True)
            (root / "src/python/tools/_paths.py").write_text("ROOT = 1\n", encoding="utf-8")
            self.assertEqual(cps.check_tool_stdio(root), [])


class LineEndingRule(unittest.TestCase):
    def test_repo_gitattributes_pins_lf_for_shell(self):
        self.assertEqual(cps.check_line_endings(), [])


class BashProbe(unittest.TestCase):
    def test_missing_bash_returns_none(self):
        with mock.patch.object(_support.shutil, "which", return_value=None):
            self.assertIsNone(_support.bash_exe())

    def test_stub_bash_that_cannot_run_returns_none(self):
        stub = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with (
            mock.patch.object(_support.shutil, "which", return_value="bash"),
            mock.patch.object(_support.subprocess, "run", return_value=stub),
        ):
            self.assertIsNone(_support.bash_exe())

    def test_working_bash_is_returned(self):
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(_support.shutil, "which", return_value="/bin/bash"),
            mock.patch.object(_support.subprocess, "run", return_value=ok),
        ):
            self.assertEqual(_support.bash_exe(), "/bin/bash")


if __name__ == "__main__":
    unittest.main()
