"""门禁戳（`hook_gate_stamp`）：同一份代码不重复跑全量门禁。

守的原因：每轮 push 都跑一遍 ~7 分钟的全量门禁（4 轮用例），
而"代码没变"时结论必然一样。戳按「跟踪文件路径 + 内容」的 sha256 算，
与是否提交无关；改任何一个文件都会让戳失效。
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python.tools import hook_gate_stamp


def run_stamp(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = hook_gate_stamp.main(argv)
    return code, out.getvalue()


class StampFile(unittest.TestCase):
    def test_missing_stamp_does_not_match(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(hook_gate_stamp, "fingerprint", return_value="abc"),
        ):
            self.assertFalse(hook_gate_stamp.stamp_matches(Path(tmp)))

    def test_write_then_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(hook_gate_stamp, "fingerprint", return_value="abc"):
                hook_gate_stamp.write_stamp(root)
                self.assertTrue(hook_gate_stamp.stamp_matches(root))
                # 代码一变（指纹变）就不匹配
                with mock.patch.object(hook_gate_stamp, "fingerprint", return_value="def"):
                    self.assertFalse(hook_gate_stamp.stamp_matches(root))

    def test_corrupted_stamp_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = hook_gate_stamp.stamp_path(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not json", encoding="utf-8")
            self.assertFalse(hook_gate_stamp.stamp_matches(root))

    def test_stamp_metadata_is_json_with_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(hook_gate_stamp, "fingerprint", return_value="abc"):
                hook_gate_stamp.write_stamp(root)
            data = json.loads(hook_gate_stamp.stamp_path(root).read_text(encoding="utf-8"))
        self.assertEqual(data["fingerprint"], "abc")
        self.assertIn("T", data["at"])


class Fingerprint(unittest.TestCase):
    def test_changes_when_tracked_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("1\n", encoding="utf-8")
            for cmd in (["git", "init", "-q"], ["git", "add", "a.txt"]):
                subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)
            first = hook_gate_stamp.fingerprint(root)
            (root / "a.txt").write_text("2\n", encoding="utf-8")
            second = hook_gate_stamp.fingerprint(root)
        self.assertNotEqual(first, second)

    def test_ignores_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("1\n", encoding="utf-8")
            for cmd in (["git", "init", "-q"], ["git", "add", "a.txt"]):
                subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)
            before = hook_gate_stamp.fingerprint(root)
            (root / "b.txt").write_text("新文件\n", encoding="utf-8")
            after = hook_gate_stamp.fingerprint(root)
        self.assertEqual(before, after)


class CommandLine(unittest.TestCase):
    def test_check_reports_miss(self):
        # git 目录也钉在临时根上：否则临时目录若落在仓库内，
        # `git rev-parse --git-dir` 会指回真实仓库，读到真戳而不是"没戳"
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(hook_gate_stamp, "ROOT", Path(tmp)),
            mock.patch.object(hook_gate_stamp, "git_dir", return_value=Path(tmp) / ".git"),
            mock.patch.object(hook_gate_stamp, "fingerprint", return_value="abc"),
        ):
            code, out = run_stamp(["--check"])
        self.assertEqual(code, 1)
        self.assertIn("真跑一次全量门禁", out)

    def test_write_then_check_reports_hit(self):
        # git 目录也钉在临时根上：否则临时目录若落在仓库内，
        # `git rev-parse --git-dir` 会指回真实仓库，读到真戳而不是"没戳"
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(hook_gate_stamp, "ROOT", Path(tmp)),
            mock.patch.object(hook_gate_stamp, "git_dir", return_value=Path(tmp) / ".git"),
            mock.patch.object(hook_gate_stamp, "fingerprint", return_value="abc"),
        ):
            self.assertEqual(run_stamp(["--write"])[0], 0)
            code, out = run_stamp(["--check"])
        self.assertEqual(code, 0)
        self.assertIn("跳过重跑", out)


if __name__ == "__main__":
    unittest.main()
