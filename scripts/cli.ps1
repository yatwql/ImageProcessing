# 命令行入口。逻辑在 src/python；这里只找系统 Python 转交。
# 首次运行会自动准备环境（缺依赖时安装；设 IMG_P_NO_AUTO_SETUP=1 可关掉自动安装）。
#   .\scripts\cli.ps1 data --list
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

$forward = @("cli")
if ($args.Count -eq 0) { $forward += "--help" } else { $forward += $args }
& $launcher.Source -m src.python.launch @forward
exit $LASTEXITCODE
