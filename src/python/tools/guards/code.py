"""代码守护：分层方向、单文件长度、显式编码、测试目录与字体、脚本类型与编码（守护第 3~6/10/17~18 项）。"""

from __future__ import annotations

import ast
import subprocess
import sys

from .._paths import ROOT
from .common import (
    DOCS,
    LAUNCHER_MAX_LINES,
    MAX_FILE_LINES,
    SRC,
    _read,
)


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


COMPLEXITY_CEILING = 50  # 单个函数的圈复杂度红线：超过就必须先拆再合入


def check_complexity_ceiling() -> list[str]:
    """圈复杂度上限（守护「复杂度上限」）。

    现有几个"搜索/交互"函数天然偏长（`ui_actions.handle` 48、`fit_font` 27、
    `edit.replace_image` 30），一次拆完风险大于收益；这里钉住**上限**，只防"更糟"。
    基线见 technical.md「已知技术债」表。
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "C901",
            "--config",
            f"lint.mccabe.max-complexity={COMPLEXITY_CEILING}",
            "--output-format",
            "concise",
            "src/python",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        return []
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if "C901" in line
    ] or ["复杂度检查失败（ruff 不可用？）"]


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
    if (isinstance(fn, ast.Name) and fn.id == "open") or (
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


def check_scripts_are_launchers() -> list[str]:
    """`scripts/` 只放 .sh/.ps1 启动脚本：业务逻辑进 `src/python`，工程工具进 `tools/`。

    判断标准是"薄"：单个脚本不超过 40 行。超过说明逻辑堆在这里了，
    要么挪进 `src/python/<渠道>`，要么挪进 `src/python/tools/`。
    """
    problems = []
    for path in sorted((ROOT / "scripts").iterdir()):
        if not path.is_file():
            continue
        if path.suffix not in (".sh", ".ps1"):
            problems.append(
                f"{path.relative_to(ROOT)} 不是 .sh/.ps1：scripts/ 只放启动脚本，"
                "逻辑请移到 src/python（渠道或 tools/）"
            )
            continue
        n = len(path.read_text(encoding="utf-8").splitlines())
        if n > LAUNCHER_MAX_LINES:
            problems.append(
                f"{path.relative_to(ROOT)} 有 {n} 行（上限 {LAUNCHER_MAX_LINES}）："
                "scripts/ 只放启动脚本，逻辑请移到 src/python 或 tools/"
            )
    return problems
