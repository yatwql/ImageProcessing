#!/usr/bin/env python3
"""耗时守卫：把最热的几步钉住，退化即红。

    python scripts/check-perf.py           # 人读
    python scripts/check-perf.py --ci      # 只输出一行结论

不依赖 OCR 与系统字体（CI 上没有中文字体），只量：模糊 IoU、擦除 inpaint、
PNG 读写、写盘日志追加。阈值取本机实测值的 5 倍以上，只挡"数量级退化"，
不追求机器间可比。改动这里的阈值要同步 `docs/managements/technical.md`。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.python.core import audit, edit, image  # noqa: E402
from src.python.core.style import soft_iou  # noqa: E402

# 单步上限（秒）。CI 机器比开发机慢，留足余量。
LIMITS = {
    "soft_iou×50": 1.0,
    "erase(2000×1500)": 1.5,
    "PNG 读写(2000×1500)": 2.0,
    "日志追加×300": 1.0,
}
TOTAL_LIMIT = 6.0


def _noise_mask(w: int, h: int) -> np.ndarray:
    rng = np.random.default_rng(7)
    return (rng.random((h, w)) > 0.85).astype(bool)


def bench_soft_iou() -> None:
    a = _noise_mask(220, 48)
    b = _noise_mask(220, 48)
    for _ in range(50):
        soft_iou(a, b, radius=3)


def bench_erase(tmp: Path) -> None:
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


def main(argv: list[str] | None = None) -> int:
    quiet = "--ci" in (sys.argv[1:] if argv is None else argv)
    env_dir = os.environ.get("IMG_P_TMP_DIR")
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
            started = time.perf_counter()
            try:
                fn(tmp)
            except Exception as exc:  # 跑不动本身就是缺陷
                failed.append(f"{name} 执行失败：{exc}")
                continue
            spent = time.perf_counter() - started
            total += spent
            limit = LIMITS[name]
            verdict = "ok" if spent <= limit else "SLOW"
            if spent > limit:
                failed.append(f"{name} 用了 {spent:.2f}s（上限 {limit:.1f}s）")
            if not quiet:
                print(f"[{verdict:4}] {name}: {spent:.2f}s / {limit:.1f}s")

    if total > TOTAL_LIMIT:
        failed.append(f"合计 {total:.2f}s（上限 {TOTAL_LIMIT:.1f}s）")
    if quiet:
        status = "FAIL" if failed else "ok"
        print(
            f"perf: {status} 合计 {total:.2f}s / {TOTAL_LIMIT:.1f}s"
            + (f"（{failed[0]}）" if failed else "")
        )
    else:
        print(f"合计 {total:.2f}s / 上限 {TOTAL_LIMIT:.1f}s")
        for msg in failed:
            print(f"[FAIL] {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
