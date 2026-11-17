#!/usr/bin/env bash
# 跑完整测试并生成测试报告
#
#   ./scripts/test.sh                 # 全部用例 + 覆盖率 + HTML 报告
#   ./scripts/test.sh --fast          # 只跑用例，不算覆盖率/不出 HTML
#   ./scripts/test.sh -k 关键字        # 其余参数原样透传给 pytest
#
# 产物：/test-reports/{junit.xml,test-report.html,coverage/index.html,summary.md}
# 测试中间文件：/data/tmp（目录建不出来时退回系统临时目录）
set -uo pipefail
cd "$(dirname "$0")/.."

# 临时文件与系统临时目录分开，绝不落到 data/output/
TMP_ROOT="/data/tmp"
if mkdir -p "$TMP_ROOT" 2>/dev/null; then
  export TMPDIR="$TMP_ROOT"
  export IMG_P_TMP_DIR="$TMP_ROOT"
  export PYTHONPYCACHEPREFIX="$TMP_ROOT/pycache"
  export COVERAGE_FILE="$TMP_ROOT/coverage/.coverage"
  mkdir -p "$TMP_ROOT/coverage" 2>/dev/null || true
else
  echo "[!] 无法创建 $TMP_ROOT，测试临时文件改用系统临时目录" >&2
fi

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "缺少运行环境，请先执行 ./scripts/setup.sh（再装测试依赖: .venv/bin/pip install -r requirements-dev.txt）" >&2
  exit 1
fi
if ! $PY -c "import pytest" >/dev/null 2>&1; then
  echo "缺少 pytest，请先执行 .venv/bin/pip install -r requirements-dev.txt" >&2
  exit 1
fi

REPORT_DIR="/test-reports"
if ! mkdir -p "$REPORT_DIR" 2>/dev/null; then
  echo "[!] 无法创建 $REPORT_DIR，报告改写到 ./reports" >&2
  REPORT_DIR="reports"
fi
FAST=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --fast) FAST=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

# 避免读到上一轮的陈数据
rm -rf "$REPORT_DIR/junit.xml" "$REPORT_DIR/coverage.xml" "$REPORT_DIR/test-report.html"
if [ "$FAST" -eq 1 ]; then
  rm -rf "$REPORT_DIR/coverage"
fi

PASS_ARGS=(
  "src/test"
  -q
  "--junitxml=$REPORT_DIR/junit.xml"
  "-o" "cache_dir=$TMP_ROOT/pytest-cache"
)
if [ "$FAST" -eq 0 ]; then
  if $PY -c "import pytest_cov, pytest_html" >/dev/null 2>&1; then
    PASS_ARGS+=(
      "--cov=src/python"
      "--cov-report=term-missing:skip-covered"
      "--cov-report=xml:$REPORT_DIR/coverage.xml"
      "--cov-report=html:$REPORT_DIR/coverage"
      "--html=$REPORT_DIR/test-report.html"
      "--self-contained-html"
    )
  else
    echo "[!] 未安装 pytest-cov / pytest-html，本次只出 junit 与摘要" >&2
    PASS_ARGS+=("--html=$REPORT_DIR/test-report.html" "--self-contained-html")
  fi
fi

cleanup_repo() {
  # 仓库里不留运行产物：字节码缓存与 pytest 缓存都清掉
  find src -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
}
trap cleanup_repo EXIT

echo "== 运行测试 =="
$PY -m pytest "${PASS_ARGS[@]}" ${ARGS[@]+"${ARGS[@]}"}
CODE=$?

# ---- 汇总（junit.xml + coverage.xml）
$PY - "$REPORT_DIR" "$FAST" <<'PY'
import os
import sys
import xml.etree.ElementTree as ET

report_dir = sys.argv[1]
fast = sys.argv[2] == "1"
lines = []

junit_path = os.path.join(report_dir, "junit.xml")
if os.path.exists(junit_path):
    root = ET.parse(junit_path).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    seconds = float(suite.get("time", 0.0))
    lines.append(f"用例：{total} 个（通过 {total - failures - errors - skipped}，"
                 f"失败 {failures}，错误 {errors}，跳过 {skipped}），耗时 {seconds:.1f}s")

cov_path = os.path.join(report_dir, "coverage.xml")
if not fast and os.path.exists(cov_path):
    cov = ET.parse(cov_path).getroot()
    rate = float(cov.get("line-rate", 0.0)) * 100
    lines.append(f"覆盖率：行覆盖 {rate:.1f}%")

html = os.path.join(report_dir, "test-report.html")
links = [p for p in (html,
                     os.path.join(report_dir, "coverage", "index.html"),
                     junit_path,
                     cov_path) if os.path.exists(p)]
if links:
    lines.append("报告：" + "  ".join(links))

summary = "\n".join(lines) if lines else "未生成 junit 报告"
os.makedirs(report_dir, exist_ok=True)
with open(os.path.join(report_dir, "summary.md"), "w", encoding="utf-8") as f:
    f.write("# 测试报告\n\n" + summary + "\n")
print("\n== 汇总 ==")
print(summary)
PY

exit "$CODE"
