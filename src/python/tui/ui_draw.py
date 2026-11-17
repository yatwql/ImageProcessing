"""TUI 绘制层：把 `App` 的状态画到窗口上（宽/窄两种布局）。"""

from __future__ import annotations

import contextlib
import curses
import os

from .app import App
from .ui_base import HELP, attr, put


def draw_main(win, app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    img = app.cur

    head = " 文字替换 "
    head += (f"| 已保存 {os.path.basename(app.last_saved)} " if app.last_saved
             else f"| 输出 {os.path.basename(app.out_dir.rstrip('/'))}/ ")
    if w < 60:
        head += f"[{w}x{h}] "
    put(win, 0, 0, head, w, attr("title", curses.A_BOLD))

    body_h = max(1, h - 5)
    narrow = w < 60                     # 手机竖屏 / 小窗口：一次只显示一栏

    if narrow:
        draw_narrow(win, app, w, body_h)
    else:
        draw_wide(win, app, h, w, body_h)

    # 底部：详情 / 消息 / 键位
    blk = app.cur_block()
    if blk is not None:
        new, _inline = app.display_new(blk)
        detail = f"选：{blk.text}"
        if blk.find:
            detail += f"　行内「{blk.find}」"
        detail += f"　→{new}" if new else "　未设置"
    elif app.focus == "files" and img is not None:
        detail = f"{img.name}　{len(app.blocks())} 块　{app.pending_count(img)} 待替换"
    else:
        detail = ""
    put(win, h - 3, 0, detail, w, attr("dim"))

    if app.focus == "files":
        keys = ("↑↓ 选图  1-9/0 跳图  Enter 右栏  e 映射  r 替换  q 退出" if narrow else
                "↑↓ 选图  数字键直接跳图  Enter 进右栏  m 映射  e 映射表  c 样式  "
                "r 替换  R 全部  ? 帮助  q 退出")
    else:
        keys = ("↑↓ 选块  Enter 整行  i 行内  空格 启用  r 替换  Tab 换栏  q 退出" if narrow else
                "↑↓ 选块  Enter 整行换  i 只换几个字  空格 启用  u 清除  r 替换  Esc 返回  q 退出")
    put(win, h - 2, 0, app.message or app.status, w, attr("warn"))
    put(win, h - 1, 0, keys, w, attr("dim", curses.A_REVERSE))
    win.refresh()


def row_label(app: App, kind: str, path: str, visible_index: int) -> str:
    """左栏一行怎么显示：父目录 / 子目录 / 图片（图片带序号与状态）。"""
    if kind == "parent":
        return "  ..  上级目录"
    if kind == "dir":
        return f"  / {os.path.basename(path)}/"
    item = app.image_for(path)
    name = image_label(app, item) if item is not None else f" {os.path.basename(path)}"
    return f"{digit_of(visible_index)}{name}"


def draw_wide(win, app: App, h: int, w: int, body_h: int) -> None:
    left_w = min(32, max(18, w // 3))
    right_w = max(1, w - left_w - 1)

    pos_img = f"{app.image_position() or '—'}/{len(app.images)}"
    put(win, 1, 0, f" ① 图片 {pos_img}", left_w - 1, attr("title"))
    nblk = len(app.blocks())
    pos_blk = f"{app.sel_blk + 1}/{nblk}" if nblk else "0/0"
    hint = ("Enter 进右侧" if app.focus == "files"
            else f"{pos_blk}　Enter 整行换　i 只换几个字")
    put(win, 1, left_w + 1, f" ② 识别到的文字 {hint}", right_w,
        attr("title", curses.A_BOLD if app.focus != "files" else 0))

    app.img_rows = body_h
    start_img, visible = app.image_window(body_h)
    app.img_start = start_img
    shown = 0
    for i, (kind, path) in enumerate(visible):
        real = start_img + i
        label = row_label(app, kind, path, shown)
        if kind == "img":
            shown += 1
        put(win, 2 + i, 0, label, left_w - 1,
            _sel_style(app, real == app.sel_row, "files"))

    start = max(0, app.sel_blk - body_h + 1) if app.sel_blk >= body_h else 0
    blks = app.blocks()
    if app.cur is not None and app.cur.error:
        put(win, 2, left_w + 1, f" {app.cur.error}", right_w, attr("warn"))
    elif app.cur is not None and app.cur.blocks is None:
        put(win, 2, left_w + 1, " 正在识别文字，请稍等…", right_w, attr("dim"))
    for idx, blk in enumerate(blks[start:start + body_h]):
        real = start + idx
        put(win, 2 + idx, left_w + 1, block_label(app, blk), right_w,
            _sel_style(app, real == app.sel_blk, "blocks"))

    for y in range(1, h - 3):
        with contextlib.suppress(curses.error):
            win.addch(y, left_w, curses.ACS_VLINE, attr("dim"))


def draw_narrow(win, app: App, w: int, body_h: int) -> None:
    """窄屏：只画当前焦点那一栏，Tab 切换。"""
    if app.focus == "files":
        put(win, 1, 0,
            f" 图片 {app.image_position() or '—'}/{len(app.images)}　Tab→文字", w,
            attr("title", curses.A_BOLD))
        app.img_rows = body_h
        start_img, visible = app.image_window(body_h)
        app.img_start = start_img
        shown = 0
        for i, (kind, path) in enumerate(visible):
            real = start_img + i
            label = row_label(app, kind, path, shown)
            if kind == "img":
                shown += 1
            put(win, 2 + i, 0, label, w,
                _sel_style(app, real == app.sel_row, "files"))
    else:
        nblk = len(app.blocks())
        pos = f"{app.sel_blk + 1}/{nblk}" if nblk else "0/0"
        put(win, 1, 0, f" 文字 {pos}　Tab→图片", w, attr("title", curses.A_BOLD))
        if app.cur is not None and app.cur.error:
            put(win, 2, 0, f" {app.cur.error}", w, attr("warn"))
        elif app.cur is not None and app.cur.blocks is None:
            put(win, 2, 0, " 正在识别文字，请稍等…", w, attr("dim"))
        start = max(0, app.sel_blk - body_h + 1) if app.sel_blk >= body_h else 0
        for idx, blk in enumerate(app.blocks()[start:start + body_h]):
            put(win, 2 + idx, 0, block_label(app, blk), w,
                _sel_style(app, start + idx == app.sel_blk, "blocks"))


def digit_of(offset: int) -> str:
    """列表前 10 项的快捷键序号：1..9，第 10 项是 0。"""
    if offset < 9:
        return f"{offset + 1} "
    if offset == 9:
        return "0 "
    return "  "


def image_label(app: App, item) -> str:
    mark = "✓" if item.done else ("!" if item.error else "·")
    cnt = app.pending_count(item)
    return f" {mark} {item.name}" + (f" ({cnt})" if cnt else "")


def block_label(app: App, blk) -> str:
    new, inline = app.display_new(blk)
    flag = "●" if (blk.enabled and new) else "○"
    text = f" {flag} {blk.text}"
    if new:
        text += f"「{blk.find}」→{new}" if (inline and blk.find) else f"　→{new}"
    return text


def _sel_style(app: App, selected: bool, panel: str) -> int:
    if not selected:
        return 0
    if app.focus == panel:
        return attr("sel", curses.A_BOLD)
    return curses.A_BOLD


def draw_map(win, app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    put(win, 0, 0, f" 全局映射表（{len(app.mapping)} 条，对全部图片生效） ", w,
        attr("title", curses.A_BOLD))
    items = list(app.mapping.items())
    if not items:
        put(win, 2, 2, "还没有条目。按 n 新增一条「旧文字 → 新文字」", w - 4, attr("dim"))
        put(win, 3, 2, "条目写的是片段时（如 2023），会做行内替换。", w - 4, attr("dim"))
    for i, (k, v) in enumerate(items[:max(1, h - 4)]):
        a = attr("sel", curses.A_BOLD) if i == app.sel_map else 0
        put(win, 1 + i, 0, f" {k}  →  {v}", w, a)
    put(win, h - 2, 0, app.message or app.status, w, attr("warn"))
    put(win, h - 1, 0, " n 新增   Enter 改新文字   d 删除   w 导出 JSON   Esc 返回", w,
        attr("dim", curses.A_REVERSE))
    win.refresh()


def draw_settings(win, app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    put(win, 0, 0, " 样式选项（对下一次 r / R 生效） ", w, attr("title", curses.A_BOLD))
    rows = app.setting_notes()
    for i, (_field, title, value) in enumerate(rows[:max(1, h - 4)]):
        sel = i == app.sel_setting
        a = attr("sel", curses.A_BOLD) if sel else 0
        put(win, 1 + i, 0, f" {title}：{value}", w, a)
    hint = dict(app.SETTING_ROWS_HINT)
    put(win, h - 3, 0, " " + hint.get(rows[app.sel_setting][0], "") if rows else "", w,
        attr("dim"))
    put(win, h - 2, 0, app.message or app.status, w, attr("warn"))
    put(win, h - 1, 0, " ↑↓ 选择   Enter 修改   留空=自动   Esc 返回", w,
        attr("dim", curses.A_REVERSE))
    win.refresh()

def draw_help(win, _app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    for i, line in enumerate(HELP.splitlines()[:h - 2]):
        a = attr("title", curses.A_BOLD) if i == 0 else 0
        put(win, i, 0, " " + line, w, a)
    put(win, h - 1, 0, " 按任意键返回", w, attr("dim", curses.A_REVERSE))
    win.refresh()

def draw_too_small(win, h: int, w: int) -> None:
    """终端太小（手机竖屏常见）时给一句提示，不要崩。"""
    win.erase()
    put(win, max(0, h // 2) - 1, 0, " 太窄了", w, attr("warn"))
    put(win, max(0, h // 2), 0, f" 现在 {w}列 x {h}行", w, attr("dim"))
    put(win, max(0, h // 2) + 1, 0, " 横屏或缩小字号", w, attr("dim"))
    put(win, h - 1, 0, " q 退出", w, attr("dim", curses.A_REVERSE))
    win.refresh()


def draw_frame(win, app: App) -> None:
    """画一帧；任何绘制异常都吞掉，绝不让界面把程序带崩。"""
    try:
        h, w = win.getmaxyx()
        if h < 8 or w < 16:
            draw_too_small(win, h, w)
            return
        if app.panel == "help":
            draw_help(win, app)
        elif app.panel == "map":
            draw_map(win, app)
        elif app.panel == "settings":
            draw_settings(win, app)
        else:
            draw_main(win, app)
    except curses.error:
        with contextlib.suppress(curses.error):
            curses.update_lines_cols()      # 窗口尺寸变了，刷新缓存后下一帧重画
    except Exception as exc:                # 兜底：不退出，提示后继续
        app.message = f"界面绘制出错: {exc}"

