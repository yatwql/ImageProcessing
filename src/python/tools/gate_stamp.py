#!/usr/bin/env python3
"""全量门禁通过戳：同一份代码不重复跑整条全量门禁。

全量门禁现在约 3 分钟（静态并发 + 四档环境矩阵 × `-n 8` + 覆盖率 + 分片重排），
发布流程里 `check` 与 `gate` 各要一次，同一份代码跑两遍是纯浪费。

    python -m src.python.tools.gate_stamp --write   # 全量 check_all 全绿后写戳
    python -m src.python.tools.gate_stamp --check   # pre-push / release 先问一句，命中就跳过重跑

指纹 = 全部跟踪文件（`git ls-files`）内容 + 路径的 sha256，**与是否已提交无关**：
只要工作区的代码/文档和上次全量通过时一模一样，再跑一遍结论不会变。
戳存在 git 目录里（`.git/retype-gate-stamp.json`），入库、跨机器都不携带。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT

STAMP_NAME = "retype-gate-stamp.json"


def git_dir(root: Path) -> Path:
    """真实的 git 目录（worktree 下是 .git/worktrees/<name> 之类）。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return root / ".git"
    path = out.stdout.strip()
    return (root / path).resolve() if path else root / ".git"


def fingerprint(root: Path | None = None) -> str:
    """跟踪文件（路径 + 内容）的 sha256；没装 git 时退化为空串。"""
    base = root if root is not None else ROOT
    try:
        raw = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=str(base),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        ).stdout
    except OSError:
        return ""
    digest = hashlib.sha256()
    for rel in sorted(p for p in raw.split("\0") if p):
        path = base / rel
        digest.update(rel.encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def stamp_path(root: Path | None = None) -> Path:
    return git_dir(root if root is not None else ROOT) / STAMP_NAME


def write_stamp(root: Path | None = None) -> str:
    base = root if root is not None else ROOT
    value = fingerprint(base)
    path = stamp_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"fingerprint": value, "at": dt.datetime.now().isoformat(timespec="seconds")},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return value


def stamp_matches(root: Path | None = None) -> bool:
    base = root if root is not None else ROOT
    path = stamp_path(base)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return data.get("fingerprint") == fingerprint(base)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="全量门禁通过戳")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="写戳（check_all 全绿后调用）")
    group.add_argument("--check", action="store_true", help="同一份代码是否已全量通过")
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.write:
        print(f"[ok] 已写门禁戳 {write_stamp()}")
        return 0
    if stamp_matches():
        print("[ok] 同一份代码已通过全量门禁（跳过重跑）")
        return 0
    print("[!] 没有可用的门禁戳：需要真跑一次全量门禁")
    return 1


if __name__ == "__main__":
    sys.exit(main())
