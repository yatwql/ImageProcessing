#!/usr/bin/env python3
"""重新生成 `docs/managements/folders.md` 的两个"机器可算"部分：目录树与项目统计。

    python -m src.python.tools.gen_folders            # 只打印将要写入的内容摘要
    python -m src.python.tools.gen_folders --write    # 写回文档（正文段落不动）

为什么要有它：目录树之前靠手改，搬文件时容易漏；统计数字（文件数/行数/用例数）
更是每次都要重算。这里按 `git ls-files` 生成，文件说明取自模块文档串
（`.py`）与下面的 `FILE_NOTE` / `DIR_NOTE` 表，改完布局跑一次即可。
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unicodedata

from ._paths import ROOT

DOC = ROOT / "docs" / "managements" / "folders.md"
TREE_FENCE = "```text"
INDENT = 4

DIR_NOTE = {
    ".": "仓库根",
    ".githooks": "git 钩子（core.hooksPath 指向这里）",
    ".github/workflows": "CI 流水线",
    "scripts": "只放 .sh/.ps1 薄壳",
    "src": "源码包根",
    "src/python": "程序代码",
    "src/python/core": "核心层：唯一实现替换逻辑的地方",
    "src/python/cli": "命令行渠道",
    "src/python/tui": "交互渠道",
    "src/python/tools": "开发工具（不进发行包、不计覆盖率）",
    "src/test": "测试用例",
    "src/test/cli": "CLI 用例",
    "src/test/core": "核心层用例",
    "src/test/core/background": "背景类型用例",
    "src/test/core/color": "颜色与透明用例",
    "src/test/core/font": "字体用例",
    "src/test/core/format": "图片格式用例",
    "src/test/core/layout": "排版用例",
    "src/test/core/pipeline": "端到端用例",
    "src/test/core/primitives": "渲染/擦除原语用例",
    "src/test/tui": "交互用例",
    "src/test/snapshots": "界面快照数据",
    "data/demo": "回归样例图",
    "docs": "文档",
    "docs/managements": "管理文档",
    "docs/manuals": "使用手册",
}

FILE_NOTE = {
    "README.md": "项目简介 / 快速开始 / 门禁 / 文档索引",
    "CLAUDE.md": "AI 协作者约定：架构硬约束、纪律、已知坑",
    "pyproject.toml": "唯一配置源：依赖 + dev extra + ruff/mypy/pytest/coverage",
    "constraints.txt": "锁定依赖组合（含 3.10 与 Windows 分档）",
    "requirements.txt": "兼容壳：`-e .`",
    "requirements-dev.txt": "兼容壳：`-e .[dev]`",
    ".gitignore": "忽略虚拟环境 / 缓存 / 输出 / 日志",
    ".githooks/pre-commit": "提交前门禁：check_all --quick",
    ".githooks/pre-push": "推送前门禁：check_all 全量",
    ".githooks/install-hooks.sh": "启用/关闭仓库钩子",
    ".github/workflows/ci.yml": "CI：test×3 / lint / typecheck / guards / perf / windows / audit / release",
    "scripts/cli.sh": "→ launch cli",
    "scripts/cli.ps1": "→ launch cli（Windows）",
    "scripts/tui.sh": "→ launch tui",
    "scripts/tui.ps1": "→ launch tui（Windows）",
    "scripts/setup.sh": "→ src.python.bootstrap",
    "scripts/setup.ps1": "→ src.python.bootstrap（Windows）",
    "scripts/runTest.sh": "→ src.python.tools.run_tests",
    "scripts/runTest.ps1": "→ src.python.tools.run_tests（Windows）",
    "scripts/log-query.sh": "→ launch log-query",
    "scripts/log-query.ps1": "→ launch log-query（Windows）",
    "data/demo/示例-报告.png": "回归样例（报告版式）",
    "data/demo/示例-通知1.png": "回归样例（通知版式）",
    "data/demo/示例-通知2.png": "回归样例（通知版式）",
    "data/demo/示例-通知3.png": "回归样例（通知版式）",
    "docs/README.md": "文档索引与推荐阅读顺序",
}


def tracked_files() -> list[str]:
    raw = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    ).stdout
    return [
        p
        for p in raw.split("\0")
        if p and not p.startswith(("data/output/", "logs/", "reports/", "test-reports/"))
    ]


def dwidth(text: str) -> int:
    return sum(
        0
        if unicodedata.combining(ch)
        else (2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1)
        for ch in text
    )


def docstring_line(rel: str) -> str:
    try:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ""
    doc = ast.get_docstring(tree) or ""
    return doc.splitlines()[0].strip().rstrip("。")[:52] if doc else ""


def note_for(rel: str, name: str) -> str:
    if rel in FILE_NOTE:
        return FILE_NOTE[rel]
    if name.endswith(".py"):
        found = docstring_line(rel)
        if found:
            return found
    parent = rel.rsplit("/", 1)[0] if "/" in rel else "."
    return DIR_NOTE.get(parent, "")


def build_tree(files: list[str]) -> str:
    tree: dict = {}
    for path in files:
        node = tree
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    def render(node: dict, path: tuple[str, ...] = (), prefix: str = "") -> list[str]:
        names = sorted(node)
        dirs = [n for n in names if isinstance(node[n], dict)]
        plain = [n for n in names if node[n] is None]
        out: list[str] = []
        items = [(d, True) for d in dirs] + [(f, False) for f in plain]
        for index, (name, is_dir) in enumerate(items):
            last = index == len(items) - 1
            rel = "/".join(path + (name,))
            label = name + ("/" if is_dir else "")
            line = f"{prefix}{'└── ' if last else '├── '}{label}"
            note = DIR_NOTE.get(rel, "") if is_dir else note_for(rel, name)
            if note:
                line += " " * max(2, 46 - dwidth(line)) + f"# {note}"
            out.append(line)
            if is_dir:
                out += render(node[name], path + (name,), prefix + ("    " if last else "│   "))
        return out

    return "\n".join(["ImageProcessing/", *render(tree)])


def count_lines(files: list[str]) -> tuple[int, int]:
    total_files = total_lines = 0
    for rel in files:
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        total_files += 1
        total_lines += text.count("\n") + (0 if text.endswith("\n") else 1)
    return total_files, total_lines


def test_function_count(files: list[str]) -> int:
    """`def test_` 出现次数（与文档里的口径一致，比 pytest 收集数略少）。"""
    count = 0
    for rel in files:
        if not rel.endswith(".py"):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        count += sum(1 for line in text.splitlines() if line.strip().startswith("def test_"))
    return count


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    files = tracked_files()
    tree = build_tree(files)
    tests = [f for f in files if f.startswith("src/test/") and f.endswith(".py")]
    test_files, test_lines = count_lines(tests)
    if "--write" in args:
        text = DOC.read_text(encoding="utf-8")
        start = text.index(TREE_FENCE)
        end = text.index("```", start + len(TREE_FENCE))
        text = text[:start] + f"{TREE_FENCE}\n{tree}\n" + text[end:]
        DOC.write_text(text, encoding="utf-8")
        print(
            f"已更新目录树：{len(files)} 个跟踪文件，测试 {test_files} 个文件 / {test_lines:,} 行 / "
            f"{test_function_count(tests)} 个 test 函数"
        )
        print("统计表里的数字如需同步，请按上面的读数手改（只改数字，不改说明）")
        return 0
    print(tree)
    print(
        f"\n跟踪文件 {len(files)}；测试 {test_files} 个文件 / {test_lines:,} 行 / "
        f"{test_function_count(tests)} 个 test 函数"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
