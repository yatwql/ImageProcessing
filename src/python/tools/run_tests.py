#!/usr/bin/env python3
"""测试入口：跑全量用例并生成 junit / html / 覆盖率报告与摘要。

    .venv/bin/python tools/run_tests.py            # 全量 + 覆盖率 + HTML
    .venv/bin/python tools/run_tests.py --fast     # 只跑用例
    .venv/bin/python tools/run_tests.py -k 关键字   # 其余参数透传给 pytest

`scripts/runTest.sh` / `scripts/runTest.ps1` 只是薄壳，逻辑都在这里，
省得两个平台各维护一份 130 行脚本。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT  # noqa: E402  (工具共用仓库根)

TMP_ROOT = Path(os.environ.get("IMG_P_TMP_DIR", "/data/tmp"))  # platform-safe
REPORT_DIR_FALLBACK = ROOT / "reports"


def prepare_tmp() -> str:
    """中间文件统一放 /data/tmp（不可写时退回系统临时目录），并导出给子进程。"""
    try:
        (TMP_ROOT / "coverage").mkdir(parents=True, exist_ok=True)
        env = {
            "TMPDIR": str(TMP_ROOT),
            "IMG_P_TMP_DIR": str(TMP_ROOT),
            "PYTHONPYCACHEPREFIX": str(TMP_ROOT / "pycache"),
            "COVERAGE_FILE": str(TMP_ROOT / "coverage" / ".coverage"),
        }
        os.environ.update(env)
        return str(TMP_ROOT)
    except OSError:
        print(f"[!] 无法创建 {TMP_ROOT}，测试临时文件改用系统临时目录", file=sys.stderr)
        return ""


def prepare_report_dir() -> Path:
    """报告目录 /test-reports（不可写时退回 ./reports）。"""
    target = Path("/test-reports")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        print("[!] 无法创建 /test-reports，报告改写到 ./reports", file=sys.stderr)
        target = REPORT_DIR_FALLBACK
        target.mkdir(parents=True, exist_ok=True)
    stale = ["junit.xml", "coverage.xml", "test-report.html"]
    for name in stale:
        (target / name).unlink(missing_ok=True)
    return target


def build_args(report_dir: Path, fast: bool, extra: list[str]) -> list[str]:
    args = [
        "src/test",
        "-q",
        f"--junitxml={report_dir / 'junit.xml'}",
        "-o",
        f"cache_dir={TMP_ROOT / 'pytest-cache'}",
        *extra,
    ]
    if fast:
        return args
    if has_module("pytest_cov") and has_module("pytest_html"):
        args += [
            "--cov=src/python",
            "--cov-report=term-missing:skip-covered",
            f"--cov-report=xml:{report_dir / 'coverage.xml'}",
            f"--cov-report=html:{report_dir / 'coverage'}",
            f"--html={report_dir / 'test-report.html'}",
            "--self-contained-html",
        ]
    else:
        print("[!] 未安装 pytest-cov / pytest-html，本次只出 junit 与摘要", file=sys.stderr)
    return args


def has_module(name: str) -> bool:
    return (
        subprocess.run(
            [sys.executable, "-c", f"import {name}"], capture_output=True, check=False
        ).returncode
        == 0
    )


def cleanup_repo() -> None:
    """仓库里不留运行产物：字节码缓存与 pytest 缓存都清掉（清不掉也不影响结果）。"""
    # 清理失败不该影响测试结果：逐项 try/except，而不是让整轮因为一个只读目录炸掉
    try:
        for cache in ROOT.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    except OSError:
        pass
    for name in (".pytest_cache", ".ruff_cache"):
        try:
            shutil.rmtree(ROOT / name, ignore_errors=True)
        except OSError:
            pass


def _junit_suite(path: Path) -> ET.Element | None:
    """读 junit 的 <testsuite>；文件缺失或结构不对时返回 None（只影响摘要文字）。"""
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    if root.tag == "testsuites":
        return root.find("testsuite")
    return root


def summarize(report_dir: Path, fast: bool) -> str:
    lines: list[str] = []
    junit = report_dir / "junit.xml"
    suite = _junit_suite(junit)
    if suite is not None:
        total = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        seconds = float(suite.get("time", 0.0))
        lines.append(
            f"用例：{total} 个（通过 {total - failures - errors - skipped}，"
            f"失败 {failures}，错误 {errors}，跳过 {skipped}），耗时 {seconds:.1f}s"
        )
    cov = report_dir / "coverage.xml"
    if not fast and cov.exists():
        rate = float(ET.parse(cov).getroot().get("line-rate", 0.0)) * 100
        lines.append(f"覆盖率：行覆盖 {rate:.1f}%")
    links = [
        str(p)
        for p in (
            report_dir / "test-report.html",
            report_dir / "coverage" / "index.html",
            junit,
            cov,
        )
        if p.exists()
    ]
    if links:
        lines.append("报告：" + "  ".join(links))
    summary = "\n".join(lines) if lines else "未生成 junit 报告"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "summary.md").write_text("# 测试报告\n\n" + summary + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    fast = "--fast" in args
    extra = [a for a in args if a != "--fast"]
    prepare_tmp()
    report_dir = prepare_report_dir()
    print("== 运行测试 ==")
    code = subprocess.run(
        [sys.executable, "-m", "pytest", *build_args(report_dir, fast, extra)], cwd=str(ROOT)
    ).returncode
    cleanup_repo()
    print("\n== 汇总 ==")
    print(summarize(report_dir, fast))
    return code


if __name__ == "__main__":
    sys.exit(main())
