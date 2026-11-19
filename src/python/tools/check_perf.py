#!/usr/bin/env python3
"""耗时守卫：把最热的几步钉住，退化即红。

    python tools/check_perf.py           # 人读
    python tools/check_perf.py --ci      # 只输出一行结论

不依赖 OCR 与系统字体（CI 上没有中文字体），只量：模糊 IoU、擦除 inpaint、
PNG 读写、写盘日志追加。阈值取本机实测值的 5 倍以上，只挡"数量级退化"，
不追求机器间可比。改动这里的阈值要同步 `docs/managements/technical.md`。
"""

from __future__ import annotations

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


def main(argv: Sequence[str] = ()) -> int:
    ensure_utf8_stdio()

    # 用空序列而不是 None 表示"没传参"，顺带避开 `x is None` 这类静态规则的噪音
    args = list(argv) if argv else sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    quiet = "--ci" in args
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
    with tempfile.TemporaryDirectory(dir=env_dir) as raw:
        tmp = Path(raw)
        for name, fn in checks:
            limit = limits[name]
            spent = _measure(fn, tmp, limit)
            if spent is None:
                failed.append(f"{name} 执行失败")
                continue
            total += spent
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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
