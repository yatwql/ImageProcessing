"""补齐覆盖率薄弱点：把每个模块最后的"难触达分支"逐个打掉。

这里的用例都很"窄"——专门针对某一行：错误分支、空输入、平台/终端异常、
入口薄壳。它们与功能用例互补：功能用例证明"能用"，这里证明"出错也能收敛"。
"""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.python import bootstrap, config, launch
from src.python.cli import log_query
from src.python.cli import main as cli_main
from src.python.core import audit, edit, fonts, image, match, ocr, options, render, style
from src.python.core.errors import CoreError
from src.python.tui import ui, ui_actions, ui_base, ui_draw, ui_input
from src.test._support import FONT_CJK, FakeWin, TuiTestCase, has_cjk_font, patch_curses


class BootstrapGaps(unittest.TestCase):
    def test_pip_install_calls_pip_in_repo_root(self):
        # `str(Path)` 在 Windows 上给反斜杠，期望值也用 Path 算，不能写死 "/x/python"
        expected_py = str(Path("/x/python"))
        with mock.patch.object(bootstrap.subprocess, "run") as run:
            bootstrap.pip_install(Path("/x/python"), "-r", "requirements.txt")
        args, kwargs = run.call_args
        self.assertEqual(args[0][:4], [expected_py, "-m", "pip", "install"])
        self.assertEqual(kwargs["cwd"], str(bootstrap.ROOT))
        self.assertTrue(kwargs["check"])


class EntryShimGaps(unittest.TestCase):
    """`python -m` 薄壳：`if __name__` 块只在被当脚本执行时跑。"""

    def run_shim(self, module: str, patch_target: str) -> None:
        with mock.patch(patch_target, return_value=0):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_module(module, run_name="__main__")
        self.assertEqual(ctx.exception.code, 0)

    def test_cli_main_shim(self):
        self.run_shim("src.python.cli", "src.python.cli.main.main")

    def test_tui_main_shim(self):
        self.run_shim("src.python.tui", "src.python.tui.ui.main")


class LogQueryGaps(unittest.TestCase):
    def test_core_error_from_reader_is_reported(self):
        err = io.StringIO()
        with (
            mock.patch.object(log_query, "read_entries", side_effect=CoreError("读不了")),
            contextlib.redirect_stderr(err),
        ):
            code = log_query.main(["--log-dir", "/tmp/x"])  # platform-safe
        self.assertEqual(code, 2)
        self.assertIn("读不了", err.getvalue())


class CliReportGaps(unittest.TestCase):
    def test_unwritable_report_path_is_reported_not_raised(self):
        err = io.StringIO()
        with (
            mock.patch("builtins.open", side_effect=OSError("no space")),
            contextlib.redirect_stderr(err),
        ):
            cli_main.write_report(
                "/nope/report.json", [], [], [], 0, 0, dry_run=False, out_dir="/tmp"
            )
        self.assertIn("写摘要失败", err.getvalue())


class ConfigGaps(unittest.TestCase):
    def test_plain_keys_are_applied_via_setattr(self):
        opts = options.Options()
        opts.size = None
        opts.tracking = None
        with mock.patch.object(
            config, "option_defaults", return_value={"size": 30, "tracking": 1.5}
        ):
            config.apply_to_options(opts)
        self.assertEqual(opts.size, 30)
        self.assertAlmostEqual(opts.tracking or 0, 1.5, places=3)


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

            with mock.patch("builtins.open", side_effect=guarded):
                with self.assertRaises(CoreError):
                    audit.read_entries(tmp)


class EditGaps(unittest.TestCase):
    def test_debug_log_failure_only_warns(self):
        rgb = np.full((80, 160, 3), 255, np.uint8)
        info = {
            "mask": np.zeros((80, 160), bool),
            "ink_box": (5, 5, 100, 30),
            "text_color": (0, 0, 0),
            "stroke": 2.0,
            "stroke_core": 2.0,
            "slant": 0.0,
        }
        warnings: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            opts = options.Options(debug=tmp, log_dir=tmp, quiet=True, font=FONT_CJK)
            opts.warn = warnings.append
            with (
                mock.patch.object(edit, "analyze", return_value=info),
                mock.patch.object(edit, "record_write", side_effect=CoreError("日志满了")),
            ):
                _out, _alpha, report = edit.replace_image(
                    rgb, None, [edit.Job((5, 5, 100, 25), "原文", "新文")], opts, []
                )
        self.assertEqual(len(report), 1, "记日志失败不该影响替换结果")
        self.assertTrue(any("日志满了" in w for w in warnings))


class FontGaps(unittest.TestCase):
    def test_empty_pool_raises_core_error_with_hint(self):
        with (
            mock.patch.object(fonts, "font_dirs", return_value=["/no/such/dir"]),
            mock.patch.object(fonts, "fc_list_files", return_value=[]),
            mock.patch.object(fonts, "fc_lang_files", return_value=set()),
            mock.patch.object(fonts, "fc_charset_files", return_value=set()),
            mock.patch.object(fonts, "_read_cache", return_value={}),
            mock.patch.object(fonts, "_write_cache"),
        ):
            with self.assertRaises(CoreError):
                fonts.build_font_pool(["年度"], None, 10)


class ImageGaps(unittest.TestCase):
    def test_png_with_alpha_keeps_transparency(self):
        with tempfile.TemporaryDirectory() as tmp:
            rgb = np.full((20, 20, 3), 200, np.uint8)
            alpha = np.full((20, 20), 128, np.uint8)
            dst = os.path.join(tmp, "a.png")
            image.save_image(rgb, alpha, dst)
            _rgb, loaded_alpha = image.load_image(dst)
            self.assertIsNotNone(loaded_alpha)
            assert loaded_alpha is not None
            self.assertLess(int(loaded_alpha.min()), 255, "半透明应被保留")


class MatchGaps(unittest.TestCase):
    def test_unmatched_key_is_reported_to_sink(self):
        seen: list[str] = []
        regions = [{"text": "完全无关的一行", "rect": (0, 0, 100, 30), "score": 1.0}]
        match.plan_jobs(regions, {"2023": "2024"}, warn=True, sink=seen.append)
        self.assertTrue(any("未找到待替换文字" in item for item in seen))


class OcrGaps(unittest.TestCase):
    def test_empty_crop_returns_none(self):
        rgb = np.full((20, 20, 3), 255, np.uint8)
        self.assertIsNone(ocr.ocr_crop(rgb, (5, 5, 0, 0)))


class OptionGaps(unittest.TestCase):
    def test_rgb_component_out_of_range_is_rejected(self):
        with self.assertRaises(CoreError):
            options.parse_color("300,0,0")


class RenderGaps(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 CJK 字体")
    def test_solve_tracking_stops_when_text_has_no_ink(self):
        face = style.FontFace(FONT_CJK, 0) if hasattr(style, "FontFace") else None
        face = face or fonts.FontFace(FONT_CJK, 0)
        with mock.patch.object(render, "ink_size", return_value=(0, 0)):
            tracking = render.solve_tracking("年度", face, 20, 0.0, 200.0)
        self.assertEqual(tracking, 0.0, "没有墨迹时不该继续累加字距")


class StyleGaps(unittest.TestCase):
    @unittest.skipUnless(has_cjk_font(), "需要 CJK 字体")
    def test_wide_tracking_search_wins_when_narrow_fails(self):
        face = fonts.FontFace(FONT_CJK, 0)
        text = "国国"
        arr, box, _pad = render.render_line(text, face, 40, tracking=40.0)
        mask = np.zeros((200, 600), np.uint8)
        top, left = 20, 20
        h, w = arr.shape
        mask[top : top + h, left : left + w] = arr
        ink_box = (left + box[0], top + box[1], left + box[2], top + box[3])
        found = style.fit_font(text, mask > 127, ink_box, [face], 4)
        self.assertIsNotNone(found, "大间距的标题应当能在放宽范围后匹配到")
        assert found is not None
        _score, _face, _size, tracking, _iou = found
        self.assertGreater(abs(tracking), 0.35 * (_size or 1), "应当走到放宽后的那一轮搜索")


class LaunchGaps(unittest.TestCase):
    def test_repo_root_is_added_to_sys_path_on_import(self):
        saved = list(sys.path)
        try:
            sys.path = [p for p in sys.path if p != str(launch.ROOT)]
            import importlib

            importlib.reload(launch)
            self.assertIn(str(launch.ROOT), sys.path)
        finally:
            sys.path = saved


class TuiGaps(TuiTestCase):
    def test_jump_to_last_block_in_blocks_panel(self):
        app = self.make_app(count=1)
        app.focus = "blocks"
        app.ensure_blocks()
        app.sel_blk = 0
        app.jump(first=False)
        self.assertEqual(app.sel_blk, max(0, len(app.blocks()) - 1))

    def test_loop_survives_action_exceptions(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        win.keys.extend(["x", "y", "q"])
        with mock.patch.object(
            ui, "handle", side_effect=[curses_error(), CoreError("坏"), RuntimeError("炸")]
        ):
            with contextlib.suppress(KeyboardInterrupt):
                ui.loop(win, app)
        self.assertIn("操作出错", app.message)

    def test_settings_enter_with_no_rows_returns(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        app.panel = "settings"
        with mock.patch.object(app, "setting_notes", return_value=[]):
            ui_actions.handle_settings(app, win, "\n")
        self.assertEqual(app.panel, "settings")

    def test_map_enter_with_empty_mapping_returns(self):
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        app.mapping = {}
        app.panel = "map"
        ui_actions.handle_map(app, win, "\n")
        self.assertEqual(app.mapping, {})

    def test_attr_falls_back_when_colors_unavailable(self):
        with mock.patch.object(ui_base.curses, "color_pair", side_effect=ui_base.curses.error):
            self.assertEqual(ui_base.attr("title", 7), 7)

    def test_draw_frame_survives_curses_error(self):
        patch_curses()
        app = self.make_app(count=1)
        win = FakeWin([], rows=26, cols=100)
        with mock.patch.object(ui_draw, "draw_main", side_effect=ui_draw.curses.error):
            with mock.patch.object(ui_draw.curses, "update_lines_cols") as update:
                ui_draw.draw_frame(win, app)
        update.assert_called_once()

    def test_escape_sequence_ends_when_a_keycode_arrives(self):
        win = FakeWin(["\x1b", 65])  # ESC 后直接来个功能键码
        self.assertEqual(ui_input.read_key(win), "ESC")


def curses_error() -> BaseException:
    return ui_draw.curses.error("boom")


if __name__ == "__main__":
    unittest.main()
