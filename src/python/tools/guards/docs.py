"""文档守护：目录树文档、文档索引、归档目录与台账索引（守护第 9/12/13 项）。"""

from __future__ import annotations

from pathlib import Path

from .._paths import ROOT
from .common import (
    ARCHIVE,
    ARCHIVE_FILE,
    ARCHIVE_HEADING,
    ARCHIVE_LEDGERS,
    ARCHIVE_META,
    ARCHIVE_SERIES_DIR,
    DOCS,
    SRC,
    TREE_FENCE,
    TREE_LINE,
    _read,
)


def tree_paths(text: str) -> set[str]:
    """把 folders.md 里的树状图解析成完整路径集合（按缩进还原层级）。

    目录以 `/` 结尾；行尾的 `# 说明` 先剥掉再取名字。
    """
    paths: set[str] = set()
    stack: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith(TREE_FENCE):
            inside, stack = True, []
            continue
        if inside and line.startswith("```"):
            break
        if not inside:
            continue
        m = TREE_LINE.match(line)
        if m is None:
            continue
        depth = len(m.group(1)) // 4
        name = m.group(2).split("#", 1)[0].strip()
        stack = stack[:depth]
        if not name:
            continue
        if name.endswith("/"):
            stack.append(name.rstrip("/"))
        else:
            paths.add("/".join([*stack, name]))
    return paths


def check_folders_doc() -> list[str]:
    """目录树文档必须覆盖所有源文件/文档：新增或移动文件时忘了同步，这里会红。

    运行期产物（data/output、logs、reports、.venv、缓存）不在核对范围内。
    """
    doc = DOCS / "folders.md"
    if not doc.is_file():
        return ["缺少 docs/managements/folders.md（目录树文档）"]
    documented = tree_paths(_read(doc))
    if not documented:
        return ["folders.md 里没有可解析的目录树（```text 区块）"]
    roots = [
        SRC,
        ROOT / "tools",
        ROOT / "scripts",
        ROOT / "docs",
        ROOT / ".githooks",
        ROOT / ".github",
    ]
    missing = []
    for base in roots:
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel == "docs/managements/folders.md":
                continue  # 自引用：文档自己在树里出现会显得多余
            if rel not in documented:
                missing.append(rel)
    for name in (
        "README.md",
        "CLAUDE.md",
        "pyproject.toml",
        "constraints.txt",
        "requirements.txt",
        "requirements-dev.txt",
        ".gitignore",
    ):
        if name not in documented:
            missing.append(name)
    if missing:
        return [
            f"folders.md 未覆盖：{', '.join(missing[:6])}"
            + (f" 等 {len(missing)} 个文件" if len(missing) > 6 else "")
        ]
    return []


def check_docs_index() -> list[str]:
    """文档索引：`docs/README.md` 必须链接到每份管理文档与手册，否则等于没入口。"""
    index = ROOT / "docs" / "README.md"
    if not index.is_file():
        return ["缺少 docs/README.md（文档索引）"]
    text = _read(index)
    problems = []
    for base in (DOCS, ROOT / "docs" / "manuals"):
        for path in sorted(base.glob("*.md")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "docs/README.md":
                continue
            if path.name not in text and rel not in text:
                problems.append(f"{rel} 未出现在 docs/README.md 索引里")
    return problems


def _check_archive_file(path: Path, series: str) -> list[str]:
    """单个归档文件：命名里的台账名与系列号要合法，头部四个字段不能少。"""
    rel = path.relative_to(ROOT).as_posix()
    m = ARCHIVE_FILE.fullmatch(path.name)
    if m is None:
        return [f"{rel} 命名应为 archived_<plan|review-findings|changelog>.<系列>.md"]
    problems: list[str] = []
    if m.group(2) != series:
        problems.append(f"{rel} 的系列号与目录 v{series} 不一致")
    text = _read(path)
    missing = [key for key in ARCHIVE_META if f"> {key}" not in text]
    if missing:
        problems.append(f"{rel} 缺少归档头部「> {'」「> '.join(missing)}」")
    return problems


def check_archive_layout() -> list[str]:
    """归档目录：只有 `vX.Y.x/` 子目录，归档文件命名与头部字段固定，三份台账都有归档索引。

    规则见 `docs/archive/README.md`：旧版本的台账内容按版本系列整块搬进归档，
    主文件只留当前开发版本的内容与索引；归档文件不改一字，也不参与版本号守护。
    """
    if not ARCHIVE.is_dir():
        return ["缺少 docs/archive/（归档目录与规范）"]
    problems: list[str] = []
    readme = ARCHIVE / "README.md"
    index = ROOT / "docs" / "README.md"
    if not readme.is_file():
        problems.append("缺少 docs/archive/README.md（归档规范）")
    elif not index.is_file() or "archive/README.md" not in _read(index):
        problems.append("docs/archive/README.md 未出现在 docs/README.md 索引里")
    for series_dir in sorted(p for p in ARCHIVE.iterdir() if p.is_dir()):
        if not ARCHIVE_SERIES_DIR.fullmatch(series_dir.name):
            problems.append(f"docs/archive/{series_dir.name}/ 目录名应为 vX.Y.x（版本系列）")
            continue
        series = series_dir.name[1:]
        for path in sorted(series_dir.iterdir()):
            if not path.is_dir():  # 设计稿/中间稿按任务建子目录，名字不限
                problems += _check_archive_file(path, series)
    for name in ARCHIVE_LEDGERS:
        ledger = DOCS / name
        if ledger.is_file() and ARCHIVE_HEADING not in _read(ledger):
            problems.append(f"docs/managements/{name} 缺 `{ARCHIVE_HEADING}` 索引段")
    return problems
