#!/usr/bin/env python3
"""CI 工作流自检：把"只在 runner 上才炸"的脚本错误搬到本地。

    python tools/check_workflows.py

检查项：
1. `ci.yml` 能被 YAML 解析，且作业集合与文档一致；
2. 每个 `run:` 块通过 `bash -n` 语法检查（默认 shell 为 bash）；
3. `run:` 里出现的 `python -c "…"` 片段能被 `compile()` 通过
   （多行 `-c` 在 3.10 上会 IndentationError——本轮真实事故）；
4. `audit` 作业必须带 `--skip-editable`（本地 editable 安装在 PyPI 上查不到，
   不带这个参数 pip-audit 直接非零退出——本轮另一处真实事故）；
5. `release` 作业必须只在 `v*` 标签触发且有 `contents: write`。

这些都是"本地跑不通、只有 CI 能暴露"的类别，所以做成门禁而不是靠记忆。
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from ._paths import ROOT  # noqa: E402  (工具共用仓库根)

CI = ROOT / ".github" / "workflows" / "ci.yml"

EXPECTED_JOBS = {"test", "lint", "typecheck", "guards", "perf", "windows", "audit", "release"}
PY_C_SNIPPET = re.compile(r'python\s+-c\s+"([^"]+)"')


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # CI 上装了 pyyaml；本地缺就跳过解析
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def iter_steps(workflow: dict) -> Iterator[tuple[str, dict]]:
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if isinstance(step, dict):
                yield job_name, step


def bash_runs() -> bool:
    """本机 `bash` 是否真的能执行。

    windows-latest 上的 `bash` 常是 WSL 存根：跑起来就退 1、stderr 还是空的。
    不探测就在这里给每个 run 块判"语法错误"——守护自己在别的平台上是假红。
    """
    exe = shutil.which("bash")
    if not exe:
        return False
    try:
        proc = subprocess.run(
            [exe, "-c", "exit 0"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


BASH_OK = bash_runs()   # 没有可执行的 bash 时跳过 bash -n（Windows 上的 WSL 存根）


def check_run_blocks(workflow: dict) -> list[str]:
    problems: list[str] = []
    for job_name, step in iter_steps(workflow):
        script = step.get("run")
        if not isinstance(script, str):
            continue
        name = step.get("name", "(unnamed)")
        if "<<'PY'" in script or "<<\"PY\"" in script or re.search(r"python.*\s-\s*<<", script):
            problems.append(
                f"{job_name} / {name}：run 块里内联 python 脚本（heredoc）——"
                "代码要进 src/python/tools（能 ensure_utf8_stdio、能写用例、能病态输入打桩）"
            )
            continue
        if step.get("shell", "bash") != "bash":
            continue  # 非 bash 的步骤只做 YAML 解析
        if not BASH_OK:
            continue  # 没有能真正执行的 bash（WSL 存根）：只保留 YAML 与 python 片段检查
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as f:
            f.write(script)
            temp_path = Path(f.name)
        try:
            result = subprocess.run(["bash", "-n", str(temp_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            temp_path.unlink(missing_ok=True)
        if result.returncode != 0:
            problems.append(f"{job_name}/{name}: bash 语法错误 {result.stderr.strip()[:160]}")
        for snippet in PY_C_SNIPPET.findall(script):
            source = snippet.replace("\\n", "\n")
            try:
                ast.parse(source, filename=f"<{job_name}/{name}>")  # 只解析语法，不执行
            except SyntaxError as exc:
                problems.append(f"{job_name}/{name}: python -c 片段语法错误（{exc.msg}）")
    return problems


def check_audit_step(workflow: dict) -> list[str]:
    """audit 必须审计"冻结的依赖清单"：直接审计环境会撞上本地 editable 包而失败。"""
    for _job, step in iter_steps(workflow):
        script = step.get("run")
        if isinstance(script, str) and "pip_audit" in script:
            if "-r " not in script:
                return ["audit 作业要用 `-r <冻结清单>` 审计依赖，而不是审计当前环境"]
            if 'grep -v "^-e"' not in script:
                return ["audit 作业要先把 editable 安装过滤掉（`pip freeze | grep -v '^-e'`）"]
            return []
    return ["缺少 pip-audit 步骤"]


def check_release_job(workflow: dict) -> list[str]:
    job = (workflow.get("jobs") or {}).get("release")
    if not job:
        return ["缺少 release 作业（推 v* 标签时构建并发布）"]
    problems = []
    trigger = str(job.get("if", ""))
    if "refs/tags/v" not in trigger:
        problems.append(
            "release 作业必须只在 v* 标签触发（if: startsWith(github.ref, 'refs/tags/v')）"
        )
    if (job.get("permissions") or {}).get("contents") != "write":
        problems.append("release 作业需要 permissions.contents: write 才能建 Release")
    return problems


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    if not CI.is_file():
        print(f"[FAIL] 缺少 {CI.relative_to(ROOT)}")
        return 1
    workflow = load_yaml(CI)
    problems: list[str] = []
    if workflow:
        jobs = set((workflow.get("jobs") or {}).keys())
        if jobs != EXPECTED_JOBS:
            problems.append(f"作业集合与预期不符：实际 {sorted(jobs)}")
        problems += check_run_blocks(workflow)
        problems += check_audit_step(workflow)
        problems += check_release_job(workflow)
    if problems:
        for item in problems:
            print(f"[FAIL] {item}")
        return 1
    print("[ok] 工作流自检通过（YAML / bash 语法 / python -c / audit 参数 / release 作业）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
