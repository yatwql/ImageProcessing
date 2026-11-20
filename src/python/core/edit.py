"""擦除原字迹并重绘新文字（replace_image 是整条流水线）。"""

from __future__ import annotations

import os
from collections.abc import Callable

import cv2
import numpy as np

from .audit import ACTION_DEBUG, record_write
from .errors import CoreError
from .fonts import FontFace
from .match import Job
from .options import Options, _log, parse_color, warn
from .render import char_spans, draw_text, solve_tracking
from .style import analyze, fit_font, guess_size

# inpaint 半径：固定 4 在粗笔画（大标题、加粗）上会留下模糊边，
# 太大会把邻近的细笔画/纹理一起糊掉，所以按笔画宽度自适应。
INPAINT_RADIUS_MIN = 4
INPAINT_RADIUS_MAX = 14
INPAINT_STROKE_FACTOR = 0.75


def inpaint_radius(mask: np.ndarray) -> int:
    """按笔画宽度定 inpaint 半径：笔画越粗，需要覆盖的邻域越大。

    用距离变换的均值×2 估计笔画宽度（细体约 2~3px，粗体/大标题 10px+），
    再按系数换算成半径并夹到 [MIN, MAX]，保证细字不会被过度模糊。
    """
    m = (np.asarray(mask) > 0).astype(np.uint8)
    if int(m.sum()) == 0:
        return INPAINT_RADIUS_MIN
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    stroke = float(dt[m > 0].mean()) * 2.0
    radius = round(stroke * INPAINT_STROKE_FACTOR)
    return max(INPAINT_RADIUS_MIN, min(INPAINT_RADIUS_MAX, radius))


def erase(
    img: np.ndarray, mask: np.ndarray, x_range: tuple[float, float] | None = None
) -> np.ndarray:
    m: np.ndarray = mask.astype(np.uint8)
    if x_range is not None:
        keep = np.zeros_like(m)
        x0 = max(0, int(np.floor(x_range[0])))
        x1 = max(0, int(np.ceil(x_range[1])))
        keep[:, x0:x1] = 1
        m = m & keep
    if int(m.sum()) == 0:
        return img
    m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=1)
    m = (cv2.GaussianBlur(m * 255, (3, 3), 0) > 40).astype(np.uint8)
    return cv2.inpaint(img, m, inpaint_radius(m), cv2.INPAINT_TELEA)


Style = tuple[FontFace, int, float]
Box = tuple[float, float, float, float]   # (left, right, top, bottom)

# 同一块上多条任务时，记"哪些区间已经擦过"；None 表示整块
EraseLog = dict[tuple[int, int, int, int], set[tuple[float, float] | None]]


def _pick_style(
    job: Job,
    info: dict,
    opts: Options,
    pool: list[FontFace],
    fit: tuple[float, FontFace, int, float, float] | None,
) -> tuple[Style, float]:
    """定字体/字号/字距（含命令行的强制覆盖），返回 ((face, size, tracking), iou)。"""
    if fit is not None:
        _score, face, size, tracking, iou = fit
        if opts.size:
            size = opts.size
    else:
        if opts.font:
            face = FontFace(opts.font, 0)
        elif pool:
            face = pool[0]
        else:
            # 字体池为空（系统没字体 / --font 指向坏文件）时不能裸 IndexError，
            # 核心层只抛可预期异常，渠道据此提示一句就够
            raise CoreError("没有可用字体：请用 --font 指定字体文件，或安装中文字体")
        height = info["ink_box"][3] - info["ink_box"][1]
        size = opts.size or guess_size(height, face)
        tracking, iou = 0.0, 0.0
        if job.src:
            warn(
                opts,
                f"{job.rect} 字体自动匹配不可靠（区域文字可能未被完整识别），"
                f"已退回默认字体 {face.name}；可用 --font 指定",
            )
    if opts.tracking is not None:
        tracking = opts.tracking
    return (face, size, tracking), iou


def _resolve_box(
    job: Job, info: dict, style: Style
) -> tuple[tuple[int, int] | None, Box, tuple[float, float] | None]:
    """算这一块的绘制框与擦除区间；行内命中时收窄到那几个字的横向范围。"""
    face, size, tracking = style
    o_l, o_t, o_r, o_b = info["ink_box"]
    span = job.span
    box = (float(o_l), float(o_r), float(o_t), float(o_b))
    erase_range = None
    if not (span and job.src):
        return span, box, erase_range
    spans = char_spans(job.src, face, size, tracking, o_l)
    if not (spans and len(spans) >= span[1]):
        return None, box, None
    x_a = spans[span[0]][0]
    x_b = spans[span[1] - 1][1]
    sub = info["mask"][:, int(max(0, x_a)) : int(x_b)]
    ys = np.nonzero(sub)[0]
    if len(ys):
        y_a, y_b = float(min(ys)), float(max(ys) + 1)
    else:
        y_a, y_b = float(o_t), float(o_b)
    return span, (x_a, x_b, y_a, y_b), (x_a - 1.0, x_b + 1.0)


def _resolve_align(opts: Options, span: tuple[int, int] | None, box: Box, width: int) -> str:
    """`auto`：行内一律居中；整行看原文字块是否基本居中，否则左对齐。"""
    if opts.align != "auto":
        return opts.align
    if span:
        return "center"
    centre = abs((box[0] + box[1]) / 2.0 - width / 2.0)
    return "center" if centre < 0.04 * width else "left"


def _paint(
    out: np.ndarray,
    alpha: np.ndarray | None,
    info: dict,
    job: Job,
    style: Style,
    box: Box,
    align: str,
    color: tuple[int, int, int],
    erased: EraseLog,
    erase_range: tuple[float, float] | None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """擦掉原字迹再写新文字；同一块已擦过的区间不再擦第二遍。"""
    face, size, tracking = style
    done = erased.setdefault(job.rect, set())
    if not (erase_range in done or (erase_range is not None and None in done)):
        out = erase(out, info["mask"], erase_range)
        if alpha is not None:
            alpha = erase(alpha, info["mask"], erase_range)
        done.add(erase_range)
    return draw_text(
        out, job.new, face, size, tracking, color, box, align, alpha_canvas=alpha
    ), alpha


def _write_debug_mask(opts: Options, info: dict, tag: str, idx: int, source: str | None) -> None:
    """把这一块的二值 mask 写成调试图（并在 write 日志里留痕）。"""
    try:
        os.makedirs(opts.debug or "", exist_ok=True)
    except OSError as e:
        raise CoreError(f"无法创建调试图目录: {e}") from e
    mask_path = os.path.join(opts.debug or "", f"{tag}mask_{idx:02d}.png")
    if not cv2.imwrite(mask_path, (info["mask"].astype(np.uint8) * 255)):
        raise CoreError(f"无法写出调试图: {mask_path}")
    if not opts.log_dir:
        return
    try:
        record_write(
            source or mask_path,
            mask_path,
            (),
            log_dir=opts.log_dir,
            action=ACTION_DEBUG,
            channel=opts.channel,
            options=opts,
        )
    except CoreError as e:
        warn(opts, str(e))


def _analyse_and_fit(
    rgb: np.ndarray,
    job: Job,
    opts: Options,
    pool: list[FontFace],
    memo: dict | None,
    abort: Callable[[], bool] | None,
) -> tuple[dict | None, tuple[float, FontFace, int, float, float] | None, bool]:
    """分析这一块并匹配字体；返回 (info, fit, 是否被取消)。"""
    key_a = ("a", tuple(job.rect))
    info = memo.get(key_a) if memo is not None else None
    if info is None:
        info = analyze(rgb, job.rect)
        if memo is not None and info is not None:
            memo[key_a] = info
    if info is None:
        return None, None, False

    key_f = ("f", tuple(job.rect), job.src)
    fit = memo.get(key_f) if memo is not None else None
    if fit is None and job.src:
        fit = fit_font(
            job.src,
            info["mask"],
            info["ink_box"],
            pool,
            opts.max_fonts,
            a_stroke=info.get("stroke_core"),
            slant=info.get("slant"),
            abort=abort,
        )
        if abort is not None and abort():
            return info, None, True
        if memo is not None:
            memo[key_f] = fit
    if fit is not None and fit[4] < 0.35:
        _log(f"匹配度过低 {fit[4]:.2f}，判定字体不可靠")
        fit = None
    return info, fit, False


def replace_image(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    jobs: list[Job],
    opts: Options,
    pool: list[FontFace],
    tag: str = "",
    memo: dict | None = None,
    source: str | None = None,
    should_stop: Callable[[], bool] | None = None,
    abort: Callable[[], bool] | None = None,
) -> tuple[np.ndarray, np.ndarray | None, list[dict]]:
    """在已加载的图上执行全部任务，返回 (新图, 新alpha, 报告)。

    memo: 可选的每图缓存，重复执行同一张图时跳过 OCR 分析/字体匹配（TUI 用）。
    source: 原图路径，仅用于给调试图的写盘日志记录源文件。
    should_stop: 可选中断回调，每处理一块之前问一次；返回 True 就停手，
        已完成的块保留在报告里（调用方据此提示“已取消，完成 x/y”）。
    abort: 可选“随时可查”的中断标志，供字体匹配的候选循环轮询（不占用块边界的调用次数）。
    """
    _h, W = rgb.shape[:2]
    out = rgb.copy()
    report: list[dict] = []
    erased: EraseLog = {}

    for idx, job in enumerate(jobs):
        if should_stop is not None and should_stop():
            _log(f"已取消，完成 {len(report)}/{len(jobs)} 块")
            break
        info, fit, stopped = _analyse_and_fit(rgb, job, opts, pool, memo, abort)
        if stopped:
            _log(f"已取消，完成 {len(report)}/{len(jobs)} 块")
            break
        if info is None:
            warn(opts, f"区域 {job.rect} 未检测到文字，跳过")
            continue

        style, iou = _pick_style(job, info, opts, pool, fit)
        color = parse_color(opts.color) if opts.color else info["text_color"]
        hit = job.span
        fragment = job.src[hit[0] : hit[1]] if hit and job.src and hit[1] <= len(job.src) else None
        span, box, erase_range = _resolve_box(job, info, style)
        align = _resolve_align(opts, span, box, W)
        face, size, tracking = style
        if opts.fit_width:
            tracking = solve_tracking(job.new, face, size, tracking, box[1] - box[0])
            style = (face, size, tracking)

        if not opts.dry_run:  # 预演只要分析/匹配结果，不碰像素也不写图
            out, alpha = _paint(
                out, alpha, info, job, style, box, align, color, erased, erase_range
            )

        if opts.debug and not opts.dry_run:
            _write_debug_mask(opts, info, tag, idx, source)

        report.append(
            {
                "old": job.src,
                "new": job.new,
                "fragment": fragment,
                "span": list(hit) if hit else None,
                "rect": list(job.rect),
                "mode": "行内" if span else "整行",
                "font": face.name,
                "size": size,
                "tracking": round(tracking, 2),
                "color": list(color),
                "align": align,
                "iou": round(iou, 3),
            }
        )
    return out, alpha, report
