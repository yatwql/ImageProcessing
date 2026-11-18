#!/usr/bin/env bash
# 命令行入口（单图 / 目录批量）。逻辑在 src/python；这里只找系统 Python 转交。
# 首次运行会自动准备环境（缺依赖时安装；设 IMG_P_NO_AUTO_SETUP=1 可关掉自动安装）。
set -euo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3 || command -v python) || {
  echo "找不到 Python，请先安装 Python 3.10+ 并加入 PATH" >&2
  exit 1
}
if [ $# -eq 0 ]; then
  exec "$PY" -m src.python.launch cli --help
fi
exec "$PY" -m src.python.launch cli "$@"
