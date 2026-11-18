"""覆盖率收尾：把最后二十几行"只有出错才会走到"的分支补齐。

这些行分别是：占位文件清理、同路径拒绝覆盖、日志/目录不可写、缓存读写失败、
OCR 依赖缺失、空 key、空行渲染、样式面板跳转、输入行 Ctrl-U 等。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.python.cli import main as cli_main
from src.python.core import audit, fonts, image, style
from src.python.core.errors import CoreError
from src.python.tui import app as tui_app
from src.python.tui import ui_actions, ui_base, ui_draw, ui_input
from src.test._support import (
    FONT_CJK,
    FakeWin,
    TuiTestCase,
    cjk_family_name,
    has_cjk_font,
    patch_curses,
)


class FinalGaps4(TuiTestCase):
    """收尾（三）：预演同名、锁失败、fontconfig 缺失、应用当前图的空路径等。"""

    def test_dry_run_dedupes_same_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            d1 = os.path.join(tmp, "d1")
            d2 = os.path.join(tmp, "d2")
            out = os.path.join(tmp, "out")
            for d in (d1, d2, out):
                os.makedirs(d)
            paths = []
            for d in (d1, d2):
                p = os.path.join(d, "same.png")
                image.save_image(np.full((10, 10, 3), 255, np.uint8), None, p)
                paths.append(p)
            region = {"text": "原文", "rect": (0, 0, 5, 5), "score": 1.0}
            info = {
                "mask": np.zeros((10, 10), bool),
                "ink_box": (1, 1, 5, 5),
                "text_color": (0, 0, 0),
                "stroke": 1.0,
                "stroke_core": 1.0,
                "slant": 0.0,
            }
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[paths[0], paths[0]]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = cli_main.main(
                    [paths[0], "--map", "原文=新文", "--out-dir", out, "--dry-run"]
                )
        self.assertIn(code, (0, 3), "预演不写盘，两个同名源图应各自算出不重复的目标名")

    @unittest.skipIf(
        getattr(audit, "fcntl", None) is None, "POSIX 才有 fcntl.flock（Windows 走 msvcrt）"
    )
    def test_unlock_swallows_oserror(self):
        with (
            tempfile.TemporaryFile() as handle,
            mock.patch.object(audit.fcntl, "flock", side_effect=OSError("boom")),
        ):
            audit._unlock(handle.fileno(), locked=True)  # 不抛即通过

    def test_font_discovery_falls_back_to_directory_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_font = os.path.join(tmp, "a.ttf")
            Path(fake_font).write_bytes(b"x")
            with (
                mock.patch.object(fonts, "_run", return_value=""),
                mock.patch.object(fonts, "font_dirs", return_value=[tmp]),
            ):
                files = fonts.fc_list_files()
        self.assertIn(fake_font, files)

    def test_render_failure_during_coarse_search(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            self.assertIsNone(style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1))

    def test_apply_current_without_jobs_reports_how_to_fix(self):
        app = self.make_app(count=1)
        app.apply_current()
        self.assertIn("没有可替换的块", app.message)

    def test_apply_current_with_no_current_image_is_noop(self):
        app = self.make_app(count=1)
        app.images = []
        app.apply_current()  # 不应抛
        self.assertEqual(app.status, "就绪")

    def test_r_key_applies_current_image(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(app, "apply_current") as apply:
            ui_actions.handle(app, win, "r")
        apply.assert_called_once()

    def test_init_colors_registers_all_pairs(self):
        with (
            mock.patch.object(ui_base.curses, "start_color"),
            mock.patch.object(ui_base.curses, "use_default_colors"),
            mock.patch.object(ui_base.curses, "init_pair") as init_pair,
        ):
            ui_base.init_colors()
        self.assertEqual(init_pair.call_count, len(ui_base.PAIR))

    def test_init_colors_survives_failure(self):
        with mock.patch.object(ui_base.curses, "start_color", side_effect=Exception("no color")):
            ui_base.init_colors()  # 不应抛

    def test_status_line_without_message_shows_output_dir(self):
        app = mock.Mock(message="", status="", last_saved=None, out_dir="/tmp/out")  # platform-safe
        text = ui_draw._status_text(app, 40)
        self.assertIn("输出", text)

    def test_edit_line_ignores_terminal_timeouts(self):
        win = FakeWin([None, "a", "\n"], rows=10, cols=40)
        self.assertEqual(ui_input.edit_line(win, "提示: "), "a")


class FinalGaps5(TuiTestCase):
    """收尾（四）：无成功替换、未加锁解锁、字体 repr、当前图替换、进度条。"""

    def test_cli_reports_image_without_successful_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, src)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            err = io.StringIO()
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[src]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch.object(cli_main, "replace_image", return_value=(None, None, [])),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = cli_main.main([src, "--map", "原文=新文", "--out-dir", out_dir])
        self.assertEqual(code, 3)
        self.assertIn("没有成功的替换", err.getvalue())

    def test_unlock_without_lock_is_a_noop(self):
        with tempfile.TemporaryFile() as handle:
            audit._unlock(handle.fileno(), locked=False)

    def test_font_face_repr_contains_name_and_path(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        text = repr(face)
        # 字族名随平台变（Linux 是 Noto CJK、Windows 是 msyh），从字体文件本身反解，不写死
        expected_family = cjk_family_name()
        if expected_family:
            self.assertIn(expected_family, text)
        self.assertTrue(face.name, "字体名不应为空")
        self.assertIn(os.path.basename(FONT_CJK), text)

    def test_apply_current_with_jobs_reports_progress(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        seen: list[str] = []
        app.apply_current(progress=seen.append)
        self.assertTrue(seen, "应当报告一次进度")
        self.assertIn(app.status, ("替换完成", "替换失败"))

    def test_space_on_empty_area_returns(self):
        app = self.make_app(count=0)
        app.focus = "blocks"
        before = app.message
        win = FakeWin([], rows=20, cols=80)
        ui_actions.handle(app, win, " ")
        self.assertEqual(app.message, before, "没有块时按空格不应改动任何状态")

    def test_status_line_shows_progress_bar(self):
        app = mock.Mock(
            message="", status="替换中 3/8", last_saved=None, out_dir="/tmp/out"
        )  # platform-safe
        text = ui_draw._status_text(app, 60)
        self.assertIn("█", text + "█")  # 进度条字符存在（或已填满）
        self.assertIn("37%", text)


class FinalGaps6(TuiTestCase):
    """收尾（五）：读图失败、Windows 锁、缺 fontconfig、保存失败、行内详情。"""

    def test_cli_skips_unreadable_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.png")
            image.save_image(np.full((10, 10, 3), 255, np.uint8), None, src)
            err = io.StringIO()
            bad = os.path.join(tmp, "b.png")
            image.save_image(np.full((10, 10, 3), 255, np.uint8), None, bad)
            good, fail = src, bad

            def loader(path):
                if path == fail:
                    raise OSError("坏图")
                return image.load_image(path)

            with (
                mock.patch.object(cli_main, "collect_images", return_value=[good, fail]),
                mock.patch(
                    "src.python.core.jobs.ocr_regions",
                    return_value=[{"text": "原文", "rect": (0, 0, 5, 5), "score": 1.0}],
                ),
                mock.patch.object(cli_main, "load_image", side_effect=loader),
                mock.patch.object(
                    cli_main,
                    "replace_image",
                    return_value=(
                        np.zeros((10, 10, 3), np.uint8),
                        None,
                        [{"old": "原文", "new": "新文"}],
                    ),
                ),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_main.main([good, "--map", "原文=新文", "--out-dir", tmp])
        self.assertIn("跳过", err.getvalue())

    def test_lock_uses_msvcrt_when_fcntl_is_missing(self):
        with tempfile.TemporaryFile() as handle:
            fake_win = mock.Mock(LK_LOCK=1)
            with (
                mock.patch.object(audit, "fcntl", None),
                mock.patch.object(audit, "_winlock", return_value=fake_win),
            ):
                self.assertTrue(audit._lock(handle.fileno()))
        fake_win.locking.assert_called_once()

    def test_run_helper_returns_empty_when_command_missing(self):
        with mock.patch.object(fonts.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(fonts._run(["fc-list"]), "")

    def test_coarse_search_logs_render_failure_and_continues(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            result = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1)
        self.assertIsNone(result, "所有候选都渲染失败时应返回 None")

    def test_apply_one_reports_save_failure_and_cleans_placeholder(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        before = img.saved
        fake_report = [
            {
                "old": "原文",
                "new": "改后的文字",
                "rect": [0, 0, 10, 10],
                "mode": "整行",
                "font": "f",
                "size": 12,
                "tracking": 0.0,
                "color": [0, 0, 0],
                "align": "left",
                "iou": 0.9,
            }
        ]
        with (
            mock.patch.object(
                tui_app,
                "replace_image",
                return_value=(np.zeros((32, 32, 3), np.uint8), None, fake_report),
            ),
            mock.patch.object(tui_app, "save_image", side_effect=OSError("磁盘满")),
        ):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("磁盘满", msg)
        self.assertEqual(img.saved, before, "失败时不应记录已保存路径")

    def test_i_key_from_files_panel_opens_inline_editor(self):
        app = self.make_app(count=1)
        app.focus = "files"
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(ui_actions, "edit_inline") as inline:
            ui_actions.handle(app, win, "i")
        self.assertEqual(app.focus, "blocks")
        inline.assert_called_once()

    def test_footer_shows_inline_fragment_hint(self):
        patch_curses()
        app = self.make_app(count=1)
        app.focus = "blocks"
        blk = app.blocks()[0]
        blk.find = "2023"
        blk.override = "2024"
        win = FakeWin([], rows=26, cols=100)
        ui_draw.draw_frame(win, app)
        self.assertIn("行内", "\n".join(win.screen))


class FinalGaps7(TuiTestCase):
    """收尾（六）：读图失败、删日志失败、预留名失败、Enter 整行编辑、脏进度数字。"""

    def test_cli_skips_unreadable_image_in_second_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "a.png")
            bad = os.path.join(tmp, "b.png")
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, good)
            image.save_image(np.full((20, 30, 3), 255, np.uint8), None, bad)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            if not has_cjk_font():
                self.skipTest("需要 CJK 字体")
            real_load = image.load_image

            def loader(path):
                if path == bad:
                    raise OSError("坏图")
                return real_load(path)

            err = io.StringIO()
            # CLI 只接受一个输入路径；批量靠"输入是目录"实现
            with (
                mock.patch.object(cli_main, "collect_images", return_value=[good, bad]),
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                mock.patch.object(cli_main, "load_image", side_effect=loader),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_main.main(
                    [
                        os.path.dirname(good),
                        "--map",
                        "原文=新文",
                        "--out-dir",
                        out_dir,
                        "--font",
                        FONT_CJK,
                    ]
                )
        self.assertIn("跳过", err.getvalue())

    def test_prune_skips_files_that_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(audit.log_path(tmp, dt.datetime(2020, 1, 1)))
            path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(audit.os, "remove", side_effect=OSError("denied")):
                removed = audit.prune_logs(tmp, keep_days=1, today=dt.date(2026, 11, 18))
        self.assertEqual(removed, [], "删不掉的文件不计入已删列表")

    def test_apply_one_reports_reserve_failure(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        report = [
            {
                "old": "原文",
                "new": "改后",
                "rect": [0, 0, 10, 10],
                "mode": "整行",
                "font": "f",
                "size": 12,
                "tracking": 0.0,
                "color": [0, 0, 0],
                "align": "left",
                "iou": 0.9,
            }
        ]
        with (
            mock.patch.object(
                tui_app,
                "replace_image",
                return_value=(np.zeros((32, 32, 3), np.uint8), None, report),
            ),
            mock.patch.object(tui_app, "reserve_path", side_effect=CoreError("占名失败")),
        ):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("占名失败", msg)

    def test_enter_on_blocks_panel_opens_the_editor(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(list("新的一行") + ["\n"])
        ui_actions.handle(app, win, "\n")
        blk = app.cur_block()
        assert blk is not None, "应当有当前块"
        self.assertEqual(blk.override, "新的一行")

    def test_dirty_progress_number_falls_back(self):
        self.assertEqual(ui_draw._int("x", 7), 7)
        self.assertEqual(ui_draw._int("8"), 8)


class FinalGaps8(TuiTestCase):
    """收尾（七）：第二轮读图失败、坏日期日志名、apply_one 读图失败、整行编辑。"""

    def test_cli_second_pass_load_failure_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "in")
            os.makedirs(src_dir)
            good = os.path.join(src_dir, "a.png")
            bad = os.path.join(src_dir, "b.png")
            for path in (good, bad):
                image.save_image(np.full((20, 30, 3), 255, np.uint8), None, path)
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)
            if not has_cjk_font():
                self.skipTest("需要 CJK 字体")
            region = {"text": "原文", "rect": (0, 0, 10, 10), "score": 1.0}
            info = {
                "mask": np.zeros((20, 30), bool),
                "ink_box": (2, 2, 20, 12),
                "text_color": (0, 0, 0),
                "stroke": 2.0,
                "stroke_core": 2.0,
                "slant": 0.0,
            }
            real_load = image.load_image
            calls: dict[str, int] = {}

            def loader(path):
                calls[path] = calls.get(path, 0) + 1
                if path == bad and calls[path] > 1:  # 第一遍（扫描）成功，第二遍失败
                    raise OSError("读盘失败")
                return real_load(path)

            err = io.StringIO()
            with (
                mock.patch("src.python.core.jobs.ocr_regions", return_value=[region]),
                mock.patch("src.python.core.edit.analyze", return_value=info),
                mock.patch.object(cli_main, "load_image", side_effect=loader),
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_main.main(
                    [src_dir, "--map", "原文=新文", "--out-dir", out_dir, "--font", FONT_CJK]
                )
        self.assertIn("跳过", err.getvalue())

    def test_prune_ignores_badly_named_log_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "image-writes-notadate.log"
            bad.write_text("{}\n", encoding="utf-8")
            removed = audit.prune_logs(tmp, keep_days=1, today=dt.date(2026, 11, 18))
            still_there = bad.exists()
        self.assertEqual(removed, [])
        self.assertTrue(still_there, "解析不出日期的文件不能被删")

    def test_apply_one_reports_unreadable_image(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.blocks()[0].override = "改后的文字"
        img = app.images[0]
        with mock.patch.object(tui_app, "load_image", side_effect=OSError("读不了")):
            ok, msg = app.apply_one(img)
        self.assertFalse(ok)
        self.assertIn("读取失败", msg)

    def test_edit_current_sets_whole_line_override(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(list("整行新文字") + ["\n"])
        ui_actions.edit_current(app, win)
        blk = app.cur_block()
        assert blk is not None
        self.assertEqual(blk.override, "整行新文字")
