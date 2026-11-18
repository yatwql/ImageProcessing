"""归档流程（`release.py archive`）的用例。

守的是 `docs/archive/README.md` 里的规则：旧版本台账整块搬进
`docs/archive/v<系列>/`、主台账只留文件头与归档索引、重复跑幂等、
同系列第二次发布追加批次而不是覆盖。
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from src.python.tools import release

HEAD = "# 计划任务\n\n> 版本：v0.1\n\n> 说明块。\n\n"


def write_ledger(docs: Path) -> None:
    """在临时 docs/ 下造三份最小台账。"""
    managements = docs / "managements"
    managements.mkdir(parents=True, exist_ok=True)
    for name, row in (
        ("plan.md", "| PLAN-1 | 任务一 | 验收 | 完成 |\n"),
        ("review-findings.md", "| RF-1 | 类型 | 问题 | 处理 | 已修 |\n"),
        ("changelog.md", "- 首次变更\n"),
    ):
        (managements / name).write_text(HEAD + "## 正文\n\n" + row, encoding="utf-8")


def run_archive(docs: Path, version: str, yes: bool) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = release.cmd_archive(version, yes, docs=docs)
    return code, out.getvalue()


class SeriesName(unittest.TestCase):
    def test_minor_version_becomes_series(self):
        self.assertEqual(release.series_of("0.1"), "0.1.x")
        self.assertEqual(release.series_of("1.10"), "1.10.x")


class SplitDoc(unittest.TestCase):
    def test_body_is_between_first_heading_and_archive_index(self):
        text = HEAD + "## 1. 任务\n\n| PLAN-1 | … |\n\n## 归档\n\n| 系列 |\n"
        head, body, tail = release.split_doc(text)
        self.assertEqual(head, HEAD.rstrip("\n") + "\n")
        self.assertEqual(body, "## 1. 任务\n\n| PLAN-1 | … |")
        self.assertTrue(tail is not None and tail.startswith("## 归档"))

    def test_doc_without_archive_index_has_whole_body(self):
        _head, body, tail = release.split_doc(HEAD + "## 正文\n\n- 一条\n")
        self.assertEqual(body, "## 正文\n\n- 一条")
        self.assertIsNone(tail)

    def test_doc_without_sections_has_empty_body(self):
        _head, body, _tail = release.split_doc(HEAD)
        self.assertEqual(body, "")


class ArchiveCommand(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            write_ledger(docs)
            before = {p.name: p.read_text(encoding="utf-8") for p in docs.rglob("*.md")}
            code, out = run_archive(docs, "0.1", yes=False)
            self.assertEqual(code, 0)
            self.assertIn("[plan]", out)
            self.assertIn("--yes 才会真的搬", out)
            after = {p.name: p.read_text(encoding="utf-8") for p in docs.rglob("*.md")}
            self.assertEqual(before, after)
            self.assertFalse((docs / "archive").exists())

    def test_yes_moves_body_and_keeps_header_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            write_ledger(docs)
            code, _out = run_archive(docs, "0.1", yes=True)
            self.assertEqual(code, 0)
            archive = docs / "archive" / "v0.1.x" / "archived_plan.0.1.x.md"
            self.assertTrue(archive.is_file())
            archived = archive.read_text(encoding="utf-8")
            for key in (
                "# 计划归档 — v0.1.x",
                "> 归档时间：",
                "> 原始文件：",
                "> 涵盖版本：v0.1",
                "> 归档内容：",
                "| PLAN-1 |",
            ):
                self.assertIn(key, archived)
            main = (docs / "managements" / "plan.md").read_text(encoding="utf-8")
            self.assertTrue(main.startswith(HEAD.rstrip("\n")))
            self.assertIn("## 归档", main)
            self.assertIn(
                "[`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md)", main
            )
            self.assertNotIn("| PLAN-1 |", main)  # 正文整块搬走，主台账不留旧内容

    def test_second_run_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            write_ledger(docs)
            run_archive(docs, "0.1", yes=True)
            snapshot = {p: p.read_text(encoding="utf-8") for p in docs.rglob("*.md")}
            code, out = run_archive(docs, "0.1", yes=True)
            self.assertEqual(code, 0)
            self.assertIn("没有待归档正文", out)
            self.assertEqual(
                snapshot, {p: p.read_text(encoding="utf-8") for p in docs.rglob("*.md")}
            )

    def test_second_batch_appends_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            write_ledger(docs)
            run_archive(docs, "0.1", yes=True)
            # 同一 MINOR 内又攒了新内容：主台账补一段后再归档
            main_path = docs / "managements" / "changelog.md"
            main_path.write_text(
                main_path.read_text(encoding="utf-8").replace(
                    "## 归档", "## 补记\n\n- 第二批变更\n\n## 归档"
                ),
                encoding="utf-8",
            )
            code, _out = run_archive(docs, "0.1", yes=True)
            self.assertEqual(code, 0)
            archived = (docs / "archive" / "v0.1.x" / "archived_changelog.0.1.x.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- 首次变更", archived)
            self.assertIn("## 归档批次 v0.1（", archived)
            self.assertIn("- 第二批变更", archived)


class IndexBlock(unittest.TestCase):
    def test_index_lists_series_newest_first_and_has_placeholder_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            empty = release.build_index(archive_root, "archived_plan")
            self.assertIn("暂无归档文件", empty)
            for series in ("v0.2.x", "v0.10.x"):
                target = archive_root / series / f"archived_plan.{series[1:]}.md"
                target.parent.mkdir(parents=True)
                target.write_text(
                    f"> 归档时间：2026-11-0{1 if series == 'v0.2.x' else 2}\n"
                    f"> 涵盖版本：v{series[1:]}\n",
                    encoding="utf-8",
                )
            text = release.build_index(archive_root, "archived_plan")
            self.assertLess(text.index("v0.10.x"), text.index("v0.2.x"))


if __name__ == "__main__":
    unittest.main()
