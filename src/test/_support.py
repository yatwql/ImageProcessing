"""测试公共设施：字体路径、合成 OCR 结果、TUI 假窗口。

文件名不以 test_ 开头，pytest 不会把它当用例收集。
"""

from __future__ import annotations

import contextlib
import curses
import os
import tempfile
import unittest
from collections.abc import Callable, Sequence
from typing import TypeAlias

import numpy as np
from PIL import Image, ImageDraw, ImageFont

Rect: TypeAlias = tuple[int, int, int, int]
RegionPairs: TypeAlias = Sequence[tuple[str, Rect]]

# 常见的中日韩字体位置：Debian/Ubuntu（含 GitHub Actions 装了 fonts-noto-cjk 之后）、
# macOS、Windows。真要用某个字体时再显式传 font_path。
_CJK_BOLD_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
)
_CJK_REG_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
)


def _first_loadable(paths: Sequence[str], fallback: str) -> str:
    """挑第一个真的能加载的字体文件；都不可用时返回原路径（has_cjk_font 会为 False）。"""
    for path in paths:
        try:
            ImageFont.truetype(path, 12)
        except OSError:
            continue
        return path
    return fallback


FONT_CJK = _first_loadable(_CJK_BOLD_CANDIDATES, _CJK_BOLD_CANDIDATES[0])
FONT_CJK_REG = _first_loadable(_CJK_REG_CANDIDATES, _CJK_REG_CANDIDATES[0])


def ocr_available() -> bool:
    """OCR 依赖是否真的能加载（onnxruntime 在部分平台/版本上 import 就会失败）。"""
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def has_cjk_font() -> bool:
    """字体不只是存在，还要真的能打开（CI 上常见"路径存在但字体损坏/是符号链接"）。"""
    for path in (FONT_CJK, FONT_CJK_REG):
        try:
            ImageFont.truetype(path, 12)
        except OSError:
            return False
    return True


def regions(*texts_and_rects):
    """把 (文字, 矩形) 组合成 OCR 结果的形状。"""
    return [{"text": t, "rect": r, "score": 1.0} for t, r in texts_and_rects]


class FakeWin:
    """最小 curses 窗口替身：按键从队列里取，按行存屏。

    队列元素可以是字符、键码（int），或 None 表示“这个时间窗内没有更多输入”。
    """

    def __init__(self, keys: Sequence[str | int | None], rows: int = 28, cols: int = 100):
        self.keys: list[str | int | None] = list(keys)
        self.rows = rows
        self.cols = cols
        self.screen = [""] * rows
        self.timeout_ms = -1
        self.refresh_count = 0          # 真的调过 refresh 才 +1（黑屏就是没刷新）
        self.cell_count = 0             # addch 次数（边框走 addch，用来断言线框画了）

    def getmaxyx(self):
        return self.rows, self.cols

    def erase(self):
        self.screen = [""] * self.rows

    def refresh(self):
        self.refresh_count += 1

    def keypad(self, *_args):
        pass

    def timeout(self, ms):
        self.timeout_ms = ms

    def nodelay(self, flag):
        """非阻塞模式开关（批量替换途中轮询 Esc 用）。"""
        self.no_delay = bool(flag)

    def getch(self):
        """非阻塞取键：队列空了或遇上 None 就返回 -1（curses 的约定）。"""
        if not self.keys or self.keys[0] is None:
            if self.keys:
                self.keys.pop(0)
            return -1
        key = self.keys.pop(0)
        if isinstance(key, str):
            return ord(key[0])
        return -1 if key is None else int(key)

    def move(self, *_args):
        pass

    def addstr(self, y, x, text, _attr=0):
        """按**显示列**写，而不是按字符下标——真 curses 就是按列算的。

        并且像真 curses 一样只接受 str：线框（ACS_*）在部分构建里是 **int**，
        若误把 int 传给 addstr，真终端会抛 TypeError 导致整帧画不出来（黑屏），
        这里同样抛，好让用例当场发现。
        """
        if not isinstance(text, str):
            raise TypeError(f"expect bytes or str, got {type(text).__name__}")
        if not 0 <= y < self.rows:
            return
        from src.python.tui.ui_base import cut, dwidth

        line = self.screen[y]
        left = cut(line, x)
        left += " " * max(0, x - dwidth(left))
        self.screen[y] = left + cut(text, max(0, self.cols - x))

    def addch(self, y, x, ch, _attr=0):
        """线框字符：可以是 str，也可以是 curses 的 ACS int 码（真 curses 两者都收）。"""
        if not isinstance(ch, (str, int)):
            raise TypeError(f"expect str or int, got {type(ch).__name__}")
        self.cell_count += 1

    def get_wch(self):
        if self.keys and self.keys[0] is None:
            self.keys.pop(0)
            raise curses.error("timeout")
        if not self.keys:
            if self.timeout_ms >= 0:
                raise curses.error("timeout")
            raise KeyboardInterrupt  # 队列空了＝人跑了，循环自行收尾
        return self.keys.pop(0)


def patch_curses() -> None:
    """无终端环境下让绘制/配色退化为纯文本。"""
    import src.python.tui.ui as ui

    # 打桩必须改模块属性：签名与真身不同（curses 常量还是 Final），用 ignore 说明意图
    ui.init_colors = lambda: None
    ui.attr = lambda _name, extra=0: extra  # type: ignore[assignment]
    curses.ACS_VLINE = "|"  # type: ignore[misc,assignment]


class TuiTestCase(unittest.TestCase):
    """TUI 用例基类：配色打桩 + 临时输出目录。"""

    def setUp(self):
        patch_curses()
        self.tmp = tempfile.TemporaryDirectory()  # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)

    def make_app(self, count: int = 3):
        """临时目录里造 count 张图再启动 App：不依赖仓库 data/ 的内容。"""
        from src.python.tui.app import App, Block

        images_dir = os.path.join(self.tmp.name, "in")
        os.makedirs(images_dir, exist_ok=True)
        canvas = Image.new("RGB", (320, 200), (255, 255, 255))
        for i in range(count):
            canvas.save(os.path.join(images_dir, f"img{i + 1}.png"))
        app = App([images_dir])
        app.out_dir = os.path.join(self.tmp.name, "out")
        for img in app.images:  # 预置文字块，跳过 OCR
            img.blocks = [Block(f"第{i}行文字", (10, 20 + i * 30, 200, 24)) for i in range(3)]
        return app

    def drive(self, app, keys):
        import src.python.tui.ui as ui

        win = FakeWin(keys)
        with contextlib.suppress(KeyboardInterrupt):
            ui.loop(win, app)
        return win


# --------------------------------------------------------------------------- 图片与 OCR


def make_text_image(
    lines: Sequence[str],
    *,
    size: int = 36,
    color=(30, 30, 30),
    bg=(255, 255, 255),
    line_gap: int = 60,
    margin: int = 40,
    font_path: str | None = None,
    index: int = 0,
) -> tuple[np.ndarray, list[tuple[str, Rect]]]:
    """按行画一张白底图，返回 (rgb ndarray, [(文字, (x, y, w, h))])。"""
    font = ImageFont.truetype(font_path or FONT_CJK, size, index=index)
    width = margin * 2 + max(1, max(len(s) for s in lines)) * size
    height = margin * 2 + line_gap * len(lines)
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    boxes = []
    for i, text in enumerate(lines):
        x, y = margin, margin + i * line_gap
        draw.text((x, y), text, font=font, fill=color)
        w = int(draw.textlength(text, font=font))
        boxes.append((text, (x, y, max(1, w), size)))
    return np.array(img), boxes


@contextlib.contextmanager
def patch_ocr(regions_for_image: RegionPairs | Callable[[np.ndarray], RegionPairs]):
    """把 OCR 换成桩，避免测试里加载 RapidOCR。

    regions_for_image: 一个函数 (rgb) -> [(文字, 矩形)]，或直接给一份固定列表。
    """
    from src.python.cli import main as cli_main
    from src.python.core import jobs as jobs_mod

    def pairs_of(rgb: np.ndarray) -> RegionPairs:
        return regions_for_image(rgb) if callable(regions_for_image) else regions_for_image

    def fake_regions(rgb, *_args, **_kwargs):
        return [{"text": t, "rect": r, "score": 1.0} for t, r in pairs_of(rgb)]

    def fake_crop(rgb, *_args, **_kwargs):
        pairs = pairs_of(rgb)
        return pairs[0][0] if pairs else None

    original_ocr = (jobs_mod.ocr_regions, jobs_mod.ocr_crop)
    original_cli = cli_main.ocr_regions
    jobs_mod.ocr_regions = fake_regions  # type: ignore[assignment]
    jobs_mod.ocr_crop = fake_crop  # type: ignore[assignment]
    cli_main.ocr_regions = fake_regions  # type: ignore[assignment]
    try:
        yield
    finally:
        jobs_mod.ocr_regions = original_ocr[0]
        jobs_mod.ocr_crop = original_ocr[1]
        cli_main.ocr_regions = original_cli
