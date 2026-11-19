#!/usr/bin/env python3
"""列出失败的用例并给出「单跑一条」的命令：排障时别重跑全量。

    python -m src.python.tools.test_failures                  # 读 reports/junit.xml
    python -m src.python.tools.test_failures --path 报告/junit.xml --max 20
    python -m src.python.tools.test_failures --json           # 机器可读

和 `test_junit_summary` 分工：那个给 CI 一句话摘要（`class::name` 一行一条），
这个给本地排障——带失败类型、消息首行与可直接复制的 pytest 命令。

退出码：0 = 没有失败；1 = 有失败；2 = 报告缺失或解析不了。
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT

DEFAULT_JUNIT = ROOT / "reports" / "junit.xml"


def _nodeid(classname: str, name: str) -> str:
    """junit 的 classname/name → pytest 节点 ID（`src/test/x.py::Cls::test_y`）。

    pytest 用 ``src.test.x.Cls`` 形式写 classname：末段首字母大写即类名，
    要拆出来放进节点 ID；纯模块形式（模块级函数用例）则直接是 ``模块.py::name``。
    """
    parts = [p for p in classname.split(".") if p]
    if parts and parts[-1][:1].isupper():
        return "/".join(parts[:-1]) + f".py::{parts[-1]}::{name}"
    return ("/".join(parts) + ".py::" if parts else "") + name


def failing_cases(junit_xml: Path) -> list[dict[str, str]]:
    """解析 junit，返回失败/错误用例（节点 ID、类型、消息首行）。"""
    # 只解析本机 pytest 生成的报告（可信来源）：外部 XML 不走这里
    tree = ET.parse(junit_xml)  # nosemgrep
    root = tree.getroot()
    cases: list[dict[str, str]] = []
    for case in root.iter("testcase"):
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")
        if bad is None:
            continue
        message = (bad.get("message") or "").strip().splitlines()
        cases.append(
            {
                "nodeid": _nodeid(case.get("classname", ""), case.get("name", "")),
                "type": bad.get("type") or bad.tag,
                "message": message[0][:160] if message else "",
            }
        )
    return cases


def rerun_command(nodeids: Sequence[str]) -> str:
    """一条能直接粘进终端的复现命令（多个用例时都带上）。"""
    return ".venv/bin/python -m pytest -q " + " ".join(nodeids)


def main(argv: Sequence[str] = ()) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="列出失败用例并给出单跑命令")
    ap.add_argument("--path", default=str(DEFAULT_JUNIT), help="junit 报告路径")
    ap.add_argument("--max", type=int, default=50, help="最多列几条（默认 50）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(list(argv) if argv else sys.argv[1:])

    path = Path(args.path)
    if not path.is_file():
        print(
            f"找不到 junit 报告：{path}（先跑 ./scripts/run-test.sh 或 check_all）", file=sys.stderr
        )
        return 2
    try:
        cases = failing_cases(path)
    except (OSError, ET.ParseError) as exc:
        print(f"解析失败：{exc}", file=sys.stderr)
        return 2

    shown = cases[: max(0, args.max)]
    if args.json:
        print(
            json.dumps(
                {
                    "total": len(cases),
                    "cases": shown,
                    "rerun": rerun_command([c["nodeid"] for c in shown]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif not cases:
        print("没有失败用例 ✅")
    else:
        print(f"失败 {len(cases)} 个（列出 {len(shown)} 个）：")
        for item in shown:
            print(f"  {item['nodeid']}")
            if item["message"]:
                print(f"      [{item['type']}] {item['message']}")
        if len(cases) > len(shown):
            print(f"  …… 另有 {len(cases) - len(shown)} 个（--max 调大）")
        print(f"\n单跑复现：{rerun_command([c['nodeid'] for c in shown])}")
    return 1 if cases else 0


if __name__ == "__main__":
    sys.exit(main())
