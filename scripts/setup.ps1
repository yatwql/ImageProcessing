# 一键准备运行环境（Windows / PowerShell，Python 3.10+）
# 用法：  .\scripts\setup.ps1
# 可选：  .\scripts\setup.ps1 -Dev      # 连测试依赖一起装
param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $launcher = Get-Command python -ErrorAction SilentlyContinue
    if (-not $launcher) {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $launcher) {
        Write-Error "找不到 Python，请先安装 Python 3.10+ 并勾选“Add python.exe to PATH”"
        exit 1
    }
    & $launcher.Source -m venv .venv
}

& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r requirements.txt
if ($Dev) {
    & $py -m pip install --quiet -r requirements-dev.txt
}

# 配置文件：/data/config/img-p.json（不存在时写一份默认的；没有权限就跳过）
$confDir = "/data/config"
try {
    New-Item -ItemType Directory -Force -Path $confDir | Out-Null
    $confFile = Join-Path $confDir "img-p.json"
    $example = Join-Path $confDir "img-p.example.json"
    @'
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
'@ | Set-Content -Encoding utf8 $example
    if (-not (Test-Path $confFile)) {
        Copy-Item $example $confFile
        Write-Host "已写入默认配置 $confFile（示例：img-p.example.json）"
    }
} catch {
    Write-Host "[!] 无法创建 $confDir，配置改用内置默认（可设 IMG_P_CONFIG 指定文件）"
}

Write-Host "环境就绪，可以这样用："
Write-Host "  .\scripts\cli.ps1 data --list          # 命令行"
Write-Host "  .\scripts\tui.ps1                      # 交互界面（需要 windows-curses，已随依赖安装）"
if (-not $Dev) {
    Write-Host "  .\scripts\setup.ps1 -Dev               # 需要跑测试时再装一次"
}
