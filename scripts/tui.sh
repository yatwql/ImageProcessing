#!/usr/bin/env bash
# 交互界面入口。逻辑在 src/python；这里只做终端检查与转交。
# 首次运行会自动准备环境（缺依赖时安装；设 IMG_P_NO_AUTO_SETUP=1 可关掉自动安装）。
set -euo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3 || command -v python) || {
  echo "找不到 Python，请先安装 Python 3.10+ 并加入 PATH" >&2
  exit 1
}
for a in "$@"; do
  case "$a" in
    -h|--help) exec "$PY" -m src.python.launch tui --help ;;
  esac
done
if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "tui 需要真终端（交互界面），批处理请用 ./scripts/cli.sh" >&2
  exit 1
fi
if [ $# -eq 0 ]; then
  exec "$PY" -m src.python.launch tui data
fi
exec "$PY" -m src.python.launch tui "$@"
