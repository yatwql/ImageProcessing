# 命令行入口（单图 / 目录批量）：把参数原样转给 src.python.cli
#   .\scripts\cli.ps1 data --list
#   .\scripts\cli.ps1 data --map "旧=新" --map-file 映射.json
#   .\scripts\cli.ps1 data\某图.png -o 输出.png --map "2023=2024"
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "缺少运行环境，请先执行 .\scripts\setup.ps1"
    exit 1
}

$forward = @($args)
if ($forward.Count -eq 0) {
    & $py -m src.python.cli --help
} else {
    & $py -m src.python.cli @forward
}
exit $LASTEXITCODE
