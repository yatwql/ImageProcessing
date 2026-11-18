"""控制台编码：保证中文提示在非 UTF-8 的终端（Windows cp936/cp1252）上也能打印。

不加这层，Windows 上 `retype --help` / `--list` 一打印中文就抛
`UnicodeEncodeError`，进程直接退出码 1——用户看到的是"程序打不开"。
"""

from __future__ import annotations

import sys

ENCODING = "utf-8"
_NORMALIZED = ENCODING.replace("-", "")  # 与 stream.encoding 的比较口径一致


def ensure_utf8_stdio() -> None:
    """把 stdout/stderr 调到 UTF-8（不可写编码时退化成替换字符，不抛异常）。"""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if encoding == _NORMALIZED:
            continue
        try:
            stream.reconfigure(encoding=ENCODING, errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError, ValueError):
            continue
