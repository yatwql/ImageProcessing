"""工程元信息守护：版本号与名称、依赖锁、导入方向、工作流、跨平台安全（守护第 7~8/11/14~16 项）。"""

from __future__ import annotations

import re
import subprocess
import sys

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # 3.10：用 tomli（dev 依赖，带平台标记）
    import tomli as tomllib

from .._paths import ROOT
from .common import (
    PIN_LINE,
    SRC,
    VERSION_DOCS,
    VERSION_LINE,
    _read,
)


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


def current_updated() -> str | None:
    """从 version.py 读代码更新日期（YYYY-MM-DD）。"""
    text = _read(SRC / "python" / "version.py")
    m = re.search(r'^UPDATED\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else None


def git_src_date() -> str | None:
    """`src/` 最后一次提交的日期；没有 git（安装包）或命令不可用时返回 None。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", "src"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    stamp = out.stdout.strip()
    return stamp or None


def check_version_consistency() -> list[str]:
    """版本号：代码是唯一来源，打包配置与各文档开头必须与之一致。"""
    version = current_version()
    problems = []
    updated = current_updated()
    if updated is None:
        problems.append('src/python/version.py 里没有 UPDATED = "YYYY-MM-DD"')
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
        problems.append(f"UPDATED 格式应为 YYYY-MM-DD，收到 {updated!r}")
    else:
        commit_date = git_src_date()
        if commit_date and commit_date != updated:
            problems.append(
                f"UPDATED 是 {updated}，但 src/ 最后提交是 {commit_date}"
                "（改了代码要同步更新 src/python/version.py 的 UPDATED）"
            )
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


def check_name_consistency() -> list[str]:
    """程序名：version.NAME 是唯一来源，打包名与入口脚本名必须与之一致。"""
    name = current_name()
    problems = []
    pyproject = _read(ROOT / "pyproject.toml")
    if re.search(rf'^name\s*=\s*"{re.escape(name)}"', pyproject, re.MULTILINE) is None:
        problems.append(f"pyproject.toml 的 [project].name 不是 {name!r}")
    if re.search(rf'^{re.escape(name)}\s*=\s*"', pyproject, re.MULTILINE) is None:
        problems.append(f'pyproject.toml 缺控制台脚本 {name} = "..."')
    audit = _read(SRC / "python" / "core" / "audit.py")
    if '"app": NAME' not in audit:
        problems.append("写盘日志没有记录 app 字段（core/audit.build_entry）")
    return problems


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


def check_import_surface() -> list[str]:
    """架构约束（AR-1/AR-2）：导入方向必须单一，渠道之间不得互相依赖。"""
    result = subprocess.run(
        [sys.executable, "-m", "src.python.tools.check_import_surface"],
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
        line.strip().removeprefix("[FAIL] ")
        for line in result.stdout.splitlines()
        if line.startswith("[FAIL]")
    ] or ["导入方向检查失败"]


def check_workflows() -> list[str]:
    """CI 工作流自检：run 块的 bash 语法、python -c 片段、audit 参数、release 作业。"""
    result = subprocess.run(
        [sys.executable, "-m", "src.python.tools.check_workflows"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        return []
    problems = [
        line.strip().removeprefix("[FAIL] ")
        for line in result.stdout.splitlines()
        if line.startswith("[FAIL]")
    ]
    return problems or ["工作流自检失败"]


def check_platform_safety() -> list[str]:
    """跨平台安全：POSIX 路径 / 子进程编码 / POSIX-only 模块（守护「跨平台」）。"""
    result = subprocess.run(
        [sys.executable, "-m", "src.python.tools.check_platform_safety"],
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
        line.strip().removeprefix("[FAIL] ")
        for line in result.stdout.splitlines()
        if line.startswith("[FAIL]")
    ] or ["跨平台检查失败"]
