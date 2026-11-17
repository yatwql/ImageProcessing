# 跑完整测试并生成测试报告（Windows / PowerShell）
#
#   .\scripts\test.ps1                 # 全部用例 + 覆盖率 + HTML 报告
#   .\scripts\test.ps1 -Fast           # 只跑用例，不算覆盖率/不出 HTML
#   .\scripts\test.ps1 -k 关键字       # 其余参数原样透传给 pytest
#
# 产物：/test-reports/{junit.xml,test-report.html,coverage/index.html,summary.md}
# 测试中间文件：/data/tmp（建不出来时退回系统临时目录）
param(
    [switch]$Fast,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "缺少运行环境，请先执行 .\scripts\setup.ps1 -Dev"
    exit 1
}
& $py -c "import pytest" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "缺少 pytest，请先执行 $py -m pip install -r requirements-dev.txt"
    exit 1
}

$tmpRoot = "/data/tmp"
try {
    New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
    $env:TEMP = $tmpRoot
    $env:TMP = $tmpRoot
    $env:IMG_P_TMP_DIR = $tmpRoot
    $env:PYTHONPYCACHEPREFIX = Join-Path $tmpRoot "pycache"
    $env:COVERAGE_FILE = Join-Path $tmpRoot "coverage/.coverage"
} catch {
    Write-Host "[!] 无法创建 $tmpRoot，测试临时文件改用系统临时目录"
}

$reportDir = "/test-reports"
try {
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
} catch {
    Write-Host "[!] 无法创建 /test-reports，报告改写到 ./reports"
    $reportDir = Join-Path $root "reports"
}
$fastMode = $Fast.IsPresent
$passthrough = @()
foreach ($a in @($Rest)) {
    if ($a -eq "--fast") { $fastMode = $true } else { $passthrough += $a }
}

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue `
    (Join-Path $reportDir "junit.xml"), `
    (Join-Path $reportDir "coverage.xml"), `
    (Join-Path $reportDir "test-report.html")
if ($fastMode) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $reportDir "coverage")
}

$pytestArgs = @("src/test", "-q",
    "--junitxml=$(Join-Path $reportDir 'junit.xml')",
    "-o", "cache_dir=$(Join-Path $tmpRoot 'pytest-cache')")
if ($fastMode) {
    # 预演：只出 junit 与摘要
} else {
    & $py -c "import pytest_cov, pytest_html" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pytestArgs += @(
            "--cov=src/python",
            "--cov-report=term-missing:skip-covered",
            "--cov-report=xml:$(Join-Path $reportDir 'coverage.xml')",
            "--cov-report=html:$(Join-Path $reportDir 'coverage')",
            "--html=$(Join-Path $reportDir 'test-report.html')",
            "--self-contained-html"
        )
    } else {
        Write-Host "[!] 未安装 pytest-cov / pytest-html，本次只出 junit 与摘要"
        $pytestArgs += @("--html=$(Join-Path $reportDir 'test-report.html')", "--self-contained-html")
    }
}
$pytestArgs += $passthrough

function Clear-RepoCache {
    Get-ChildItem -Path (Join-Path $root "src") -Directory -Recurse -Filter "__pycache__" |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($d in @(".pytest_cache", ".ruff_cache")) {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $root $d)
    }
}

Write-Host "== 运行测试 =="
& $py -m pytest @pytestArgs
$code = $LASTEXITCODE

# ---- 汇总（junit.xml + coverage.xml）：与 bash 版同一段逻辑
$summaryScript = @'
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
'@

$fastFlag = if ($fastMode) { "1" } else { "0" }
$summaryScript | & $py - $reportDir $fastFlag

Clear-RepoCache
exit $code
