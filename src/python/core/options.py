"""运行选项与颜色解析。"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

from .errors import CoreError


def _log(msg: str) -> None:
    if os.environ.get("TEXT_REPLACE_VERBOSE"):
        print(f"! {msg}", file=sys.stderr)


@dataclass
class Options:
    font: str | None = None
    size: int | None = None
    color: str | None = None
    align: str = "auto"
    fit_width: bool = False
    tracking: float | None = None
    max_fonts: int = 160
    quality: int | None = None       # JPEG 输出质量 1-100；None=默认 95
    debug: str | None = None
    quiet: bool = False
    log_dir: str | None = None      # 写盘日志目录；None=用调用方默认（logs/）
    channel: str = "cli"            # 写盘日志里的来源渠道：cli / tui
    warn: Callable[[str], None] | None = None   # 警告出口；TUI 用它回填消息行


def warn(opts: Options | None, msg: str) -> None:
    """向调用方指定的出口发一条提示；没有出口才落到 stderr。"""
    if opts is not None and opts.warn is not None:
        opts.warn(msg)
        return
    if opts is None or not opts.quiet:
        print(f"! {msg}", file=sys.stderr)


def parse_color(spec: str) -> tuple[int, int, int]:
    cs = spec.strip().lstrip("#")
    try:
        if "," in cs:
            parts = [int(p) for p in re.split(r"[,\s]+", cs) if p]
            return (parts[0], parts[1], parts[2])
        if len(cs) == 3:
            cs = "".join(c * 2 for c in cs)
        return (int(cs[0:2], 16), int(cs[2:4], 16), int(cs[4:6], 16))
    except (ValueError, IndexError) as exc:
        raise CoreError(f"颜色格式错误: {spec}（用 #RRGGBB 或 r,g,b）") from exc
