"""运行选项与颜色解析。"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

from .errors import CoreError

# 关键阈值集中在这里，改一个数就能同步到匹配/分析/绘制三处
MIN_OCR_SCORE = 0.0  # OCR 置信度下限；低于它的块不参与自动匹配
FUZZY_MIN = 0.8  # 模糊兜底的最低相似度（difflib ratio）


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
    min_score: float = MIN_OCR_SCORE  # OCR 置信度下限（0=不过滤）
    fuzzy_min: float = FUZZY_MIN  # 模糊兜底阈值
    dry_run: bool = False  # 预演：只算分析/匹配结果，不改像素、不写文件
    quality: int | None = None  # JPEG 输出质量 1-100；None=默认 95
    debug: str | None = None
    quiet: bool = False
    log_dir: str | None = None  # 写盘日志目录；None=用调用方默认（logs/）
    channel: str = "cli"  # 写盘日志里的来源渠道：cli / tui
    warn: Callable[[str], None] | None = None  # 警告出口；TUI 用它回填消息行


def warn(opts: Options | None, msg: str) -> None:
    """向调用方指定的出口发一条提示；没有出口才落到 stderr。"""
    if opts is not None and opts.warn is not None:
        opts.warn(msg)
        return
    if opts is None or not opts.quiet:
        print(f"! {msg}", file=sys.stderr)


def parse_color(spec: str) -> tuple[int, int, int]:
    """`#RRGGBB` / `#RGB` / `r,g,b` → (r, g, b)，分量必须在 0~255。

    6 位十六进制要求整串都是十六进制：#12345 这类半截输入以前会被静默截成
    (0x12, 0x34, 0x05)，看不出来但颜色完全不对，所以这里严格校验长度与字符集。
    """
    cs = spec.strip().lstrip("#")
    try:
        if "," in cs:
            parts = [int(p) for p in re.split(r"[,\s]+", cs) if p]
            if len(parts) < 3:
                raise ValueError("需要三个分量")
            rgb = (parts[0], parts[1], parts[2])
        else:
            if len(cs) == 3:
                cs = "".join(c * 2 for c in cs)
            if len(cs) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in cs):
                raise ValueError("十六进制颜色需要 3 或 6 位")
            rgb = (int(cs[0:2], 16), int(cs[2:4], 16), int(cs[4:6], 16))
        if any(not 0 <= value <= 255 for value in rgb):
            raise ValueError("分量应在 0~255")
        return rgb
    except (ValueError, IndexError) as exc:
        raise CoreError(f"颜色格式错误: {spec}（用 #RRGGBB 或 r,g,b）") from exc
