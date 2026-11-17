"""擦除原字迹并重绘新文字（replace_image 是整条流水线）。"""

from __future__ import annotations

import os

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
    radius = int(round(stroke * INPAINT_STROKE_FACTOR))
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


def replace_image(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    jobs: list[Job],
    opts: Options,
    pool: list[FontFace],
    tag: str = "",
    memo: dict | None = None,
    source: str | None = None,
) -> tuple[np.ndarray, np.ndarray | None, list[dict]]:
    """在已加载的图上执行全部任务，返回 (新图, 新alpha, 报告)。

    memo: 可选的每图缓存，重复执行同一张图时跳过 OCR 分析/字体匹配（TUI 用）。
    source: 原图路径，仅用于给调试图的写盘日志记录源文件。
    """
    H, W = rgb.shape[:2]
    out = rgb.copy()
    report: list[dict] = []

    for idx, job in enumerate(jobs):
        key_a = ("a", tuple(job.rect))
        info = memo.get(key_a) if memo is not None else None
        if info is None:
            info = analyze(rgb, job.rect)
            if memo is not None and info is not None:
                memo[key_a] = info
        if info is None:
            warn(opts, f"区域 {job.rect} 未检测到文字，跳过")
            continue

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
            )
            if memo is not None:
                memo[key_f] = fit
        if fit is not None and fit[4] < 0.35:
            _log(f"匹配度过低 {fit[4]:.2f}，判定字体不可靠")
            fit = None
        if fit is None:
            face = FontFace(opts.font, 0) if opts.font else pool[0]
            hh = info["ink_box"][3] - info["ink_box"][1]
            size = opts.size or guess_size(hh, face)
            tracking, iou = 0.0, 0.0
            if job.src:
                warn(
                    opts,
                    f"{job.rect} 字体自动匹配不可靠（区域文字可能未被完整识别），"
                    f"已退回默认字体 {face.name}；可用 --font 指定",
                )
        else:
            _score, face, size, tracking, iou = fit
            if opts.size:
                size = opts.size
        if opts.tracking is not None:
            tracking = opts.tracking
        color = parse_color(opts.color) if opts.color else info["text_color"]

        o_l, o_t, o_r, o_b = info["ink_box"]
        span = job.span
        box = (float(o_l), float(o_r), float(o_t), float(o_b))
        erase_range = None
        if span and job.src:
            spans = char_spans(job.src, face, size, tracking, o_l)
            if spans and len(spans) >= span[1]:
                x_a = spans[span[0]][0]
                x_b = spans[span[1] - 1][1]
                sub = info["mask"][:, int(max(0, x_a)) : int(x_b)]
                ys = np.nonzero(sub)[0]
                if len(ys):
                    y_a, y_b = float(min(ys)), float(max(ys) + 1)
                else:
                    y_a, y_b = float(o_t), float(o_b)
                box = (x_a, x_b, y_a, y_b)
                erase_range = (x_a - 1.0, x_b + 1.0)
            else:
                span = None

        align = opts.align
        if align == "auto":
            if span:
                align = "center"
            else:
                align = "center" if abs((o_l + o_r) / 2.0 - W / 2.0) < 0.04 * W else "left"

        if opts.fit_width:
            tracking = solve_tracking(job.new, face, size, tracking, box[1] - box[0])

        out = erase(out, info["mask"], erase_range)
        if alpha is not None:
            alpha = erase(alpha, info["mask"], erase_range)
        out = draw_text(out, job.new, face, size, tracking, color, box, align, alpha_canvas=alpha)

        if opts.debug:
            try:
                os.makedirs(opts.debug, exist_ok=True)
            except OSError as e:
                raise CoreError(f"无法创建调试图目录: {e}") from e
            mask_path = os.path.join(opts.debug, f"{tag}mask_{idx:02d}.png")
            if not cv2.imwrite(mask_path, (info["mask"].astype(np.uint8) * 255)):
                raise CoreError(f"无法写出调试图: {mask_path}")
            if opts.log_dir:
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

        report.append(
            {
                "old": job.src,
                "new": job.new,
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
