#!/usr/bin/env bash
# 日志查询入口（薄壳）：实现在 src/python/cli/log_query.py。
#   ./scripts/log-query.sh --src 报告
#   ./scripts/log-query.sh --date 20261110 --json
set -euo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3 || command -v python) || {
  echo "找不到 Python，请先安装 Python 3.10+ 并加入 PATH" >&2
  exit 1
}
exec "$PY" -m src.python.launch log-query "$@"
