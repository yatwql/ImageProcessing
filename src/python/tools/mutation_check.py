#!/usr/bin/env python3
"""变异测试（opt-in）：验证用例真的能"杀死"错误实现，而不只是覆盖到行。

    .venv/bin/python -m pip install mutmut
    python tools/mutation_check.py                  # 默认试点 core/match.py
    python tools/mutation_check.py core/options.py

没装 mutmut 就说明怎么装并退出 0（不阻塞日常门禁）。
变异存活意味着"代码改错了用例还绿"——那类漏洞光看覆盖率发现不了。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT  # noqa: E402  (工具共用仓库根)

DEFAULT_TARGETS = ["src/python/core/match.py"]


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv) or DEFAULT_TARGETS
    if importlib.util.find_spec("mutmut") is None:
        print("未安装 mutmut：`.venv/bin/python -m pip install mutmut` 后再来")
        print("建议先跑 core/match.py 与 core/options.py（逻辑密集、用例最多）")
        return 0

    if not (ROOT / "setup.cfg").exists() and not (ROOT / "pyproject.toml").exists():
        print("缺少项目配置，mutmut 需要能定位包")
        return 1

    cmd = [sys.executable, "-m", "mutmut", "run", "--paths-to-mutate", ",".join(args)]
    print("运行：" + " ".join(cmd))
    code = subprocess.run(cmd, cwd=str(ROOT)).returncode
    print("\n看结果：python -m mutmut results；逐条看：python -m mutmut show <id>")
    return code


if __name__ == "__main__":
    sys.exit(main())
