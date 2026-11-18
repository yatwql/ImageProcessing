"""字体池测试：候选池构建、并发上限、CJK 过滤、落盘缓存与失效。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from src.python.core import fonts
from src.python.core.fonts import FontFace, build_font_pool, ttc_face_count
from src.test._support import FONT_CJK, has_cjk_font


class FontDiscoveryPaths(unittest.TestCase):
    """没有 fontconfig 时（含 Windows）也要能定位到系统字体目录。"""

    def test_posix_falls_back_to_common_font_dirs(self):
        self.assertIn("/usr/share/fonts", fonts.font_dirs())

    def test_windows_uses_system_and_user_font_dirs(self):
        windir = r"C:\Windows"
        local = r"C:\Users\me\AppData\Local"
        with mock.patch.object(fonts.os, "name", "nt"), \
                mock.patch.dict(fonts.os.environ, {"WINDIR": windir, "LOCALAPPDATA": local}):
            dirs = fonts.font_dirs()
            expected = [
                os.path.join(windir, "Fonts"),
                os.path.join(local, "Microsoft", "Windows", "Fonts"),
            ]
        self.assertEqual(dirs, expected)

    def test_windows_cache_lives_under_local_appdata(self):
        local = r"C:\Users\me\AppData\Local"
        with mock.patch.object(fonts.os, "name", "nt"), \
                mock.patch.dict(fonts.os.environ, {"LOCALAPPDATA": local}):
            path = fonts.cache_file()
        self.assertEqual(path, os.path.join(local, "retype", "fonts.json"))


class FontFaceIdentity(unittest.TestCase):
    def test_missing_file_falls_back_to_basename(self):
        face = FontFace("/no/such/font.ttf", 0)
        self.assertEqual(face.name, "font.ttf")

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_ttc_exposes_multiple_faces(self):
        self.assertGreater(ttc_face_count(FONT_CJK), 1)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_font_size_is_used_as_rendered(self):
        face = FontFace(FONT_CJK, 0)
        self.assertEqual(face.font(40).size, 40)
        self.assertEqual(face.font(2).size, 6)          # 下限保护


class FontPoolBuilding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()        # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self._old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = self.tmp.name

    def tearDown(self):
        if self._old_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self._old_cache

    def test_forced_font_bypasses_scan(self):
        pool = build_font_pool(["任意文字"], FONT_CJK, 160)
        self.assertTrue(all(f.path == FONT_CJK for f in pool))

    def test_max_faces_is_respected(self):
        pool = build_font_pool(["测试"], None, 5)
        self.assertLessEqual(len(pool), 5)
        self.assertGreaterEqual(len(pool), 1)

    @unittest.skipUnless(has_cjk_font(), "需要 Noto CJK 字体")
    def test_cjk_text_only_yields_cjk_capable_faces(self):
        pool = build_font_pool(["中文标题"], None, 160)
        self.assertTrue(pool)
        for face in pool[:5]:
            self.assertTrue(os.path.exists(face.path))

    def test_second_build_is_served_from_disk_cache(self):
        build_font_pool(["缓存测试"], None, 8)
        cache_path = fonts.cache_file()
        self.assertTrue(os.path.exists(cache_path))
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["version"], fonts.CACHE_VERSION)
        self.assertTrue(data["entries"])
        first = build_font_pool(["缓存测试"], None, 8)
        second = build_font_pool(["缓存测试"], None, 8)
        self.assertEqual([f.name for f in first], [f.name for f in second])

    def test_cache_file_is_corrupt_tolerant(self):
        path = fonts.cache_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ not json")
        pool = build_font_pool(["坏缓存"], None, 4)
        self.assertTrue(pool)
        self.assertTrue(os.path.exists(path))            # 会重新写回

    def test_italic_detection_by_name(self):
        from src.python.core.style import _is_italic

        self.assertTrue(_is_italic(FontFace("/no/DejaVuSans-Oblique.ttf", 0)))
        self.assertFalse(_is_italic(FontFace("/no/NotoSansCJK-Bold.ttc", 0)))


if __name__ == "__main__":
    unittest.main()
