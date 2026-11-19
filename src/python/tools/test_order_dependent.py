#!/usr/bin/env python3
"""定位「顺序依赖」：单跑通过、和别的用例一起跑却失败的用例，二分找出污染它的前置文件。

典型场景：模块级 `mock.patch` / 缓存 / 全局单例没清干净，目标用例单独跑绿、
排在泄漏文件之后跑红。手工二分要十几轮 pytest 往返，这里把候选前缀缩到最小复现集。

    python -m src.python.tools.order_dependent <目标节点ID>
    python -m src.python.tools.order_dependent <目标> --candidates src/test/tui/test_x.py
    python -m src.python.tools.order_dependent <目标> --max-runs 30 --json

流程：① 单跑目标必须通过 → ② 按收集顺序取目标之前的文件作候选 → ③ 候选 + 目标能复现失败
→ ④ 二分最小前缀 → ⑤ 单文件配对确认 → 输出污染源与最小复现命令。

退出码：0 = 已定位；1 = 非顺序依赖（单跑就失败）；2 = 无法复现 / 前置含无关失败 / 用法错误。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from ..stdio import ensure_utf8_stdio

PYTEST_FLAGS = ["-q", "--tb=no", "-rf", "-p", "no:cacheprovider", "--no-header"]
NODE_FILE = re.compile(r"^(\S+\.py)(?:::.*)?$")


class Outcome(Enum):
    """一次 pytest 运行对目标用例的判定。"""

    TARGET_FAILED = "target_failed"
    TARGET_PASSED = "target_passed"
    OTHER_FAILURE = "other_failure"
    ERROR = "error"


@dataclass
class Finding:
    """定位结果：污染源文件与最小复现集。"""

    culprit: str | None
    minimal: list[str]
    runs: int

    def command(self, target: str) -> str:
        files = " ".join(self.minimal or [])
        return f".venv/bin/python -m pytest {files} {target}".replace("  ", " ")


def parse_collect_order(output: str) -> list[str]:
    """从 `pytest --collect-only -q` 输出里按首次出现顺序抽出测试文件（逐文件去重）。"""
    files: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith(("=", "!", "_")):
            continue
        match = NODE_FILE.match(line)
        if match is None:
            continue
        path = match.group(1)
        if path not in seen:
            seen.add(path)
            files.append(path)
    return files


def minimize_prefix(
    candidates: Sequence[str], fails_with: Callable[[Sequence[str]], bool]
) -> list[str]:
    """二分出「最短仍能复现失败」的前缀（`fails_with([])` 为 False 时返回空表）。

    `fails_with` 单调：前缀越长越可能复现。找不到最短前缀时返回空表，由调用方判定。
    """
    if not fails_with(candidates):
        return []
    lo, hi = 0, len(candidates)
    while lo < hi:  # 不变式：candidates[:hi] 能复现，candidates[:lo] 不能
        mid = (lo + hi) // 2
        if fails_with(candidates[:mid]):
            hi = mid - 1
        else:
            lo = mid + 1
    return list(candidates[:lo])


def locate(
    target: str,
    candidates: Sequence[str],
    run: Callable[[Sequence[str], str], Outcome],
    *,
    max_runs: int = 60,
) -> tuple[Finding, Outcome]:
    """跑定位主流程；`run` 是"给定前置文件与目标，跑一次 pytest"的注入点（便于单测）。"""
    runs = 0

    def once(files: Sequence[str]) -> Outcome:
        nonlocal runs
        if runs >= max_runs:
            return Outcome.ERROR
        runs += 1
        return run(files, target)

    solo = once([])
    if solo is not Outcome.TARGET_PASSED:
        # 单跑就失败（或跑不起来）：这不是顺序依赖，别浪费时间二分
        return Finding(None, [], runs), solo

    def fails_with(files: Sequence[str]) -> bool:
        return once(files) is Outcome.TARGET_FAILED

    minimal = minimize_prefix(candidates, fails_with)
    if not minimal:
        return Finding(None, [], runs), Outcome.OTHER_FAILURE
    culprit = _confirm_culprit(minimal, fails_with)
    return Finding(culprit, minimal, runs), Outcome.TARGET_FAILED


def _confirm_culprit(minimal: list[str], fails_with: Callable[[Sequence[str]], bool]) -> str | None:
    """在最小集里逐个剔除，找出"去掉它就不再失败"的那个文件。"""
    for path in reversed(minimal):
        rest = [p for p in minimal if p != path]
        if rest and not fails_with(rest):
            return path
    return minimal[-1] if minimal else None


def run_pytest(files: Sequence[str], target: str) -> Outcome:
    """真跑一次 pytest；`-rf` 让"目标失败"与"别的也失败"能区分开。"""
    cmd = [sys.executable, "-m", "pytest", *PYTEST_FLAGS, *files, target]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
    except OSError:
        return Outcome.ERROR
    if proc.returncode == 0:
        return Outcome.TARGET_PASSED
    short_target = target.split("::")[-1]
    failed_lines = [
        ln for ln in (proc.stdout or "").splitlines() if ln.startswith(("FAILED ", "ERROR "))
    ]
    others = [ln for ln in failed_lines if short_target not in ln]
    return Outcome.OTHER_FAILURE if others else Outcome.TARGET_FAILED


def collect_order(extra_args: Sequence[str] = ()) -> list[str]:
    """按收集顺序列出测试文件；收集失败就直接退出（不给错误的定位）。"""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", *extra_args]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    if proc.returncode != 0:
        raise SystemExit(f"收集失败（退出码 {proc.returncode}）：{proc.stdout[-400:]}")
    return parse_collect_order(proc.stdout)


def main(argv: Sequence[str] = ()) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="定位顺序依赖用例的最小污染源")
    ap.add_argument("target", help="目标用例节点 ID，如 src/test/tui/test_x.py::Cls::test_y")
    ap.add_argument(
        "--candidates",
        action="append",
        default=[],
        help="只在给定文件里找（可重复）；不给则用收集顺序里目标之前的全部文件",
    )
    ap.add_argument("--collect-root", default="src/test", help="收集根目录（默认 src/test）")
    ap.add_argument("--max-runs", type=int, default=60, help="pytest 次数上限（默认 60）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(list(argv) if argv else sys.argv[1:])

    target_file = args.target.split("::")[0]
    candidates = args.candidates or [
        p for p in collect_order([args.collect_root]) if p != target_file
    ]
    if not candidates:
        print("没有候选前置文件：目标之前没有别的测试文件", file=sys.stderr)
        return 2

    finding, outcome = locate(
        target_file and args.target, candidates, run_pytest, max_runs=args.max_runs
    )
    payload = {
        "target": args.target,
        "outcome": outcome.value,
        "runs": finding.runs,
        "culprit": finding.culprit,
        "minimal_set": finding.minimal,
        "reproduce": finding.command(args.target) if finding.minimal else None,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif outcome is Outcome.TARGET_PASSED:
        print(f"单跑就失败（{finding.runs} 次运行）：这不是顺序依赖，先修用例本身")
    elif finding.minimal:
        print(f"顺序依赖：{args.target}")
        print(f"  污染源（去掉它就不再失败）：{finding.culprit}")
        print(f"  最小复现集（{len(finding.minimal)} 个文件）：{' '.join(finding.minimal)}")
        print(f"  复现：{finding.command(args.target)}")
    else:
        print(f"无法在候选集内复现（{finding.runs} 次运行）；用 --candidates 缩小范围再试")
    return 0 if finding.minimal else (1 if outcome is Outcome.TARGET_PASSED else 2)


if __name__ == "__main__":
    sys.exit(main())
