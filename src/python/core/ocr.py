"""OCR（RapidOCR，离线中英文）：整图文字块与区域文字。"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from .errors import CoreError

_LOCAL = threading.local()  # 每个线程一个引擎，批量并发时各跑各的


def _engine() -> Any:
    engine = getattr(_LOCAL, "engine", None)
    if engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise CoreError(
                "缺少 OCR 依赖：pip install rapidocr-onnxruntime （也可用 --area 手工指定区域）"
            ) from exc
        engine = RapidOCR()
        _LOCAL.engine = engine
    return engine


def _ocr(result: Any) -> list[dict[str, Any]]:
    out = []
    for box, txt, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1 = int(min(xs)), int(max(xs))
        y0, y1 = int(min(ys)), int(max(ys))
        if txt.strip():
            out.append({"text": txt, "rect": (x0, y0, x1 - x0, y1 - y0), "score": float(score)})
    return out


def ocr_regions(img_rgb: np.ndarray) -> list[dict[str, Any]]:
    res, _ = _engine()(img_rgb[:, :, ::-1].copy())
    return _ocr(res)


def ocr_crop(img_rgb: np.ndarray, rect: tuple[int, int, int, int]) -> str | None:
    x, y, w, h = rect
    crop = img_rgb[max(0, y) : y + h, max(0, x) : x + w]
    if crop.size == 0:
        return None
    res, _ = _engine()(crop[:, :, ::-1].copy())
    got = _ocr(res)
    if not got:
        return None
    got.sort(key=lambda g: (g["rect"][1], g["rect"][0]))
    return " ".join(g["text"] for g in got)
