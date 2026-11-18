#!/usr/bin/env bash
# 一键准备运行环境（Python 3.10+）：建 .venv、按 constraints.txt 装依赖、写默认配置。
# 逻辑在 src/python/bootstrap.py；这里只找解释器并转交（系统 Python 也能跑）。
#
#   ./scripts/setup.sh          # 运行时依赖
#   ./scripts/setup.sh --dev    # 连测试依赖一起装
set -euo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3 || command -v python) || {
  echo "找不到 Python，请先安装 Python 3.10+ 并加入 PATH" >&2
  exit 1
}
exec "$PY" -m src.python.bootstrap "$@"
