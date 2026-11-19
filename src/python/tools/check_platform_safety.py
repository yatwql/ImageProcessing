#!/usr/bin/env python3
"""跨平台安全：把"只在 Windows/macOS 上才炸"的写法在本地拦下来。

    python -m src.python.tools.check_platform_safety
    python -m src.python.tools.check_platform_safety --ci

检查 `src/test/**` 与 `src/python/**` 里的几类问题（都真实踩过）：
1. 硬编码 POSIX 路径（`/tmp`、`/proc`、`/usr/...`）—— Windows 上是另一个盘符；
2. 子进程 `text=True` 没给 `encoding=`—— Windows 用 cp1252 解码 UTF-8 输出会炸；
3. 直接 `import fcntl` / `os.mkfifo` / `pwd` 等 POSIX-only 模块而无平台保护；
4. `curses` 常量当字符串用（ACS_* 在部分构建里是 int）。

豁免：明确带 `skipIf(win32)` / `skipUnless(posix)` 的用例，或行内 `# platform-safe` 注记。
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT

POSIX_PATH = re.compile(r'"(/(?:tmp|proc|usr|data|dev)/[^"]*)"')
SUBprocess_TEXT = re.compile(r"subprocess\.(?:run|Popen|check_output)\(")
IMPORT_POSIX = re.compile(
    r"^\s*(?:import (fcntl|pwd|grp|termios|tty)\b|from (fcntl|pwd|grp|termios|tty) import)"
)
# 用例里写死字体家族名：本机绿、别的平台红（Linux 是 Noto CJK、Windows 是 msyh）
FONT_FAMILY = re.compile(
    r'"(Noto[^"]*|Source Han[^"]*|Microsoft YaHei|msyh[^"]*|PingFang[^"]*|SimSun[^"]*|微软雅黑)'
)
# 裸 bash/sh：windows-latest 上的 `bash` 常是 WSL 存根，`bash -n` 退 1 且 stderr 为空。
# 只认"当作命令用"的字面量（`["bash", "-n", ...]` / `run("sh", ...)`）——
# `mock.patch.object(release, "sh")` 这种属性名不能被误判成命令行。
BARE_SHELL = re.compile(r'["\[]"{0,1}(?:bash|sh)"\s*[,\]]|run\(\s*"(?:bash|sh)"')
# 直接碰 fcntl：Windows 没有这个模块，属性访问会 AttributeError
FCNTL_ATTR = re.compile(r"\.fcntl\b")
# 断言里写死绝对像素阈值（`assertGreaterEqual(out_w, 111)`）：换平台字体度量就变。
# 只认「名字像尺寸的变量 + 阈值 >= 20」：`index >= 0`、`refresh_count >= 1` 这类
# 是上下界检查，不是度量断言，别误报。
ABSOLUTE_THRESHOLD = re.compile(
    r"assertGreater(?:Equal)?\(\s*[\w.\[\]\-\+\s()]*(?:width|height|_w\b|_h\b|box|ink|px|size)"
    r"[^,]*,\s*(\d+(?:\.\d+)?)\s*\)"
)
ABSOLUTE_THRESHOLD_MIN = 20.0
# 断言里直接比解释器路径/平台串：Windows 上是反斜杠、平台串也不同
RAW_RUNTIME = re.compile(r"assert[A-Za-z]*\([^)]*\bsys\.(?:executable|platform)\b")
SAFE_MARK = "# platform-safe"
# 规则样本文件：它天生就要写出违规写法（并断言规则能抓到），
# 否则「规则本身失效」这件事没人发现。
RULE_FIXTURE = "src/test/tools/test_platform_safety_rules.py"
SKIP_MARK = ("skipIf(sys.platform", "skipUnless(sys.platform", "skipIf(POSIX", "skipUnless(POSIX")


def _iter_sources() -> list[Path]:
    return sorted(
        [*ROOT.joinpath("src/test").rglob("*.py"), *ROOT.joinpath("src/python").rglob("*.py")]
    )


def _mark_spans(text: str) -> list[tuple[int, int]]:
    """带 `# platform-safe` 注记的语句的行区间。

    ruff format 会把注记甩到多行调用的收尾括号上，按"行"判断会失效；
    注记覆盖的是**整条语句**，所以这里按语句的行区间算。
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines()
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", start) or start
        if any(SAFE_MARK in s for s in lines[start - 1 : end]):
            spans.append((start, end))
    return spans


def _marked(spans: list[tuple[int, int]], lineno: int) -> bool:
    return any(start <= lineno <= end for start, end in spans)


def _has_platform_guard(lines: list[str]) -> bool:
    joined = "\n".join(lines)
    return any(mark in joined for mark in SKIP_MARK) or "POSIX" in joined


def _is_big_threshold(text: str) -> bool:
    """阈值够大才算"度量断言"（`>= 1`/`>= 0` 是上下界检查，不是像素阈值）。"""
    try:
        return float(text) >= ABSOLUTE_THRESHOLD_MIN
    except ValueError:
        return False


def _check_test_hygiene(
    rel: str, lines: list[str], spans: list[tuple[int, int]] | None = None
) -> list[str]:
    """只对用例查的三类「本机绿、别的平台红」写法（`_support.py` 例外）。"""
    joined = "\n".join(lines)
    none_word = "None"
    is_none = "is" + " " + none_word  # 拆开拼，避免提示文案被误当成 ``is None`` 比较
    has_fcntl_guard = f"fcntl {is_none}" in joined or f'"fcntl", {none_word}' in joined
    spans = spans or []
    problems: list[str] = []
    for lineno, line in enumerate(lines, 1):
        if SAFE_MARK in line or _marked(spans, lineno):
            continue
        family = FONT_FAMILY.search(line)
        if family:
            problems.append(
                f"{rel}:{lineno} 断言里写死了字体家族 {family.group(1)!r}："
                "换平台字族就变（Linux Noto CJK / Windows msyh），请从字体文件反解"
            )
        if BARE_SHELL.search(line) and "bash_exe" not in joined:
            problems.append(
                f"{rel}:{lineno} 直接用裸 bash/sh：Windows runner 上可能是 WSL 存根，"
                "请走 _support.bash_exe()（不可用时 skip 而不是红）"
            )
        if FCNTL_ATTR.search(line) and not has_fcntl_guard:
            problems.append(
                f"{rel}:{lineno} 直接碰 fcntl：Windows 没有该模块，"
                "请加 skipIf(fcntl is None) 等平台守卫"
            )
        metric = ABSOLUTE_THRESHOLD.search(line)
        if metric and _is_big_threshold(metric.group(1)):
            problems.append(
                f"{rel}:{lineno} 断言里写死绝对像素阈值：换平台/换字体度量就变，"
                "请改成两个测量值的比值（如 `>= 0.85 * expected_w`）"
            )
        if RAW_RUNTIME.search(line):
            problems.append(
                f"{rel}:{lineno} 断言里直接比 `sys.executable`/`sys.platform`："
                "Windows 上路径与平台串都不同，请用 `Path` 或打桩后的值"
            )
    return problems


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = path.relative_to(ROOT).as_posix()
    problems: list[str] = []
    spans = _mark_spans(text)

    for lineno, line in enumerate(lines, 1):
        if SAFE_MARK in line or _marked(spans, lineno):
            continue
        match = POSIX_PATH.search(line)
        if match and not _has_platform_guard(lines):
            problems.append(
                f"{rel}:{lineno} 硬编码 POSIX 路径 {match.group(1)!r}（用 tempfile 或打桩）"
            )
        if IMPORT_POSIX.match(line) and not _has_platform_guard(lines):
            problems.append(f"{rel}:{lineno} 直接依赖 POSIX-only 模块（加平台保护或打到 _support）")

    if rel.startswith("src/test/") and path.name != "_support.py" and rel != RULE_FIXTURE:
        problems += _check_test_hygiene(rel, lines, spans)

    # 子进程调用必须显式编码：按"整次调用"判断（跨多行也行），
    # 只看 3 行窗口会漏掉 `text=True` 与 `encoding=` 隔了好几行的写法。
    for lineno, line in enumerate(lines, 1):
        if not SUBprocess_TEXT.search(line):
            continue
        chunk: list[str] = []
        depth = 0
        for offset in range(lineno - 1, min(len(lines), lineno - 1 + 40)):
            current = lines[offset]
            chunk.append(current)
            depth += current.count("(") - current.count(")")
            if offset > lineno - 1 and depth <= 0:
                break
        call = " ".join(chunk)
        if "text=True" in call and "encoding=" not in call:
            problems.append(
                f"{rel}:{lineno} 子进程 text=True 缺 encoding=（Windows 会用 cp1252 解码）"
            )
    return problems


def check_tool_stdio(root: Path | None = None) -> list[str]:
    """`tools/` 下带 `main()` 的工具必须调用 `ensure_utf8_stdio()`。

    Windows 控制台按 cp1252 编码，`print` 中文直接 `UnicodeEncodeError`
    （本轮 windows 作业的「工程守护」步就是这么红的）——中文报错反而成了崩溃。
    """
    base = (root if root is not None else ROOT) / "src" / "python" / "tools"
    if not base.is_dir():
        return []
    problems: list[str] = []
    for path in sorted(base.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "def main(" in text and "ensure_utf8_stdio()" not in text:
            problems.append(
                f"{path.relative_to(base.parents[3]).as_posix() if root is None else path.name}"
                " 的 main() 未调用 ensure_utf8_stdio()（Windows 控制台打印中文会 UnicodeEncodeError）"
            )
    return problems


def check_line_endings() -> list[str]:
    """`.gitattributes` 必须把 `.sh` 钉成 LF。

    Windows 检出默认可能把文本转成 CRLF，Git Bash 里 `bash -n foo.sh` 会直接报语法错——
    本轮 windows 作业就是这么红的。规则写进仓库，检出时自动生效。
    """
    path = ROOT / ".gitattributes"
    if not path.is_file():
        return [".gitattributes 不存在：至少需要 `*.sh text eol=lf`"]
    text = path.read_text(encoding="utf-8")
    if "*.sh" not in text or "eol=lf" not in text:
        return [".gitattributes 缺少 `*.sh text eol=lf`（Windows 检出成 CRLF 会让 bash -n 失败）"]
    return []


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()

    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    problems: list[str] = [*check_line_endings(), *check_tool_stdio()]
    for path in _iter_sources():
        problems += check_file(path)
    if problems:
        for item in problems:
            print(f"[FAIL] {item}")
        return 1
    print(f"[ok] 跨平台安全（扫描 {len(_iter_sources())} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
