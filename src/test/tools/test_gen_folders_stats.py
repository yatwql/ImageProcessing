"""`make_folders` 的统计表重算：数字由脚本算，说明列与表结构一概不动。

为什么守这个：之前的数字是手改的，`tools/` 从 10 个涨到 16 个、`data/demo/`
从 0 张涨到 4 张都没人发现——文档和实际对不上，守护又查不出来。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.python.tools import make_folders


def make_tree(root: Path) -> list[str]:
    """造一小棵仓库树：主程序 3 行、测试 5 行（2 个 test 函数）、示例图 1 张。"""
    (root / "src/python").mkdir(parents=True)
    (root / "src/python/a.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    (root / "src/test").mkdir(parents=True)
    (root / "src/test/test_x.py").write_text(
        "def test_one():\n    pass\n\ndef test_two():\n    pass\n", encoding="utf-8"
    )
    (root / "data/demo").mkdir(parents=True)
    (root / "data/demo/示例-通知1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return [
        "src/python/a.py",
        "src/test/test_x.py",
        "data/demo/示例-通知1.png",
    ]


SAMPLE_DOC = """# 目录结构与项目统计

## 项目统计

| 类别 | 语言 | 文件数 | 代码行数 | 说明 |
| --- | --- | ---: | ---: | --- |
| 主程序代码 | Python | 9 | 9 | 说明一（不许改） |
| 测试代码 | Python | 9 | 9 | 说明二（不许改） |
| 测试用例 | — | — | 9 | `def test_` 口径 |
| 示例图 | PNG | 0 | — | 二进制不计行数 |
| **合计（不含示例图）** | — | **9** | **9** | 旧尾巴 |

## 目录树

```text
ImageProcessing/
```
"""


class StatsCells(unittest.TestCase):
    def test_counts_files_lines_tests_and_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = make_tree(root)
            cells = make_folders.stats_cells(files, root)
        self.assertEqual(cells["主程序代码"], ("1", "3"))
        self.assertEqual(cells["测试代码"], ("1", "5"))
        self.assertEqual(cells["测试用例"], ("—", "2"))
        self.assertEqual(cells["示例图"], ("1", "—"))

    def test_total_excludes_demo_images_and_reports_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = make_tree(root)
            cells = make_folders.stats_cells(files, root)
        files_cell, lines_cell = cells[make_folders.STAT_TOTAL_LABEL]
        self.assertEqual(files_cell, "**2**")  # 不含示例图
        self.assertEqual(lines_cell.split(" | ")[0], "**8**")
        self.assertIn("主程序 : 测试 ≈ 1 : 1.67", lines_cell)
        self.assertIn("仓库共 3 个跟踪文件（含示例图 1 个）", lines_cell)


class RefreshStats(unittest.TestCase):
    def test_numbers_rewritten_and_prose_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = make_tree(root)
            text = make_folders.refresh_stats(SAMPLE_DOC, files, root)
        self.assertIn("| 主程序代码 | Python | 1 | 3 | 说明一（不许改） |", text)
        self.assertIn("| 测试用例 | — | — | 2 | `def test_` 口径 |", text)
        self.assertIn("| 示例图 | PNG | 1 | — | 二进制不计行数 |", text)
        self.assertIn("仓库共 3 个跟踪文件（含示例图 1 个）", text)
        self.assertNotIn("旧尾巴", text)

    def test_tree_section_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = make_tree(root)
            text = make_folders.refresh_stats(SAMPLE_DOC, files, root)
        self.assertIn("## 目录树\n\n```text\nImageProcessing/\n```", text)


if __name__ == "__main__":
    unittest.main()
