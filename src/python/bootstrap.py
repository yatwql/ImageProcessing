"""环境引导：建 `.venv`、按 `constraints.txt` 装依赖、写默认配置。

由 `scripts/setup.sh` / `scripts/setup.ps1` 用**系统 Python** 调用：

    python -m src.python.bootstrap          # 运行时依赖
    python -m src.python.bootstrap --dev    # 连测试依赖一起装

这里只用标准库：此时项目依赖还没装，import 任何第三方包都会失败。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def default_conf_dir() -> Path:
    """配置目录默认值：Linux/macOS 用 /data/config；Windows 没有 /data，用仓库内 data/config。"""
    if sys.platform == "win32":
        return ROOT / "data" / "config"
    return Path("/data/config")


def _conf_dir() -> Path:
    """配置目录：IMG_P_CONFIG_DIR 覆盖（相对路径按仓库根解析），否则用平台默认。"""
    raw = os.environ.get("IMG_P_CONFIG_DIR")
    if not raw:
        return default_conf_dir()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path  # 相对路径视为相对仓库根，不再直接报错
    return path.resolve()


CONF_DIR = _conf_dir()
EXAMPLE = CONF_DIR / "retype.example.json"
CONFIG = CONF_DIR / "retype.json"

DEFAULT_CONFIG = {
    "data_dir": "/data",
    "out_dir": "/data/output",
    "log_dir": "/data/logs",
    "font": None,
    "size": None,
    "color": None,
    "align": "auto",
    "fit_width": False,
    "tracking": None,
    "max_fonts": 160,
    "quality": 95,
}


def venv_python(root: Path = ROOT) -> Path:
    """当前平台 `.venv` 里的解释器路径。"""
    if sys.platform == "win32":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def ensure_venv(root: Path = ROOT) -> Path:
    """没有 `.venv` 就建一个，返回其中的解释器路径。"""
    py = venv_python(root)
    if not py.exists():
        print(f"creating {root / '.venv'} …")
        venv.EnvBuilder(with_pip=True).create(str(root / ".venv"))
    return py


def missing_modules(py: Path, need_dev: bool = False) -> list[str]:
    """`.venv` 里缺哪些关键依赖（缺了就得重新装）。

    只探运行时会用到的几个：PIL / numpy / cv2 与（跑测试时）pytest。
    逐个 import 会慢，所以一次进程里试完；`rapidocr` 是延迟导入，不在这里探。
    """
    if not py.exists():
        return ["venv"]
    names = ["PIL", "numpy", "cv2"] + (["pytest"] if need_dev else [])
    probe = "import importlib, sys\n" + "\n".join(
        f"try:\n    importlib.import_module({n!r})\nexcept Exception:\n    print({n!r})"
        for n in names
    )
    try:
        out = subprocess.run([str(py), "-c", probe], capture_output=True, text=True, check=False)
    except OSError:
        return ["venv"]
    if out.returncode != 0:
        return ["venv"]
    return [line.strip().strip("'\"") for line in out.stdout.splitlines() if line.strip()]


def ensure_dependencies(py: Path, need_dev: bool = False, auto: bool = True) -> bool:
    """缺依赖就补装；`auto=False`（`IMG_P_NO_AUTO_SETUP=1`）时只报告不安装。

    返回是否可以继续跑。
    """
    missing = missing_modules(py, need_dev)
    if not missing:
        return True
    if not auto:
        print(
            "缺少运行环境（" + "、".join(missing) + "）。已设 IMG_P_NO_AUTO_SETUP=1，"
            "请手动执行 scripts/setup.sh（Windows：.\\scripts\\setup.ps1）",
            file=sys.stderr,
        )
        return False
    print("首次运行，正在准备环境（装依赖，可能需要一两分钟）…", file=sys.stderr)
    py = ensure_venv()
    pip_install(py, "--upgrade", "pip")
    pip_install(py, "-c", "constraints.txt", "-r", "requirements.txt")
    if need_dev:
        pip_install(py, "-c", "constraints.txt", "-r", "requirements-dev.txt")
    return not missing_modules(py, need_dev)


def pip_install(py: Path, *args: str) -> None:
    """安装依赖；一律经 `python -m pip`，避免 `.venv/bin/pip` 的 shebang 在搬目录后失效。"""
    cmd = [str(py), "-m", "pip", "install", "--quiet", *args]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def write_config() -> None:
    """写一份示例配置与默认配置；没有权限就跳过（程序有内置默认）。"""
    try:
        CONF_DIR.mkdir(parents=True, exist_ok=True)
        EXAMPLE.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if not CONFIG.exists():
            shutil.copyfile(EXAMPLE, CONFIG)
            print(f"已写入默认配置 {CONFIG}（示例：{EXAMPLE.name}）")
    except OSError:
        print(f"[!] 无法创建 {CONF_DIR}，配置改用内置默认（可设 IMG_P_CONFIG 指定文件）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="准备运行环境（建 venv、装依赖、写默认配置）")
    ap.add_argument("--dev", action="store_true", help="连测试依赖一起装（pytest/ruff/mypy…）")
    ap.add_argument("--skip-install", action="store_true", help="只建 venv 与配置，不装依赖")
    ap.add_argument(
        "--check",
        action="store_true",
        help="只检查环境是否就绪（缺依赖则按需补装，由启动脚本 --ensure 使用）",
    )
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.check:
        py = venv_python()
        ready = ensure_dependencies(
            py, need_dev=args.dev, auto=os.environ.get("IMG_P_NO_AUTO_SETUP") != "1"
        )
        return 0 if ready else 1

    py = ensure_venv()
    if not args.skip_install:
        pip_install(py, "--upgrade", "pip")
        pip_install(py, "-c", "constraints.txt", "-r", "requirements.txt")
        if args.dev:
            pip_install(py, "-c", "constraints.txt", "-r", "requirements-dev.txt")
    write_config()

    launcher = "./scripts/cli.sh" if sys.platform != "win32" else r".\scripts\cli.ps1"
    tui = "./scripts/tui.sh" if sys.platform != "win32" else r".\scripts\tui.ps1"
    setup = "./scripts/setup.sh" if sys.platform != "win32" else r".\scripts\setup.ps1"
    print("环境就绪，可以这样用：")
    print(f"  {launcher} data --list          # 命令行")
    print(f"  {tui}                           # 交互界面")
    if not args.dev:
        print(f"  {setup} -Dev                    # 需要跑测试时再装一次")
    return 0


if __name__ == "__main__":
    sys.exit(main())
