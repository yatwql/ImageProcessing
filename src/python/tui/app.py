"""TUI 渠道的状态层：只维护数据与动作，不碰 curses。

界面（绘制/按键）在 ui.py；替换逻辑全部来自 src.core。
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable

from ..config import apply_to_options, default_out_dir, log_dir
from ..core import (
    IMG_EXTS,
    CoreError,
    Job,
    build_font_pool,
    collect_images,
    jobs_from_blocks,
    load_image,
    load_meta,
    norm_map,
    record_write,
    replace_image,
    reserve_path,
    same_file,
    save_image,
)
from ..core.options import Options, parse_color

Progress = Callable[[str], None]

# 样式选项面板里的条目：(字段名, 标题, 说明)
SETTING_ROWS = (
    ("font", "字体文件", "留空=自动匹配，可填 .ttf/.otf/.ttc 路径"),
    ("size", "字号", "留空=自动反解，填整数像素"),
    ("color", "字色", "留空=取原字色，可填 #FF0000 或 255,0,0"),
    ("align", "对齐", "auto / left / center / right"),
    ("fit_width", "贴合原宽度", "on / off（调字距让新文字宽度等于原文字）"),
    ("tracking", "额外字距", "留空=自动，可填像素值（可负）"),
    ("max_fonts", "候选字体上限", "默认 160，越小越快"),
    ("quality", "JPEG 质量", "留空=默认 95，可填 1-100"),
)


class Block:
    """图片里识别到的一段文字，以及用户为它设置的新文字。"""

    __slots__ = ("text", "rect", "override", "find", "enabled")

    def __init__(self, text: str, rect: tuple[int, int, int, int]):
        self.text = text
        self.rect = rect
        self.override: str | None = None  # 新文字
        self.find: str | None = None  # 行内替换：只换这一行里的这几个字
        self.enabled = True


class ImageItem:
    __slots__ = ("path", "name", "blocks", "error", "done", "memo", "sel", "saved")

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.blocks: list[Block] | None = None
        self.error: str | None = None
        self.done = False
        self.sel = 0
        self.saved: str | None = None  # 本次会话里输出到哪个文件（重复替换就覆盖它）
        self.memo: dict = {}  # 分析/字体匹配缓存，重复替换时秒出


class App:
    def __init__(
        self,
        inputs: list[str],
        out_dir: str | None = None,
        map_file: str | None = None,
        opts: Options | None = None,
    ):
        paths: list[str] = []
        for p in inputs:
            paths += collect_images(p)
        self.dir: str | None = (
            os.path.abspath(inputs[0]) if len(inputs) == 1 and os.path.isdir(inputs[0]) else None
        )
        self.images: list[ImageItem] = [ImageItem(p) for p in paths]
        # 左栏的行：父目录 / 子目录 / 图片，顺序即显示顺序
        self.rows: list[tuple[str, str]] = [("img", p) for p in paths]
        self.out_dir = out_dir or default_out_dir()
        self.opts = opts or Options()
        apply_to_options(self.opts)
        if not self.opts.log_dir:
            self.opts.log_dir = log_dir()
        self.opts.channel = "tui"
        # 核心层的警告走回调进消息行；不让它 print(stderr) 冲花 curses 界面
        self.opts.warn = self.on_core_warning
        self.warned: list[str] = []
        self.mapping: dict[str, str] = {}
        self.map_path = map_file
        self.sel_row = 0
        self.sel_blk = 0
        self.sel_map = 0
        self.sel_setting = 0
        self.img_start = 0  # 图片列表当前显示窗口的起始行（数字键用）
        self.img_rows = 1  # 图片列表可见行数，由界面每帧写入
        self.focus = "files"
        self.panel = "main"  # main | map | help | settings
        self.started = False
        self.status = "就绪"
        self.message = ""
        self.last_saved: str | None = None
        self.quit = False
        self.cancel = False  # 批量替换的中断标志（界面轮询到 Esc 时置位）
        if self.dir:
            self._load_dir(self.dir)
        if map_file:
            self.load_map(map_file)

    # ---- 映射表

    def load_map(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError('内容应为 {"旧": "新"}')
            self.mapping.update({str(k): str(v) for k, v in data.items()})
            self.message = f"已载入映射 {path}（{len(data)} 条）"
        except (OSError, ValueError) as e:
            self.message = f"载入映射失败: {e}"

    def save_map(self, path: str) -> str:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.mapping, f, ensure_ascii=False, indent=2)
            self.map_path = path
            return f"已导出映射 {path}（{len(self.mapping)} 条）"
        except OSError as e:
            return f"导出失败: {e}"

    # ---- 目录浏览

    def _scan_rows(self, path: str) -> tuple[list[ImageItem], list[tuple[str, str]]]:
        """扫描一个目录：父目录入口 + 子目录 + 图片，隐藏项与非图片文件跳过。"""
        rows: list[tuple[str, str]] = []
        parent = os.path.dirname(path)
        if parent and parent != path:
            rows.append(("parent", parent))
        try:
            names = sorted(os.listdir(path))
        except OSError as e:
            self.message = f"无法读取目录 {path}: {e}"
            names = []
        images: list[ImageItem] = []
        for name in names:
            if name.startswith("."):
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                rows.append(("dir", full))
        for name in names:
            if name.startswith(".") or not name.lower().endswith(IMG_EXTS):
                continue
            full = os.path.join(path, name)
            if os.path.isfile(full):
                rows.append(("img", full))
                images.append(ImageItem(full))
        return images, rows

    def _load_dir(self, path: str) -> bool:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            self.message = f"不是目录: {path}"
            return False
        self.dir = path
        self.images, self.rows = self._scan_rows(path)
        self.sel_row = self.first_image_row()
        self.sel_blk = 0
        self.img_start = 0
        self.message = f"{path}：{len(self.images)} 张图片"
        return True

    def open_dir(self, path: str) -> bool:
        """切到另一个目录：重建左栏（父目录/子目录/图片）。"""
        return self._load_dir(path)

    def first_image_row(self) -> int:
        for i, (kind, _path) in enumerate(self.rows):
            if kind == "img":
                return i
        return 0

    def row_kind(self, row: int | None = None) -> str | None:
        row = self.sel_row if row is None else row
        if 0 <= row < len(self.rows):
            return self.rows[row][0]
        return None

    def enter_row(self) -> bool:
        """Enter：选中的是目录就进去（返回 True）；是图片由界面切到右栏。"""
        kind = self.row_kind()
        if kind in ("parent", "dir"):
            return self.open_dir(self.rows[self.sel_row][1])
        return False

    def go_parent(self) -> bool:
        if self.dir is None:
            self.message = "当前不是从目录启动的，无法回上级目录"
            return False
        parent = os.path.dirname(self.dir)
        if not parent or parent == self.dir:
            self.message = "已经是根目录了"
            return False
        return self.open_dir(parent)

    def image_position(self) -> int:
        """当前行是第几张图片（1 起）；不在图片行返回 0。"""
        seen = 0
        for i, (kind, _path) in enumerate(self.rows):
            if kind != "img":
                continue
            seen += 1
            if i == self.sel_row:
                return seen
        return 0

    # ---- 数据访问

    def image_for(self, path: str) -> ImageItem | None:
        for img in self.images:
            if img.path == path:
                return img
        return None

    @property
    def cur(self) -> ImageItem | None:
        if self.row_kind() != "img":
            return None
        return self.image_for(self.rows[self.sel_row][1])

    def blocks(self) -> list[Block]:
        img = self.cur
        return img.blocks if img and img.blocks else []

    def cur_block(self) -> Block | None:
        blks = self.blocks()
        return blks[self.sel_blk] if 0 <= self.sel_blk < len(blks) else None

    def lookup(self, text: str) -> str | None:
        nk, _ = norm_map(text)
        for k, v in self.mapping.items():
            if norm_map(k)[0] == nk:
                return v
        return None

    def display_new(self, blk: Block) -> tuple[str | None, bool]:
        """(显示用的新文字, 是否行内替换) —— 仅用于界面展示。"""
        if blk.override is not None:
            return blk.override, blk.find is not None
        exact = self.lookup(blk.text)
        if exact:
            return exact, False
        nt, _ = norm_map(blk.text)
        for k, val in self.mapping.items():
            nk, _ = norm_map(k)
            if nk and nk in nt:
                return val, True
        return None, False

    def on_core_warning(self, msg: str) -> None:
        """核心层提示的出口：存起来，执行完再拼进消息行。"""
        self.warned.append(msg)
        self.warned = self.warned[-5:]

    def jobs_for(self, img: ImageItem) -> list[Job]:
        return jobs_from_blocks(img.blocks or [], self.mapping, warn=False, sink=self.opts.warn)

    def pending_count(self, img: ImageItem) -> int:
        return len(self.jobs_for(img))

    def pool(self, images: list[ImageItem]) -> list:
        texts = []
        for img in images:
            for job in self.jobs_for(img):
                texts.append(job.src or job.new)
        sig = tuple(sorted(set(texts)))
        cached = getattr(self, "_pool_cache", None)
        if cached and cached[0] == sig:
            return cached[1]
        pool = build_font_pool(texts, self.opts.font, self.opts.max_fonts)
        self._pool_cache = (sig, pool)
        return pool

    # ---- 识别

    def ensure_blocks(self, img: ImageItem | None = None) -> None:
        img = img or self.cur
        if img is None:
            return
        if img.blocks is not None:
            return
        try:
            rgb, _alpha = load_image(img.path)
        except OSError as e:
            img.error = str(e)
            img.blocks = []
            return
        try:
            regions = ocr_regions_safe(rgb)
        except (CoreError, SystemExit) as e:
            img.error = str(e)
            img.blocks = []
            return
        img.blocks = [Block(r["text"], tuple(r["rect"])) for r in regions]
        if img.blocks:
            self.message = f"{img.name}: 识别到 {len(img.blocks)} 块文字"
        else:
            img.error = "这张图没识别出文字（按 l 重试，或换张图）"

    SETTING_ROWS_HINT = tuple((k, hint) for k, _t, hint in SETTING_ROWS)

    # ---- 样式选项

    def setting_value(self, key: str) -> str:
        val = getattr(self.opts, key, None)
        if key == "fit_width":
            return "on" if val else "off"
        if val is None or val == "":
            return "自动"
        return str(val)

    def setting_notes(self) -> list[tuple[str, str, str]]:
        return [(key, title, self.setting_value(key)) for key, title, _hint in SETTING_ROWS]

    def set_setting(self, key: str, raw: str) -> str:  # noqa: C901
        """按文本设置一个选项，返回给用户的提示。"""
        text = raw.strip()
        auto = text in ("", "自动", "auto", "-")
        try:
            if key == "font":
                if auto:
                    self.opts.font = None
                else:
                    if not os.path.exists(text):
                        return f"找不到字体文件: {text}"
                    self.opts.font = text
            elif key == "size":
                self.opts.size = None if auto else int(text)
                if self.opts.size is not None and self.opts.size < 6:
                    return "字号至少要 6"
            elif key == "color":
                if auto:
                    self.opts.color = None
                else:
                    try:
                        parse_color(text)  # 只做校验
                    except CoreError as e:
                        return str(e)
                    self.opts.color = text
            elif key == "align":
                if auto:
                    self.opts.align = "auto"
                elif text not in ("auto", "left", "center", "right"):
                    return "对齐只能是 auto/left/center/right"
                else:
                    self.opts.align = text
            elif key == "fit_width":
                self.opts.fit_width = text.lower() in ("on", "1", "true", "yes", "是")
            elif key == "tracking":
                self.opts.tracking = None if auto else float(text)
            elif key == "max_fonts":
                self.opts.max_fonts = 160 if auto else max(4, int(text))
            elif key == "quality":
                new_quality = None if auto else int(text)
                if new_quality is not None and not 1 <= new_quality <= 100:
                    return f"质量应在 1-100 之间（当前 {self.setting_value(key)}）"
                self.opts.quality = new_quality
        except (ValueError, CoreError):
            return f"「{text}」不是合法数值"
        return f"{key} → {self.setting_value(key)}"

    # ---- 编辑动作

    def set_all(self, value: bool) -> None:
        for blk in self.blocks():
            blk.enabled = value
        self.message = "当前图片已全部启用" if value else "当前图片已全部禁用"

    def clear_override(self) -> None:
        blk = self.cur_block()
        if blk is not None:
            blk.override = None
            blk.find = None
            self.message = "已清除该块的设置"

    def add_to_mapping(self) -> None:
        blk = self.cur_block()
        if blk is None:
            return
        new, _inline = self.display_new(blk)
        if not new:
            self.message = "这块还没有新文字，先按 Enter / i 设置"
            return
        self.mapping[blk.find or blk.text] = new
        self.message = f"已加入全局映射「{blk.find or blk.text}」→ {new}（其它图片同样生效）"

    # ---- 执行

    def _same_out_dir(self, path: str) -> bool:
        """输出文件是否就在当前输出目录（相对/绝对路径混用也不误判）。"""
        return os.path.abspath(os.path.dirname(path)) == os.path.abspath(self.out_dir)

    def apply_one(self, img: ImageItem, pool=None) -> tuple[bool, str]:
        if self.cancel:
            return False, "已取消"
        jobs = self.jobs_for(img)
        if not jobs:
            return False, "没有启用且填了新文字的块"
        self.warned.clear()  # 每张图重新收集，避免提示串图
        try:
            rgb, alpha = load_image(img.path)
        except OSError as e:
            return False, f"读取失败: {e}"
        pool = pool or self.pool([img])
        out, new_alpha, report = replace_image(
            rgb,
            alpha,
            jobs,
            self.opts,
            pool,
            tag=os.path.splitext(img.name)[0] + "_",
            memo=img.memo,
            source=img.path,
            should_stop=lambda: self.cancel,      # 单张图内按 Esc 也能停在块之间
        )
        if not report:
            return False, "已取消" if self.cancel else "替换全部失败"
        base = os.path.join(self.out_dir, os.path.splitext(img.name)[0] + ".png")
        if same_file(base, img.path):
            return False, f"输出目录 {self.out_dir} 会覆盖原图，按 o 换个目录"
        reserved = False
        if img.saved and self._same_out_dir(img.saved):
            dst = img.saved  # 覆盖自己刚生成的那份
        else:
            try:
                dst = reserve_path(base)  # 原子占名：已存在就 -1、-2 …
                reserved = True
            except CoreError as e:
                return False, str(e)
        try:
            save_image(out, new_alpha, dst, quality=self.opts.quality, meta=load_meta(img.path))
        except (OSError, CoreError) as e:
            if reserved:
                with contextlib.suppress(OSError):
                    os.remove(dst)
            return False, str(e)
        note = ""
        try:  # 真的写了盘才记日志
            record_write(
                img.path,
                dst,
                report,
                log_dir=self.opts.log_dir or log_dir(),
                channel=self.opts.channel,
                options=self.opts,
            )
        except CoreError as e:
            note = f"；{e}"
        img.done = True
        img.saved = dst
        self.last_saved = dst
        changes = "、".join(f"{str(r['old'])[:12]}→{r['new']}" for r in report[:3])
        more = " 等" if len(report) > 3 else ""
        warn_note = f"；{self.warned[-1]}" if self.warned else ""
        return True, (
            f"已保存 {os.path.abspath(dst)}（{len(report)} 处：{changes}{more}）{note}{warn_note}"
        )

    def runnable(self) -> list[ImageItem]:
        return [img for img in self.images if self.jobs_for(img)]

    def apply_current(self, progress: Progress | None = None) -> None:
        img = self.cur
        if img is None:
            return
        self.cancel = False
        self.ensure_blocks()
        if not self.jobs_for(img):
            self.status = "未替换"
            self.message = (
                "没有可替换的块：选中一行按 Enter（整行换）或 i（只换几个字）先设置新文字"
                if not any(b.override for b in self.blocks())
                else "启用的块没有新文字，按 空格 检查启用状态"
            )
            return
        if progress:
            progress("正在替换，请稍等…")
        ok, msg = self.apply_one(img)
        self.status = "替换完成" if ok else "替换失败"
        self.message = msg

    def apply_all(
        self, progress: Progress | None = None, should_stop: Callable[[], bool] | None = None
    ) -> None:
        """批量替换。should_stop 每张图之前问一次，返回 True 则就此收手。"""
        todo = self.runnable()
        if not todo:
            self.message = "没有任何图片有可执行的替换"
            return
        self.cancel = False
        total = len(todo)
        pool = self.pool(todo)
        done = 0
        last = ""
        for idx, img in enumerate(todo, 1):
            if should_stop is not None and should_stop():
                self.cancel = True
                break
            if progress:
                progress(f"替换中 {idx}/{total}：{img.name}（Esc 取消）")
            ok, msg = self.apply_one(img, pool)
            done += 1 if ok else 0
            last = f"{img.name}: {msg}"
        if self.cancel:
            self.status = f"已取消，完成 {done}/{total}"
            self.message = last or "已取消，未开始替换"
            return
        self.status = f"批量完成 {done}/{total}"
        self.message = last

    # ---- 列表窗口

    def image_window(self, rows: int) -> tuple[int, list[tuple[str, str]]]:
        """当前可见的左栏窗口（父目录/子目录/图片一起算行）。"""
        if rows <= 0:
            return 0, []
        start = self.sel_row - rows + 1 if self.sel_row >= rows else 0
        start = max(0, min(start, max(0, len(self.rows) - rows)))
        return start, self.rows[start : start + rows]

    def select_by_digit(self, digit: int) -> bool:
        """数字键 1..9、0(=10) 快速选中当前窗口里的第 N 张图片（目录行不计数）。"""
        max_rows = max(1, self.img_rows)
        start, visible = self.image_window(max_rows)
        idx = digit - 1
        seen = 0
        for offset, (kind, _path) in enumerate(visible):
            if kind != "img":
                continue
            if seen == idx:
                if self.focus == "files" and self.cur is not None:
                    self.cur.sel = self.sel_blk
                self.sel_row = start + offset
                self.ensure_blocks()
                self.sel_blk = self.cur.sel if self.cur else 0
                if self.focus != "files":
                    self.focus = "files"
                return True
            seen += 1
        return False

    # ---- 移动

    def move(self, delta: int) -> None:
        if self.panel == "map":
            self.sel_map = max(0, min(max(0, len(self.mapping) - 1), self.sel_map + delta))
            return
        if self.focus == "files":
            img = self.cur
            if img is not None:
                img.sel = self.sel_blk
            self.sel_row = max(0, min(len(self.rows) - 1, self.sel_row + delta))
            self.ensure_blocks()
            self.sel_blk = self.cur.sel if self.cur else 0
        else:
            n = len(self.blocks())
            if n:
                self.sel_blk = max(0, min(n - 1, self.sel_blk + delta))

    def jump(self, first: bool) -> None:
        if self.panel == "map":
            self.sel_map = 0 if first else max(0, len(self.mapping) - 1)
            return
        if self.panel == "settings":
            self.sel_setting = 0 if first else len(SETTING_ROWS) - 1
            return
        if self.focus == "files":
            self.sel_row = 0 if first else max(0, len(self.rows) - 1)
            self.ensure_blocks()
            self.sel_blk = self.cur.sel if self.cur else 0
        else:
            self.sel_blk = 0 if first else max(0, len(self.blocks()) - 1)


def ocr_regions_safe(rgb):
    """OCR 在缺依赖时抛 SystemExit，这里转成可展示的错误。"""
    from ..core import ocr_regions

    return ocr_regions(rgb)
