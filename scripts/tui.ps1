# 交互界面入口（Windows / PowerShell）：不给参数时默认读 data/，结果默认写 data/output/
#   .\scripts\tui.ps1
#   .\scripts\tui.ps1 data
#   .\scripts\tui.ps1 data -m map.json
# 依赖 windows-curses（setup.ps1 已按 Python 平台自动安装）
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "缺少运行环境，请先执行 .\scripts\setup.ps1"
    exit 2
}

$forward = @($args)
foreach ($a in $forward) {
    if ($a -eq "-h" -or $a -eq "--help") {
        & $py -m src.python.tui --help
        exit $LASTEXITCODE
    }
}

if ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected) {
    Write-Error "tui 需要真终端（交互界面），批处理请用 .\scripts\cli.ps1"
    exit 2
}

if ($forward.Count -eq 0) {
    & $py -m src.python.tui data
} else {
    & $py -m src.python.tui @forward
}
exit $LASTEXITCODE
