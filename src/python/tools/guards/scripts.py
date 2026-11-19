"""脚本与文档链路的守护：脚本命名/契约、文档死链、用例对照表覆盖。

三项检查都落在"约束既写进文档、又能被机器照出来"这条线上：

- `check_script_names()`：`scripts/` 只允许 kebab-case 薄壳；`tools/` 顶层脚本按活动类型前缀命名，
  必须有"怎么跑"的 docstring、必须被某个用例按模块名引用、`check_*` 必须支持 `--ci`。
- `check_docs_links()`：`docs/`（归档除外）与 README/CLAUDE.md 里的相对链接必须能落地。
- `check_test_doc_table()`：每个 `src/test/**/test_*.py` 都要出现在 `technical.md` 的用例对照表里。
"""

from __future__ import annotations

import re
from pathlib import Path

from .._paths import ROOT

# scripts/ 薄壳：小写 kebab-case，扩展名只认 .sh/.ps1
SHELL_NAME = re.compile(r"^[a-z][a-z0-9-]*\.(?:sh|ps1)$")

# tools/ 顶层脚本按"活动类型"前缀命名（`_` 前缀是共享设施，不在此列）
TOOL_PREFIXES = (
    "check_",
    "run_",
    "gen_",
    "gate_",
    "junit_",
    "coverage_",
    "mutation_",
    "ci_",
    "update_",
)
TOOL_STANDALONE = {"release.py"}
# 不需要"被用例引用"的一次性工具：真跑外部环境，用例里只打桩不覆盖
TOOL_UNTESTED_OK = {"mutation_check.py"}

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _tools(root: Path) -> list[Path]:
    tools = root / "src" / "python" / "tools"
    return sorted(
        p for p in tools.glob("*.py") if not p.name.startswith("_") and p.name != "__init__.py"
    )


def _test_blobs(root: Path) -> str:
    blobs = []
    for path in sorted((root / "src" / "test").rglob("*.py")):
        try:
            blobs.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(blobs)


def check_script_names(root: Path = ROOT) -> list[str]:
    """脚本命名与契约：命名、可运行说明、被用例引用、`check_*` 支持 `--ci`（守护「脚本契约」）。"""
    problems: list[str] = []
    scripts = root / "scripts"
    if scripts.is_dir():
        for path in sorted(scripts.iterdir()):
            if not path.is_file() or path.suffix not in {".sh", ".ps1"}:
                continue
            if not SHELL_NAME.match(path.name):
                problems.append(
                    f"scripts/{path.name} 命名不合规：薄壳一律小写 kebab-case（如 run-test.sh / log-query.sh）"
                )

    tests = _test_blobs(root)
    for path in _tools(root):
        name = path.name
        if name not in TOOL_STANDALONE and not name.startswith(TOOL_PREFIXES):
            problems.append(
                f"tools/{name} 命名不合规：按活动类型选前缀（check_/run_/gen_/gate_/junit_/"
                "coverage_/mutation_/ci_/update_），共享设施用 `_` 前缀"
            )
        text = path.read_text(encoding="utf-8")
        head = text.lstrip().split('"""')
        doc = head[1] if len(head) > 1 else ""
        if not doc.strip():
            problems.append(f"tools/{name} 缺模块 docstring：至少写清「跑什么、怎么跑」")
        elif not ("python -m src.python.tools." in doc or f"tools/{path.stem}.py" in doc):
            problems.append(
                f"tools/{name} 的 docstring 缺运行示例：写一行 `python -m src.python.tools.<名> …`"
            )
        if name.startswith("check_") and "--ci" not in text:
            problems.append(
                f"tools/{name} 是检查类脚本，必须支持 `--ci`（一行一结论，供门禁/CI 用）"
            )
        if name not in TOOL_UNTESTED_OK and path.stem not in tests:
            problems.append(f"tools/{name} 没有被任何用例引用：请在 src/test/tools/ 下加用例")
    return problems


def _doc_files(root: Path) -> list[Path]:
    files = [root / "README.md", root / "CLAUDE.md"]
    docs = root / "docs"
    if docs.is_dir():
        for path in sorted(docs.rglob("*.md")):
            if "archive" in path.parts:  # 归档文不改一字，不参与链接守护
                continue
            files.append(path)
    return [p for p in files if p.is_file()]


def check_docs_links(root: Path = ROOT) -> list[str]:
    """文档死链：相对链接的落点必须真实存在（守护「文档链接」）。

    只查"落点存在"：锚点校验对中文标题容易误报，收益低于噪音。
    """
    problems: list[str] = []
    for path in _doc_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith("#") or SCHEME.match(target) or target.startswith("//"):
                continue
            clean = target.split("#", 1)[0]
            if not clean:
                continue
            resolved = (path.parent / clean).resolve()
            if not resolved.exists():
                rel = path.relative_to(root).as_posix()
                problems.append(f"{rel} 链接失效：{target}")
    return problems


def check_test_doc_table(root: Path = ROOT) -> list[str]:
    """用例对照表：每个测试文件都要在 technical.md 里说明"守的是什么"（守护「用例对照」）。"""
    doc = root / "docs" / "managements" / "technical.md"
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError:
        return ["缺少 docs/managements/technical.md，无法核对用例对照表"]
    problems: list[str] = []
    for path in sorted((root / "src" / "test").rglob("test_*.py")):
        if path.stem not in text:
            problems.append(
                f"{path.relative_to(root).as_posix()} 未出现在 technical.md 的用例对照表里"
            )
    return problems


# 位置序号会随"在中间插一条守护"整体后移，写死序号等于给未来埋漂移；
# 引用守护一律写名字（`守护「导入方向」`），名字不会变。
POSITIONAL_GUARD_REF = re.compile(r"守护第\s*\d+(?:\s*[~-]\s*\d+)?\s*项")
REF_SCAN_DIRS = ("src/python", "docs/managements", "docs/manuals")


def check_guard_references(root: Path = ROOT) -> list[str]:
    """守护引用：文档与代码里不许用「守护第 N 项」这种位置序号（守护「守护引用」）。"""
    problems: list[str] = []
    files: list[Path] = [root / "README.md", root / "CLAUDE.md", root / "docs" / "README.md"]
    for rel in REF_SCAN_DIRS:
        base = root / rel
        if base.is_dir():
            files += sorted(base.rglob("*.md")) + sorted(base.rglob("*.py"))
    for path in files:
        if not path.is_file() or "archive" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if POSITIONAL_GUARD_REF.search(line):
                rel = path.relative_to(root).as_posix()
                problems.append(
                    f"{rel}:{lineno} 用位置序号引用守护（「守护第 N 项」）：改用守护名字，序号会漂移"
                )
    return problems
