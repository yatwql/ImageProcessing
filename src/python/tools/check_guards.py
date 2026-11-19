#!/usr/bin/env python3
"""工程守护：把 `CLAUDE.md` 里的硬性约束变成可执行检查。

    python -m src.python.tools.check_guards            # 人读
    python -m src.python.tools.check_guards --ci       # 只输出一行一结论，不过即退出 1

检查项按类别拆在 `tools/guards/` 里：
  ids   台账编号连续性 / 唯一性 / 归档占号
  docs  目录树文档、文档索引、归档目录与台账索引
  code  分层方向、单文件长度、显式编码、测试目录与字体、脚本类型与编码
  scripts 脚本命名与契约（前缀/运行示例/被用例引用/`--ci`）、文档死链、用例对照表
  meta  版本/名称、依赖锁、导入方向、工作流、跨平台安全
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from ..stdio import ensure_utf8_stdio
from .guards.code import (
    check_complexity_ceiling,
    check_explicit_encoding,
    check_file_length,
    check_layering,
    check_scripts_are_launchers,
    check_test_font_usage,
    check_test_layout,
    check_windows_scripts,
)
from .guards.docs import check_archive_layout, check_docs_index, check_folders_doc
from .guards.ids import check_plan_ids, check_rf_ids
from .guards.meta import (
    check_constraints,
    check_import_surface,
    check_name_consistency,
    check_platform_safety,
    check_version_consistency,
    check_workflows,
)
from .guards.scripts import check_docs_links, check_script_names, check_test_doc_table

CHECKS = [
    ("编号-plan", check_plan_ids),
    ("编号-review", check_rf_ids),
    ("分层-core", check_layering),
    ("文件长度", check_file_length),
    ("复杂度上限", check_complexity_ceiling),
    ("显式编码", check_explicit_encoding),
    ("测试目录", check_test_layout),
    ("版本号", check_version_consistency),
    ("名称", check_name_consistency),
    ("目录树文档", check_folders_doc),
    ("测试字体", check_test_font_usage),
    ("导入方向", check_import_surface),
    ("文档索引", check_docs_index),
    ("归档", check_archive_layout),
    ("工作流", check_workflows),
    ("跨平台", check_platform_safety),
    ("依赖锁", check_constraints),
    ("PS 编码", check_windows_scripts),
    ("scripts 薄壳", check_scripts_are_launchers),
    ("脚本契约", check_script_names),
    ("文档链接", check_docs_links),
    ("用例对照", check_test_doc_table),
]


def main(argv: Sequence[str] = ()) -> int:
    ensure_utf8_stdio()

    # 空序列表示"没传参"，避免 `x is None` 形式的静态规则噪音
    args = list(argv) if argv else sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
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
