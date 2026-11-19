"""替换任务（Job）与「映射表 → 任务」的匹配规则。"""

from __future__ import annotations

import difflib
import sys
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from .options import FUZZY_MIN, MIN_OCR_SCORE


@dataclass
class Job:
    """一处替换：在 rect 里把 src 换成 new；span 非空表示只换这一行里的那几个字。"""

    rect: tuple[int, int, int, int]
    src: str | None
    new: str
    span: tuple[int, int] | None = None


def norm_map(text: str) -> tuple[str, list[int]]:
    """去掉空白/零宽字符并做逐字 NFKC，返回 (归一化文本, 每个字符对应的原文下标)。

    逐字归一化而不是整串，是为了让下标始终能映射回原文，行内替换才能算准区间。
    """
    chars, idx = [], []
    for i, ch in enumerate(text):
        if ch.isspace() or unicodedata.category(ch) == "Cf":
            continue
        n = unicodedata.normalize("NFKC", ch)
        if len(n) != 1:
            n = ch
        chars.append(n)
        idx.append(i)
    return "".join(chars), idx


def _claim(
    claimed: dict[tuple[int, int, int, int], list[tuple[int, int] | None]],
    rect: tuple[int, int, int, int],
    span: tuple[int, int] | None,
) -> bool:
    """占住 (rect, 区间)；同一块上已被整块占用、或同一区间被占过就返回 False。

    整块替换与任何同块任务互斥；同一块上的不同片段互不冲突（各自擦各自的区间）。
    """
    used = claimed.setdefault(rect, [])
    if span is None:
        if used:
            return False
        used.append(None)
        return True
    if None in used or span in used:
        return False
    used.append(span)
    return True


def _prep(
    regions: list[dict], min_score: float, say: Callable[[str], None]
) -> list[tuple[tuple[int, int, int, int], str, str, list[int]]]:
    """过滤低置信块，并把归一化结果算好（后面三轮都复用，避免平方级重算）。"""
    prep: list[tuple[tuple[int, int, int, int], str, str, list[int]]] = []
    low = 0
    for r in regions:
        if _score_of(r) < min_score:
            low += 1
            continue
        nt, idx = norm_map(r["text"])
        prep.append((tuple(r["rect"]), r["text"], nt, idx))
    if low:
        say(f"跳过 {low} 块置信度过低的文字（score<{min_score:g}）")
    return prep


def _score_of(region: dict) -> float:
    """OCR 置信度；不给分（内部构造的块）按满分算。"""
    try:
        return float(region.get("score", 1.0))
    except (TypeError, ValueError):
        return 1.0


def plan_jobs(
    regions: list[dict],
    mapping: dict[str, str],
    warn: bool = True,
    sink: Callable[[str], None] | None = None,
    min_score: float = MIN_OCR_SCORE,
    fuzzy_min: float = FUZZY_MIN,
    should_stop: Callable[[], bool] | None = None,
) -> list[Job]:
    """整行匹配到就整行替换；同时把其他行里出现的子串单独替换；都不中再模糊匹配。

    min_score: 低于该置信度的 OCR 块不参与匹配（保护手抖/斜体误识别）。
    fuzzy_min: 模糊兜底的最低相似度。
    同一块被两条映射同时命中时保留先到的一条，并报冲突，不静默覆盖。
    """
    jobs: list[Job] = []

    def say(msg: str) -> None:
        if sink is not None:
            sink(msg)
        elif warn:
            print(f"! {msg}", file=sys.stderr)

    prep = _prep(regions, min_score, say)
    claimed: dict[tuple[int, int, int, int], list[tuple[int, int] | None]] = {}

    def add(
        rect: tuple[int, int, int, int],
        src: str,
        new: str,
        span: tuple[int, int] | None,
        key: str,
    ) -> None:
        if _claim(claimed, rect, span):
            jobs.append(Job(rect, src, new, span))
        else:
            say(f"映射冲突：{key!r} 与已有任务在 {rect} 重叠，已跳过该条")

    for key, new in mapping.items():
        nk, _ = norm_map(key)
        if not nk:
            continue
        if _match_known(prep, nk, new, key, add):
            continue
        if should_stop is not None and should_stop():
            break
        _match_fuzzy(prep, nk, new, key, add, say, warn, fuzzy_min)
    return jobs


def _match_known(
    prep: list[tuple[tuple[int, int, int, int], str, str, list[int]]],
    nk: str,
    new: str,
    key: str,
    add: Callable[..., None],
) -> bool:
    """整行命中 + 其他行里的所有子串命中；一个都没中返回 False。"""
    hit = False
    whole: set[int] = set()
    for i, (rect, text, nt, _idx) in enumerate(prep):
        if nt == nk:
            add(rect, text, new, None, key)
            whole.add(i)
            hit = True
    for i, (rect, text, nt, idx) in enumerate(prep):
        if i in whole:
            continue
        pos = nt.find(nk)
        while pos >= 0:
            add(rect, text, new, (idx[pos], idx[pos + len(nk) - 1] + 1), key)
            hit = True
            pos = nt.find(nk, pos + len(nk))
    return hit


def _match_fuzzy(
    prep: list[tuple[tuple[int, int, int, int], str, str, list[int]]],
    nk: str,
    new: str,
    key: str,
    add: Callable[..., None],
    say: Callable[[str], None],
    warn: bool,
    fuzzy_min: float,
) -> None:
    """全都搜不到时的兼容处理：取最相似的一行，够像就整行替换并报提示。"""
    best, score = None, 0.0
    for rect, text, nt, _idx in prep:
        v = difflib.SequenceMatcher(None, nk, nt).ratio()
        if v > score:
            best, score = (rect, text), v
    if best is not None and score >= fuzzy_min:
        add(best[0], best[1], new, None, key)
        if say is not None and warn:
            say(f"模糊匹配: {key!r} ≈ {best[1]!r} ({score:.2f})")
        return
    if warn:
        say(f"未找到待替换文字: {key!r}")
