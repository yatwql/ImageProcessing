# 全量用例 + 报告。编排在 tools/run_tests.py；这里只找系统 Python 转交。
#   .\scripts\test.ps1 [--fast] [-k 关键字]
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

$forward = @("test")
if ($args.Count -gt 0) { $forward += $args }
& $launcher.Source -m src.python.launch @forward
exit $LASTEXITCODE
