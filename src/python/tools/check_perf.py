#!/usr/bin/env python3
"""耗时守卫：把最热的几步钉住，退化即红。

    python tools/check_perf.py           # 人读
    python tools/check_perf.py --ci      # 只输出一行结论

不依赖 OCR 与系统字体（CI 上没有中文字体），只量：模糊 IoU、擦除 inpaint、
PNG 读写、写盘日志追加。阈值取本机实测值的 5 倍以上，只挡"数量级退化"，
不追求机器间可比。改动这里的阈值要同步 `docs/managements/technical.md`。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from src.python.core import audit, edit, image
from src.python.core.style import soft_iou
from src.python.stdio import ensure_utf8_stdio

from ._paths import ROOT

# 单步上限（秒）。CI 机器比开发机慢，留足余量。
LIMITS = {
    "soft_iou×50": 1.0,
    "erase(2000×1500)": 1.5,
    "PNG 读写(2000×1500)": 2.0,
    "日志追加×300": 1.0,
}
TOTAL_LIMIT = 6.0

# Windows runner 的 fsync 比 Linux 慢一个量级（日志追加×300 实测 3.5s vs 上限 1.0s）。
# 这里只放大"落盘相关"的那一步与总上限：其余步骤在两平台上本来就同量级，
# 放大它们等于把门禁调松，挡不住真实退化。
WINDOWS_SCALE = {"日志追加×300": 5.0}
WINDOWS_TOTAL_SCALE = 4.0


def limits_for(is_windows: bool) -> tuple[dict[str, float], float]:
    limits = dict(LIMITS)
    total = TOTAL_LIMIT
    if is_windows:
        for name, factor in WINDOWS_SCALE.items():
            limits[name] = round(limits[name] * factor, 2)
        total = round(total * WINDOWS_TOTAL_SCALE, 2)
    return limits, total


def _noise_mask(w: int, h: int) -> np.ndarray:
    rng = np.random.default_rng(7)
    return (rng.random((h, w)) > 0.85).astype(bool)


def bench_soft_iou() -> None:
    a = _noise_mask(220, 48)
    b = _noise_mask(220, 48)
    for _ in range(50):
        soft_iou(a, b, radius=3)


def bench_erase(_tmp: Path) -> None:
    img = np.full((1500, 2000, 3), 250, np.uint8)
    mask = np.zeros((1500, 2000), bool)
    mask[600:660, 500:800] = True
    edit.erase(img, mask)


def bench_png(tmp: Path) -> None:
    img = np.random.default_rng(3).integers(0, 255, (1500, 2000, 3), dtype=np.uint8)
    path = str(tmp / "perf.png")
    image.save_image(img, None, path)
    image.load_image(path)


def bench_audit(tmp: Path) -> None:
    log_dir = tmp / "logs"
    for i in range(300):
        audit.record_write(
            src="a.png",
            dst=f"b-{i}.png",
            action="替换",
            channel="perf",
            report=[{"old": "2023", "new": "2024"}],
            log_dir=str(log_dir),
        )


def _measure(fn: Callable[[Path], None], tmp: Path, limit: float) -> float | None:
    """跑一次；超限再跑一次取最小值。

    CI 与开发机都可能被别的进程抢占（并行跑的 mypy、冷磁盘缓存），
    单次读数偶发超限；门禁要么稳定，要么就会被当成噪音忽略掉。
    """
    best: float | None = None
    for _attempt in range(2):
        started = time.perf_counter()
        try:
            fn(tmp)
        except Exception:  # 跑不动本身就是缺陷，交给调用方报错
            return None
        spent = time.perf_counter() - started
        best = spent if best is None else min(best, spent)
        if spent <= limit:
            break
    return best


# 性能台账：只做"观察"，**不参与门槛判定**（机器/负载不同，历史值不可比）。
# 门禁永远是"当前这次 vs 固定上限"；台账用来回答"这周是不是越来越慢"。
PERF_LOG = ROOT / "logs" / "perf.jsonl"


def append_record(total: float, results: dict[str, float], limits: dict[str, float]) -> str | None:
    """把本次四步实测追加进台账（一行一条 JSON），失败返回 None。

    台账是**观察**用的，写不了（只读盘/权限）不能影响门禁结论——所以这里自己接住 OSError。
    """
    try:
        PERF_LOG.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    entry = {
        "when": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": sys.platform,
        "total": round(total, 3),
        "steps": {name: round(sec, 3) for name, sec in results.items()},
        "limits": {name: round(lim, 3) for name, lim in limits.items()},
    }
    try:
        with open(PERF_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return str(PERF_LOG)


def read_history(limit: int) -> list[dict[str, object]]:
    """最近 `limit` 条台账（读不了/坏行跳过，不影响门禁结论）。"""
    if not PERF_LOG.is_file():
        return []
    rows: list[dict[str, object]] = []
    try:
        for line in PERF_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-max(1, limit) :]


def print_history(rows: list[dict[str, object]]) -> None:
    """打印趋势：合计秒数与每一步的最慢值，够看"是否在退化"。"""
    if not rows:
        print("（台账为空：先跑一次 --record）")
        return
    print(f"最近 {len(rows)} 次实测（合计秒 / 各步最慢）：")
    for row in rows:
        steps = row.get("steps") or {}
        worst = max(steps.items(), key=lambda kv: kv[1]) if isinstance(steps, dict) else ("-", 0)
        print(f"  {row.get('when')}  {row.get('total')}s  最慢 {worst[0]} {worst[1]}s")


def _history_limit(args: list[str]) -> int:
    """`--history` 取最近 N 条（默认 10）；`--history=5` 也认。"""
    for i, arg in enumerate(args):
        if arg == "--history":
            nxt = args[i + 1] if i + 1 < len(args) else ""
            return int(nxt) if nxt.isdigit() else 10
        if arg.startswith("--history="):
            value = arg.split("=", 1)[1]
            return int(value) if value.isdigit() else 10
    return 0


def main(argv: Sequence[str] = ()) -> int:
    ensure_utf8_stdio()

    # 用空序列而不是 None 表示"没传参"，顺带避开 `x is None` 这类静态规则的噪音
    args = list(argv) if argv else sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    quiet = "--ci" in args
    record = "--record" in args
    history = _history_limit(args)
    env_dir = os.environ.get("IMG_P_TMP_DIR")
    limits, total_limit = limits_for(os.name == "nt")
    checks: list[tuple[str, Callable[[Path], None]]] = [
        ("soft_iou×50", lambda _t: bench_soft_iou()),
        ("erase(2000×1500)", bench_erase),
        ("PNG 读写(2000×1500)", bench_png),
        ("日志追加×300", bench_audit),
    ]
    failed = []
    total = 0.0
    results: dict[str, float] = {}
    with tempfile.TemporaryDirectory(dir=env_dir) as raw:
        tmp = Path(raw)
        for name, fn in checks:
            limit = limits[name]
            spent = _measure(fn, tmp, limit)
            if spent is None:
                failed.append(f"{name} 执行失败")
                continue
            total += spent
            results[name] = spent
            verdict = "ok" if spent <= limit else "SLOW"
            if spent > limit:
                failed.append(f"{name} 用了 {spent:.2f}s（上限 {limit:.1f}s）")
            if not quiet:
                print(f"[{verdict:4}] {name}: {spent:.2f}s / {limit:.1f}s")

    if total > total_limit:
        failed.append(f"合计 {total:.2f}s（上限 {total_limit:.1f}s）")
    if quiet:
        status = "FAIL" if failed else "ok"
        print(
            f"perf: {status} 合计 {total:.2f}s / {total_limit:.1f}s"
            + (f"（{failed[0]}）" if failed else "")
        )
    else:
        print(f"合计 {total:.2f}s / 上限 {total_limit:.1f}s")
        for msg in failed:
            print(f"[FAIL] {msg}")
    if record and results:  # 台账只记录、不影响结论
        path = append_record(total, results, limits)
        if not quiet:
            print(f"[..] 已记入性能台账：{path}" if path else "[!] 台账写入失败（不影响门禁）")
    if history:
        print_history(read_history(history))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
