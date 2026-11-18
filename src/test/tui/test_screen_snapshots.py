"""TUI 屏幕快照：把固定尺寸 × 固定状态下的整屏文本钉住。

为什么需要它：这轮出现过两种"本机绿、真机红"的布局事故——
① 标题变长把 `[宽x高]` 挤出屏幕；② 漏 `refresh()` 导致黑屏。
前者是纯粹的排版结果，只有"整屏文本"能完整表达；后者靠 refresh 计数（另有用例）。

快照存在 `src/test/snapshots/tui.json`（一个文件，便于阅读 diff）。
有意改动界面后运行：

    UPDATE_SNAPSHOTS=1 .venv/bin/python -m pytest src/test/tui/test_screen_snapshots.py

然后把 `tui.json` 的 diff 一起提交——这是"改界面要留证据"的门槛。
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from src.python.tui import ui
from src.python.tui.app import Block
from src.python.version import VERSION
from src.test._support import FakeWin, TuiTestCase, has_cjk_font

SNAPSHOT = Path(__file__).resolve().parents[1] / "snapshots" / "tui.json"
VERSION_TOKEN = f"v{VERSION}"


def normalize(text: str) -> str:
    """版本号不进快照：升版（含 -dev 后缀）不该让 40 屏快照全红。"""
    return text.replace(VERSION_TOKEN, "v<VER>")
UPDATE = os.environ.get("UPDATE_SNAPSHOTS") == "1"

SIZES = [(32, 18), (44, 22), (50, 24), (80, 26), (130, 34)]


class ScreenSnapshots(TuiTestCase):
    def build(self, *, files_panel: bool = True, long_path: bool = False):
        """固定内容：名字、输出目录、消息都不依赖临时路径，快照才稳定。"""
        app = self.make_app(count=3)
        app.out_dir = "data/output"
        app.message = ""
        app.last_saved = None
        for idx, img in enumerate(app.images):
            img.name = f"示例-{idx + 1}.png"
            img.blocks = [
                Block("年度销售报告2023", (10, 20, 200, 24)),
                Block("负责人：张三", (10, 60, 160, 24)),
            ]
        first_blocks = app.images[0].blocks or []
        first_blocks[0].override = "年度财务总结2024"
        app.images[1].done = True
        if long_path:
            app.out_dir = "/very/deep/ci/runner/temporary/directory/for/retype/output"
            app.message = "一个相当长的提示信息，用来把状态行占满" * 2
        app.focus = "files" if files_panel else "blocks"
        return app

    def states(self) -> dict[str, ui.App]:
        """状态名 → 构造好的 App。名字即快照键。"""
        loading = self.build()
        loading.loading = True
        loading.message = "正在识别文字，请稍等…"
        empty = self.make_app(count=0)
        empty.out_dir = "data/output"
        empty.message = "示例目录里还没有图片：放好图片后按 Ctrl-R 重新扫描"

        map_panel = self.build()
        map_panel.mapping = {"2023": "2024", "张三": "李四"}
        map_panel.panel = "map"
        settings_panel = self.build()
        settings_panel.panel = "settings"
        help_panel = self.build()
        help_panel.panel = "help"
        return {
            "main_files": self.build(),
            "main_blocks": self.build(files_panel=False),
            "main_long_path": self.build(long_path=True),
            "main_loading": loading,
            "main_empty": empty,
            "map_panel": map_panel,
            "settings_panel": settings_panel,
            "help_panel": help_panel,
        }

    def render(self, app, cols: int, rows: int) -> str:
        win = FakeWin([], rows=rows, cols=cols)
        ui.draw_frame(win, app)
        return "\n".join(line.rstrip() for line in win.screen)

    def load(self) -> dict[str, str]:
        if not SNAPSHOT.exists():
            return {}
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_screens_match_snapshots(self):
        cases = self.states()
        current: dict[str, str] = {}
        for case_name, app in cases.items():
            for cols, rows in SIZES:
                key = f"{case_name}@{cols}x{rows}"
                current[key] = normalize(self.render(app, cols, rows))

        if UPDATE:
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT.write_text(
                json.dumps(dict(sorted(current.items())), ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
            self.skipTest(f"已更新快照（{len(current)} 屏）")

        expected = self.load()
        self.assertTrue(expected, "缺少快照文件：先跑一次 UPDATE_SNAPSHOTS=1")
        missing = sorted(set(expected) - set(current))
        extra = sorted(set(current) - set(expected))
        self.assertFalse(missing, f"快照里有已不存在的用例：{missing}")
        self.assertFalse(extra, f"新增用例缺快照：{extra}（UPDATE_SNAPSHOTS=1 生成）")

        expected = {key: normalize(text) for key, text in expected.items()}
        for key, want in expected.items():
            with self.subTest(screen=key):
                self.assertEqual(
                    current[key], want, f"{key} 的界面变了（确认是有意改动后更新快照）"
                )


@unittest.skipUnless(has_cjk_font(), "快照里的中文需要真实 CJK 字体")
class SnapshotSanity(ScreenSnapshots):
    """快照本身要能表达"看得见的东西"：标题、表头、底栏都在。"""

    def test_snapshot_contains_key_elements(self):
        text = self.render(self.build(), 100, 30)
        for token in ("retype", "① 图片", "② 识别到的文字", "选："):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
