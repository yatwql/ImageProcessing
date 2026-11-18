"""TUI 渠道的入口：启动参数、主循环、窗口初始化。

绘制见 `ui_draw`，按键见 `ui_input`，动作见 `ui_actions`，状态在 `app.py`。
"""

from __future__ import annotations

import contextlib
import curses
import os
import sys

from ..core import CoreError
from ..core.options import Options
from ..version import NAME, UPDATED, VERSION
from .app import App, Block
from .ui_actions import handle
from .ui_base import USAGE, attr, cut, dwidth, init_colors, pad
from .ui_draw import digit_of, draw_frame, draw_main, draw_wide
from .ui_input import edit_line, read_key

# 对外门面：用例与 _support 只依赖 ui 这一个入口，内部实现按层拆在
# ui_base / ui_draw / ui_input / ui_actions 里。
__all__ = [
    "App",
    "Block",
    "attr",
    "cut",
    "digit_of",
    "draw_frame",
    "draw_main",
    "draw_wide",
    "dwidth",
    "edit_line",
    "handle",
    "init_colors",
    "loop",
    "main",
    "pad",
    "read_key",
]


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
            draw_frame(win, app)   # 先画出"正在识别"
            app.start_loading()    # OCR 走后台线程：期间界面照样能收键
        draw_frame(win, app)
        try:
            key = read_key(win, timeout_ms=120)
        except KeyboardInterrupt:  # 手机终端偶发 Ctrl-C：一次忽略，连按两次退出
            interrupts += 1
            if interrupts >= 2:
                app.quit = True
            continue
        except curses.error:
            silent += 1
            if silent > 50:  # 终端已经不响应了，别死循环
                app.message = "终端没有响应，已退出"
                break
            with contextlib.suppress(curses.error):
                curses.update_lines_cols()  # resize / 无输入：刷新后重画
            continue
        interrupts = 0
        silent = 0
        if not key:                 # 只是到了轮询时间，重画一帧继续等
            continue
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
        except (CoreError, SystemExit) as exc:  # 核心层报错只提示，不退出
            app.message = str(exc) or "操作失败"
        except Exception as exc:  # 其它异常也不退出
            app.message = f"操作出错: {exc}"


def parse_args(argv: list[str]) -> tuple[list[str], str | None, str | None, Options]:
    """手工解析，避免 argparse 的错误信息冲掉 curses 界面。"""
    inputs: list[str] = []
    out_dir = None
    map_file = None
    opts = Options()
    takes_value = {
        "-o": "out_dir",
        "--out-dir": "out_dir",
        "-m": "map_file",
        "--map-file": "map_file",
        "-f": "font",
        "--font": "font",
        "--color": "color",
        "--align": "align",
        "--size": "size",
        "--tracking": "tracking",
        "--max-fonts": "max_fonts",
        "--quality": "quality",
        "--log-dir": "log_dir",
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
    # 进 curses 之前先报版本：界面外的日志/终端记录里也能看到跑的是哪一版
    print(f"{NAME} {VERSION} ({UPDATED})")
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
        # 空目录也允许进界面：先把图复制进来，再按 Ctrl-R 重新扫描即可
        app.message = (
            f"{inputs[0]} 里还没有图片（支持 png/jpg/bmp/webp/tif）"
            "：放好图片后按 Ctrl-R 重新扫描"
        )
    try:
        curses.wrapper(loop, app)
    except KeyboardInterrupt:
        return 130
    return 0
