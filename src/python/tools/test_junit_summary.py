#!/usr/bin/env python3
"""JUnit 报告摘要：把失败用例列成一行一条，CI 里一眼看清红在哪。

    python -m src.python.tools.test_junit_summary reports/junit.xml

为什么单独成工具、不写在工作流的 `run:` 里：CI 日志走 Windows 控制台，
直接在 shell 里 `print` 中文会 `UnicodeEncodeError: 'charmap'`（cp1252），
本轮就是这么红的；统一走 `ensure_utf8_stdio()` 才稳。顺带也能本地跑、能写用例。
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ..stdio import ensure_utf8_stdio


def failing_cases(xml_path: Path) -> list[str]:
    """返回 `classname::name` 列表（失败 + 错误）；报告不存在时返回空列表。"""
    if not xml_path.is_file():
        return []
    root = ET.parse(xml_path).getroot()
    out: list[str] = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            out.append(f"{case.get('classname', '?')}::{case.get('name', '?')}")
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    if not args:
        print("用法：python -m src.python.tools.test_junit_summary <junit.xml>")
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"[!] 没有 junit 报告：{path}（用例可能没跑到，跳过摘要）")
        return 0
    cases = failing_cases(path)
    print(f"失败/错误用例：{len(cases)}")
    for case in cases:
        print(f"- {case}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
