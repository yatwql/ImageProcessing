"""TUI 绘制层：把 `App` 的状态画到窗口上（宽屏双栏 / 窄屏单栏）。

布局（宽屏，外圈一圈边框）：

    ┌ retype v0.1 · 图片文字替换 ──────────────── 2/5 张 ┐
    │ ① 图片 2/5        │ ② 识别到的文字 2/6           │
    │ ▸ 示例-报告.png    │ ● 年度销售报告2023            │
    │   ✓ 示例-通知1.png │ ○ 负责人：张三                │
    ├───────────────────┴─────────────────────────────┤
    │ 选：年度销售报告2023 → 年度财务总结2024            │
    │ 已保存 示例-报告.png  输出 data/output  [██░░] 35% │
    │ ↑↓ 选图  Enter 右栏  r 替换  R 全部  ? 帮助  q 退出│
    └──────────────────────────────────────────────────┘

边框/分隔线走 `addch`（FakeWin 里不可见），文字走 `put`（可断言）。
"""

from __future__ import annotations

import contextlib
import curses
import os
import re

from ..version import NAME, TITLE, UPDATED, VERSION
from .app import App
from .ui_base import HELP, attr, box, divider, dwidth, pad, progress_bar, put, vline

TITLE_TEXT = f"{NAME} v{VERSION} ({UPDATED}) · {TITLE}"
PROGRESS = re.compile(r"(\d+)\s*/\s*(\d+)")


def _int(text: str, default: int = 0) -> int:
    """状态行里的数字来自自家拼的进度串，但别让一个脏字符把整帧绘制打挂。"""
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def _frame(win, h: int, w: int, title: str, right: str = "") -> None:
    """外框 + 左上标题 + 右上角信息。"""
    box(win, h, w, title, attr("frame"))
    if right and w > dwidth(title) + dwidth(right) + 8:
        put(win, 0, w - dwidth(right) - 2, f" {right} ", dwidth(right) + 2, attr("dim"))


def _banner() -> str:
    return TITLE_TEXT


def draw_main(win, app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    img = app.cur
    pos_img = f"{app.image_position() or '—'}/{len(app.images)}"
    # 窄屏把终端尺寸写在右上角：排障时一眼知道界面被压缩到多少列
    right = f"[{w}x{h}]" if w < 60 else f"{pos_img} 张"
    _frame(win, h, w, _banner(), right)

    body_top = 2
    body_bottom = h - 6  # 分隔线在 h-5，其上为列表区
    body_h = max(1, body_bottom - body_top + 1)
    narrow = w < 60

    if narrow:
        draw_narrow(win, app, w, body_h)
    else:
        draw_wide(win, app, h, w, body_h)

    # ── 分隔线 + 底部三行（详情 / 状态 / 键位）+ 底边框
    divider(win, h - 5, 1, w - 2, attr("frame"))
    _draw_footer(win, app, h, w, img)
    win.refresh()  # 主界面必须自己 flush：漏了这一行就是一片黑屏


def _draw_footer(win, app: App, h: int, w: int, img) -> None:
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
        detail = app.status if not app.images else ""
    put(win, h - 4, 2, detail, w - 4, attr("accent"))
    # 右上角的 [宽x高] 单独右对齐画：之前的写法把它拼在状态文字末尾，
    # 路径一长（CI 的临时目录比本机深）就被裁掉——本机绿、CI 红的经典来源。
    size_marker = f"[{w}x{h}]" if w < 60 else ""
    marker_cols = dwidth(size_marker) + 1 if size_marker else 0
    put(
        win,
        h - 3,
        2,
        _status_text(app, max(0, w - 4 - marker_cols)),
        w - 4 - marker_cols,
        attr("ok"),
    )
    if size_marker:
        put(win, h - 3, w - 1 - dwidth(size_marker), size_marker, dwidth(size_marker), attr("dim"))
    put(win, h - 2, 2, f" {_keys_hint(app, w)} ", w - 4, attr("sel"))


def _status_text(app: App, cols: int) -> str:
    """状态行：消息优先；批量替换时带进度条。"""
    total = app.out_dir.rstrip("/\\ ") or app.out_dir
    base = f"输出 {total}"
    if app.last_saved:
        base += f"　已保存 {os.path.basename(app.last_saved)}"
    text = app.message or app.status
    m = PROGRESS.search(app.status or "") if "替换" in (app.status or "") else None
    if m and _int(m.group(2)):
        done, total_n = _int(m.group(1)), _int(m.group(2))
        bar_w = max(6, min(24, cols - dwidth(text) - 12))
        text = f"{text}  {progress_bar(done / total_n, bar_w)} {done * 100 // total_n}%"
    if not text:
        return base
    room = max(0, cols - dwidth(text) - 2)
    tail = pad(base, room) if room > 6 else ""
    return f"{text}{('  ' + tail) if tail else ''}"


def _keys_hint(app: App, w: int) -> str:
    """键位提示按宽度分三档：手机窄屏只留最常用的几个，宽屏才给全套。"""
    if w < 40:  # 手机竖屏：一行只放得下 3~4 组
        return (
            "↑↓ 选  Enter 进  r 替换  ? 帮助"
            if app.focus == "files"
            else "↑↓ 选块  Enter 改  r 替换  Esc 返回"
        )
    if w < 60:  # 小窗口 / 分屏
        return (
            "↑↓ 选图  Enter 右栏  r 替换  Tab 换栏  q 退出"
            if app.focus == "files"
            else "↑↓ 选块  Enter 整行  i 行内  空格 启用  r 替换  Esc 返回"
        )
    if app.focus == "files":
        return (
            "↑↓ 选图  数字跳图  Enter 进右栏  m 映射  e 映射表  c 样式  r 替换  "
            "R 全部  Ctrl-R 刷新  ? 帮助  q 退出"
        )
    return (
        "↑↓ 选块  Enter 整行换  i 只换几个字  空格 启用  u 清除  z 撤销  r 替换  "
        "Esc 返回  Tab 换栏  q 退出"
    )


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
    left_w = min(34, max(20, w // 3))
    right_x = left_w + 2
    right_w = max(1, w - right_x - 2)

    pos_img = f"{app.image_position() or '—'}/{len(app.images)}"
    put(win, 1, 2, f" ① 图片 {pos_img}", left_w - 2, attr("title", curses.A_BOLD))
    nblk = len(app.blocks())
    pos_blk = f"{app.sel_blk + 1}/{nblk}" if nblk else "0/0"
    empty_hint = " 目录里还没有图片：放好图片后按 Ctrl-R 重新扫描" if not app.images else ""
    hint = "Enter 进右侧" if app.focus == "files" else f"{pos_blk}　Enter 整行换　i 只换几个字"
    put(
        win,
        1,
        right_x,
        f" ② 识别到的文字 {empty_hint or hint}",
        right_w,
        attr("title", curses.A_BOLD if app.focus != "blocks" else 0),
    )
    # 两栏之间一条竖线（从表头下到分隔线）
    vline(win, left_w, 1, h - 6, attr("frame"))

    app.img_rows = body_h
    start_img, visible = app.image_window(body_h)
    app.img_start = start_img
    shown = 0
    for i, (kind, path) in enumerate(visible):
        real = start_img + i
        label = row_label(app, kind, path, shown)
        if kind == "img":
            shown += 1
        put(win, 2 + i, 2, label, left_w - 2, _sel_style(app, real == app.sel_row, "files"))

    start = max(0, app.sel_blk - body_h + 1) if app.sel_blk >= body_h else 0
    if app.cur is not None and app.cur.error:
        put(win, 2, right_x, f" {app.cur.error}", right_w, attr("warn"))
    elif app.cur is not None and app.cur.blocks is None:
        put(win, 2, right_x, " 正在识别文字，请稍等…", right_w, attr("dim"))
    for idx, blk in enumerate(app.blocks()[start : start + body_h]):
        real = start + idx
        put(
            win,
            2 + idx,
            right_x,
            block_label(app, blk),
            right_w,
            _sel_style(app, real == app.sel_blk, "blocks"),
        )


def draw_narrow(win, app: App, w: int, body_h: int) -> None:
    """窄屏：只画当前焦点那一栏，Tab 切换。

    手机竖屏常见 30~45 列：极窄时表头只留计数（`图片 2/5`），
    省下来的宽度留给文件名与"→新文字"。
    """
    inner = max(1, w - 4)
    compact = w < 44
    if app.focus == "files":
        pos = f"{app.image_position() or '—'}/{len(app.images)}"
        head = f" 图片 {pos}" if compact else f" ① 图片 {pos}　Tab→文字"
        put(win, 1, 2, head, inner, attr("title", curses.A_BOLD))
        app.img_rows = body_h
        start_img, visible = app.image_window(body_h)
        app.img_start = start_img
        shown = 0
        for i, (kind, path) in enumerate(visible):
            real = start_img + i
            label = row_label(app, kind, path, shown)
            if kind == "img":
                shown += 1
            put(win, 2 + i, 2, label, inner, _sel_style(app, real == app.sel_row, "files"))
        return

    nblk = len(app.blocks())
    pos = f"{app.sel_blk + 1}/{nblk}" if nblk else "0/0"
    head = f" 文字 {pos}" if compact else f" ② 文字 {pos}　Tab→图片"
    put(win, 1, 2, head, inner, attr("title", curses.A_BOLD))
    if app.cur is not None and app.cur.error:
        put(win, 2, 2, f" {app.cur.error}", inner, attr("warn"))
    elif app.cur is not None and app.cur.blocks is None:
        put(win, 2, 2, " 正在识别文字，请稍等…", inner, attr("dim"))
    start = max(0, app.sel_blk - body_h + 1) if app.sel_blk >= body_h else 0
    for idx, blk in enumerate(app.blocks()[start : start + body_h]):
        put(
            win,
            2 + idx,
            2,
            block_label(app, blk),
            inner,
            _sel_style(app, start + idx == app.sel_blk, "blocks"),
        )


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
    return attr("accent", curses.A_BOLD)


def draw_map(win, app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    _frame(win, h, w, f"{NAME} · 全局映射表（{len(app.mapping)} 条，对全部图片生效）")
    items = list(app.mapping.items())
    if not items:
        put(win, 2, 3, "还没有条目。按 n 新增一条「旧文字 → 新文字」", w - 6, attr("dim"))
        put(win, 3, 3, "条目写的是片段时（如 2023），会做行内替换。", w - 6, attr("dim"))
    for i, (k, v) in enumerate(items[: max(1, h - 6)]):
        a = attr("sel", curses.A_BOLD) if i == app.sel_map else 0
        put(win, 2 + i, 2, f" {k}  →  {v}", w - 4, a)
    divider(win, h - 3, 1, w - 2, attr("frame"))
    put(win, h - 2, 2, app.message or app.status, w - 4, attr("warn"))
    put(
        win,
        h - 2,
        max(2, w - 46),
        " n 新增  Enter 改  d 删除  w 导出  Esc 返回 ",
        min(44, w - 4),
        attr("sel"),
    )
    win.refresh()


def draw_settings(win, app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    _frame(win, h, w, f"{NAME} · 样式选项（对下一次 r / R 生效）")
    rows = app.setting_notes()
    for i, (_field, title, value) in enumerate(rows[: max(1, h - 6)]):
        sel = i == app.sel_setting
        a = attr("sel", curses.A_BOLD) if sel else 0
        put(win, 2 + i, 2, f" {title}：{value}", w - 4, a)
    hint = dict(app.SETTING_ROWS_HINT)
    put(
        win,
        h - 4,
        2,
        " " + hint.get(rows[app.sel_setting][0], "") if rows else "",
        w - 4,
        attr("dim"),
    )
    divider(win, h - 3, 1, w - 2, attr("frame"))
    put(win, h - 2, 2, app.message or app.status, w - 4, attr("warn"))
    put(
        win,
        h - 2,
        max(2, w - 42),
        " ↑↓ 选择  Enter 修改  留空=自动  Esc 返回 ",
        min(40, w - 4),
        attr("sel"),
    )
    win.refresh()


def draw_help(win, _app: App) -> None:
    win.erase()
    h, w = win.getmaxyx()
    _frame(win, h, w, f"{NAME} v{VERSION} · 帮助")
    for i, line in enumerate(HELP.splitlines()[: h - 3]):
        a = attr("title", curses.A_BOLD) if line and not line.startswith(" ") else 0
        if line.startswith("  "):
            a = attr("dim")
        put(win, 1 + i, 2, " " + line, w - 4, a)
    put(win, h - 2, 2, " 按任意键返回 ", w - 4, attr("sel"))
    win.refresh()


def draw_too_small(win, h: int, w: int) -> None:
    """终端太小（手机竖屏常见）时给一句提示，不要崩。"""
    win.erase()
    put(win, max(0, h // 2) - 1, 0, " 太窄了", w, attr("warn"))
    put(win, max(0, h // 2), 0, f" 现在 {w}列 x {h}行", w, attr("dim"))
    put(win, max(0, h // 2) + 1, 0, " 横屏或缩小字号", w, attr("dim"))
    put(win, h - 1, 0, " q 退出", w, attr("sel"))
    win.refresh()


def draw_frame(win, app: App) -> None:
    """画一帧；任何绘制异常都吞掉，绝不让界面把程序带崩。"""
    try:
        h, w = win.getmaxyx()
        if h < 10 or w < 24:
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
            curses.update_lines_cols()  # 窗口尺寸变了，刷新缓存后下一帧重画
    except Exception as exc:  # 兜底：不退出，提示后继续
        app.message = f"界面绘制出错: {exc}"
