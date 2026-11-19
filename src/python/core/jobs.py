"""把「映射表 / 手工区域 / TUI 里的块」统一变成 Job 列表。"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from .errors import CoreError
from .match import Job, norm_map, plan_jobs
from .ocr import ocr_crop, ocr_regions
from .options import FUZZY_MIN, MIN_OCR_SCORE


def area_jobs(specs: list[str]) -> list[Job]:
    jobs: list[Job] = []
    for spec in specs:
        if "=" not in spec:
            raise CoreError(f"--area 格式错误: {spec}（应为 x,y,w,h=新文字）")
        xywh, new = spec.split("=", 1)
        try:
            x, y, w, h = (round(float(v)) for v in re.split(r"[,\s]+", xywh.strip()))
        except ValueError as exc:
            raise CoreError(f"--area 坐标错误: {xywh}") from exc
        jobs.append(Job((x, y, w, h), None, new))
    return jobs


def make_jobs(
    rgb: np.ndarray,
    mapping: dict[str, str],
    areas: list[str],
    *,
    min_score: float = MIN_OCR_SCORE,
    fuzzy_min: float = FUZZY_MIN,
    should_stop: Callable[[], bool] | None = None,
) -> list[Job]:
    """把映射表 + 手工区域变成具体的替换任务（含原文字来源）。"""
    jobs: list[Job] = area_jobs(areas)
    if mapping:
        jobs += plan_jobs(
            ocr_regions(rgb),
            mapping,
            min_score=min_score,
            fuzzy_min=fuzzy_min,
            should_stop=should_stop,
        )
    for job in jobs:
        if job.src is None:
            job.src = ocr_crop(rgb, job.rect)
    return jobs


def jobs_from_blocks(
    blocks: Sequence[Any],
    mapping: dict[str, str],
    warn: bool = True,
    sink: Callable[[str], None] | None = None,
    min_score: float = MIN_OCR_SCORE,
    fuzzy_min: float = FUZZY_MIN,
) -> list[Job]:
    """TUI 用：块级自定义优先，其余块交给全局映射（支持行内子串）。"""
    jobs: list[Job] = []
    rest: list[dict] = []
    for blk in blocks:
        if not blk.enabled:
            continue
        if blk.override:
            span = None
            if blk.find:
                nt, idx = norm_map(blk.text)
                nf, _ = norm_map(blk.find)
                pos = nt.find(nf) if nf else -1
                if pos >= 0:
                    span = (idx[pos], idx[pos + len(nf) - 1] + 1)
            jobs.append(Job(blk.rect, blk.text, blk.override, span))
        else:
            rest.append({"text": blk.text, "rect": blk.rect, "score": 1.0})
    if rest and mapping:
        jobs += plan_jobs(
            rest, mapping, warn=warn, sink=sink, min_score=min_score, fuzzy_min=fuzzy_min
        )
    return jobs
