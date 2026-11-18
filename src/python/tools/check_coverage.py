#!/usr/bin/env python3
"""覆盖率门禁：总覆盖率 + 高风险模块单独设限 + skip 上限。

    python tools/check_coverage.py reports/coverage.xml reports/junit.xml

只看总覆盖率会被"核心模块 40%、界面 95%"这种结构掩盖，所以对真正吃重判断的模块
（匹配、渲染、擦除、审计、按键分发）单独设阈值；skip 太多也说明用例在躲问题。
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ..stdio import ensure_utf8_stdio

# 模块 → 最低行覆盖率。挑的是"判断密集、出错代价高"的文件。
# 键是相对 `source = ["src/python"]` 的路径（coverage.xml 里就是这么写的）
MODULE_MIN = {
    "core/match.py": 0.90,
    "core/options.py": 0.90,
    "core/edit.py": 0.85,
    "core/render.py": 0.85,
    "core/image.py": 0.85,
    "core/audit.py": 0.85,
    "tui/ui_actions.py": 0.80,
    "tui/ui_draw.py": 0.85,
    "tui/app.py": 0.80,
    # 以下为本轮补测后新达标的模块：门槛贴着实测值下沿，防止回落
    "bootstrap.py": 0.90,
    "launch.py": 0.90,
    "tui/ui.py": 0.90,
    "tui/ui_input.py": 0.80,
    "tui/ui_base.py": 0.80,
    "cli/main.py": 0.85,
    "cli/log_query.py": 0.90,
}
TOTAL_MIN = 0.96
SKIP_MAX_RATIO = 0.15  # 正常模式（有中文字体）下，跳过用例不该超过 15%


def file_rates(coverage_xml: Path) -> dict[str, float]:
    root = ET.parse(coverage_xml).getroot()
    rates: dict[str, float] = {}
    for cls in root.iter("class"):
        name = cls.get("filename")
        if not name:
            continue
        lines = [ln for ln in cls.iter("line") if ln.get("number")]
        if not lines:
            continue
        hits = sum(1 for ln in lines if int(ln.get("hits", "0")) > 0)
        rates[name] = hits / len(lines)
    return rates


def total_rate(coverage_xml: Path) -> float:
    root = ET.parse(coverage_xml).getroot()
    return float(root.get("line-rate", "0"))


def skip_ratio(junit_xml: Path) -> tuple[int, int]:
    root = ET.parse(junit_xml).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    if suite is None:
        return 0, 0
    total = int(suite.get("tests", 0))
    skipped = int(suite.get("skipped", 0))
    return skipped, total


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(argv) if argv else sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    coverage_xml = Path(args[0] if args else "reports/coverage.xml")
    junit_xml = Path(args[1] if len(args) > 1 else "reports/junit.xml")

    problems: list[str] = []
    if not coverage_xml.exists():
        print(f"[FAIL] 找不到覆盖率报告 {coverage_xml}（先跑 pytest --cov-report=xml:…）")
        return 1

    rate = total_rate(coverage_xml)
    print(
        f"[{'ok' if rate >= TOTAL_MIN else 'FAIL'}] 总行覆盖率 {rate:.1%}（下限 {TOTAL_MIN:.0%}）"
    )
    if rate < TOTAL_MIN:
        problems.append(f"总覆盖率 {rate:.1%} 低于 {TOTAL_MIN:.0%}")

    rates = file_rates(coverage_xml)
    for module, floor in sorted(MODULE_MIN.items()):
        actual = rates.get(module)
        if actual is None:
            continue  # 该模块没被采集到（例如平台条件导入）
        verdict = "ok" if actual >= floor else "FAIL"
        print(f"[{verdict:4}] {module}: {actual:.1%}（下限 {floor:.0%}）")
        if actual < floor:
            problems.append(f"{module} 覆盖率 {actual:.1%} 低于 {floor:.0%}")

    if junit_xml.exists():
        skipped, total = skip_ratio(junit_xml)
        ratio = skipped / total if total else 0.0
        verdict = "ok" if ratio <= SKIP_MAX_RATIO else "FAIL"
        print(f"[{verdict:4}] 跳过用例 {skipped}/{total}（{ratio:.1%}，上限 {SKIP_MAX_RATIO:.0%}）")
        if ratio > SKIP_MAX_RATIO:
            problems.append(
                f"跳过 {ratio:.1%} 的用例，超过 {SKIP_MAX_RATIO:.0%}："
                "要么环境缺依赖，要么用例在躲问题"
            )

    if problems:
        for item in problems:
            print(f"[FAIL] {item}")
        return 1
    print("覆盖率门禁通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
