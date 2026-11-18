"""TUI 基础层：文案、宽字符处理、颜色与落字。

`ui.py` 只做入口与主循环；绘制在 `ui_draw.py`，按键/输入行在 `ui_input.py`，
编辑动作在 `ui_actions.py`。这里放它们都依赖的底层件。
"""

from __future__ import annotations

import contextlib
import curses
import unicodedata

from ..version import NAME, TITLE, UPDATED, VERSION

PAIR = {"title": 1, "sel": 2, "dim": 3, "ok": 4, "warn": 5, "err": 6,
        "accent": 7, "frame": 8}
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

HELP = f"""\
{NAME} v{VERSION} ({UPDATED}) · {TITLE} —— 操作说明

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
  Ctrl-R     重新扫描目录（先开界面、再往目录里放图片时用；F5 同效）
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
        curses.init_pair(PAIR["accent"], curses.COLOR_MAGENTA, -1)
        curses.init_pair(PAIR["frame"], curses.COLOR_BLUE, -1)
    except Exception:                                   # 无颜色/未初始化时退化成黑白
        return


def attr(name: str, extra: int = 0) -> int:
    try:
        return curses.color_pair(PAIR[name]) | extra
    except curses.error:
        return extra


def put(win, y: int, x: int, text: str, cols: int, a: int = 0) -> None:
    """在 (y, x) 写一段文本，最多占 cols 列；再按窗口宽度兜底裁剪。

    调用方给的 cols 可能超出窗口右边界（例如 x=2、cols=w-2），
    这里统一收紧到"x 到窗口右侧"，任何布局都不会画出界。
    """
    if cols <= 0:
        return
    with contextlib.suppress(curses.error):
        _h, win_w = win.getmaxyx()
        cols = min(cols, max(0, win_w - x))
        if cols <= 0:
            return
        win.addstr(y, x, pad(text, cols), a)




# --------------------------------------------------------------------------- 边框与分栏
#
# curses 的 ACS_* 是线框字符；FakeWin/无颜色终端里退化成 ASCII。
# 所有边框都用 addch 画（不进 FakeWin 的屏幕快照），文字仍走 put()。


def _acs(name: str, fallback: str) -> str | int:
    """取 curses 的线框字符。

    注意：ACS_* 在不同构建里可能是 **str**（'q'）也可能是 **int**（终端专用码），
    而 `addstr` 只接受 str —— 所以线框一律用 `addch` 画（它两种都收）。
    """
    return getattr(curses, name, fallback)


def hline(win, y: int, x: int, cols: int, a: int = 0) -> None:
    if cols <= 0:
        return
    ch = _acs("ACS_HLINE", "-")
    for offset in range(cols):
        with contextlib.suppress(curses.error):
            win.addch(y, x + offset, ch, a)


def vline(win, x: int, top: int, bottom: int, a: int = 0) -> None:
    ch = _acs("ACS_VLINE", "|")
    for y in range(top, bottom + 1):
        with contextlib.suppress(curses.error):
            win.addch(y, x, ch, a)


def box(win, h: int, w: int, title: str = "", a: int = 0) -> None:
    """画一圈边框；title 覆盖在上边框左侧（不含两端）。"""
    if h < 3 or w < 4:
        return
    corners = {
        (0, 0): _acs("ACS_ULCORNER", "+"),
        (0, w - 1): _acs("ACS_URCORNER", "+"),
        (h - 1, 0): _acs("ACS_LLCORNER", "+"),
        (h - 1, w - 1): _acs("ACS_LRCORNER", "+"),
    }
    for (y, x), ch in corners.items():
        with contextlib.suppress(curses.error):
            win.addch(y, x, ch, a)
    hline(win, 0, 1, w - 2, a)
    hline(win, h - 1, 1, w - 2, a)
    vline(win, 0, 1, h - 2, a)
    vline(win, w - 1, 1, h - 2, a)
    if title and w > 6:
        put(win, 0, 2, f" {title} ", min(w - 4, dwidth(title) + 2), a)


def divider(win, y: int, x: int, cols: int, a: int = 0, tee: str = "sep") -> None:
    """横向分隔线；tee="sep" 时在与竖线交叉处画竖接头。"""
    hline(win, y, x, cols, a)
    if tee == "sep":
        with contextlib.suppress(curses.error):
            win.addch(y, x, _acs("ACS_LTEE", "+"), a)
        with contextlib.suppress(curses.error):
            win.addch(y, x + cols - 1, _acs("ACS_RTEE", "+"), a)


def progress_bar(fraction: float, width: int) -> str:
    """纯文本进度条（curses 里画方块比逐格填色可靠）。"""
    width = max(3, width)
    filled = int(round(max(0.0, min(1.0, fraction)) * width))
    return "█" * filled + "░" * (width - filled)
