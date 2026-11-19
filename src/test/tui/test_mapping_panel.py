"""TUI 全局映射面板（e 键）：新增、修改、删除、导出 JSON。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import json
import os
import unittest

from src.test._support import TuiTestCase


class MappingPanel(TuiTestCase):
    def test_add_entry(self):
        app = self.make_app()
        self.drive(app, ["e", "n", *list("2023"), "\n", *list("2024"), "\n", "q", "q"])
        self.assertEqual(app.mapping.get("2023"), "2024")

    def test_edit_existing_entry(self):
        app = self.make_app()
        app.mapping["2023"] = "2024"
        self.drive(app, ["e", "\n"] + ["\x7f"] * 4 + list("2030") + ["\n", "q", "q"])
        self.assertEqual(app.mapping["2023"], "2030")

    def test_delete_entry(self):
        app = self.make_app()
        app.mapping["2023"] = "2024"
        self.drive(app, ["e", "d", "q", "q"])
        self.assertEqual(app.mapping, {})

    def test_export_writes_json(self):
        app = self.make_app()
        app.mapping["2023"] = "2024"
        target = os.path.join(self.tmp.name, "map.json")
        self.drive(app, ["e", "w", *list(target), "\n", "q", "q"])
        self.assertTrue(os.path.exists(target))
        with open(target, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"2023": "2024"})

    def test_navigation_does_not_overflow(self):
        app = self.make_app()
        app.mapping.update({"a": "1", "b": "2"})
        self.drive(app, ["e"] + ["j"] * 5 + ["k"] * 3 + ["q", "q"])
        self.assertGreaterEqual(app.sel_map, 0)
        self.assertLess(app.sel_map, len(app.mapping))


if __name__ == "__main__":
    unittest.main()
