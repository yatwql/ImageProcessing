"""替换任务（Job）与「映射表 → 任务」的匹配规则。"""

from __future__ import annotations

import difflib
import sys
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass


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


def plan_jobs(regions: list[dict], mapping: dict[str, str], warn: bool = True,
              sink: Callable[[str], None] | None = None) -> list["Job"]:
    """整行匹配到就整行替换；同时把其他行里出现的子串单独替换；都不中再模糊匹配。"""
    jobs: list[Job] = []
    for key, new in mapping.items():
        nk, _ = norm_map(key)
        if not nk:
            continue
        hit = False
        whole: set[int] = set()
        for i, r in enumerate(regions):
            if norm_map(r["text"])[0] == nk:
                jobs.append(Job(tuple(r["rect"]), r["text"], new))
                whole.add(i)
                hit = True
        for i, r in enumerate(regions):
            if i in whole:
                continue
            nt, idx = norm_map(r["text"])
            pos = nt.find(nk)
            while pos >= 0:
                jobs.append(Job(tuple(r["rect"]), r["text"], new,
                                (idx[pos], idx[pos + len(nk) - 1] + 1)))
                hit = True
                pos = nt.find(nk, pos + len(nk))
        if hit:
            continue
        best, score = None, 0.0
        for r in regions:
            v = difflib.SequenceMatcher(None, nk, norm_map(r["text"])[0]).ratio()
            if v > score:
                best, score = r, v
        if best is not None and score >= 0.8:
            jobs.append(Job(tuple(best["rect"]), best["text"], new))
            if sink is not None:
                sink(f"模糊匹配: {key!r} ≈ {best['text']!r} ({score:.2f})")
            elif warn:
                print(f"~ 模糊匹配: {key!r} ≈ {best['text']!r} ({score:.2f})", file=sys.stderr)
        elif warn:
            if sink is not None:
                sink(f"未找到待替换文字: {key!r}")
            else:
                print(f"! 未找到待替换文字: {key!r}", file=sys.stderr)
    return jobs
