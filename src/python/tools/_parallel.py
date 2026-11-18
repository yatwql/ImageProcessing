#!/usr/bin/env python3
"""门禁并行执行：worker 数规划与"互不干扰"的批次并发。

背景（实测，16 核容器，703 个用例）：
  单档全量：串行 1 进程 69s；`-n 8` 25s；`-n 16` 25s（已饱和）
  四档矩阵：档位串行 + 每档 `-n 8` 123s；四档并发各 `-n 4` 103s；各 `-n 2` 129s
所以并发跑"档位"不划算：矩阵档之间抢核，反而比"档位串行 + 每档 8 worker"更慢，
机器越忙差距越大。结论固定成默认策略：

* **档位串行**（plain / ci / nofont / font / stress 依次跑）；
* **每档 `-n 8`**（超过 8 不再变快，16 核也一样）；
* 静态检查（ruff / mypy / mypy-win32 / guards）彼此只读、**并发**跑。

覆盖方式：
    IMG_P_TEST_WORKERS=4    固定 worker 数（0 = 单进程）
    IMG_P_GATE_SERIAL=1     整条门禁退回串行（内存小的机器 / 排障时）
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

#: worker 上限：实测 8 路即饱和，再往上只有进程争抢与磁盘抖动
MAX_WORKERS = 8

WORKERS_ENV = "IMG_P_TEST_WORKERS"
SERIAL_ENV = "IMG_P_GATE_SERIAL"

#: 失败时回放的输出行数（只留尾部，避免整段 pytest 输出刷屏）
TAIL_LINES = 40


@dataclass(frozen=True)
class Step:
    """一条要执行的子命令。`env` 只叠加到当前环境之上。"""

    name: str
    cmd: Sequence[str]
    env: dict[str, str]
    isolated: bool = False  # True = 必须独占 CPU（耗时守卫靠墙钟判定）


@dataclass(frozen=True)
class Result:
    name: str
    code: int
    seconds: float
    output: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def cpu_count() -> int:
    return os.cpu_count() or 4


def gate_is_serial() -> bool:
    raw = (os.environ.get(SERIAL_ENV) or "").strip().lower()
    return raw not in ("", "0", "false", "no")


def worker_count(override: int | None = None) -> int:
    """`pytest -n` 的 worker 数；`0` 表示不加 `-n`（单进程）。

    优先级：显式参数 > `IMG_P_TEST_WORKERS` > `IMG_P_GATE_SERIAL` > 默认（核数，上限 8）。
    """
    if override is not None:
        return max(0, override)
    raw = (os.environ.get(WORKERS_ENV) or "").strip()
    if raw.isdigit():
        return max(0, int(raw))
    if gate_is_serial():
        return 0
    return min(MAX_WORKERS, max(1, cpu_count()))


def parallel_args(workers: int) -> list[str]:
    """`-n` 相关的命令行片段；`workers <= 1` 时返回空列表（单进程无需 xdist）。"""
    if workers <= 1:
        return []
    return ["-n", str(workers)]


def run_one(step: Step, root: Path) -> Result:
    """执行一条子命令，捕获输出（成功时不回放，失败时只看尾部）。"""
    started = time.perf_counter()
    env = {**os.environ, **step.env}
    try:
        proc = subprocess.run(
            list(step.cmd),
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:  # 解释器/命令不存在：当成失败，别让门禁假绿
        return Result(step.name, 127, time.perf_counter() - started, str(exc))
    output = (proc.stdout or "") + (proc.stderr or "")
    return Result(step.name, proc.returncode, time.perf_counter() - started, output)


def run_batch(steps: Sequence[Step], root: Path, jobs: int | None = None) -> list[Result]:
    """并发跑一组互不干扰的步骤，结果按输入顺序返回。

    `jobs` 缺省 = 步骤数（静态检查彼此只读，全开最省时间）；
    标记 `isolated=True` 的步骤不参与并发，由调用方单独串行执行。
    """
    batch = [s for s in steps if not s.isolated]
    solo = [s for s in steps if s.isolated]
    results: list[Result] = []
    if batch:
        width = len(batch) if jobs is None else max(1, min(jobs, len(batch)))
        if width == 1:
            results.extend(run_one(step, root) for step in batch)
        else:
            with cf.ThreadPoolExecutor(max_workers=width) as pool:
                results.extend(pool.map(lambda s: run_one(s, root), batch))
    results.extend(run_one(step, root) for step in solo)
    return results


def tail(output: str, lines: int = TAIL_LINES) -> str:
    """输出尾部（去掉空行），用于失败回放。"""
    kept = [ln for ln in output.rstrip().splitlines() if ln.strip()]
    return "\n".join(kept[-lines:])


__all__ = [
    "MAX_WORKERS",
    "SERIAL_ENV",
    "WORKERS_ENV",
    "Result",
    "Step",
    "cpu_count",
    "gate_is_serial",
    "parallel_args",
    "run_batch",
    "run_one",
    "tail",
    "worker_count",
]
