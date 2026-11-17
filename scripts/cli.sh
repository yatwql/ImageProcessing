#!/usr/bin/env bash
# 命令行入口（单图 / 目录批量）：透传参数给 src.python.cli
#   ./scripts/cli.sh data --list
#   ./scripts/cli.sh data --map "旧=新" --map-file 映射.json
#   ./scripts/cli.sh data/某图.png -o 输出.png --map "2023=2024"
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "缺少运行环境，请先执行 ./setup.sh" >&2
  exit 1
fi

if [ $# -eq 0 ]; then
  exec "$PY" -m src.python.cli --help
fi

exec "$PY" -m src.python.cli "$@"
