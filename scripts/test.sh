#!/usr/bin/env bash
# 全量用例 + 报告。编排在 tools/run_tests.py；这里只找系统 Python 转交。
# 首次运行会自动准备环境（缺 pytest 时连测试依赖一起装）。
#
#   ./scripts/test.sh [--fast] [-k 关键字]
set -uo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3 || command -v python) || {
  echo "找不到 Python，请先安装 Python 3.10+ 并加入 PATH" >&2
  exit 1
}
exec "$PY" -m src.python.launch test "$@"
