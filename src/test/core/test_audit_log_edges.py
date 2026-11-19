"""写盘日志与文件锁：坏行跳过、写入失败、跨平台锁后端、旧日志清理。"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python.core import audit, options
from src.python.core.errors import CoreError
from src.test._support import (
    TuiTestCase,
)


class WinLockImportFailure(unittest.TestCase):
    def test_winlock_returns_none_without_msvcrt(self):
        with mock.patch.object(
            audit.importlib, "import_module", side_effect=ImportError("no msvcrt")
        ):
            self.assertIsNone(audit._winlock())


class AuditGaps(unittest.TestCase):
    def test_permission_error_becomes_core_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp))
            path.write_text("{}\n", encoding="utf-8")
            real_open = open

            def guarded(file, *args, **kwargs):
                if str(file).endswith(".log"):
                    raise PermissionError("denied")
                return real_open(file, *args, **kwargs)

            with mock.patch("builtins.open", side_effect=guarded), self.assertRaises(CoreError):
                audit.read_entries(tmp)


class AuditBadLine(unittest.TestCase):
    def test_non_object_json_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp))
            path.write_text('[1, 2]\n\n{"src_file": "a.png"}\n', encoding="utf-8")
            entries = audit.read_entries(tmp)
        self.assertEqual(len(entries), 1, "数组行与空行都应被跳过")


class AuditJsonError(unittest.TestCase):
    def test_broken_json_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp))
            path.write_text("{坏的\n", encoding="utf-8")
            self.assertEqual(audit.read_entries(tmp), [])
            self.assertTrue(json.dumps({"a": 1}))


class AuditWriteFailure(unittest.TestCase):
    def test_oserror_while_opening_log_becomes_core_error(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(audit.os, "open", side_effect=OSError("denied")),
            self.assertRaises(CoreError),
        ):
            audit.record_write("a.png", "b.png", (), log_dir=tmp)


class FinalGaps2(TuiTestCase):
    """收尾：写日志失败、缓存版本不符、目录不可读、空白渲染、翻页与 DC 键。"""

    def test_log_write_failure_becomes_core_error(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(audit.os, "write", side_effect=OSError("disk full")),
            self.assertRaises(CoreError),
        ):
            audit.record_write("a.png", "b.png", (), log_dir=tmp)


class FinalGaps3(TuiTestCase):
    """收尾（二）：平台分支、空窗口、右对齐、错误的 cur、ESC 取消等。"""

    def test_unlock_windows_branch(self):
        # 用真实临时文件描述符：git 钩子里 fd 3 是 git 自己的管道，
        # lseek 会失败，测试会误红（这类"写死 fd"的用例本身就是隐患）
        with tempfile.TemporaryFile() as handle:
            fd = handle.fileno()
            fake_win = mock.Mock(LK_UNLCK=1)
            with (
                mock.patch.object(audit, "fcntl", None),
                mock.patch.object(audit, "_winlock", return_value=fake_win),
            ):
                audit._unlock(fd, locked=True)
        fake_win.locking.assert_called_once()

    def test_unlock_windows_branch_without_msvcrt(self):
        with (
            tempfile.TemporaryFile() as handle,
            mock.patch.object(audit, "fcntl", None),
            mock.patch.object(audit, "_winlock", return_value=None),
        ):
            audit._unlock(handle.fileno(), locked=True)


class LockWithoutAnyBackend(unittest.TestCase):
    """既没有 fcntl 也没有 msvcrt（极端环境）：`_lock` 返回 False，写日志照常进行。"""

    def test_lock_returns_false_without_any_backend(self):
        with (
            tempfile.TemporaryFile() as handle,
            mock.patch.object(audit, "fcntl", None),
            mock.patch.object(audit, "_winlock", return_value=None),
        ):
            self.assertFalse(audit._lock(handle.fileno()))


class FinalGaps4(TuiTestCase):
    """收尾（三）：预演同名、锁失败、fontconfig 缺失、应用当前图的空路径等。"""

    def test_unlock_swallows_oserror(self):
        with (
            tempfile.TemporaryFile() as handle,
            mock.patch.object(audit.fcntl, "flock", side_effect=OSError("boom")),
        ):
            audit._unlock(handle.fileno(), locked=True)


class FinalGaps5(TuiTestCase):
    """收尾（四）：无成功替换、未加锁解锁、字体 repr、当前图替换、进度条。"""

    def test_unlock_without_lock_is_a_noop(self):
        with tempfile.TemporaryFile() as handle:
            audit._unlock(handle.fileno(), locked=False)


class FinalGaps6(TuiTestCase):
    """收尾（五）：读图失败、Windows 锁、缺 fontconfig、保存失败、行内详情。"""

    def test_lock_uses_msvcrt_when_fcntl_is_missing(self):
        with tempfile.TemporaryFile() as handle:
            fake_win = mock.Mock(LK_LOCK=1)
            with (
                mock.patch.object(audit, "fcntl", None),
                mock.patch.object(audit, "_winlock", return_value=fake_win),
            ):
                self.assertTrue(audit._lock(handle.fileno()))
        fake_win.locking.assert_called_once()


class FinalGaps7(TuiTestCase):
    """收尾（六）：读图失败、删日志失败、预留名失败、Enter 整行编辑、脏进度数字。"""

    def test_prune_skips_files_that_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp, dt.datetime(2020, 1, 1)))
            path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(audit.os, "remove", side_effect=OSError("denied")):
                removed = audit.prune_logs(tmp, keep_days=1, today=dt.date(2026, 11, 18))
        self.assertEqual(removed, [], "删不掉的文件不计入已删列表")


class FinalGaps8(TuiTestCase):
    """收尾（七）：第二轮读图失败、坏日期日志名、apply_one 读图失败、整行编辑。"""

    def test_prune_ignores_badly_named_log_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "image-writes-notadate.log"
            bad.write_text("{}\n", encoding="utf-8")
            removed = audit.prune_logs(tmp, keep_days=1, today=dt.date(2026, 11, 18))
            still_there = bad.exists()
        self.assertEqual(removed, [])
        self.assertTrue(still_there, "解析不出日期的文件不能被删")


class LogRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write_log(self, day: dt.date) -> str:
        path = audit.log_path(self.tmp.name, dt.datetime.combine(day, dt.time()))
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}\n")
        return path

    def test_old_days_are_pruned_and_recent_kept(self):
        today = dt.date(2026, 11, 18)
        old = self.write_log(today - dt.timedelta(days=40))
        fresh = self.write_log(today - dt.timedelta(days=1))
        removed = audit.prune_logs(self.tmp.name, keep_days=30, today=today)
        self.assertEqual([os.path.basename(old)], removed)
        self.assertTrue(os.path.exists(fresh))

    def test_unrelated_files_are_never_touched(self):
        keep = os.path.join(self.tmp.name, "notes.txt")
        with open(keep, "w", encoding="utf-8") as f:
            f.write("keep me")
        audit.prune_logs(self.tmp.name, keep_days=1, today=dt.date(2026, 11, 18))
        self.assertTrue(os.path.exists(keep))

    def test_missing_directory_is_not_an_error(self):
        self.assertEqual(audit.prune_logs(os.path.join(self.tmp.name, "nope")), [])


class OptionsSummary(unittest.TestCase):
    def test_defaults_are_omitted(self):
        self.assertEqual(audit.options_summary(options.Options()), {})

    def test_explicit_values_are_recorded(self):
        summary = audit.options_summary(
            options.Options(font="/tmp/a.ttf", size=28)
        )  # platform-safe
        self.assertEqual(summary.get("size"), 28)
        self.assertIn("font", summary)

    def test_none_options_yield_empty_summary(self):
        self.assertEqual(audit.options_summary(None), {})
