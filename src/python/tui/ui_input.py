"""TUI 输入层：按键序列解析与单行输入。"""

from __future__ import annotations

import contextlib
import curses

from .ui_base import attr, cut, dwidth, put

# --------------------------------------------------------------------------- 输入行


class _Editor:
    """单行编辑器的缓冲区状态：只存数据、只做最小动作（curses 在 `edit_line` 里）。"""

    __slots__ = ("buf", "pos", "touched")

    def __init__(self, initial: str):
        self.buf = list(initial)
        self.pos = len(self.buf)
        self.touched = not initial  # 预填内容：第一次输入直接替换，不用手动删

    def text(self) -> str:
        return "".join(self.buf)

    def insert(self, ch: str) -> None:
        if not self.touched:
            self.buf, self.pos, self.touched = [], 0, True
        self.buf.insert(self.pos, ch)
        self.pos += 1

    def backspace(self) -> None:
        self.touched = True
        if self.pos:
            del self.buf[self.pos - 1]
            self.pos -= 1

    def delete(self) -> None:
        self.touched = True
        if self.pos < len(self.buf):
            del self.buf[self.pos]

    def left(self) -> None:
        self.pos = max(0, self.pos - 1)

    def right(self) -> None:
        self.pos = min(len(self.buf), self.pos + 1)

    def home(self) -> None:
        self.pos = 0

    def end(self) -> None:
        self.pos = len(self.buf)

    def clear(self) -> None:
        self.buf, self.pos, self.touched = [], 0, True


# 只改变光标/内容的键 → 编辑器动作（新增一个键＝加一行，不再往 if 链里塞分支）
EDITOR_KEYS: dict[object, str] = {
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
    curses.KEY_HOME: "home",
    "\x01": "home",
    curses.KEY_END: "end",
    "\x05": "end",
    curses.KEY_BACKSPACE: "backspace",
    "\x7f": "backspace",
    "\b": "backspace",
    curses.KEY_DC: "delete",
    "\x15": "clear",
}
ENTER_KEYS = ("\n", "\r", curses.KEY_ENTER)


def edit_line(win, prompt: str, initial: str = "") -> str | None:
    """底部单行编辑器；返回输入内容，Esc 返回 None。"""
    h, w = win.getmaxyx()
    editor = _Editor(initial)
    with contextlib.suppress(curses.error):
        curses.curs_set(1)
    try:
        while True:
            head = cut(prompt, max(4, w // 2))
            shown = editor.text()
            while dwidth(head) + dwidth(shown) > max(4, w - 2) and shown:
                shown = shown[1:]
            put(win, h - 1, 0, head + shown, w - 1, attr("warn") | curses.A_REVERSE)
            cx = min(w - 2, dwidth(head) + dwidth("".join(editor.buf[: editor.pos])))
            with contextlib.suppress(curses.error):
                win.move(h - 1, cx)
            win.refresh()
            try:
                key = win.get_wch()
            except curses.error:
                continue
            if key in ENTER_KEYS:
                return editor.text()
            if key == "\x1b":
                return None
            action = EDITOR_KEYS.get(key)
            if action is not None:
                getattr(editor, action)()
                continue
            if isinstance(key, str) and key.isprintable():
                editor.insert(key)
    finally:
        with contextlib.suppress(curses.error):
            curses.curs_set(0)


KEYMAP = {
    curses.KEY_UP: "KEY_UP",
    curses.KEY_DOWN: "KEY_DOWN",
    curses.KEY_LEFT: "KEY_LEFT",
    curses.KEY_RIGHT: "KEY_RIGHT",
    curses.KEY_HOME: "KEY_HOME",
    curses.KEY_END: "KEY_END",
    curses.KEY_NPAGE: "KEY_NPAGE",
    curses.KEY_PPAGE: "KEY_PPAGE",
    curses.KEY_ENTER: "KEY_ENTER",
    curses.KEY_BACKSPACE: "KEY_BACKSPACE",
    "\n": "KEY_ENTER",
}

# 手机/各种终端的方向键转义序列（curses 认不出来的那些）
SEQ_MAP = {
    "[A": "KEY_UP",
    "OA": "KEY_UP",
    "[1;2A": "KEY_UP",
    "[B": "KEY_DOWN",
    "OB": "KEY_DOWN",
    "[1;2B": "KEY_DOWN",
    "[C": "KEY_RIGHT",
    "OC": "KEY_RIGHT",
    "[D": "KEY_LEFT",
    "OD": "KEY_LEFT",
    "[H": "KEY_HOME",
    "OH": "KEY_HOME",
    "[1~": "KEY_HOME",
    "[F": "KEY_END",
    "OF": "KEY_END",
    "[4~": "KEY_END",
    "[5~": "KEY_PPAGE",
    "[6~": "KEY_NPAGE",
    "[Z": "BTAB",
}

ESC_WAIT_MS = 45  # 独立 ESC 与之字形转义序列的区分窗口


def read_key(win, timeout_ms: int = -1) -> str:
    """读一个按键并归一成 token；`timeout_ms >= 0` 时到点返回空串（不阻塞）。

    主循环用 100~200ms 的轮询而不是死等：Windows 上首次 OCR 加载很慢，
    死等期间界面收不到任何按键（用户看到的就是"按 q 没反应"）。

    有些手机终端/SSH 客户端不把方向键交给 curses，直接吐 `ESC [ A` 这样的字节；
    这里自己收尾把它们翻译成方向键，同时保证"单按 Esc"仍然是返回上一层。
    """
    if timeout_ms >= 0:
        with contextlib.suppress(curses.error):
            win.timeout(timeout_ms)
    try:
        key = _read_one(win)
    except curses.error:
        return ""  # 到点没有输入
    finally:
        if timeout_ms >= 0:
            with contextlib.suppress(curses.error):
                win.timeout(-1)
    return key


def _read_one(win) -> str:
    key = win.get_wch()
    if isinstance(key, int):
        return KEYMAP.get(key, "")
    if key != "\x1b":
        return key
    seq = ""
    with contextlib.suppress(curses.error):
        win.timeout(ESC_WAIT_MS)
    try:
        while len(seq) < 6:
            nxt = win.get_wch()
            if isinstance(nxt, int):
                break
            seq += nxt
    except (curses.error, KeyboardInterrupt):
        pass  # 序列结束（或这个窗口里没有更多输入）
    finally:
        with contextlib.suppress(curses.error):
            win.timeout(-1)
    if not seq:
        return "ESC"
    return SEQ_MAP.get(seq, "")
