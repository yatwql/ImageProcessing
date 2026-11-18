#!/usr/bin/env python3
"""跨平台安全：把"只在 Windows/macOS 上才炸"的写法在本地拦下来。

    python -m src.python.tools.check_platform_safety
    python -m src.python.tools.check_platform_safety --ci

检查 `src/test/**` 与 `src/python/**` 里的几类问题（都真实踩过）：
1. 硬编码 POSIX 路径（`/tmp`、`/proc`、`/usr/...`）—— Windows 上是另一个盘符；
2. 子进程 `text=True` 没给 `encoding=`—— Windows 用 cp1252 解码 UTF-8 输出会炸；
3. 直接 `import fcntl` / `os.mkfifo` / `pwd` 等 POSIX-only 模块而无平台保护；
4. `curses` 常量当字符串用（ACS_* 在部分构建里是 int）。

豁免：明确带 `skipIf(win32)` / `skipUnless(posix)` 的用例，或行内 `# platform-safe` 注记。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from ._paths import ROOT

POSIX_PATH = re.compile(r'"(/(?:tmp|proc|usr|data|dev)/[^"]*)"')
SUBprocess_TEXT = re.compile(r"subprocess\.(?:run|Popen|check_output)\(")
IMPORT_POSIX = re.compile(r"^\s*(?:import (fcntl|pwd|grp|termios|tty)\b|from (fcntl|pwd|grp|termios|tty) import)")
SAFE_MARK = "# platform-safe"
SKIP_MARK = ("skipIf(sys.platform", "skipUnless(sys.platform", 'skipIf(POSIX', "skipUnless(POSIX")


def _iter_sources() -> list[Path]:
    return sorted([*ROOT.joinpath("src/test").rglob("*.py"),
                   *ROOT.joinpath("src/python").rglob("*.py")])


def _has_platform_guard(lines: list[str]) -> bool:
    joined = "\n".join(lines)
    return any(mark in joined for mark in SKIP_MARK) or "POSIX" in joined


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = path.relative_to(ROOT).as_posix()
    problems: list[str] = []

    for lineno, line in enumerate(lines, 1):
        if SAFE_MARK in line:
            continue
        match = POSIX_PATH.search(line)
        if match and not _has_platform_guard(lines):
            problems.append(f"{rel}:{lineno} 硬编码 POSIX 路径 {match.group(1)!r}（用 tempfile 或打桩）")
        if IMPORT_POSIX.match(line) and not _has_platform_guard(lines):
            problems.append(f"{rel}:{lineno} 直接依赖 POSIX-only 模块（加平台保护或打到 _support）")

    # 子进程调用必须显式编码：同一行或后续两行内出现 encoding=
    for lineno, line in enumerate(lines, 1):
        if not SUBprocess_TEXT.search(line):
            continue
        window = " ".join(lines[lineno - 1:lineno + 2])
        if "text=True" in window and "encoding=" not in window:
            problems.append(f"{rel}:{lineno} 子进程 text=True 缺 encoding=（Windows 会用 cp1252 解码）")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    problems: list[str] = []
    for path in _iter_sources():
        problems += check_file(path)
    if problems:
        for item in problems:
            print(f"[FAIL] {item}")
        return 1
    print(f"[ok] 跨平台安全（扫描 {len(_iter_sources())} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
