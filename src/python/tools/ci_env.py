#!/usr/bin/env python3
"""CI 环境指纹：把"这次跑在什么环境"落成文件，失败时随 artifact 上传。

    python tools/ci_env.py [输出目录]        # 默认 ci-env/

写：python.txt（解释器与构建信息）、platform.txt、pip-freeze.txt（依赖精确版本）、
fonts.txt（前 50 个系统字体，判断"有没有中文字体"用）。
为什么用脚本而不是在 workflow 里塞 `python -c`：多行 `-c` 在 3.10 上直接
IndentationError，且本地无法验证——写成脚本就能被 `check_workflows.py` 与用例覆盖。
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

from ..stdio import ensure_utf8_stdio

OUT = Path("ci-env")
FONT_LIMIT = 50


def write(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    python_info = out / "python.txt"
    python_info.write_text(f"{sys.version}\n{sys.executable}\n", encoding="utf-8")
    written.append(python_info)

    platform_info = out / "platform.txt"
    platform_info.write_text(
        f"{platform.platform()}\n{sys.platform}\n{os.cpu_count()} cpus\n", encoding="utf-8"
    )
    written.append(platform_info)

    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    freeze_path = out / "pip-freeze.txt"
    freeze_path.write_text(freeze.stdout, encoding="utf-8")
    written.append(freeze_path)

    fonts_path = out / "fonts.txt"
    try:
        listing = subprocess.run(["fc-list"], capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
        lines = listing.stdout.splitlines()[:FONT_LIMIT]
        fonts_path.write_text(
            "\n".join(lines) if lines else "(no fonts / fc-list 不可用)\n", encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError):
        fonts_path.write_text("(fc-list 不可用)\n", encoding="utf-8")
    written.append(fonts_path)
    return written


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    target = Path(args[0]) if args else OUT
    for path in write(target):
        print(f"[ok] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
