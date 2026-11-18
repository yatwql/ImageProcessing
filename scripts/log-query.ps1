# 日志查询入口（薄壳）：实现在 src/python/cli/log_query.py。
#   .\scripts\log-query.ps1 --src 报告
#   .\scripts\log-query.ps1 --date 20261110 --json
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$launcher = Get-Command python -ErrorAction SilentlyContinue
if (-not $launcher) { $launcher = Get-Command py -ErrorAction SilentlyContinue }
if (-not $launcher) {
    Write-Error "找不到 Python，请先安装 Python 3.10+ 并勾选“Add python.exe to PATH”"
    exit 1
}
& $launcher.Source -m src.python.launch log-query @args
exit $LASTEXITCODE
