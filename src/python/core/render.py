"""文字排版渲染：行渲染、字符横向区间、绘制到画布。"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .fonts import FontFace

InkBox = tuple[int, int, int, int]


def render_line(
    text: str, face: FontFace, size: int, tracking: float = 0.0
) -> tuple[np.ndarray, InkBox, int]:
    """渲染单行，返回 (alpha HxW uint8, ink_box(l,t,r,b), pad)。"""
    font = face.font(size)
    adv = [font.getlength(c) for c in text]
    width = sum(adv) + tracking * max(0, len(text) - 1)
    asc, desc = font.getmetrics()
    pad = int(max(4, size * 0.45))
    W = int(width) + 2 * pad + 8
    H = asc + desc + 2 * pad
    img = Image.new("L", (max(1, W), max(1, H)), 0)
    d = ImageDraw.Draw(img)
    x = float(pad)
    base = pad + asc
    for c, a in zip(text, adv, strict=False):
        d.text((x, base), c, font=font, fill=255, anchor="ls")
        x += a + tracking
    arr = np.array(img)
    ys, xs = np.nonzero(arr > 8)
    if len(xs) == 0:
        return arr, (0, 0, 0, 0), pad
    # 用内建 min/max 而不是 ndarray 的方法：坐标数组很小，取值方式不影响耗时，
    # 但内建写法在 numpy 的类型桩下无需依赖任何配置就成立。
    return arr, (int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1), pad


def char_spans(
    text: str, face: FontFace, size: int, tracking: float, origin_x: float
) -> list[tuple[float, float]]:
    """整行墨迹左边界为 origin_x 时，反推每个字符的 [x0,x1]（图像坐标）。"""
    _arr, box, pad = render_line(text, face, size, tracking)
    if box[3] <= box[1]:
        return []
    font = face.font(size)
    off = origin_x - (box[0] - pad)
    spans = []
    x = 0.0
    for c in text:
        a = font.getlength(c)
        spans.append((off + x - tracking / 2.0, off + x + a + tracking / 2.0))
        x += a + tracking
    return spans


def ink_size(text: str, face: FontFace, size: int, tracking: float = 0.0) -> tuple[int, int]:
    _, (left, top, right, bottom), _ = render_line(text, face, size, tracking)
    return max(1, right - left), max(1, bottom - top)


def draw_text(
    canvas: np.ndarray,
    text: str,
    face: FontFace,
    size: int,
    tracking: float,
    color: tuple[int, int, int],
    box: tuple[float, float, float, float],
    align: str,
    alpha_canvas: np.ndarray | None = None,
) -> np.ndarray:
    """在参考框 box=(x0,x1,y0,y1) 内绘制；垂直居中，水平按 align。"""
    x0, x1, y0, y1 = box
    lines = text.split("\n")
    rendered: list[tuple[np.ndarray | None, InkBox]] = []
    for ln in lines:
        if ln == "":
            rendered.append((None, (0, 0, 0, 0)))
            continue
        arr, b, _ = render_line(ln, face, size, tracking)
        rendered.append((arr, b))

    heights = [b[3] - b[1] for a, b in rendered if a is not None] or [size]
    pitch = int(round(size * 1.34))
    total_h = pitch * (len(lines) - 1) + max(heights) if len(lines) > 1 else heights[0]
    y_cursor = (y0 + y1) / 2.0 - total_h / 2.0

    H, W = canvas.shape[:2]
    for arr_i, b in rendered:
        if arr_i is None:
            y_cursor += pitch
            continue
        left, top_, right, bottom = b
        nw, nh = right - left, bottom - top_
        if align == "left":
            x = x0
        elif align == "right":
            x = x1 - nw
        else:
            x = (x0 + x1) / 2.0 - nw / 2.0

        xi, yi = int(round(x)), int(round(y_cursor))
        px0, py0 = max(0, xi), max(0, yi)
        px1, py1 = min(W, xi + nw), min(H, yi + nh)
        if px1 <= px0 or py1 <= py0:
            y_cursor += pitch
            continue
        sx, sy = px0 - xi, py0 - yi
        patch = arr_i[top_:bottom, left:right].astype(np.float32) / 255.0
        a = patch[sy : sy + (py1 - py0), sx : sx + (px1 - px0)][..., None]
        dst = canvas[py0:py1, px0:px1].astype(np.float32)
        col = np.array(color, np.float32)[None, None, :]
        canvas[py0:py1, px0:px1] = np.clip(dst * (1 - a) + col * a + 0.5, 0, 255).astype(np.uint8)
        if alpha_canvas is not None:
            ac = alpha_canvas[py0:py1, px0:px1]
            alpha_canvas[py0:py1, px0:px1] = np.maximum(ac, (a[..., 0] * 255).astype(np.uint8))
        y_cursor += pitch
    return canvas


def solve_tracking(text: str, face: FontFace, size: int, tracking: float, target_w: float) -> float:
    flat = text.replace("\n", "")
    if len(flat) < 2:
        return tracking
    for _ in range(4):
        nw = ink_size(flat, face, size, tracking)[0]
        if nw <= 0:
            break
        tracking += (target_w - nw) / (len(flat) - 1)
        tracking = float(np.clip(tracking, -0.35 * size, 1.6 * size))
    return tracking
