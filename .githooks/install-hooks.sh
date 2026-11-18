#!/usr/bin/env sh
# 启用仓库自带的 git 钩子（不改 .git/hooks，避免升级/重装后丢失）。
#
#   sh .githooks/install-hooks.sh          # 启用
#   sh .githooks/install-hooks.sh --off    # 关闭（走回默认 .git/hooks）

set -e
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

if [ "${1:-}" = "--off" ]; then
  git config --unset core.hooksPath || true
  echo "已关闭仓库钩子（core.hooksPath 已清除）"
  exit 0
fi

chmod +x .githooks/pre-commit .githooks/pre-push
git config core.hooksPath .githooks
echo "已启用仓库钩子："
echo "  pre-commit  → python -m src.python.tools.check_all --quick（由钩子调用）（ruff/mypy/guards/perf/用例）"
echo "  pre-push    → src.python.tools.check_all（再加覆盖率与无字体复跑）"
echo "  IMG_P_SKIP_HOOK=1 可临时跳过"
