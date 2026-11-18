#!/usr/bin/env python3
"""架构约束：模块导入方向（谁可以依赖谁）。

    python tools/check_import_surface.py          # 违规即非零退出
    python tools/check_import_surface.py -v       # 打印扫描范围

规则（与 `docs/managements/technical.md` 的分层一致）：
- `core/` 只依赖标准库/第三方与 `src.python.{core,version,config?}`；
  **不得**导入 `cli` / `tui`（核心层不认识渠道）；
- `cli/` 与 `tui/` 可以依赖 `core`、`config`、`version`，但**彼此不得互相导入**；
- `tools/` 与 `src/test/` 不受限（工程工具与用例可以随便用）。

这样"替换逻辑只在 core"就不是靠自觉，而是导入图上的硬约束。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "python"

CORE_ALLOWED = {"core", "version", "config"}
CHANNEL_ALLOWED = {"core", "version", "config"}


def module_package(path: Path) -> str | None:
    """文件属于哪个顶层包（core / cli / tui / None）。"""
    try:
        rel = path.relative_to(SRC)
    except ValueError:
        return None
    return rel.parts[0] if len(rel.parts) > 1 else None


def imported_packages(path: Path) -> list[tuple[str, int]]:
    """返回该文件里所有 `src.python.X` 形式的导入（包名, 行号）。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.startswith("src.python."):
                found.append((node.module.split(".")[2], node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src.python."):
                    found.append((alias.name.split(".")[2], node.lineno))
    return found


def violations() -> list[str]:
    problems: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        package = module_package(path)
        if package not in ("core", "cli", "tui"):
            continue
        allowed = CORE_ALLOWED if package == "core" else CHANNEL_ALLOWED
        for imported, lineno in imported_packages(path):
            if imported in allowed:
                continue
            problems.append(
                f"{path.relative_to(ROOT)}:{lineno} `{package}` 导入了 `{imported}`"
                f"（允许：{', '.join(sorted(allowed))}）"
            )
        # 渠道之间、渠道与 core 的反向依赖已经在上面覆盖
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    problems = violations()
    if not problems:
        print(f"[ok] 导入方向合规（扫描 {len(list(SRC.rglob('*.py')))} 个文件）")
        return 0
    for item in problems:
        print(f"[FAIL] {item}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
