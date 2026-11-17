#!/usr/bin/env bash
# 一键准备运行环境（Python 3.10+）：在项目根目录建 .venv 并安装依赖
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# 一律经 python -m pip：.venv 整体搬家后 .venv/bin/pip 的 shebang 会指向旧路径（无法执行），
# 而 python 解释器自身是可直接运行的。
PY=".venv/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt

# 配置目录：/data/config（写一份带注释说明的示例 + 默认配置；没有权限就跳过）
CONF_DIR="/data/config"
if mkdir -p "$CONF_DIR" 2>/dev/null; then
  cat > "$CONF_DIR/img-p.example.json" <<'JSON'
{
  "data_dir": "/data",
  "out_dir": "/data/output",
  "log_dir": "/data/logs",
  "font": null,
  "size": null,
  "color": null,
  "align": "auto",
  "fit_width": false,
  "tracking": null,
  "max_fonts": 160,
  "quality": 95
}
JSON
  if [ ! -f "$CONF_DIR/img-p.json" ]; then
    cp "$CONF_DIR/img-p.example.json" "$CONF_DIR/img-p.json"
    echo "已写入默认配置 $CONF_DIR/img-p.json（示例：img-p.example.json）"
  fi
else
  echo "[!] 无法创建 $CONF_DIR，配置改用内置默认（可设 IMG_P_CONFIG 指定文件）"
fi

echo "环境就绪，可以这样用："
echo "  ./scripts/cli.sh data --list                 # 命令行"
echo "  ./scripts/tui.sh                             # 交互界面"
