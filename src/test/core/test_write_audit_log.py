"""写盘日志：真实保存图片后必须留下一条可追溯的记录。

覆盖三层：
- 记录本身：字段（源/目标文件名与大小、替换明细、时间）、按天命名、追加语义、目录自建；
- 渠道联动：CLI/TUI 保存后各记一条、批量逐图记、调试图也记、预演不记、
  日志目录覆盖优先级、日志不可写时不影响已保存的图片；
- 错误契约：保存失败或拒绝覆盖时不留下任何日志。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import multiprocessing
import os
import tempfile
import unittest
from unittest import mock

from PIL import Image

from src.python.cli.main import main
from src.python.core import audit
from src.python.core.errors import CoreError
from src.python.core.options import Options
from src.python.tui.app import App, Block
from src.test._support import TuiTestCase, has_cjk_font, make_text_image, patch_ocr


def read_entries(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def audit_worker(log_dir: str, tag: str) -> None:
    """子进程里连续写日志，用来验证跨进程加锁。"""
    for i in range(10):
        audit.record_write("a.png", "b.png", [{"old": f"{tag}-{i}", "new": tag * 3}],
                           log_dir=log_dir)


def all_entries(log_dir: str) -> list[dict]:
    if not os.path.isdir(log_dir):
        return []
    entries: list[dict] = []
    for name in sorted(os.listdir(log_dir)):
        entries += read_entries(os.path.join(log_dir, name))
    return entries


class AuditEntryFields(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "旧图.png")
        self.dst = os.path.join(self.tmp.name, "新图.png")
        with open(self.src, "wb") as f:
            f.write(b"x" * 1234)
        with open(self.dst, "wb") as f:
            f.write(b"y" * 99)

    def test_entry_carries_names_sizes_and_replacement(self):
        when = dt.datetime(2024, 5, 1, 12, 30, 15, tzinfo=dt.timezone.utc)   # dt.UTC 是 3.11+，CI 还跑 3.10
        report = [{"old": "2023", "new": "2024", "mode": "整体", "rect": [1, 2, 3, 4],
                   "font": "NotoSans", "size": 36, "tracking": 0.5,
                   "color": [0, 0, 0], "align": "center", "iou": 0.91}]
        entry = audit.build_entry(self.src, self.dst, report, when=when)

        self.assertEqual(entry["time"], "2024-05-01T12:30:15+00:00")
        self.assertEqual(entry["src_file"], "旧图.png")
        self.assertEqual(entry["src_size"], 1234)
        self.assertEqual(entry["dst_file"], "新图.png")
        self.assertEqual(entry["dst_size"], 99)
        self.assertEqual(entry["replaced"], 1)
        self.assertEqual(entry["operations"][0]["old"], "2023")
        self.assertEqual(entry["operations"][0]["new"], "2024")
        self.assertEqual(entry["operations"][0]["font"], "NotoSans")

    def test_operation_keeps_every_documented_field(self):
        report = [{"old": "A", "new": "B", "mode": "行内", "rect": [1, 2, 3, 4],
                   "font": "F", "size": 10, "tracking": -0.5, "color": [1, 2, 3],
                   "align": "right", "iou": 0.5, "extra_ignored": True}]
        entry = audit.build_entry(self.src, self.dst, report)
        self.assertEqual(set(entry["operations"][0]), set(audit.OP_FIELDS))

    def test_multiple_operations_are_all_recorded(self):
        report = [{"old": "甲", "new": "乙"}, {"old": "丙", "new": "丁"}]
        entry = audit.build_entry(self.src, self.dst, report)
        self.assertEqual(entry["replaced"], 2)
        self.assertEqual([op["new"] for op in entry["operations"]], ["乙", "丁"])

    def test_entry_records_output_dimensions_and_digest(self):
        Image.new("RGB", (12, 7), (9, 9, 9)).save(self.dst)
        entry = audit.build_entry(self.src, self.dst, ())
        self.assertEqual((entry["dst_width"], entry["dst_height"]), (12, 7))
        self.assertEqual(len(entry["dst_sha256"] or ""), 64)

    def test_missing_source_size_is_none_not_an_exception(self):
        ghost = os.path.join(self.tmp.name, "不存在.png")
        entry = audit.build_entry(ghost, self.dst, ())
        self.assertIsNone(entry["src_size"])
        self.assertEqual(entry["replaced"], 0)

    def test_options_summary_keeps_only_explicit_settings(self):
        font = os.path.join(self.tmp.name, "x.ttf")
        summary = audit.options_summary(Options(font=font, size=40, align="left"))
        self.assertEqual(summary, {"font": font, "size": 40, "align": "left"})
        self.assertEqual(audit.options_summary(None), {})

    def test_options_summary_skips_defaults_and_runtime_fields(self):
        summary = audit.options_summary(Options(max_fonts=160, quiet=True,
                                                log_dir=os.path.join(self.tmp.name, "logs"),
                                                channel="cli"))
        self.assertEqual(summary, {})


class AuditLogFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.log_dir = os.path.join(self.tmp.name, "logs")
        self.src = os.path.join(self.tmp.name, "a.png")
        self.dst = os.path.join(self.tmp.name, "b.png")
        for path in (self.src, self.dst):
            with open(path, "wb") as f:
                f.write(b"z")

    def test_log_file_is_named_by_day(self):
        when = dt.datetime(2024, 5, 1, 8, 0, 0)
        path = audit.log_path(self.log_dir, when)
        self.assertEqual(path, os.path.join(self.log_dir, "image-writes-20240501.log"))

    def test_record_write_creates_missing_log_dir(self):
        nested = os.path.join(self.log_dir, "a", "b")
        path = audit.record_write(self.src, self.dst, (), log_dir=nested)
        self.assertTrue(os.path.isfile(path))

    def test_record_write_appends_one_json_line_per_call(self):
        first = audit.record_write(self.src, self.dst, [{"old": "A", "new": "B"}],
                                   log_dir=self.log_dir)
        second = audit.record_write(self.src, self.dst, [], log_dir=self.log_dir,
                                    action=audit.ACTION_DEBUG)
        self.assertEqual(first, second)                 # 同一天写同一个文件
        entries = read_entries(first)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["operations"][0]["new"], "B")
        self.assertEqual(entries[1]["action"], audit.ACTION_DEBUG)

    def test_entries_are_one_per_line_and_valid_json(self):
        for text in ("中文", "带 \"引号\"", "emoji 🎉"):
            audit.record_write(self.src, self.dst, [{"old": text, "new": text}],
                               log_dir=self.log_dir)
        path = audit.log_path(self.log_dir)
        with open(path, encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 3)
        self.assertEqual([json.loads(line)["operations"][0]["old"] for line in lines],
                         ["中文", "带 \"引号\"", "emoji 🎉"])

    def test_time_has_timezone_offset(self):
        audit.record_write(self.src, self.dst, (), log_dir=self.log_dir)
        stamp = dt.datetime.fromisoformat(all_entries(self.log_dir)[0]["time"])
        self.assertIsNotNone(stamp.tzinfo)

    def test_logs_older_than_keep_days_are_pruned(self):
        old = os.path.join(self.log_dir, "image-writes-20200101.log")
        os.makedirs(self.log_dir, exist_ok=True)
        with open(old, "w", encoding="utf-8") as f:
            f.write("{}\n")
        path = audit.record_write(self.src, self.dst, (), log_dir=self.log_dir)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(path))            # 当天的留着

    def test_prune_can_be_disabled(self):
        old = os.path.join(self.log_dir, "image-writes-20200101.log")
        os.makedirs(self.log_dir, exist_ok=True)
        with open(old, "w", encoding="utf-8") as f:
            f.write("{}\n")
        self.assertEqual(audit.prune_logs(self.log_dir, keep_days=0), [])
        self.assertTrue(os.path.exists(old))

    def test_concurrent_writers_never_interleave_lines(self):
        ctx = multiprocessing.get_context("spawn")      # 不依赖 fork，Windows 也能跑
        procs = [ctx.Process(target=audit_worker, args=(self.log_dir, tag))
                 for tag in ("A", "B", "C")]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=60)

        entries = all_entries(self.log_dir)
        self.assertEqual(len(entries), 30)               # 一行一条，没有撕开的行
        self.assertEqual(sorted({e["operations"][0]["old"][0] for e in entries}),
                         ["A", "B", "C"])

    def test_unwritable_log_dir_raises_core_error(self):
        blocker = os.path.join(self.tmp.name, "blocker")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("not a directory")
        with self.assertRaises(CoreError):
            audit.record_write(self.src, self.dst, (), log_dir=os.path.join(blocker, "logs"))


@unittest.skipUnless(has_cjk_font(), "缺少 Noto CJK 字体")
class CliWritesAuditLog(unittest.TestCase):
    TITLE = "年度报告2023"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.rgb, self.boxes = make_text_image([self.TITLE])
        self.path = os.path.join(self.tmp.name, "report.png")
        Image.fromarray(self.rgb).save(self.path)
        self.log_dir = os.path.join(self.tmp.name, "logs")

    def run_cli(self, *argv: str, log_dir: str | None = None) -> int:
        code, _out, _err = self.run_cli_capture(*argv, log_dir=log_dir)
        return code

    def run_cli_capture(self, *argv: str, log_dir: str | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        target = {"IMG_P_LOG_DIR": log_dir or self.log_dir}
        with patch_ocr(self.boxes), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err), mock.patch.dict(os.environ, target):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def logs(self, log_dir: str | None = None) -> list[dict]:
        return all_entries(log_dir or self.log_dir)

    def test_real_save_is_logged_with_old_and_new_text(self):
        out_dir = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.run_cli(self.path, "--map", f"{self.TITLE}=年度报告2024",
                                      "--out-dir", out_dir, "--quiet"), 0)
        entries = self.logs()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["src_file"], "report.png")
        self.assertEqual(entries[0]["src_size"], os.path.getsize(self.path))
        self.assertEqual(entries[0]["dst_file"], "report.png")
        self.assertEqual(entries[0]["dst_size"], os.path.getsize(os.path.join(out_dir, "report.png")))
        self.assertEqual(entries[0]["operations"][0]["old"], self.TITLE)
        self.assertEqual(entries[0]["operations"][0]["new"], "年度报告2024")
        self.assertEqual(entries[0]["channel"], "cli")
        self.assertEqual(entries[0]["action"], audit.ACTION_REPLACE)

    def test_dry_run_leaves_no_log(self):
        self.assertEqual(self.run_cli(self.path, "--map", f"{self.TITLE}=年度报告2024",
                                      "--dry-run"), 0)
        self.assertEqual(self.logs(), [])

    def test_second_save_appends_a_second_record(self):
        self.run_cli(self.path, "--map", f"{self.TITLE}=年度报告2024", "--quiet")
        self.run_cli(self.path, "--map", f"{self.TITLE}=年度报告2025", "--quiet")
        self.assertEqual([e["operations"][0]["new"] for e in self.logs()],
                         ["年度报告2024", "年度报告2025"])

    def test_debug_masks_are_logged_as_debug_action(self):
        debug_dir = os.path.join(self.tmp.name, "debug")
        self.assertEqual(self.run_cli(self.path, "--map", f"{self.TITLE}=年度报告2024",
                                      "--debug", debug_dir, "--quiet"), 0)
        self.assertTrue(os.listdir(debug_dir))          # 真的写了 mask
        actions = [e["action"] for e in self.logs()]
        self.assertIn(audit.ACTION_DEBUG, actions)
        self.assertIn(audit.ACTION_REPLACE, actions)
        debug_entries = [e for e in self.logs() if e["action"] == audit.ACTION_DEBUG]
        self.assertTrue(debug_entries[0]["dst_file"].endswith(".png"))
        self.assertEqual(debug_entries[0]["src_file"], "report.png")
        self.assertEqual(debug_entries[0]["replaced"], 0)

    def test_dry_run_ignores_debug_and_writes_nothing(self):
        debug_dir = os.path.join(self.tmp.name, "debug")
        code, _out, err = self.run_cli_capture(self.path, "--map", f"{self.TITLE}=年度报告2024",
                                               "--dry-run", "--debug", debug_dir)
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(debug_dir))
        self.assertEqual(self.logs(), [])
        self.assertIn("--debug 已忽略", err)

    def test_explicit_log_dir_wins_over_environment(self):
        chosen = os.path.join(self.tmp.name, "chosen")
        self.run_cli(self.path, "--map", f"{self.TITLE}=年度报告2024", "--log-dir", chosen,
                     "--quiet")
        self.assertEqual(len(self.logs(chosen)), 1)
        self.assertFalse(os.path.exists(self.log_dir))

    def test_save_failure_writes_no_log(self):
        blocker = os.path.join(self.tmp.name, "blocker")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("file, not a directory")
        code, _out, err = self.run_cli_capture(self.path, "--map", f"{self.TITLE}=年度报告2024",
                                               "-o", os.path.join(blocker, "x.png"), "--quiet")
        self.assertNotEqual(code, 0)
        self.assertIn("保存失败", err)
        self.assertEqual(self.logs(), [])

    def test_log_failure_keeps_saved_image_and_exit_code(self):
        blocker = os.path.join(self.tmp.name, "logfile")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("file, not a directory")
        dst = os.path.join(self.tmp.name, "out.png")
        code, _out, err = self.run_cli_capture(self.path, "--map", f"{self.TITLE}=年度报告2024",
                                               "-o", dst, "--quiet", log_dir=blocker)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(dst))
        self.assertIn("日志", err)

    def test_batch_logs_one_entry_per_saved_image(self):
        batch_dir = os.path.join(self.tmp.name, "batch")
        os.makedirs(batch_dir)
        for name in ("a.png", "b.png"):
            Image.fromarray(self.rgb).save(os.path.join(batch_dir, name))
        out_dir = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.run_cli(batch_dir, "--map", f"{self.TITLE}=年度报告2024",
                                      "--out-dir", out_dir, "--quiet"), 0)
        entries = self.logs()
        self.assertEqual([e["src_file"] for e in entries], ["a.png", "b.png"])
        self.assertTrue(all(e["channel"] == "cli" for e in entries))


@unittest.skipUnless(has_cjk_font(), "缺少 Noto CJK 字体")
class TuiWritesAuditLog(TuiTestCase):
    TITLE = "年度报告2023"

    def build_app(self, names: tuple[str, ...] = ("report.png",)) -> App:
        rgb, boxes = make_text_image([self.TITLE])
        for name in names:
            Image.fromarray(rgb).save(os.path.join(self.tmp.name, name))
        app = App([self.tmp.name])
        app.out_dir = os.path.join(self.tmp.name, "out")
        app.opts.log_dir = os.path.join(self.tmp.name, "logs")
        for img in app.images:
            img.blocks = [Block(text, rect) for text, rect in boxes]
        return app

    def logs(self, app: App) -> list[dict]:
        return all_entries(app.opts.log_dir or "")

    def first_block(self, img) -> Block:
        blocks = img.blocks or []
        self.assertTrue(blocks, "图片没有预置文字块")
        return blocks[0]

    def test_apply_one_logs_the_saved_image(self):
        app = self.build_app()
        img = app.cur
        assert img is not None
        self.first_block(img).override = "改过的文字"

        ok, msg = app.apply_one(img)

        self.assertTrue(ok, msg)
        entries = self.logs(app)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["channel"], "tui")
        self.assertEqual(entries[0]["operations"][0]["new"], "改过的文字")
        self.assertEqual(entries[0]["dst_file"], os.path.basename(img.saved or ""))

    def test_reapply_appends_another_record(self):
        app = self.build_app()
        img = app.cur
        assert img is not None
        self.first_block(img).override = "第一次"
        app.apply_one(img)
        self.first_block(img).override = "第二次"
        app.apply_one(img)
        entries = self.logs(app)
        self.assertEqual([e["operations"][0]["new"] for e in entries], ["第一次", "第二次"])
        self.assertEqual(len({e["dst_file"] for e in entries}), 1)   # 覆盖同一个输出文件

    def test_refused_overwrite_logs_nothing(self):
        app = self.build_app()
        app.out_dir = self.tmp.name                 # 输出到输入目录 = 会覆盖原图
        img = app.cur
        assert img is not None
        self.first_block(img).override = "改过的文字"
        ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("覆盖原图", msg)
        self.assertEqual(self.logs(app), [])

    def test_no_new_text_logs_nothing(self):
        app = self.build_app()
        img = app.cur
        assert img is not None
        ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("没有启用", msg)
        self.assertEqual(self.logs(app), [])

    def test_log_failure_still_reports_saved(self):
        app = self.build_app()
        blocker = os.path.join(self.tmp.name, "logfile")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("file, not a directory")
        app.opts.log_dir = blocker
        img = app.cur
        assert img is not None
        self.first_block(img).override = "改过的文字"
        ok, msg = app.apply_one(img)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(img.saved or ""))
        self.assertIn("日志", msg)

    def test_batch_apply_logs_each_image(self):
        app = self.build_app(("a.png", "b.png"))
        for img in app.images:
            assert img.blocks
            self.first_block(img).override = "批量改过"
        app.apply_all()
        entries = self.logs(app)
        self.assertEqual(len(entries), 2)
        self.assertEqual(sorted(e["src_file"] for e in entries), ["a.png", "b.png"])
        self.assertTrue(all(e["channel"] == "tui" for e in entries))

    def test_apply_one_records_the_running_version(self):
        """日志要能回答"这是哪一版写的"：真实写盘的记录带 app_version。"""
        from src.python.version import VERSION

        app = self.build_app()
        img = app.cur
        assert img is not None
        self.first_block(img).override = "改过的文字"
        app.apply_one(img)
        self.assertEqual(self.logs(app)[0]["app_version"], VERSION)


if __name__ == "__main__":
    unittest.main()
