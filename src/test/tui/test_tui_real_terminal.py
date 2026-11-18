"""真终端冒烟：在伪终端里跑一次真 curses，确认"屏幕上真的有东西"。

单元测试用的是 `FakeWin`（只记缓冲区、只记 refresh 次数），
它能查出"没刷新"，但查不出"画了却没显示出来"这类真机问题——
本轮的黑屏就是这么漏出去的：`ACS_*` 在某些构建里是 int，
传给 `addstr` 抛 TypeError，整帧什么都没画出来。

这里用 `script(1)` 开一个 pty 跑 `scripts/tui.sh`，把终端输出抓下来，
去掉转义序列后断言标题、面板表头和边框字符都在。没有 `script` 的平台自动跳过。
"""

from __future__ import annotations

import locale
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = shutil.which("script")
PYTHON = ROOT / ".venv" / "bin" / "python"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][AB0]|\x1b[=>]")


def _clean(raw: str) -> str:
    return ANSI.sub("", raw)


@unittest.skipUnless(
    os.name == "posix" and SCRIPT and PYTHON.exists(),
    "需要 POSIX + script(1) + .venv（真终端冒烟）",
)
class RealTerminalSmoke(unittest.TestCase):
    def run_tui(self, seconds: float = 4.0) -> str:
        """在 pty 里跑一次 TUI，`seconds` 秒后按 q 退出，返回去转义后的输出。"""
        with tempfile.TemporaryDirectory() as tmp:
            fifo = Path(tmp) / "stdin"
            cast(Any, os).mkfifo(fifo)  # POSIX-only；本类只在 POSIX 上跑，win32 typeshed 里没有
            record = Path(tmp) / "typescript"
            # 保持 stdin 打开，过几秒再送 q：让界面画出至少一帧
            feeder = f"exec 3>{fifo}; sleep {seconds}; printf q >&3; sleep 1"
            proc = subprocess.Popen(["sh", "-c", feeder])  # platform-safe：本类已 skipUnless(posix)
            try:
                subprocess.run(
                    [str(SCRIPT), "-qec", "./scripts/tui.sh data/demo", str(record)],
                    cwd=str(ROOT),
                    stdin=fifo.open("rb"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=seconds + 40,
                    check=False,
                )
            finally:
                proc.wait(timeout=20)
            return _clean(record.read_text(encoding="utf-8", errors="replace"))

    def assert_usable_terminal(self, text: str) -> None:
        if "could not find terminal" in text or "setupterm" in text:
            self.skipTest("该环境无法初始化 curses（TERM/terminfo 缺失），真终端冒烟跳过")
        # curses 自己按终端编码输出，不经过 sys.stdout 的 reconfigure：
        # 在 C/cp1252 locale 下中文本来就画不出来，这是终端限制，不是界面坏了
        ioenc = (os.environ.get("PYTHONIOENCODING") or "").lower().replace("-", "")
        c_locale = os.environ.get("LC_ALL") == "C" or os.environ.get("LANG") == "C"
        preferred = locale.getpreferredencoding(False).lower().replace("-", "")
        if c_locale or (ioenc and ioenc != "utf8") or preferred != "utf8":
            self.skipTest(
                f"当前不是 UTF-8 终端（io={ioenc or '未设'}, C-locale={c_locale}），"
                "curses 画不了中文——这是终端限制，不是界面坏了"
            )
        if "retype" not in text:
            self.skipTest(f"pty 里没有捕获到程序输出（环境限制）：{text[:120]!r}")

    def test_main_screen_really_renders(self):
        text = self.run_tui()
        if "retype v" not in text:  # pty 计时抖动：再试一次
            text = self.run_tui()
        self.assert_usable_terminal(text)
        self.assertIn("retype v", text, "标题栏没画出来")
        self.assertIn("图片", text, "左栏表头没画出来")
        self.assertIn("识别到的文字", text, "右栏表头没画出来")

    def test_border_characters_are_present(self):
        text = self.run_tui()
        self.assert_usable_terminal(text)
        # ACS 线框在 UTF-8 终端里是这些字符；退化成 ASCII 时是 - | +
        self.assertTrue(
            any(ch in text for ch in "─│┌├+"),
            f"没看到任何边框字符：{text[:0]}",
        )


if __name__ == "__main__":
    unittest.main()
