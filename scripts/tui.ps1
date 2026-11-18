# 交互界面入口。逻辑在 src/python；这里只做终端检查与转交。
# 首次运行会自动准备环境（缺依赖时安装；设 IMG_P_NO_AUTO_SETUP=1 可关掉自动安装）。
#   .\scripts\tui.ps1
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

foreach ($a in $args) {
    if ($a -eq "-h" -or $a -eq "--help") {
        & $launcher.Source -m src.python.launch tui --help
        exit $LASTEXITCODE
    }
}
if ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected) {
    Write-Error "tui 需要真终端（交互界面），批处理请用 .\scripts\cli.ps1"
    exit 1
}

$forward = @("tui")
if ($args.Count -eq 0) { $forward += "data" } else { $forward += $args }
& $launcher.Source -m src.python.launch @forward
exit $LASTEXITCODE
