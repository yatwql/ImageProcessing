#!/usr/bin/env python3
"""发布流程编排：把"出一次版本"固化成可审阅的子命令，失败即停。

    python tools/release.py check                 # 工作区干净 + 版本一致 + 快速门禁
    python tools/release.py prepare --version 0.2 # 改 version.py 与 changelog 标题
    python tools/release.py gate                  # 全量门禁（= check_all）
    python tools/release.py build                 # 打 wheel/sdist + SHA256SUMS
    python tools/release.py tag                   # 打附注标签 vX.Y（--yes 才真执行）
    python tools/release.py publish --yes         # gh release create（不带 --yes 只打印命令）

设计取向与 investor-review 一致：**每一步都单独可跑、可审阅、可重试**，
且"发布前必须全绿"这件事由 `gate` 自己保证，不靠人记。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "python" / "version.py"
CHANGELOG = ROOT / "docs" / "managements" / "changelog.md"
DIST = ROOT / "dist"
PY = sys.executable


def sh(cmd: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=check)


def read_version() -> tuple[str, str]:
    text = VERSION_FILE.read_text(encoding="utf-8")
    version = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    updated = re.search(r'^UPDATED = "([^"]+)"', text, re.MULTILINE)
    if not version or not updated:
        raise SystemExit("version.py 里缺 VERSION 或 UPDATED")
    return version.group(1), updated.group(1)


def cmd_check() -> int:
    problems: list[str] = []
    status = sh(["git", "status", "--porcelain"]).stdout.strip()
    if status:
        problems.append("工作区不干净（先提交或 stash）：\n" + status)
    version, updated = read_version()
    commit_date = sh(["git", "log", "-1", "--format=%cs", "--", "src"]).stdout.strip()
    if commit_date and commit_date != updated:
        problems.append(f"UPDATED={updated} 与 src/ 最后提交 {commit_date} 不一致")
    if not re.fullmatch(r"\d+\.\d+", version):
        problems.append(f"版本号格式应为 MAJOR.MINOR，收到 {version!r}")
    quick = sh([PY, "tools/check_all.py", "--quick"], check=False)
    if quick.returncode != 0:
        problems.append("check_all --quick 未通过")
    if problems:
        for item in problems:
            print(f"[FAIL] {item}")
        return 1
    print(f"[ok] 预检通过：版本 {version}（{updated}），工作区干净，quick 门禁全绿")
    return 0


def cmd_prepare(version: str) -> int:
    if not re.fullmatch(r"\d+\.\d+", version):
        print(f"[FAIL] 版本号格式应为 MAJOR.MINOR，收到 {version!r}")
        return 2
    today = dt.date.today().isoformat()
    text = VERSION_FILE.read_text(encoding="utf-8")
    text = re.sub(r'^VERSION = "[^"]+"', f'VERSION = "{version}"', text, flags=re.MULTILINE)
    text = re.sub(r'^UPDATED = "[^"]+"', f'UPDATED = "{today}"', text, flags=re.MULTILINE)
    VERSION_FILE.write_text(text, encoding="utf-8")

    changelog = CHANGELOG.read_text(encoding="utf-8")
    head = f"## v{version} — {today}"
    if head in changelog:
        print(f"[ok] changelog 已有 {head} 标题")
    else:
        lines = changelog.splitlines()
        insert_at = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
        block = [head, "", "### 变更", "", "- 待补：本版本的主要内容。", ""]
        lines[insert_at:insert_at] = block
        CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[ok] changelog 已插入 {head}（记得补内容）")
    print("下一步：补 changelog 内容 → python tools/release.py gate")
    return 0


def cmd_gate() -> int:
    proc = subprocess.run([PY, "tools/check_all.py"], cwd=str(ROOT))
    return proc.returncode


def cmd_build() -> int:
    DIST.mkdir(exist_ok=True)
    for stale in DIST.iterdir():
        stale.unlink()
    proc = subprocess.run(
        [PY, "-m", "pip", "wheel", "--no-deps", "-w", str(DIST), "."], cwd=str(ROOT)
    )
    if proc.returncode != 0:
        return 1
    sdist = subprocess.run(
        [PY, "-m", "build", "--sdist", "--outdir", str(DIST)], cwd=str(ROOT), check=False
    )
    if sdist.returncode != 0:
        print("[!] 没有 `build` 包，跳过 sdist（pip install build 后可生成）")
    sums = []
    for artifact in sorted(DIST.iterdir()):
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        sums.append(f"{digest}  {artifact.name}")
    (DIST / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print("[ok] 产物：")
    for line in sums:
        print("  " + line)
    return 0


def cmd_tag(version: str, yes: bool) -> int:
    tag = f"v{version}"
    existing = sh(["git", "tag", "--list", tag]).stdout.strip()
    if existing:
        print(f"[FAIL] 标签 {tag} 已存在")
        return 2
    message = f"retype {version}"
    print(f"将执行：git tag -a {tag} -m '{message}'")
    if not yes:
        print("（加 --yes 才会真的打标签）")
        return 0
    sh(["git", "tag", "-a", tag, "-m", message])
    print(f"[ok] 已创建标签 {tag}；推送：git push origin {tag}")
    return 0


def cmd_publish(version: str, yes: bool) -> int:
    tag = f"v{version}"
    artifacts = [str(p) for p in sorted(DIST.iterdir())] if DIST.exists() else []
    if not artifacts:
        print("[FAIL] dist/ 是空的，先跑 python tools/release.py build")
        return 2
    cmd = ["gh", "release", "create", tag, *artifacts, "--verify-tag", "--generate-notes"]
    print("将执行：" + " ".join(cmd))
    if not yes:
        print("（加 --yes 才会真的发布）")
        return 0
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    version, _updated = read_version()
    ap = argparse.ArgumentParser(description="retype 发布流程")
    ap.add_argument("command", choices=["check", "prepare", "gate", "build", "tag", "publish"])
    ap.add_argument("--version", default=version, help=f"目标版本（当前 {version}）")
    ap.add_argument("--yes", action="store_true", help="真的执行有副作用的步骤")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "check":
        return cmd_check()
    if args.command == "prepare":
        return cmd_prepare(args.version)
    if args.command == "gate":
        return cmd_gate()
    if args.command == "build":
        return cmd_build()
    if args.command == "tag":
        return cmd_tag(args.version, args.yes)
    return cmd_publish(args.version, args.yes)


if __name__ == "__main__":
    sys.exit(main())
