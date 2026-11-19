"""字体匹配与候选池的退化路径：渲染失败、缓存损坏、字号/字距搜索兜底。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.python.core import fonts, render, style
from src.python.core.errors import CoreError
from src.test._support import (
    FONT_CJK,
    TuiTestCase,
    cjk_family_name,
    has_cjk_font,
)


class StyleInkSizeFailure(unittest.TestCase):
    def test_ink_size_failure_is_logged_and_skipped(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        from src.python.core import fonts

        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        logged: list[str] = []
        with (
            mock.patch.object(style, "ink_size", side_effect=OSError("渲染不出")),
            mock.patch.object(style, "_log", side_effect=logged.append),
        ):
            result = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 1)
        self.assertIsNone(result)
        self.assertTrue(any("渲染失败" in item for item in logged), f"应记录失败：{logged}")


class FontGaps(unittest.TestCase):
    def test_empty_pool_raises_core_error_with_hint(self):
        with (
            mock.patch.object(fonts, "font_dirs", return_value=["/no/such/dir"]),
            mock.patch.object(fonts, "fc_list_files", return_value=[]),
            mock.patch.object(fonts, "fc_lang_files", return_value=set()),
            mock.patch.object(fonts, "fc_charset_files", return_value=set()),
            mock.patch.object(fonts, "_read_cache", return_value={}),
            mock.patch.object(fonts, "_write_cache"),
            self.assertRaises(CoreError),
        ):
            fonts.build_font_pool(["年度"], None, 10)


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


class FontRowParsing(unittest.TestCase):
    def test_bad_rows_return_none(self):
        self.assertIsNone(fonts._faces_from_rows([("a.ttf", "not-an-int", "n")]))
        self.assertIsNone(fonts._faces_from_rows("not-a-list"))


class StyleRenderFailure(unittest.TestCase):
    def test_render_failure_is_logged_and_skipped(self):
        from src.test._support import FONT_CJK, has_cjk_font

        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        mask = np.zeros((80, 200), bool)
        mask[20:40, 20:120] = True
        with mock.patch.object(style, "render_line", side_effect=OSError("渲染失败")):
            found = style.fit_font("年度", mask, (20, 20, 120, 40), [face], 2)
        self.assertIsNone(found)


class FontCacheFailure(unittest.TestCase):
    def test_unreadable_cache_is_ignored(self):
        with mock.patch.object(
            fonts, "cache_file", return_value="/proc/nope/fonts.json"
        ):  # platform-safe
            self.assertEqual(fonts._read_cache(), {})

    def test_unwritable_cache_does_not_raise(self):
        with mock.patch.object(
            fonts, "cache_file", return_value="/proc/nope/fonts.json"
        ):  # platform-safe
            fonts._write_cache({"k": []})


class RefineRenderFailure(unittest.TestCase):
    def test_render_failure_during_refinement_is_skipped(self):
        if not has_cjk_font():
            self.skipTest("需要 CJK 字体")
        face = fonts.FontFace(FONT_CJK, 0)
        text = "国国"
        arr, box, _pad = render.render_line(text, face, 40, tracking=0.0)
        mask = np.zeros((200, 400), np.uint8)
        top, left = 20, 20
        h, w = arr.shape
        mask[top : top + h, left : left + w] = arr
        ink_box = (left + box[0], top + box[1], left + box[2], top + box[3])

        real = style.render_line
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 12:  # 粗筛通过、精修阶段开始报错
                raise OSError("渲染失败")
            return real(*args, **kwargs)

        with mock.patch.object(style, "render_line", side_effect=flaky):
            found = style.fit_font(text, mask > 127, ink_box, [face], 1)
        self.assertTrue(calls["n"] > 12, "应进入精修阶段")
        del found


class FinalGaps(TuiTestCase):
    """最后一批单行分支：返回值异常、父目录不可建、缓存坏 JSON、span 越界等。"""

    def test_bad_cache_json_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fonts.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{坏的")
            with mock.patch.object(fonts, "cache_file", return_value=path):
                self.assertEqual(fonts._read_cache(), {})


class FinalGaps2(TuiTestCase):
    """收尾：写日志失败、缓存版本不符、目录不可读、空白渲染、翻页与 DC 键。"""

    def test_cache_with_other_version_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fonts.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"version": 0, "entries": {}}')
            with mock.patch.object(fonts, "cache_file", return_value=path):
                self.assertEqual(fonts._read_cache(), {})


class FinalGaps3(TuiTestCase):
    """收尾（二）：平台分支、空窗口、右对齐、错误的 cur、ESC 取消等。"""

    def test_font_signature_tolerates_unreadable_file(self):
        with mock.patch.object(fonts.os, "stat", side_effect=OSError("denied")):
            signature = fonts._file_signature(["/no/such/font.ttf"])
        self.assertTrue(signature, "读不到字体时也要给出一个签名，而不是崩")


class FinalGaps4(TuiTestCase):
    """收尾（三）：预演同名、锁失败、fontconfig 缺失、应用当前图的空路径等。"""

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


class FinalGaps5(TuiTestCase):
    """收尾（四）：无成功替换、未加锁解锁、字体 repr、当前图替换、进度条。"""

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
