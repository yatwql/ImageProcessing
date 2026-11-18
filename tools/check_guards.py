#!/usr/bin/env python3
"""工程守护：把 `CLAUDE.md` 里的硬性约束变成可执行检查。

    python tools/check_guards.py            # 人读
    python tools/check_guards.py --ci       # 只输出一行一结论，任一不过即退出码 1

覆盖项：
  编号      plan.md 用 `PLAN-x`（连续、唯一），review-findings.md 用 `RF-x`（唯一），无旧前缀
  分层      `core` 不得 import argparse/curses，不得调用 sys.exit/exit
  长度      单个源文件不超过 1000 行
  编码      文本 I/O 必须显式 `encoding=`（二进制模式除外）
  用例目录  `src/test` 下不得留只有 `__init__.py` 的空包，且目录要出现在 technical.md
  版本号    `src/python/version.py` 为唯一来源，pyproject 动态读取，各文档开头一致
  名称      `version.NAME` 与 pyproject 包名/控制台脚本一致，日志与界面都引用它
  目录树    `docs/managements/folders.md` 必须覆盖所有源文件与文档（新增文件要同步）
  测试字体  用例不得硬编码 `ImageFont.truetype(FONT_CJK…, index=…)`，必须走 `cjk_font()`
  依赖锁    `constraints.txt` 全部精确固定，且覆盖 pyproject 里声明的每个直接依赖
  PS 编码   `scripts/*.ps1` 必须是 UTF-8 with BOM（PowerShell 5.1 按 ANSI 读会乱码）
  scripts   `scripts/` 只放 .sh/.ps1 薄壳启动脚本（逻辑属于 `src/python` 或 `tools/`）
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Sequence
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
        try:
            nums.append(int(rid.split("-")[1]))
        except (IndexError, ValueError):
            bad.append(rid)
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


PIN_LINE = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)(?:\s*;\s*.+)?$")


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
            continue  # 平台条件依赖，非 Windows 上装不到也锁不到
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
        raise ValueError('src/python/version.py 里没有 VERSION = "..."')
    return m.group(1)


def current_name() -> str:
    """从 version.py 读出程序名（唯一来源）。"""
    text = _read(SRC / "python" / "version.py")
    m = re.search(r'^NAME\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise ValueError('src/python/version.py 里没有 NAME = "…"')
    return m.group(1)


TREE_LINE = re.compile(r"^((?:│   |    )*)(?:├── |└── )(.+)$")
TREE_FENCE = "```text"


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


def _hardcoded_font_lines(text: str) -> list[int]:
    """找出 `ImageFont.truetype(FONT_CJK…, …)` 这类调用（走 AST，不会误报文档串里的示例）。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "truetype"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        if node.args[0].id in ("FONT_CJK", "FONT_CJK_REG"):
            lines.append(node.lineno)
    return lines


def check_test_font_usage() -> list[str]:
    """用例里的字体必须走 `_support.cjk_font()`。

    硬编码 `ImageFont.truetype(FONT_CJK, size, index=2)` 假设了 Noto 的 ttc 布局：
    在 Windows（msyh.ttc）或精简镜像上会 `OSError: invalid argument`，整套用例连带失败。
    `cjk_font()` 会逐个候选字体、逐个 index 试，找不到就 SkipTest。
    """
    problems = []
    for path in sorted((SRC / "test").rglob("*.py")):
        if path.name == "_support.py":
            continue
        for lineno in _hardcoded_font_lines(_read(path)):
            problems.append(
                f"{path.relative_to(ROOT)}:{lineno} 硬编码字体 index，"
                "请改用 _support.cjk_font(size)"
            )
    return problems


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
    roots = [SRC, ROOT / "tools", ROOT / "scripts", ROOT / "docs",
             ROOT / ".githooks", ROOT / ".github"]
    missing = []
    for base in roots:
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel == "docs/managements/folders.md":
                continue                    # 自引用：文档自己在树里出现会显得多余
            if rel not in documented:
                missing.append(rel)
    for name in ("README.md", "CLAUDE.md", "pyproject.toml", "constraints.txt",
                 "requirements.txt", "requirements-dev.txt", ".gitignore"):
        if name not in documented:
            missing.append(name)
    if missing:
        return [f"folders.md 未覆盖：{', '.join(missing[:6])}"
                + (f" 等 {len(missing)} 个文件" if len(missing) > 6 else "")]
    return []


def check_name_consistency() -> list[str]:
    """程序名：version.NAME 是唯一来源，打包名与入口脚本名必须与之一致。"""
    name = current_name()
    problems = []
    pyproject = _read(ROOT / "pyproject.toml")
    if re.search(rf'^name\s*=\s*"{re.escape(name)}"', pyproject, re.MULTILINE) is None:
        problems.append(f"pyproject.toml 的 [project].name 不是 {name!r}")
    if re.search(rf'^{re.escape(name)}\s*=\s*"', pyproject, re.MULTILINE) is None:
        problems.append(f"pyproject.toml 缺控制台脚本 {name} = \"...\"")
    audit = _read(SRC / "python" / "core" / "audit.py")
    if '"app": NAME' not in audit:
        problems.append("写盘日志没有记录 app 字段（core/audit.build_entry）")
    return problems


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


def check_windows_scripts() -> list[str]:
    """Windows 脚本必须 UTF-8 with BOM：PowerShell 5.1 读无 BOM 文件按 ANSI 解释，
    中文提示会变成"缂哄皯杩愯鐜"这类乱码（用户看到的报错完全读不懂）。
    """
    problems = []
    for path in sorted((ROOT / "scripts").glob("*.ps1")):
        raw = path.read_bytes()
        if not raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{path.relative_to(ROOT)} 缺少 UTF-8 BOM（PS 5.1 下中文会乱码）")
    return problems


LAUNCHER_MAX_LINES = 40


def check_scripts_are_launchers() -> list[str]:
    """`scripts/` 只放 .sh/.ps1 启动脚本：业务逻辑进 `src/python`，工程工具进 `tools/`。

    判断标准是"薄"：单个脚本不超过 40 行。超过说明逻辑堆在这里了，
    要么挪进 `src/python/<渠道>`，要么挪进 `tools/`。
    """
    problems = []
    for path in sorted((ROOT / "scripts").iterdir()):
        if not path.is_file():
            continue
        if path.suffix not in (".sh", ".ps1"):
            problems.append(
                f"{path.relative_to(ROOT)} 不是 .sh/.ps1：scripts/ 只放启动脚本，"
                "逻辑请移到 src/python 或 tools/"
            )
            continue
        n = len(path.read_text(encoding="utf-8").splitlines())
        if n > LAUNCHER_MAX_LINES:
            problems.append(
                f"{path.relative_to(ROOT)} 有 {n} 行（上限 {LAUNCHER_MAX_LINES}）："
                "scripts/ 只放启动脚本，逻辑请移到 src/python 或 tools/"
            )
    return problems


CHECKS = [
    ("编号-plan", check_plan_ids),
    ("编号-review", check_rf_ids),
    ("分层-core", check_layering),
    ("文件长度", check_file_length),
    ("显式编码", check_explicit_encoding),
    ("测试目录", check_test_layout),
    ("版本号", check_version_consistency),
    ("名称", check_name_consistency),
    ("目录树文档", check_folders_doc),
    ("测试字体", check_test_font_usage),
    ("依赖锁", check_constraints),
    ("PS 编码", check_windows_scripts),
    ("scripts 薄壳", check_scripts_are_launchers),
]


def main(argv: Sequence[str] = ()) -> int:
    # 空序列表示"没传参"，避免 `x is None` 形式的静态规则噪音
    args = list(argv) if argv else sys.argv[1:]
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
