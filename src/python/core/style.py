"""版式分析：字迹 mask、字色、笔画粗细、字体/字号/字距反解。"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .fonts import FontFace
from .options import _log
from .render import InkBox, ink_size, render_line


def _bin(mask: np.ndarray, box: InkBox) -> np.ndarray:
    left, top, right, bottom = box
    return mask[top:bottom, left:right] > 127


def stroke_of(binary: np.ndarray) -> float:
    m = (binary.astype(np.uint8) > 0).astype(np.uint8)
    if m.sum() == 0:
        return 0.0
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    return float(2.0 * np.percentile(dt[m > 0], 75))


def soft_iou(A: np.ndarray, B: np.ndarray, radius: int = 3) -> float:
    """模糊 IoU：先模糊再平移搜索，能容忍 1px 级的栅格化差异。"""
    ha, wa = A.shape
    hb, wb = B.shape
    if min(ha, wa, hb, wb) == 0:
        return 0.0
    H, W = max(ha, hb) + 2 * radius, max(wa, wb) + 2 * radius
    fa: np.ndarray = np.zeros((H, W), np.float32)
    fa[(H - ha) // 2 : (H - ha) // 2 + ha, (W - wa) // 2 : (W - wa) // 2 + wa] = A
    fb_small: np.ndarray = np.zeros((hb, wb), np.float32)
    fb_small[:] = B
    # 模糊与平移无关，先各自模糊一次，循环里只做搬移和逐元素运算
    fa = cv2.GaussianBlur(fa, (0, 0), 1.0)
    fb_small = cv2.GaussianBlur(fb_small, (0, 0), 1.0)
    fb = np.zeros((H, W), np.float32)
    by, bx = (H - hb) // 2, (W - wb) // 2
    best = 0.0
    for dy in range(-radius, radius + 1):
        y = by + dy
        if y < 0 or y + hb > H:
            continue
        for dx in range(-radius, radius + 1):
            x = bx + dx
            if x < 0 or x + wb > W:
                continue
            fb[:] = 0
            fb[y : y + hb, x : x + wb] = fb_small
            inter = float(np.minimum(fa, fb).sum())
            union = float(np.maximum(fa, fb).sum())
            if union > 0:
                v = inter / union
                if v > best:
                    best = v
    return best


def analyze(img_rgb: np.ndarray, rect: tuple[int, int, int, int]) -> dict[str, Any] | None:
    """分析文字块：mask / 墨迹框 / 字色 / 笔画粗细。"""
    x, y, w, h = rect
    H, W = img_rgb.shape[:2]
    ex = max(6, int(h * 0.7))
    cx0, cy0 = max(0, x - ex), max(0, y - ex)
    cx1, cy1 = min(W, x + w + ex), min(H, y + h + ex)
    crop = img_rgb[cy0:cy1, cx0:cx1]
    ch, cw = crop.shape[:2]
    if ch < 4 or cw < 4:
        return None

    # 背景估计：中值窗口必须远大于笔画宽度，否则笔画中心会被当成背景（mask 变空心）
    k = min(int(max(9, round(h * 1.3)) // 2 * 2 + 1), (min(ch, cw) - 1) // 2 * 2 + 1)
    bg_est = cv2.medianBlur(crop, k) if k >= 3 else cv2.blur(crop, (3, 3))
    dist = np.abs(crop.astype(np.int16) - bg_est.astype(np.int16)).max(axis=2).astype(np.uint8)
    if int(max(dist.ravel())) < 6:
        return None
    tight = np.zeros((ch, cw), np.uint8)
    tight[
        max(0, y - cy0 - 2) : min(ch, y - cy0 + h + 2),
        max(0, x - cx0 - 2) : min(cw, x - cx0 + w + 2),
    ] = 1

    # 用区内最大色差反推阈值：Otsu 在"背景占多数"时阈值会塌到 0，不可靠
    dmax = float(max(dist[tight.astype(bool)]))
    m: np.ndarray = np.zeros((ch, cw), np.uint8)
    for frac in (0.45, 0.3, 0.2):
        m = ((dist >= max(14.0, dmax * frac)).astype(np.uint8)) & tight
        if int(m.sum()) >= 12:
            break
    if int(m.sum()) < 12:
        return None
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    # 更严格的阈值再取一次"笔画核心"：字重判别用它，避免抗锯齿把常规体看成粗体
    m_core: np.ndarray = ((dist >= max(16.0, dmax * 0.72)).astype(np.uint8)) & tight
    m_core = cv2.morphologyEx(m_core, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    core_stroke = stroke_of(m_core) if int(m_core.sum()) >= 20 else 0.0
    ys, xs = np.nonzero(m)
    ink = (int(min(xs)) + cx0, int(min(ys)) + cy0, int(max(xs)) + 1 + cx0, int(max(ys)) + 1 + cy0)

    # 字色：取色差最大的那批像素（笔画核心），腐蚀在细笔画上会失效
    sel = (dist >= np.percentile(dist[m.astype(bool)], 80)) & m.astype(bool)
    if int(sel.sum()) < 6:
        sel = m.astype(bool)
    text_color = np.median(crop[sel], axis=0)

    # 倾斜估计：下半部墨迹质心相对上半部的横向偏移（斜体字会明显偏移）
    ys_m, xs_m = np.nonzero(m)
    slant = 0.0
    if len(xs_m) > 20:
        mid = (min(ys_m) + max(ys_m)) / 2.0
        upper = xs_m[ys_m < mid]
        lower = xs_m[ys_m >= mid]
        if len(upper) > 5 and len(lower) > 5:
            span = max(1.0, float(max(ys_m) - min(ys_m)))
            slant = float(lower.mean() - upper.mean()) / span

    full = np.zeros((H, W), np.uint8)
    full[cy0:cy1, cx0:cx1] = m
    return {
        "mask": full.astype(bool),
        "ink_box": ink,
        "text_color": tuple(int(round(v)) for v in text_color),
        "stroke": stroke_of(m),
        "stroke_core": core_stroke,
        "slant": slant,
    }


def _is_italic(face: FontFace) -> bool:
    name = face.name.lower()
    return any(k in name for k in ("italic", "oblique"))


def fit_font(
    text: str,
    mask: np.ndarray,
    ink_box: InkBox,
    pool: list[FontFace],
    max_eval: int,
    a_stroke: float | None = None,
    slant: float | None = None,
) -> tuple[float, FontFace, int, float, float] | None:
    """找出与原文字最像的 (score, 字体, 字号, 字距, iou)。

    字距分两轮搜索：先只允许正常排版范围（±0.35em），避免靠大间距"作弊"；
    若整体都不像（例如稀疏排布的大字标题），再放开到 ±1.6em 重搜一次。
    """
    A = _bin(mask.astype(np.uint8) * 255, ink_box)
    h_mask = ink_box[3] - ink_box[1]
    w_mask = ink_box[2] - ink_box[0]
    if h_mask < 4 or int(A.sum()) < 8:
        return None
    if a_stroke is None or a_stroke <= 0:
        a_stroke = stroke_of(A)
    # 正体字就别拿斜体去凑：倾斜很小时过滤掉 italic/oblique
    if slant is not None and abs(slant) < 0.10:
        upright = [f for f in pool if not _is_italic(f)]
        if len(upright) >= 4:
            pool = upright
    n_gap = max(1, len(text) - 1)

    def search(track_limit: float) -> tuple[float, FontFace, int, float, float] | None:
        coarse: list[tuple[float, FontFace, int, float]] = []
        for face in pool[:max_eval]:
            try:
                h100 = ink_size(text, face, 100)[1]
                if h100 <= 0:
                    continue
                size = max(6, int(round(100.0 * h_mask / h100)))
                track0 = 0.0
                for _ in range(2):
                    w_fit = ink_size(text, face, size, track0)[0]
                    if w_fit <= 0:
                        break
                    track0 += (w_mask - w_fit) / n_gap
                # 字距残差多半是抗锯齿导致的 1~2px 宽度误差，小幅一律归零
                if abs(track0) < 0.12 * size:
                    track0 = 0.0
                if abs(track0) > track_limit * size:
                    continue
                arr, box, _ = render_line(text, face, size, track0)
                coarse.append((soft_iou(A, _bin(arr, box), radius=3), face, size, track0))
            except (OSError, ValueError) as exc:
                _log(f"渲染失败 {face.name}: {exc}")
        if not coarse:
            return None
        coarse.sort(key=lambda t: -t[0])

        best = None
        for rank, (_s, face, size, track0) in enumerate(coarse[:8]):
            ds_range = (-3, -2, -1, 0, 1, 2, 3) if rank < 3 else (-2, -1, 0, 1, 2)
            for ds in ds_range:
                sz = max(6, size + ds)
                for tr in (-0.04, -0.02, 0.0, 0.02, 0.04):
                    tracking = track0 + tr * sz
                    try:
                        arr, box, _ = render_line(text, face, sz, tracking)
                    except (OSError, ValueError) as exc:
                        _log(f"渲染失败 {face.name}: {exc}")
                        continue
                    B = _bin(arr, box)
                    if int(B.sum()) < 8:
                        continue
                    sim = soft_iou(A, B, radius=2)
                    b_stroke = stroke_of(B)
                    pen = 1.0
                    if a_stroke > 0.5 and b_stroke > 0.5:
                        pen = (min(a_stroke, b_stroke) / max(a_stroke, b_stroke)) ** 0.7
                    v = sim * pen
                    if best is None or v > best[0]:
                        best = (v, face, sz, tracking, sim)
        return best

    best = search(0.35)
    if best is None or best[4] < 0.5:
        wide = search(1.6)
        if wide is not None and (best is None or wide[4] > best[4]):
            best = wide
    return best


def guess_size(ink_h: float, face: FontFace) -> int:
    """不知道原文时，按墨迹高度反解字号。"""
    _arr, box, _ = render_line("国国", face, 100)
    h = max(1, box[3] - box[1])
    return max(6, int(round(100.0 * ink_h / h)))
