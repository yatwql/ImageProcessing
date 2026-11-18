"""TUI 动作层：按键分发与编辑动作（只改 `App` 状态，不画界面）。"""

from __future__ import annotations

import contextlib
import curses

from ..core import norm_map
from .app import App
from .ui_base import cut
from .ui_draw import draw_main
from .ui_input import edit_line

CANCEL_KEYS = (27,)  # 只用 Esc：q 在别的面板里是"返回"，混用会误停


def handle_settings(app: App, win, key) -> None:
    rows = app.setting_notes()
    if key in ("\x1b", "q"):
        app.panel = "main"
    elif key in ("j", "KEY_DOWN"):
        app.sel_setting = min(max(0, len(rows) - 1), app.sel_setting + 1)
    elif key in ("k", "KEY_UP"):
        app.sel_setting = max(0, app.sel_setting - 1)
    elif key in ("\n", "\r", "KEY_ENTER"):
        if not rows:
            return
        field, title, value = rows[app.sel_setting]
        cur = "" if value == "自动" else value
        new = edit_line(win, f"{title}（留空=自动）: ", cur)
        if new is None:
            return
        app.message = app.set_setting(field, new)


# --------------------------------------------------------------------------- 编辑动作


def edit_current(app: App, win) -> None:
    """整行替换：这一整行换成新文字。"""
    app.ensure_blocks()
    blk = app.cur_block()
    if blk is None:
        app.message = "这张图还没有文字块，按 l 重新识别"
        return
    cur = (blk.override or "") if blk.find is None else ""
    val = edit_line(win, "整行换成（回车确认 / Esc 取消）: ", cur or blk.text)
    if val is None:
        return
    if val.strip() and not cur and norm_map(val)[0] == norm_map(blk.text)[0]:
        app.message = "内容和原来一样，没有改动"
        return
    blk.override = val or None
    blk.find = None
    blk.enabled = bool(val)
    app.message = (
        f"已设置整行 → {val}　按 r 替换当前图，R 替换全部" if val else "已清空（该块不替换）"
    )


def edit_inline(app: App, win) -> None:
    """行内替换：只换这一行里的某几个字，同行其余文字不动。"""
    app.ensure_blocks()
    blk = app.cur_block()
    if blk is None:
        app.message = "这张图还没有文字块，按 l 重新识别"
        return
    src = edit_line(win, f"这行「{cut(blk.text, 20)}」里要替换哪几个字: ", blk.find or "")
    if src is None:
        return
    if not src.strip():
        blk.find = None
        blk.override = None
        app.message = "已取消行内替换（该行不改）"
        return
    if norm_map(src)[0] not in norm_map(blk.text)[0]:
        app.message = f"这行里找不到「{src}」，按 i 重来或改用 Enter 整行换"
        return
    new = edit_line(
        win,
        f"把「{cut(src, 16)}」换成（回车确认 / Esc 取消）: ",
        (blk.override or "") if blk.find else "",
    )
    if new is None or not new:
        return
    blk.find = src
    blk.override = new
    blk.enabled = True
    app.message = f"已设置行内「{src}」→ {new}　按 r 替换当前图，R 替换全部"


# --------------------------------------------------------------------------- 按键


def handle(app: App, win, key) -> None:
    if app.panel == "help":
        app.panel = "main"
        return
    if app.panel == "map":
        handle_map(app, win, key)
        return
    if app.panel == "settings":
        handle_settings(app, win, key)
        return

    if key in ("q", "Q"):
        app.quit = True
    elif key == "\x1b":
        # Esc 只做"返回"，退出统一用 q，避免手机上误触或终端吐 ESC 直接把程序关掉
        if app.focus == "blocks":
            app.focus = "files"
        elif app.panel != "main":
            app.panel = "main"
        else:
            app.message = "按 q 退出（Esc 只返回上一层）"
    elif key == "\t":
        app.focus = "blocks" if app.focus == "files" else "files"
        if app.focus == "blocks":
            app.ensure_blocks()
    elif key in ("j", "KEY_DOWN", ".", ">"):
        app.move(1)
    elif key in ("k", "KEY_UP", ",", "<"):
        app.move(-1)
    elif key in ("KEY_NPAGE", "\x06"):
        app.move(10)
    elif key in ("KEY_PPAGE", "\x02"):
        app.move(-10)
    elif key.isdigit() and len(key) == 1:
        digit = 10 if key == "0" else int(key)
        if app.select_by_digit(digit):
            app.message = f"已选中第 {app.image_position()} 张图片"
    elif key in ("t", "BTAB"):
        app.focus = "blocks" if app.focus == "files" else "files"
        if app.focus == "blocks":
            app.ensure_blocks()
    elif key in ("g", "KEY_HOME"):
        app.jump(first=True)
    elif key in ("G", "KEY_END"):
        app.jump(first=False)
    elif key in ("\x7f", "\b", "KEY_BACKSPACE"):
        if app.focus == "files":
            app.go_parent()
    elif key in ("\n", "\r", "KEY_ENTER"):
        if app.focus == "files":
            if app.enter_row():  # 选中的是父目录 / 子目录
                return
            app.focus = "blocks"
            app.ensure_blocks()
            if not app.blocks():
                app.message = "这张图没识别出文字，按 l 重试"
        else:
            edit_current(app, win)
    elif key == "i":
        if app.focus == "files":
            app.focus = "blocks"
            app.ensure_blocks()
        edit_inline(app, win)
    elif key == " ":
        blk = app.cur_block()
        if blk is None:
            return
        if app.display_new(blk)[0] is None:
            app.message = "这块还没有新文字，先按 Enter / i 设置"
            return
        blk.enabled = not blk.enabled
        app.message = f"该块已{'启用' if blk.enabled else '禁用'}"
    elif key == "a":
        app.set_all(True)
    elif key == "n":
        app.set_all(False)
    elif key == "u":
        app.clear_override()
    elif key == "m":
        app.add_to_mapping()
    elif key == "e":
        app.panel = "map"
        app.sel_map = 0
    elif key == "c":
        app.panel = "settings"
        app.sel_setting = 0
    elif key == "w":
        val = edit_line(win, "导出映射到（回车=map.json）: ")
        if val is not None:
            app.message = app.save_map(val.strip() or app.map_path or "map.json")
    elif key == "o":
        val = edit_line(win, "输出目录: ", app.out_dir)
        if val:
            app.out_dir = val
            app.message = f"输出目录 → {val}"
    elif key == "r":
        app.apply_current(progress=lambda msg: _progress(win, app, msg))
    elif key == "R":
        todo = app.runnable()
        if not todo:
            app.message = "没有任何图片有可执行的替换"
            return
        ok = edit_line(win, f"确认替换 {len(todo)} 张图片？输入 y 回车确认: ")
        if (ok or "").strip().lower() in ("y", "yes"):
            app.apply_all(
                progress=lambda msg: _progress(win, app, msg),
                should_stop=lambda: _poll_cancel(win, app),
            )
        else:
            app.message = "已取消批量替换"
    elif key in ("\x12", "KEY_F(5)"):        # Ctrl-R / F5：把新放进来的图片扫进来
        app.rescan()
    elif key == "l":
        img = app.cur
        if img:
            img.blocks = None
            img.error = None
            img.memo.clear()
            app.ensure_blocks()
    elif key == "?":
        app.panel = "help"


def _progress(win, app: App, msg: str) -> None:
    app.message = msg
    draw_main(win, app)


def _poll_cancel(win, app: App) -> bool:
    """批量途中非阻塞看一眼键盘：按了 Esc / q 就把中断标志立起来。"""
    with contextlib.suppress(curses.error, OSError):
        win.nodelay(True)
        try:
            ch = win.getch()
        finally:
            win.nodelay(False)
        if ch in CANCEL_KEYS:
            app.cancel = True
    return app.cancel


def handle_map(app: App, win, key) -> None:
    items = list(app.mapping.items())
    if key in ("\x1b", "q"):
        app.panel = "main"
    elif key == "n":
        k = edit_line(win, "原文字（可以只是片段）: ")
        if not k:
            return
        v = edit_line(win, f"把「{cut(k, 16)}」换成: ")
        if v is None:
            return
        app.mapping[k] = v
        app.message = f"已添加 {k} → {v}"
    elif key in ("\n", "\r", "KEY_ENTER"):
        if not items:
            return
        k, v = items[app.sel_map]
        nv = edit_line(win, f"「{cut(k, 20)}」换成: ", v)
        if nv is not None:
            app.mapping[k] = nv
            app.message = f"{k} → {nv}"
    elif key == "d":
        if items:
            k, _ = items[app.sel_map]
            del app.mapping[k]
            app.sel_map = max(0, app.sel_map - 1)
            app.message = f"已删除 {k}"
    elif key == "w":
        val = edit_line(win, "导出映射到（回车=map.json）: ")
        if val is not None:
            app.message = app.save_map(val.strip() or app.map_path or "map.json")
    elif key in ("j", "KEY_DOWN"):
        app.move(1)
    elif key in ("k", "KEY_UP"):
        app.move(-1)
