#!/usr/bin/env python3
"""重新生成 `docs/managements/folders.md` 的两个"机器可算"部分：目录树与项目统计。

    python -m src.python.tools.gen_folders            # 只打印将要写入的内容摘要
    python -m src.python.tools.gen_folders --write    # 写回文档（正文段落不动）

为什么要有它：目录树之前靠手改，搬文件时容易漏；统计数字（文件数/行数/用例数）
更是每次都要重算——现在 `--write` 两个都重算，只有「说明」列需要人写。
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unicodedata
from pathlib import Path

from ..stdio import ensure_utf8_stdio
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
    "docs/archive": "版本归档：旧版本台账整块搬入（规则见 README）",
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
    "scripts/run-test.sh": "→ src.python.tools.run_tests",
    "scripts/run-test.ps1": "→ src.python.tools.run_tests（Windows）",
    "scripts/log-query.sh": "→ launch log-query",
    "scripts/log-query.ps1": "→ launch log-query（Windows）",
    "data/demo/示例-报告.png": "回归样例（报告版式）",
    "data/demo/示例-通知1.png": "回归样例（通知版式）",
    "data/demo/示例-通知2.png": "回归样例（通知版式）",
    "data/demo/示例-通知3.png": "回归样例（通知版式）",
    "docs/README.md": "文档索引与推荐阅读顺序",
    "docs/archive/README.md": "归档规范：目录/命名、头部四项、搬运与编号不复用规则",
    "docs/archive/v0.1.x/archived_plan.0.1.x.md": "计划归档：v0.1 系列（待首次发布搬入）",
    "docs/archive/v0.1.x/archived_review-findings.0.1.x.md": "自检记录归档：v0.1 系列（待首次发布搬入）",
    "docs/archive/v0.1.x/archived_changelog.0.1.x.md": "变更记录归档：v0.1 系列（待首次发布搬入）",
}


def tracked_files() -> list[str]:
    raw = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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


def dir_note(rel: str) -> str:
    """目录说明：固定表优先，版本归档系列目录按名字生成。"""
    if rel in DIR_NOTE:
        return DIR_NOTE[rel]
    if rel.startswith("docs/archive/v"):
        return f"版本归档系列 {rel.rsplit('/', 1)[-1]}"
    return ""


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
            rel = "/".join((*path, name))
            label = name + ("/" if is_dir else "")
            line = f"{prefix}{'└── ' if last else '├── '}{label}"
            note = dir_note(rel) if is_dir else note_for(rel, name)
            if note:
                line += " " * max(2, 46 - dwidth(line)) + f"# {note}"
            out.append(line)
            if is_dir:
                out += render(node[name], (*path, name), prefix + ("    " if last else "│   "))
        return out

    return "\n".join(["ImageProcessing/", *render(tree)])


def count_lines(files: list[str], root: Path | None = None) -> tuple[int, int]:
    base = root if root is not None else ROOT
    total_files = total_lines = 0
    for rel in files:
        try:
            text = (base / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        total_files += 1
        total_lines += text.count("\n") + (0 if text.endswith("\n") else 1)
    return total_files, total_lines


def test_function_count(files: list[str], root: Path | None = None) -> int:
    """`def test_` 出现次数（与文档里的口径一致，比 pytest 收集数略少）。"""
    base = root if root is not None else ROOT
    count = 0
    for rel in files:
        if not rel.endswith(".py"):
            continue
        try:
            text = (base / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        count += sum(1 for line in text.splitlines() if line.strip().startswith("def test_"))
    return count


ROOT_FILES = {
    "README.md",
    "CLAUDE.md",
    "pyproject.toml",
    "constraints.txt",
    "requirements.txt",
    "requirements-dev.txt",
    ".gitignore",
}

# 统计表的每一行：标签 → (文件谓词, 行数口径)。
# text = 数实际行数；count = 数 `def test_`；binary = 不统计行数。
STAT_SPEC: dict[str, tuple] = {
    "主程序代码": (
        lambda f: (
            f.startswith("src/python/")
            and f.endswith(".py")
            and not f.startswith("src/python/tools/")
        ),
        "text",
    ),
    "测试代码": (lambda f: f.startswith("src/test/") and f.endswith(".py"), "text"),
    "工程工具": (lambda f: f.startswith("src/python/tools/"), "text"),
    "启动脚本": (lambda f: f.startswith("scripts/"), "text"),
    "CI 与钩子": (lambda f: f.startswith((".github/", ".githooks/")), "text"),
    "管理文档": (lambda f: f.startswith("docs/managements/"), "text"),
    "归档文档": (lambda f: f.startswith("docs/archive/"), "text"),
    "使用手册": (lambda f: f.startswith("docs/manuals/"), "text"),
    "根文档与配置": (lambda f: f in ROOT_FILES, "text"),
    "文档索引": (lambda f: f == "docs/README.md", "text"),
    "示例图": (lambda f: f.startswith("data/demo/"), "binary"),
}
STAT_TOTAL_LABEL = "**合计（不含示例图）**"


def stats_cells(files: list[str], root: Path | None = None) -> dict[str, tuple[str, str]]:
    """算出每个统计行的（文件数, 行数）显示文本（合计行单独算）。"""
    cells: dict[str, tuple[str, str]] = {}
    for label, (predicate, kind) in STAT_SPEC.items():
        selected = [f for f in files if predicate(f)]
        if kind == "count":
            cells[label] = ("—", f"{test_function_count(selected, root):,}")
            continue
        if kind == "binary":
            cells[label] = (f"{len(selected):,}", "—")
            continue
        count, lines = count_lines(selected, root)
        cells[label] = (f"{count:,}", f"{lines:,}")
    demo = [f for f in files if f.startswith("data/demo/")]
    others = [f for f in files if not f.startswith("data/demo/")]
    total_files, total_lines = count_lines(others, root)
    tests = [f for f in files if f.startswith("src/test/") and f.endswith(".py")]
    _test_files, test_lines = count_lines(tests, root)
    _main_files, main_lines = count_lines([f for f in files if STAT_SPEC["主程序代码"][0](f)], root)
    cells["测试用例"] = ("—", f"{test_function_count(tests, root):,}")
    ratio = test_lines / main_lines if main_lines else 0.0
    cells[STAT_TOTAL_LABEL] = (
        f"**{total_files:,}**",
        f"**{total_lines:,}**"
        f" | 主程序 : 测试 ≈ 1 : {ratio:.2f}；仓库共 {len(files)} 个跟踪文件"
        f"（含示例图 {len(demo)} 个）",
    )
    return cells


def refresh_stats(text: str, files: list[str], root: Path | None = None) -> str:
    """重写「## 项目统计」表的数字列（说明列不动，合计行与尾巴一并重算）。"""
    cells = stats_cells(files, root)
    if not cells:
        return text
    start = text.index("## 项目统计")
    end = text.index("## 目录树")
    section = text[start:end]
    out: list[str] = []
    for line in section.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if not stripped.startswith("| "):
            out.append(line)
            continue
        cols = stripped.split("|")
        label = cols[1].strip()
        if label not in cells or len(cols) < 6:
            out.append(line)
            continue
        files_cell, lines_cell = cells[label]
        cols[3] = f" {files_cell} "
        if label == STAT_TOTAL_LABEL:
            head, _, tail = lines_cell.partition(" | ")
            cols[4] = f" {head} "
            cols[5] = f" {tail} "
        else:
            cols[4] = f" {lines_cell} "
        out.append("|".join(cols).rstrip() + "\n")
    return text[:start] + "".join(out) + text[end:]


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()

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
        text = refresh_stats(text, files)
        DOC.write_text(text, encoding="utf-8")
        print(
            f"已更新目录树与统计表：{len(files)} 个跟踪文件，"
            f"测试 {test_files} 个文件 / {test_lines:,} 行 / {test_function_count(tests)} 个 test 函数"
        )
        return 0
    print(tree)
    print(
        f"\n跟踪文件 {len(files)}；测试 {test_files} 个文件 / {test_lines:,} 行 / "
        f"{test_function_count(tests)} 个 test 函数"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
