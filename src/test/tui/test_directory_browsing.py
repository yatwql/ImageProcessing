"""TUI 目录浏览：左栏同时列出「上级目录 / 子目录 / 图片」，可进入、可回上级。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

from src.python import config
from src.python.tui.app import App
from src.test._support import TuiTestCase, patch_curses


def make_tree(root: str) -> None:
    for name in ("a.png", "b.png"):
        Image.fromarray(np.full((8, 8, 3), 200, np.uint8)).save(os.path.join(root, name))
    os.makedirs(os.path.join(root, "sub"))
    Image.fromarray(np.full((8, 8, 3), 100, np.uint8)).save(os.path.join(root, "sub", "c.png"))
    os.makedirs(os.path.join(root, ".hidden"))
    with open(os.path.join(root, "notes.txt"), "w", encoding="utf-8") as f:
        f.write("not an image")


class DirectoryRows(TuiTestCase):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp.name, "data")
        os.makedirs(self.root)
        make_tree(self.root)
        self.app = App([self.root])

    def kinds(self) -> list[str]:
        return [kind for kind, _path in self.app.rows]

    def row_of(self, kind: str, name: str = "") -> int:
        for i, (k, path) in enumerate(self.app.rows):
            if k == kind and (not name or os.path.basename(path) == name):
                return i
        raise AssertionError(f"没有 {kind} {name} 这一行：{self.app.rows}")

    def test_rows_show_parent_dirs_and_images_only(self):
        self.assertEqual(self.kinds(), ["parent", "dir", "img", "img"])
        names = [os.path.basename(p) for _k, p in self.app.rows]
        self.assertIn("sub", names)
        self.assertNotIn(".hidden", names)
        self.assertNotIn("notes.txt", names)

    def test_initial_selection_is_the_first_image(self):
        self.assertEqual(self.app.row_kind(), "img")
        self.assertEqual(self.app.image_position(), 1)
        cur = self.app.cur
        assert cur is not None
        self.assertEqual(cur.name, "a.png")

    def test_enter_on_directory_changes_image_list(self):
        self.app.sel_row = self.row_of("dir", "sub")
        self.assertTrue(self.app.enter_row())
        self.assertEqual(self.app.dir, os.path.abspath(os.path.join(self.root, "sub")))
        self.assertEqual([img.name for img in self.app.images], ["c.png"])
        self.assertEqual(self.app.image_position(), 1)

    def test_go_parent_returns_to_root(self):
        self.app.open_dir(os.path.join(self.root, "sub"))
        self.assertTrue(self.app.go_parent())
        self.assertEqual(self.app.dir, os.path.abspath(self.root))
        self.assertEqual([img.name for img in self.app.images], ["a.png", "b.png"])

    def test_enter_on_image_is_handled_by_main_panel(self):
        self.app.sel_row = self.row_of("img", "b.png")
        self.assertFalse(self.app.enter_row())
        cur = self.app.cur
        assert cur is not None
        self.assertEqual(cur.name, "b.png")

    def test_rows_selection_is_clamped(self):
        self.app.move(-99)
        self.assertEqual(self.app.sel_row, 0)
        self.app.move(99)
        self.assertEqual(self.app.sel_row, len(self.app.rows) - 1)

    def test_session_started_from_file_cannot_go_up(self):
        app = App([os.path.join(self.root, "a.png")])
        self.assertEqual(app.rows, [("img", os.path.abspath(os.path.join(self.root, "a.png")))])
        self.assertFalse(app.go_parent())
        self.assertIn("无法回上级", app.message)


class BrowseKeys(TuiTestCase):
    def test_backspace_walks_up_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp)
            sub = os.path.join(tmp, "sub")
            app = App([sub])
            self.drive(app, ["\x7f", "q"])
            self.assertEqual(app.dir, os.path.abspath(tmp))

    def test_enter_on_parent_row_goes_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp)
            app = App([os.path.join(tmp, "sub")])
            app.sel_row = 0  # 第一行是「.. 上级目录」
            self.drive(app, ["\n", "q"])
            self.assertEqual(app.dir, os.path.abspath(tmp))

    def test_directory_rows_are_drawn_in_left_panel(self):
        patch_curses()
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp)
            app = App([tmp])
            win = self.drive(app, [None, "q"])
            screen = "\n".join(win.screen)
            self.assertIn("上级目录", screen)
            self.assertIn("sub", screen)


class DefaultInput(unittest.TestCase):
    def test_environment_override_wins(self):
        with mock.patch.dict(os.environ, {"IMG_P_DATA_DIR": "/mnt/pics"}):
            self.assertEqual(config.default_input(), "/mnt/pics")

    def test_falls_back_to_data_dir_when_slash_data_missing(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMG_P_DATA_DIR", None)
            if os.path.isdir("/data"):
                self.assertEqual(config.default_input(), "/data")
            else:
                self.assertEqual(config.default_input(), config.DATA_DIR)


if __name__ == "__main__":
    unittest.main()
