#!/usr/bin/env python3
"""工程守护：把 `CLAUDE.md` 里的硬性约束变成可执行检查。

    python scripts/check-guards.py            # 人读
    python scripts/check-guards.py --ci       # 只输出一行一结论，任一不过即退出码 1

覆盖项：
  编号      plan.md 用 `PLAN-x`（连续、唯一），review-findings.md 用 `RF-x`（唯一），无旧前缀
  分层      `core` 不得 import argparse/curses，不得调用 sys.exit/exit
  长度      单个源文件不超过 1000 行
  编码      文本 I/O 必须显式 `encoding=`（二进制模式除外）
  用例目录  `src/test` 下不得留只有 `__init__.py` 的空包，且目录要出现在 technical.md
  版本号    `src/python/version.py` 为唯一来源，pyproject 动态读取，各文档开头一致
  依赖锁    `constraints.txt` 全部精确固定，且覆盖 pyproject 里声明的每个直接依赖
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DOCS = ROOT / "docs" / "managements"

MAX_FILE_LINES = 1000
LEGACY_ID = re.compile(r"\b(?:TD|P|F|N)-\d+\b")
ROW_ID = re.compile(r"^\|\s*([A-Z]+-\d+)\s*\|")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_plan_ids() -> list[str]:
    """plan.md 的任务编号必须是 PLAN-1..PLAN-N，连续且唯一。"""
    path = DOCS / "plan.md"
    if not path.is_file():
        return ["缺少 docs/managements/plan.md"]
    nums = []
    bad = []
    for line in _read(path).splitlines():
        m = ROW_ID.match(line)
        if not m:
            continue
        rid = m.group(1)
        if not rid.startswith("PLAN-"):
            bad.append(rid)
            continue
        nums.append(int(rid.split("-")[1]))
    if bad:
        return [f"plan.md 出现非 PLAN- 编号：{', '.join(sorted(set(bad))[:5])}"]
    if sorted(nums) != list(range(1, len(nums) + 1)):
        dup = sorted({n for n in nums if nums.count(n) > 1})
        return [f"plan.md 编号不连续或重复（重复：{dup or '无'}，共 {len(nums)} 条）"]
    return []


def check_rf_ids() -> list[str]:
    """review-findings.md 的任务编号必须是 RF-x（唯一），且不出现旧前缀。"""
    path = DOCS / "review-findings.md"
    if not path.is_file():
        return ["缺少 docs/managements/review-findings.md"]
    text = _read(path)
    ids = [m.group(1) for m in (ROW_ID.match(line) for line in text.splitlines()) if m]
    bad = [i for i in ids if not i.startswith("RF-")]
    if bad:
        return [f"review-findings.md 出现非 RF- 编号：{', '.join(sorted(set(bad))[:5])}"]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        return [f"review-findings.md 编号重复：{', '.join(dups[:5])}"]
    legacy = sorted(set(LEGACY_ID.findall(text)))
    if legacy:
        return [f"review-findings.md 残留旧编号：{', '.join(legacy[:5])}"]
    return []


def check_layering() -> list[str]:
    """core 是纯逻辑层：不得依赖命令行/终端，也不得自己退出进程。"""
    problems = []
    for path in sorted((SRC / "python" / "core").rglob("*.py")):
        tree = ast.parse(_read(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
                for banned in ("argparse", "curses"):
                    if banned in names:
                        problems.append(f"{path.relative_to(ROOT)}:{node.lineno} import {banned}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in ("argparse", "curses"):
                    problems.append(f"{path.relative_to(ROOT)}:{node.lineno} from {top}")
            elif isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name == "exit":
                    problems.append(f"{path.relative_to(ROOT)}:{node.lineno} 调用 exit()")
    return problems


def check_file_length() -> list[str]:
    problems = []
    for path in sorted(SRC.rglob("*.py")):
        n = len(_read(path).splitlines())
        if n > MAX_FILE_LINES:
            problems.append(f"{path.relative_to(ROOT)} 有 {n} 行（上限 {MAX_FILE_LINES}）")
    return problems


def _is_text_open(node: ast.Call) -> str | None:
    """返回文本模式字符串；二进制模式或不是内建 open 时返回 None。"""
    fn = node.func
    if isinstance(fn, ast.Name) and fn.id == "open":
        pass
    elif (
        isinstance(fn, ast.Attribute)
        and fn.attr == "open"
        and isinstance(fn.value, ast.Name)
        and fn.value.id == "io"
    ):
        pass
    else:
        return None
    mode = "r"
    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
        mode = str(node.args[1].value)
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = str(kw.value.value)
    return None if "b" in mode else mode


def check_explicit_encoding() -> list[str]:
    """文本 I/O 必须显式 encoding（跨平台中文不炸）。"""
    problems = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(_read(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            mode = _is_text_open(node)
            if mode is not None:
                if not any(kw.arg == "encoding" for kw in node.keywords):
                    problems.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} open({mode!r}) 缺 encoding="
                    )
                continue
            name = getattr(node.func, "attr", "")
            if name in ("read_text", "write_text") and not any(
                kw.arg == "encoding" for kw in node.keywords
            ):
                problems.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}() 缺 encoding=")
    return problems


def check_test_layout() -> list[str]:
    """测试目录：不留空包，且每个目录都写进 technical.md 的用例对照表。"""
    test_root = SRC / "test"
    doc = DOCS / "technical.md"
    doc_text = _read(doc) if doc.is_file() else ""
    problems = []
    dirs = {p.parent for p in test_root.rglob("test_*.py")}
    for d in sorted(dirs):
        rel = d.relative_to(ROOT).as_posix()
        if d.name not in doc_text:
            problems.append(f"{rel} 未出现在 technical.md 的用例对照表")
    for d in sorted(p for p in test_root.rglob("*") if p.is_dir()):
        if any(d.glob("*.py")) and not any(d.rglob("test_*.py")):
            problems.append(f"{d.relative_to(ROOT).as_posix()} 是空测试包（只有 __init__.py）")
    return problems


PIN_LINE = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)$")


def _dep_name(spec: str) -> str:
    """'pillow>=10.0' / 'windows-curses; sys_platform == "win32"' → 'pillow'。"""
    return re.split(r"[<>=!~;\[ ]", spec.strip(), maxsplit=1)[0].lower().replace("_", "-")


def check_constraints() -> list[str]:
    """依赖锁：必须全量精确固定，且覆盖 pyproject 的直接依赖（漏一个就会浮动升级）。"""
    path = ROOT / "constraints.txt"
    if not path.is_file():
        return ["缺少 constraints.txt（依赖版本会随上游漂移）"]
    pinned: set[str] = set()
    problems = []
    for raw in _read(path).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = PIN_LINE.match(line)
        if not m:
            problems.append(f"constraints.txt 未精确固定：{line}")
            continue
        pinned.add(m.group(1).lower().replace("_", "-"))
    data = tomllib.loads(_read(ROOT / "pyproject.toml"))
    for spec in data.get("project", {}).get("dependencies", []):
        name = _dep_name(spec)
        if name == "windows-curses" and sys.platform != "win32":
            continue                      # 平台条件依赖，非 Windows 上装不到也锁不到
        if name not in pinned:
            problems.append(f"constraints.txt 缺少直接依赖 {name}")
    return problems


VERSION_LINE = re.compile(r"^>\s*版本：v(\S+)\s*$", re.MULTILINE)
VERSION_DOCS = [
    "README.md",
    "CLAUDE.md",
    "docs/managements/requirements.md",
    "docs/managements/technical.md",
    "docs/managements/plan.md",
    "docs/managements/changelog.md",
    "docs/managements/review-findings.md",
    "docs/manuals/how-to-use.md",
]


def current_version() -> str:
    """从 version.py 读出版本号（唯一来源）。"""
    text = _read(SRC / "python" / "version.py")
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise ValueError("src/python/version.py 里没有 VERSION = \"...\"")
    return m.group(1)


def check_version_consistency() -> list[str]:
    """版本号：代码是唯一来源，打包配置与各文档开头必须与之一致。"""
    version = current_version()
    problems = []
    pyproject = _read(ROOT / "pyproject.toml")
    if 'version = { attr = "src.python.version.VERSION" }' not in pyproject:
        problems.append("pyproject.toml 未指向 src.python.version.VERSION（版本号会两处不一致）")
    for rel in VERSION_DOCS:
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} 不存在")
            continue
        m = VERSION_LINE.search(_read(path))
        if not m:
            problems.append(f"{rel} 开头缺少「> 版本：v{version}」行")
        elif m.group(1) != version:
            problems.append(f"{rel} 版本是 v{m.group(1)}，与 version.py 的 v{version} 不一致")
    return problems


CHECKS = [
    ("编号-plan", check_plan_ids),
    ("编号-review", check_rf_ids),
    ("分层-core", check_layering),
    ("文件长度", check_file_length),
    ("显式编码", check_explicit_encoding),
    ("测试目录", check_test_layout),
    ("版本号", check_version_consistency),
    ("依赖锁", check_constraints),
]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    quiet = "--ci" in args
    failed = 0
    for name, fn in CHECKS:
        try:
            problems = fn()
        except (OSError, SyntaxError, ValueError) as exc:  # 解析不了本身就是缺陷
            problems = [f"检查失败：{exc}"]
        if problems:
            failed += 1
            if quiet:
                print(
                    f"FAIL {name}: {problems[0]}"
                    + (f"（共 {len(problems)} 处）" if len(problems) > 1 else "")
                )
            else:
                print(f"[FAIL] {name}")
                for p in problems[:20]:
                    print(f"       {p}")
                if len(problems) > 20:
                    print(f"       …… 另有 {len(problems) - 20} 处")
        elif not quiet:
            print(f"[ok]   {name}")
    if quiet:
        print(f"guards: {len(CHECKS) - failed}/{len(CHECKS)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
