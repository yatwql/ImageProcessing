#!/usr/bin/env python3
"""本地全量门禁：一条命令跑完 CI 跑的所有检查，绿了再推。

    python tools/check_all.py              # 全量（含覆盖率与"无字体"复跑）
    python tools/check_all.py --quick      # 快速：ruff / mypy / guards / perf / 用例
    python tools/check_all.py --ci-matrix  # 额外跑"cp1252 控制台 + C locale"（Windows runner 的样子）
    python tools/check_all.py -k mapping   # 其余参数透传给 pytest

顺序是"越快越先"，失败即停：静态检查几十毫秒，用例一分钟。
CI 的六个作业（lint / typecheck / guards / perf / test / windows）在这里都有对应；
windows 专属的差异用 `--no-font` 与 `layout_rendering.WindowsStyleAcs` 覆盖。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT  # noqa: E402  (工具共用仓库根)

PY = sys.executable


def run(name: str, cmd: list[str], *, env: dict[str, str] | None = None) -> bool:
    started = time.perf_counter()
    print(f"== {name}")
    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(cmd, cwd=str(ROOT), env=merged)
    spent = time.perf_counter() - started
    if proc.returncode != 0:
        print(f"!! {name} 失败（{spent:.1f}s）")
        return False
    print(f"   {name} ok（{spent:.1f}s）")
    return True


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    quick = "--quick" in args
    no_font = "--no-font" in args
    matrix = "--ci-matrix" in args
    extra = [a for a in args if a not in ("--quick", "--no-font", "--ci-matrix")]

    steps: list[tuple[str, list[str], dict[str, str] | None]] = [
        ("ruff", [PY, "-m", "ruff", "check", "src/"], None),
        ("mypy", [PY, "-m", "mypy"], None),
        ("guards", [PY, "-m", "src.python.tools.check_guards"], None),
        ("perf", [PY, "-m", "src.python.tools.check_perf", "--ci"], None),
    ]
    if quick:
        steps.append(
            (
                "pytest（快速：不算覆盖率）",
                [PY, "-m", "pytest", "src/test", "-q", "-x", *extra],
                None,
            )
        )
    else:
        reports = ROOT / "reports"
        reports.mkdir(exist_ok=True)
        steps.append(
            (
                "pytest + 覆盖率",
                [
                    PY,
                    "-m",
                    "pytest",
                    "src/test",
                    "-q",
                    "--cov",
                    f"--cov-report=xml:{reports / 'coverage.xml'}",
                    f"--junitxml={reports / 'junit.xml'}",
                    *extra,
                ],
                None,
            )
        )
        steps.append(
            (
                "覆盖率门禁（总量 / 分模块 / skip 比例）",
                [
                    PY,
                    "-m",
                    "src.python.tools.check_coverage",
                    str(reports / "coverage.xml"),
                    str(reports / "junit.xml"),
                ],
                None,
            )
        )

    for name, cmd, env in steps:
        if not run(name, cmd, env=env):
            return 1

    # CI 环境矩阵：把"只有 runner 上才有"的条件在本机复现一次。
    # ① 没有中文字体（Windows runner / 精简镜像）
    # ② 非 UTF-8 控制台 + C locale（Windows cp1252、POSIX 最小镜像）——
    #    这一档专治"子进程/打印按 cp1252 解码"这类只在 CI 炸的问题
    if matrix or not quick:
        if not run(
            "pytest（CI 矩阵：cp1252 控制台 + C locale）",
            [PY, "-m", "pytest", "src/test", "-q", "--no-header"],
            env={"PYTHONIOENCODING": "cp1252", "LC_ALL": "C", "LANG": "C"},
        ):
            return 1

    # "机器上没有中文字体"是 CI 上最容易漏的一档（Windows runner 就是这种环境）
    if no_font or not quick:
        if not run(
            "pytest（模拟无中文字体）",
            [PY, "-m", "pytest", "src/test", "-q", "--no-header"],
            env={"IMG_P_TEST_NO_CJK_FONT": "1"},
        ):
            return 1

    print("\n全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
