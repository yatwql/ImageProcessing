"""TUI 渠道的界面层：curses 绘制、按键、输入行。

状态与动作在 app.py；替换逻辑在 src.core。这里只做“画出来 / 收键”。
"""

from __future__ import annotations

import contextlib
import curses
import os
import sys
import unicodedata

from ..core import CoreError, norm_map
from ..core.options import Options
from .app import App, Block

PAIR = {"title": 1, "sel": 2, "dim": 3, "ok": 4, "warn": 5, "err": 6}

USAGE = """\
用法: tui.sh [图片或目录 ...] [选项]

  -o, --out-dir DIR    输出目录（默认 data/output）
  -m, --map-file JSON  启动时载入映射表
  -f, --font 文件      强制字体，跳过自动匹配
      --color COLOR    强制字色，如 #C00000 或 200,0,0
      --align MODE     auto|left|center|right（默认 auto）
      --size N         强制字号
      --tracking N     强制字距（px，可负）
      --fit-width      调字距贴合原文字宽度
      --max-fonts N    候选字体上限（默认 160）
      --quality N      JPEG/WEBP 输出质量 1-100（默认 95）
      --log-dir DIR    写盘日志目录（默认 logs/）
  -h, --help           显示本帮助

不带参数时默认读 data/。界面里按 ? 看按键说明，q 退出。
"""

HELP = """\
PNG 文字替换 —— 操作说明

左栏「图片」                     右栏「识别到的文字」
  ↑↓ / j k   选图片               1..9 / 0   直接跳到第 1..10 张
                                  ↑↓ / j k   选文字块
  Enter      进入右栏             Enter      整行换成新文字
  q          退出                 i          行内替换：只换这行里的某几个字
  Esc        返回（不会退出）
                                 空格       启用 / 禁用这个块
                                 u          清除这个块的设置
                                 m          把「旧→新」加入全局映射

通用
  Tab        左右面板切换         a / n      启用 / 禁用当前图片的全部块
  e          全局映射表（n 新增、Enter 改、d 删除）
  c          样式选项（字体/字号/字色/对齐/贴合宽度/字距/字体上限/JPEG 质量）
  w          把全局映射导出成 JSON，可直接给 ./scripts/cli.sh --map-file 用
  Enter      在左栏里是「进目录」；↑↓ 可选 .. 上级或子目录
  Backspace  回上级目录           o          修改输出目录         r          替换当前图片
  R          批量替换所有图片（会先确认）     l   重新识别当前图片
  ?          本帮助               g / G      跳到首行 / 末行

两个典型用法
  1) 只换一行里的某几个字，其余像素不动
     选图片 → Enter 进右栏 → 选中那行 → i
     → 输入要替换的字（如 2023）→ 回车 → 输入新字（如 2024）→ 回车
     → r 替换（底部显示「已保存 <路径>」）
  2) 整行换成别的内容
     选中那行 → Enter → 输入整行的新文字 → 回车 → r

小贴士
  · 只有「●」的块会被替换；按 空格 可以临时去掉某个块。
  · m 把当前设置加入全局映射，之后对其它图片的同名文字自动生效。
  · 输出默认写到 <输入目录>/replaced/，原图不会被覆盖；按 o 可改目录。
  · 改了某一行再按 r 是重新生成，不会叠加，放心多试。
"""


# --------------------------------------------------------------------------- 宽字符


def dwidth(text: str) -> int:
    total = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def cut(text: str, cols: int) -> str:
    if cols <= 0:
        return ""
    out = []
    used = 0
    for ch in text:
        w = 0 if unicodedata.combining(ch) else (
            2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1)
        if used + w > cols:
            break
        out.append(ch)
        used += w
    return "".join(out)


def pad(text: str, cols: int) -> str:
    text = cut(text, cols)
    return text + " " * max(0, cols - dwidth(text))


# --------------------------------------------------------------------------- 颜色与绘制


def init_colors() -> None:
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(PAIR["title"], curses.COLOR_CYAN, -1)
        curses.init_pair(PAIR["sel"], curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR["dim"], curses.COLOR_BLUE, -1)
        curses.init_pair(PAIR["ok"], curses.COLOR_GREEN, -1)
        curses.init_pair(PAIR["warn"], curses.COLOR_YELLOW, -1)
        curses.init_pair(PAIR["err"], curses.COLOR_RED, -1)
    except Exception:                                   # 无颜色/未初始化时退化成黑白
        return


def attr(name: str, extra: int = 0) -> int:
    try:
        return curses.color_pair(PAIR[name]) | extra
    except curses.error:
        return extra


def put(win, y: int, x: int, text: str, cols: int, a: int = 0) -> None:
    if cols <= 0:
        return
    with contextlib.suppress(curses.error):
        win.addstr(y, x, pad(text, cols), a)


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


def draw_help(win, _app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    for i, line in enumerate(HELP.splitlines()[:h - 2]):
        a = attr("title", curses.A_BOLD) if i == 0 else 0
        put(win, i, 0, " " + line, w, a)
    put(win, h - 1, 0, " 按任意键返回", w, attr("dim", curses.A_REVERSE))
    win.refresh()


# --------------------------------------------------------------------------- 输入行


def edit_line(win, prompt: str, initial: str = "") -> str | None:
    """底部单行编辑器；返回输入内容，Esc 返回 None。"""
    h, w = win.getmaxyx()
    buf = list(initial)
    pos = len(buf)
    touched = not initial          # 预填内容：第一次输入直接替换掉，不用手动删
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
            if key == "\x15":                              # Ctrl-U
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
    app.message = (f"已设置整行 → {val}　按 r 替换当前图，R 替换全部"
                   if val else "已清空（该块不替换）")


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
    new = edit_line(win, f"把「{cut(src, 16)}」换成（回车确认 / Esc 取消）: ",
                    (blk.override or "") if blk.find else "")
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
            if app.enter_row():                 # 选中的是父目录 / 子目录
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
            app.apply_all(progress=lambda msg: _progress(win, app, msg))
        else:
            app.message = "已取消批量替换"
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


KEYMAP = {
    curses.KEY_UP: "KEY_UP", curses.KEY_DOWN: "KEY_DOWN",
    curses.KEY_LEFT: "KEY_LEFT", curses.KEY_RIGHT: "KEY_RIGHT",
    curses.KEY_HOME: "KEY_HOME", curses.KEY_END: "KEY_END",
    curses.KEY_NPAGE: "KEY_NPAGE", curses.KEY_PPAGE: "KEY_PPAGE",
    curses.KEY_ENTER: "KEY_ENTER", curses.KEY_BACKSPACE: "KEY_BACKSPACE",
    "\n": "KEY_ENTER",
}

# 手机/各种终端的方向键转义序列（curses 认不出来的那些）
SEQ_MAP = {
    "[A": "KEY_UP", "OA": "KEY_UP", "[1;2A": "KEY_UP",
    "[B": "KEY_DOWN", "OB": "KEY_DOWN", "[1;2B": "KEY_DOWN",
    "[C": "KEY_RIGHT", "OC": "KEY_RIGHT",
    "[D": "KEY_LEFT", "OD": "KEY_LEFT",
    "[H": "KEY_HOME", "OH": "KEY_HOME", "[1~": "KEY_HOME",
    "[F": "KEY_END", "OF": "KEY_END", "[4~": "KEY_END",
    "[5~": "KEY_PPAGE", "[6~": "KEY_NPAGE",
    "[Z": "BTAB",
}

ESC_WAIT_MS = 45          # 独立 ESC 与之字形转义序列的区分窗口


def read_key(win) -> str:
    """读一个按键并归一成 token。

    有些手机终端/SSH 客户端不把方向键交给 curses，直接吐 `ESC [ A` 这样的字节；
    这里自己收尾把它们翻译成方向键，同时保证"单按 Esc"仍然是返回上一层。
    """
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
        pass                     # 序列结束（或这个窗口里没有更多输入）
    finally:
        with contextlib.suppress(curses.error):
            win.timeout(-1)
    if not seq:
        return "ESC"
    return SEQ_MAP.get(seq, "")


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


def loop(win, app: App) -> None:
    win.keypad(True)
    with contextlib.suppress(curses.error):
        curses.curs_set(0)
    init_colors()
    interrupts = 0
    silent = 0
    while not app.quit:
        if not app.started:
            app.started = True
            draw_frame(win, app)             # 先画出"正在识别"
            app.ensure_blocks()
        draw_frame(win, app)
        try:
            key = read_key(win)
        except KeyboardInterrupt:            # 手机终端偶发 Ctrl-C：一次忽略，连按两次退出
            interrupts += 1
            if interrupts >= 2:
                app.quit = True
            continue
        except curses.error:
            silent += 1
            if silent > 50:                  # 终端已经不响应了，别死循环
                app.message = "终端没有响应，已退出"
                break
            with contextlib.suppress(curses.error):
                curses.update_lines_cols()   # resize / 无输入：刷新后重画
            continue
        interrupts = 0
        silent = 0
        if key == "KEY_RESIZE":
            with contextlib.suppress(curses.error):
                curses.update_lines_cols()
            continue
        if key == "ESC":
            key = "\x1b"
        try:
            handle(app, win, key)
        except curses.error:
            continue
        except (CoreError, SystemExit) as exc:   # 核心层报错只提示，不退出
            app.message = str(exc) or "操作失败"
        except Exception as exc:             # 其它异常也不退出
            app.message = f"操作出错: {exc}"


__all__ = ["App", "Block", "loop", "main", "handle", "edit_line", "draw_main",
           "dwidth", "cut", "pad"]


def parse_args(argv: list[str]) -> tuple[list[str], str | None, str | None, Options]:
    """手工解析，避免 argparse 的错误信息冲掉 curses 界面。"""
    inputs: list[str] = []
    out_dir = None
    map_file = None
    opts = Options()
    takes_value = {
        "-o": "out_dir", "--out-dir": "out_dir",
        "-m": "map_file", "--map-file": "map_file",
        "-f": "font", "--font": "font",
        "--color": "color", "--align": "align", "--size": "size",
        "--tracking": "tracking", "--max-fonts": "max_fonts",
        "--quality": "quality", "--log-dir": "log_dir",
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        if a == "--fit-width":
            opts.fit_width = True
            i += 1
            continue
        if a in takes_value and i + 1 < len(argv):
            key, val = takes_value[a], argv[i + 1]
            try:
                if key == "out_dir":
                    out_dir = val
                elif key == "map_file":
                    map_file = val
                elif key in ("size", "max_fonts", "quality"):
                    setattr(opts, key, int(val))
                    if key == "quality" and not 1 <= int(val) <= 100:
                        print(f"--quality 应在 1-100 之间，收到 {val}", file=sys.stderr)
                        raise SystemExit(2)
                elif key == "tracking":
                    opts.tracking = float(val)
                else:
                    setattr(opts, key, val)
            except ValueError:
                print(f"{a} 需要数字，收到 {val!r}", file=sys.stderr)
                raise SystemExit(2) from None
            i += 2
            continue
        inputs.append(a)
        i += 1
    from ..config import default_input

    return inputs or [default_input()], out_dir, map_file, opts


def main(argv: list[str] | None = None) -> int:
    import os

    inputs, out_dir, map_file, opts = parse_args(sys.argv[1:] if argv is None else argv)
    missing = [p for p in inputs if not os.path.exists(p)]
    if missing:
        print(f"路径不存在: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        app = App(inputs, out_dir=out_dir, map_file=map_file, opts=opts)
    except CoreError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not app.images:
        print(f"{inputs[0]} 里没有找到图片（支持 png/jpg/bmp/webp/tif）", file=sys.stderr)
        return 2
    try:
        curses.wrapper(loop, app)
    except KeyboardInterrupt:
        return 130
    return 0
