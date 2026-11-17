#!/usr/bin/env bash
# 交互界面入口：不给参数时默认读 data/，结果默认写 data/output/
#   ./scripts/tui.sh
#   ./scripts/tui.sh data
#   ./scripts/tui.sh data -m map.json
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "缺少运行环境，请先执行 ./setup.sh" >&2
  exit 1
fi

for a in "$@"; do
  case "$a" in
    -h|--help) exec "$PY" -m src.python.tui --help ;;
  esac
done

if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "tui 需要真终端（交互界面），批处理请用 ./scripts/cli.sh" >&2
  exit 1
fi

if [ $# -eq 0 ]; then
  exec "$PY" -m src.python.tui data
fi

exec "$PY" -m src.python.tui "$@"
