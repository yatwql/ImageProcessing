"""编号守护：台账编号连续唯一、旧前缀不复用、归档编号仍占号（守护第 1~2 项）。"""

from __future__ import annotations

import re

from .._paths import ROOT
from .common import (
    ARCHIVE,
    DOCS,
    LEGACY_ID,
    ROW_ID,
    _read,
)


def _id_number(rid: str) -> int:
    """PLAN-12 → 12（排序用；解析不了就排到最前，不因脏数据抛异常）。"""
    try:
        return int(rid.split("-")[1])
    except (IndexError, ValueError):
        return -1


def check_plan_ids() -> list[str]:
    """plan.md 的任务编号必须是 PLAN-x：唯一、递增，且不与归档里的编号重复。

    归档会把已完成项整块搬走，主文件编号因此可能不再从 1 连续；「不复用」改由
    「与 `docs/archive/` 里出现过的编号不得重复」保证（归档前仍要求从 1 连续）。
    """
    path = DOCS / "plan.md"
    if not path.is_file():
        return ["缺少 docs/managements/plan.md"]
    nums = []
    bad = []
    for line in _read(path).splitlines():
        m = ROW_ID.match(line)
        if not m:
            continue
        rid = m.group(1)
        if not rid.startswith("PLAN-"):
            bad.append(rid)
            continue
        try:
            nums.append(int(rid.split("-")[1]))
        except (IndexError, ValueError):
            bad.append(rid)
    if bad:
        return [f"plan.md 出现非 PLAN- 编号：{', '.join(sorted(set(bad))[:5])}"]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    if dups:
        return [f"plan.md 编号重复：{dups[:5]}"]
    if nums != sorted(nums):
        return ["plan.md 的编号没有按出现顺序递增"]
    archived = _archived_ids("archived_plan", "PLAN")
    reused = sorted({f"PLAN-{n}" for n in nums} & archived.keys(), key=_id_number)
    if reused:
        return [f"plan.md 复用了已归档编号 {', '.join(reused[:5])}（见 {archived[reused[0]]}）"]
    if not archived and nums != list(range(1, len(nums) + 1)):
        return [f"plan.md 编号不连续（共 {len(nums)} 条），归档前必须从 PLAN-1 起连续"]
    return []


def _archived_ids(stem: str, prefix: str) -> dict[str, str]:
    """归档文件里出现过的编号 → 归档文件相对路径（用于「编号不复用」核对）。"""
    found: dict[str, str] = {}
    if not ARCHIVE.is_dir():
        return found
    for path in sorted(ARCHIVE.rglob(f"{stem}.*.md")):
        rel = path.relative_to(ROOT).as_posix()
        for rid in set(re.findall(rf"\b{prefix}-\d+\b", _read(path))):
            found.setdefault(rid, rel)
    return found


def check_rf_ids() -> list[str]:
    """review-findings.md 的任务编号必须是 RF-x（唯一），且不出现旧前缀。"""
    path = DOCS / "review-findings.md"
    if not path.is_file():
        return ["缺少 docs/managements/review-findings.md"]
    text = _read(path)
    ids = [m.group(1) for m in (ROW_ID.match(line) for line in text.splitlines()) if m]
    bad = [i for i in ids if not i.startswith("RF-")]
    if bad:
        return [f"review-findings.md 出现非 RF- 编号：{', '.join(sorted(set(bad))[:5])}"]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        return [f"review-findings.md 编号重复：{', '.join(dups[:5])}"]
    legacy = sorted(set(LEGACY_ID.findall(text)))
    if legacy:
        return [f"review-findings.md 残留旧编号：{', '.join(legacy[:5])}"]
    archived = _archived_ids("archived_review-findings", "RF")
    reused = sorted(set(ids) & archived.keys(), key=_id_number)
    if reused:
        return [
            f"review-findings.md 复用了已归档编号 {', '.join(reused[:5])}"
            f"（见 {archived[reused[0]]}）"
        ]
    return []
