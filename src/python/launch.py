"""统一启动器：先确认环境就绪（必要时自动装依赖），再把控制权交给真正的入口。

由 `scripts/*` 里的薄壳调用，用**系统 Python** 执行：

    python -m src.python.launch cli  data --list
    python -m src.python.launch tui
    python -m src.python.launch test --fast

设计要点：
- 首次运行（没有 `.venv` 或缺依赖）自动补装，用户不必先手动跑 setup；
- 装了 `IMG_P_NO_AUTO_SETUP=1` 就退回"只报告、不动手"，给 CI/离线环境用；
- 只用标准库，因为这时项目依赖可能还没装。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.python import bootstrap  # noqa: E402

CHANNELS = {
    # 渠道名: (要不要装测试依赖, 入口参数)
    "cli": (False, ["-m", "src.python.cli"]),
    "tui": (False, ["-m", "src.python.tui"]),
    "log-query": (False, ["-m", "src.python.cli.log_query"]),
    "test": (True, ["tools/run_tests.py"]),
    "setup": (False, ["-m", "src.python.bootstrap"]),
}


def auto_setup_enabled() -> bool:
    """`IMG_P_NO_AUTO_SETUP=1` 时禁止自动安装（CI / 离线 / 想手动控制时用）。"""
    return os.environ.get("IMG_P_NO_AUTO_SETUP") != "1"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help") or args[0] not in CHANNELS:
        names = " / ".join(CHANNELS)
        print(f"用法: python -m src.python.launch <{names}> [参数…]", file=sys.stderr)
        return 2

    channel, forward = args[0], args[1:]
    need_dev, entry = CHANNELS[channel]
    auto = auto_setup_enabled()
    py = bootstrap.venv_python()

    if not bootstrap.ensure_dependencies(py, need_dev=need_dev, auto=auto):
        return 1

    cmd = [str(py), *entry, *forward]
    os.chdir(ROOT)
    try:
        os.execv(str(py), cmd)  # 交给真正的入口，本进程不再返回
    except OSError as exc:  # execv 失败（极少见）就退化成子进程
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
