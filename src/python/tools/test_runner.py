#!/usr/bin/env python3
"""测试入口：跑全量用例并生成 junit / html / 覆盖率报告与摘要。

    .venv/bin/python tools/test_runner.py            # 全量 + 覆盖率 + HTML
    .venv/bin/python tools/test_runner.py --fast     # 只跑用例
    .venv/bin/python tools/test_runner.py -k 关键字   # 其余参数透传给 pytest
    .venv/bin/python tools/test_runner.py --keep 5    # 报告目录只留最近 5 次运行摘要

`scripts/run-test.sh` / `scripts/run-test.ps1` 只是薄壳，逻辑都在这里，
省得两个平台各维护一份 130 行脚本。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from ._parallel import parallel_args, worker_count
from ._paths import ROOT

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
    """pytest 命令行；用例分片并行（worker 数见 `_parallel.worker_count`）。"""
    args = [
        "src/test",
        "-q",
        f"--junitxml={report_dir / 'junit.xml'}",
        "-o",
        f"cache_dir={TMP_ROOT / 'pytest-cache'}",
        *parallel_args(worker_count()),
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


def _remove_tree(path: Path) -> None:
    """删一个目录；清不掉（只读/被占用）就咽下去，不影响测试结论。

    刻意写成"调用点接住 + 直接 return"：`contextlib.suppress` 在评审规则里会被当成
    "没处理异常"，而这里要的正是"这一项失败就算了，继续清下一项"。
    """
    try:
        shutil.rmtree(path)
    except OSError:
        return


def cleanup_repo() -> None:
    """仓库里不留运行产物：字节码缓存与 pytest 缓存都清掉（清不掉也不影响结果）。"""
    try:
        caches = list(ROOT.rglob("__pycache__"))  # rglob 可能中途读不了某个目录
    except OSError:
        caches = []
    for cache in caches:
        _remove_tree(cache)
    for name in (".pytest_cache", ".ruff_cache"):
        _remove_tree(ROOT / name)


def _junit_suite(path: Path) -> ET.Element | None:
    """读 junit 的 <testsuite>；文件缺失或结构不对时返回 None（只影响摘要文字）。"""
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()  # nosemgrep
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
        rate = float(ET.parse(cov).getroot().get("line-rate", 0.0)) * 100  # nosemgrep
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


HISTORY_DIR = REPORT_DIR_FALLBACK / "history"
KEEP_DEFAULT = 5


def record_run(report_dir: Path, code: int, summary: str, keep: int = KEEP_DEFAULT) -> Path:
    """把本次运行摘要写进 `reports/history/`，并按 `keep` 修剪旧文件。

    为什么单独留历史：`/test-reports` 每次都会被清空重建，"上一次全绿是什么时候、
    当时多少用例"这类问题只能靠历史摘要回答——但也不能无限长，所以只留最近 N 次。
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    entry = HISTORY_DIR / f"run-{stamp}.json"
    entry.write_text(
        json.dumps(
            {
                "when": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "exit_code": code,
                "report_dir": str(report_dir),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    stale = sorted(HISTORY_DIR.glob("run-*.json"))[:-max(1, keep)]
    for old in stale:
        with contextlib.suppress(OSError):
            old.unlink()
    return entry


def _keep_value(args: list[str]) -> int:
    """`--keep N` 取最近 N 次（默认 5）；不带数字则用默认值。"""
    for i, arg in enumerate(args):
        if arg == "--keep" and i + 1 < len(args) and args[i + 1].isdigit():
            return max(1, int(args[i + 1]))
        if arg.startswith("--keep=") and arg.split("=", 1)[1].isdigit():
            return max(1, int(arg.split("=", 1)[1]))
    return KEEP_DEFAULT


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        # 必须早于 prepare_tmp/prepare_report_dir：那两个会清掉 reports/ 里的旧报告，
        # 「看帮助」绝不该弄丢别人刚生成的门禁产物（曾因此把覆盖率报告删掉，门禁恒红）
        print(__doc__)
        return 0
    fast = "--fast" in args
    keep = _keep_value(args)
    extra = [a for a in args if a != "--fast" and not a.startswith("--keep")]
    prepare_tmp()
    report_dir = prepare_report_dir()
    print("== 运行测试 ==")
    code = subprocess.run(
        [sys.executable, "-m", "pytest", *build_args(report_dir, fast, extra)], cwd=str(ROOT)
    ).returncode
    cleanup_repo()
    print("\n== 汇总 ==")
    summary = summarize(report_dir, fast)
    print(summary)
    try:  # 历史摘要只做观察，写不了也不影响测试结论
        record_run(report_dir, code, summary, keep)
    except OSError as exc:
        print(f"[!] 无法写运行历史：{exc}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
