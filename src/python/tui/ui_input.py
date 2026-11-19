"""TUI 输入层：按键序列解析与单行输入。"""

from __future__ import annotations

import contextlib
import curses

from .ui_base import attr, cut, dwidth, put

# --------------------------------------------------------------------------- 输入行


def edit_line(win, prompt: str, initial: str = "") -> str | None:
    """底部单行编辑器；返回输入内容，Esc 返回 None。"""
    h, w = win.getmaxyx()
    buf = list(initial)
    pos = len(buf)
    touched = not initial  # 预填内容：第一次输入直接替换掉，不用手动删
    with contextlib.suppress(curses.error):
        curses.curs_set(1)
    try:
        while True:
            head = cut(prompt, max(4, w // 2))
            shown = "".join(buf)
            while dwidth(head) + dwidth(shown) > max(4, w - 2) and shown:
                shown = shown[1:]
            put(win, h - 1, 0, head + shown, w - 1, attr("warn") | curses.A_REVERSE)
            cx = min(w - 2, dwidth(head) + dwidth("".join(buf[:pos])))
            with contextlib.suppress(curses.error):
                win.move(h - 1, cx)
            win.refresh()
            try:
                key = win.get_wch()
            except curses.error:
                continue
            if key in ("\n", "\r", curses.KEY_ENTER):
                return "".join(buf)
            if key == "\x1b":
                return None
            if key in ("\x7f", "\b", curses.KEY_BACKSPACE):
                touched = True
                if pos:
                    del buf[pos - 1]
                    pos -= 1
                continue
            if key == curses.KEY_DC:
                touched = True
                if pos < len(buf):
                    del buf[pos]
                continue
            if key == curses.KEY_LEFT:
                pos = max(0, pos - 1)
                continue
            if key == curses.KEY_RIGHT:
                pos = min(len(buf), pos + 1)
                continue
            if key in (curses.KEY_HOME, "\x01"):
                pos = 0
                continue
            if key in (curses.KEY_END, "\x05"):
                pos = len(buf)
                continue
            if key == "\x15":  # Ctrl-U
                buf, pos, touched = [], 0, True
                continue
            if isinstance(key, str) and key.isprintable():
                if not touched:
                    buf, pos, touched = [], 0, True
                buf.insert(pos, key)
                pos += 1
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
