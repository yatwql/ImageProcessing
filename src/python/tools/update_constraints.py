#!/usr/bin/env python3
"""依赖升级助手：列出可升级项，并按当前环境重写 constraints.txt 的非标记部分。

    python tools/update_constraints.py --check      # 只看哪些包有新版本（不动文件）
    python tools/update_constraints.py --write      # 按当前 .venv 重写锁定版本

`--write` 保留文件头与被环境标记分档的包（Pillow / numpy / onnxruntime / coverage /
shapely / windows-curses），其余按 `pip freeze` 实际版本重排。
升级后必须 `python tools/check_all.py` 全绿才能提交——这是唯一的验收标准。
"""

from __future__ import annotations

import re
import subprocess
import sys

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT  # noqa: E402  (工具共用仓库根)

CONSTRAINTS = ROOT / "constraints.txt"
MARKED = re.compile(r";\s*sys_platform|;\s*python_version")
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)")
SKIP = {"img-p", "retype", "pip", "setuptools", "wheel"}


def frozen() -> dict[str, str]:
    out = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    pins: dict[str, str] = {}
    for line in out.splitlines():
        m = PIN.match(line.strip())
        if m and m.group(1).lower() not in SKIP:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def outdated() -> list[str]:
    out = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--outdated", "--format=freeze"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    write = "--write" in args

    if "--check" in args or not write:
        lines = outdated()
        if lines:
            print("可升级：")
            for line in lines:
                print("  " + line)
            print(
                "\n升级步骤：装新版本 → python tools/update_constraints.py --write → tools/check_all.py"
            )
        else:
            print("没有可升级的包")
        return 0

    pins = frozen()
    original = CONSTRAINTS.read_text(encoding="utf-8").splitlines()
    header = [ln for ln in original if ln.startswith("#")]
    kept = [ln for ln in original if ln.strip() and not ln.startswith("#") and MARKED.search(ln)]
    body = [f"{name}=={version}" for name, version in sorted(pins.items())]
    CONSTRAINTS.write_text("\n".join(header + body + kept) + "\n", encoding="utf-8")
    print(f"已按当前环境重写 {CONSTRAINTS.name}：{len(body)} 个普通依赖 + {len(kept)} 个分档依赖")
    print("别忘了跑 python tools/check_all.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
