# 一键准备运行环境（Windows / PowerShell，Python 3.10+）
# 逻辑在 src/python/bootstrap.py；这里只找解释器并转交。
#   .\scripts\setup.ps1          # 运行时依赖
#   .\scripts\setup.ps1 -Dev     # 连测试依赖一起装
param(
    [switch]$Dev
)

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

$forward = @()
if ($Dev) { $forward += "--dev" }
& $launcher.Source -m src.python.bootstrap @forward
exit $LASTEXITCODE
