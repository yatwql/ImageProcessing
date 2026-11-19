#!/usr/bin/env python3
"""生成 `docs/managements/test-coverage.md`：覆盖率报告 + 测试分组统计。

    python tools/coverage_report.py                 # 只打印
    python tools/coverage_report.py --write         # 写进 docs/managements/test-coverage.md

数据来自 `reports/coverage.xml` 与 `reports/junit.xml`（`tools/check_all.py` 全量模式会生成）。
分组口径：
- **单元测试**：`core/` 下按技术单元拆的子目录（primitives / layout / font / format / color /
  background / pipeline）以及属性测试、边界与平台用例——盯单个函数/模块的契约；
- **场景测试**：`cli/`、`tui/` 与 core 下的端到端用例（写盘日志、日志查询、中断、版本贯通、
  映射规则）——盯一条完整用户路径；
- 其余归入「其他」并显式列名，避免"看不见的桶"。
"""

from __future__ import annotations

import datetime as dt
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from ..stdio import ensure_utf8_stdio
from ..version import VERSION
from ._paths import ROOT

COVERAGE = ROOT / "reports" / "coverage.xml"
JUNIT = ROOT / "reports" / "junit.xml"
OUTPUT = ROOT / "docs" / "managements" / "test-coverage.md"

# 覆盖率下限与 src/python/tools/check_coverage.py 保持一致
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
    "bootstrap.py": 0.90,
    "launch.py": 0.90,
    "tui/ui.py": 0.90,
    "tui/ui_input.py": 0.80,
    "tui/ui_base.py": 0.80,
    "cli/main.py": 0.85,
    "cli/log_query.py": 0.90,
}
TOTAL_MIN = 0.96
SKIP_MAX = 0.15

UNIT_DIRS = (
    "src.test.core.primitives",
    "src.test.core.layout",
    "src.test.core.font",
    "src.test.core.format",
    "src.test.core.color",
    "src.test.core.background",
    "src.test.core.pipeline",
)
UNIT_FILES = (
    "test_properties",
    "test_feature_edges",
    "test_platform_stability",
    "test_style_analysis",
    "test_rendering_primitives",
)
SCENARIO_DIRS = ("src.test.cli", "src.test.tui")
SCENARIO_FILES = (
    "test_write_audit_log",
    "test_log_query",
    "test_cancel_pipeline",
    "test_version_display",
    "test_mapping_rules",
    "test_entry_smoke",
    "test_screen_snapshots",
    "test_key_dispatch",
    "test_apply_and_batch",
)


def read_coverage() -> tuple[float, list[tuple[str, float, int, int]]]:
    """返回 (总行覆盖率, [(文件, 覆盖率, 覆盖行, 总行)])。"""
    root = ET.parse(COVERAGE).getroot()
    total = float(root.get("line-rate", "0"))
    rows: list[tuple[str, float, int, int]] = []
    for cls in root.iter("class"):
        name = cls.get("filename")
        if not name:
            continue
        lines = [ln for ln in cls.iter("line") if ln.get("number")]
        if not lines:
            continue
        hit = sum(1 for ln in lines if int(ln.get("hits", "0")) > 0)
        rows.append((name, hit / len(lines), hit, len(lines)))
    return total, sorted(rows, key=lambda r: r[1])


@dataclass(frozen=True)
class Case:
    """一条 junit 用例（只留统计要用的字段）。"""

    file: str
    module: str
    name: str
    time: float
    status: str


def read_junit() -> tuple[list[Case], int, int]:
    """返回 (用例列表, 跳过数, 总数)。"""
    root = ET.parse(JUNIT).getroot()
    root_node = root.find("testsuite") if root.tag == "testsuites" else root
    cases: list[Case] = []
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        parts = classname.split(".")
        module = ".".join(parts[:5]) if len(parts) >= 5 else classname
        status = "passed"
        if case.find("failure") is not None:
            status = "failed"
        elif case.find("error") is not None:
            status = "error"
        elif case.find("skipped") is not None:
            status = "skipped"
        cases.append(
            Case(
                file=classname,
                module=module,
                name=case.get("name", ""),
                time=float(case.get("time", "0") or 0),
                status=status,
            )
        )
    total = len(cases) if cases else int(root_node.get("tests", 0) if root_node is not None else 0)
    skipped = sum(1 for c in cases if c.status == "skipped")
    return cases, skipped, total


def classify(case: Case) -> str:
    module, name = case.module, case.name
    if module.startswith(SCENARIO_DIRS) or any(
        key in module or key in name for key in SCENARIO_FILES
    ):
        return "场景测试"
    if module.startswith(UNIT_DIRS) or any(key in module for key in UNIT_FILES):
        return "单元测试"
    return "其他"


def group_rows(cases: list[Case], group: str) -> list[tuple[str, int, int, float, str]]:
    """(分组名, 用例数, 通过数, 耗时, 覆盖点) —— 覆盖点用手写映射，避免把文件名当说明书。"""
    buckets: dict[str, list[Case]] = {}
    for case in cases:
        if classify(case) != group:
            continue
        key = case.module.replace("src.test.", "")
        buckets.setdefault(key, []).append(case)
    rows = []
    for key, items in sorted(buckets.items()):
        passed = sum(1 for c in items if c.status == "passed")
        spent = sum(c.time for c in items)
        rows.append((key, len(items), passed, spent, COVERS.get(key, "")))
    return rows


COVERS = {
    "core.primitives": "渲染/擦除原语：render_line、char_spans、solve_tracking、inpaint 半径",
    "core.layout": "多行排版、行距、对位",
    "core.font": "字体发现、候选池、缓存路径、ttc 展开",
    "core.format": "图片读写、格式表、质量、元数据、占名",
    "core.color": "字色反解、alpha 两路修正",
    "core.background": "纯色/渐变/照片底图上的擦除",
    "core.pipeline": "端到端替换与 memo 幂等",
    "core": "属性测试（hypothesis）、功能边界、平台默认值、异常契约、规模与幂等、配置、错误契约、OCR 契约",
    "cli": "参数与提前报错、单图、目录批量、示例图回归、启动器/自动装环境、入口冒烟",
    "tui": "按键分发、布局与响应式、快照、批量与取消、目录浏览、映射/样式面板、会话状态、真终端冒烟",
}


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def build() -> str:
    total, files = read_coverage()
    cases, skipped, count = read_junit()
    skip_ratio = skipped / count if count else 0.0
    passed = sum(1 for c in cases if c.status == "passed")
    spent = sum(c.time for c in cases)
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 测试覆盖率与分组统计",
        "",
        f"> 版本：v{VERSION}",
        "",
        "本文件由 `python -m src.python.tools.coverage_report --write` 生成，数据取自 `reports/coverage.xml` 与",
        "`reports/junit.xml`（`python -m src.python.tools.check_all` 全量模式产出）。改完用例或实现后重新生成即可，",
        "不要手改数字。",
        "",
        f"> 生成时间：{now}　|　命令：`.venv/bin/python -m src.python.tools.check_all`",
        "",
        "## 1. 总览",
        "",
        "| 指标 | 数值 | 门槛 | 结论 |",
        "| --- | ---: | ---: | --- |",
        f"| 行覆盖率 | {fmt_pct(total)} | ≥ {fmt_pct(TOTAL_MIN)} | {'✅' if total >= TOTAL_MIN else '❌'} |",
        f"| 用例总数 | {count} | — | — |",
        f"| 通过 | {passed} | = 总数 | {'✅' if passed == count - skipped else '⚠️'} |",
        f"| 跳过 | {skipped}（{fmt_pct(skip_ratio)}） | ≤ {fmt_pct(SKIP_MAX)} | "
        f"{'✅' if skip_ratio <= SKIP_MAX else '❌'} |",
        f"| 用例总耗时 | {spent:.1f}s | — | — |",
        "",
        "## 2. 模块覆盖率（高风险模块带门槛）",
        "",
        "| 模块 | 覆盖率 | 覆盖行 / 总行 | 门槛 | 结论 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, rate, hit, lines_total in files:
        floor = MODULE_MIN.get(name)
        if floor is None:
            lines.append(f"| `{name}` | {fmt_pct(rate)} | {hit} / {lines_total} | — | — |")
        else:
            lines.append(
                f"| `{name}` | {fmt_pct(rate)} | {hit} / {lines_total} | ≥ {fmt_pct(floor)} | "
                f"{'✅' if rate >= floor else '❌'} |"
            )

    # 包级汇总
    packages: dict[str, list[tuple[float, int, int]]] = {}
    for name, rate, hit, total_lines in files:
        package = name.rsplit("/", 1)[0] if "/" in name else "."
        packages.setdefault(package, []).append((rate, hit, total_lines))
    lines += [
        "",
        "## 3. 包级汇总",
        "",
        "| 包 | 文件数 | 覆盖率 |",
        "| --- | ---: | ---: |",
    ]
    for package, items in sorted(packages.items()):
        hit = sum(i[1] for i in items)
        total_lines = sum(i[2] for i in items)
        lines.append(
            f"| `{package}` | {len(items)} | {fmt_pct(hit / total_lines if total_lines else 0)} |"
        )

    for title, group in (("4. 场景测试分组", "场景测试"), ("5. 单元测试分组", "单元测试")):
        rows = group_rows(cases, group)
        group_total = sum(r[1] for r in rows)
        lines += [
            "",
            f"## {title}（{group_total} 例）",
            "",
            "| 分组 | 用例数 | 通过 | 耗时 | 覆盖的点 |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
        for key, number, ok, seconds, covers in rows:
            lines.append(f"| `{key}` | {number} | {ok} | {seconds:.1f}s | {covers or '—'} |")

    others = group_rows(cases, "其他")
    if others:
        lines += [
            "",
            "## 6. 其他（未归类，需显式确认）",
            "",
            "| 分组 | 用例数 | 通过 | 覆盖的点 |",
            "| --- | ---: | ---: | --- |",
        ]
        for key, number, ok, _seconds, covers in others:
            lines.append(f"| `{key}` | {number} | {ok} | {covers or '待归类'} |")

    lines += [
        "",
        "## 7. 覆盖薄弱点（按覆盖率升序，前 10）",
        "",
        "| 模块 | 覆盖率 | 未覆盖行 |",
        "| --- | ---: | ---: |",
    ]
    for name, rate, hit, total_lines in files[:10]:
        lines.append(f"| `{name}` | {fmt_pct(rate)} | {total_lines - hit} |")
    lines += [
        "",
        "## 8. 怎么更新",
        "",
        "```bash",
        ".venv/bin/python -m src.python.tools.check_all                # 跑全量用例并生成 coverage.xml / junit.xml",
        ".venv/bin/python -m src.python.tools.coverage_report --write  # 重新生成本文件",
        "```",
        "",
        "覆盖率门槛由 `src/python/tools/check_coverage.py` 把关（总量 96%、16 个高风险模块、skip ≤15%），",
        "所以本文件里的 ❌ 会同时让 `check_all` 变红。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    missing = [str(p) for p in (COVERAGE, JUNIT) if not p.exists()]
    if missing:
        print("缺少报告：" + "、".join(missing) + "\n先跑 tools/check_all.py（全量模式）")
        return 1
    content = build()
    if "--write" in args:
        OUTPUT.write_text(content, encoding="utf-8")
        print(f"已写入 {OUTPUT.relative_to(ROOT)}")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
