#!/usr/bin/env python3
"""发布流程编排：把"出一次版本"固化成可审阅的子命令，失败即停。

    python tools/release.py check                 # 工作区干净 + 版本一致 + 快速门禁（含两档 CI 矩阵）
    python tools/release.py archive --yes         # 把三份台账的旧内容整块搬进 docs/archive/vX.Y.x/
    python tools/release.py prepare --version 0.2 # 定版：0.2-dev → 0.2（改 version.py 与 changelog 标题）
    python tools/release.py devbump --version 0.3 # 发布后切下一个开发版（→ 0.3-dev，在 dev 分支跑）
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
import time
from pathlib import Path

from ..stdio import ensure_utf8_stdio
from . import gate_stamp
from ._paths import ROOT

VERSION_FILE = ROOT / "src" / "python" / "version.py"
DOCS = ROOT / "docs"
CHANGELOG = DOCS / "managements" / "changelog.md"
DIST = ROOT / "dist"
DEV_SUFFIX = "-dev"  # 开发分支上的版本号后缀：0.3-dev；发布时去掉
PY = sys.executable

# 归档：三份过程台账，旧版本内容整块搬进 docs/archive/v<系列>/（规则见 docs/archive/README.md）
ARCHIVE_HEADING = "## 归档"
ARCHIVE_DOCS = [
    ("plan.md", "archived_plan", "计划归档"),
    ("review-findings.md", "archived_review-findings", "自检记录归档"),
    ("changelog.md", "archived_changelog", "变更记录归档"),
]
HEADER_KEYS = ("归档时间", "原始文件", "涵盖版本", "归档内容")


def sh(cmd: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def read_version() -> tuple[str, str]:
    text = VERSION_FILE.read_text(encoding="utf-8")
    version = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    updated = re.search(r'^UPDATED = "([^"]+)"', text, re.MULTILINE)
    if not version or not updated:
        raise SystemExit("version.py 里缺 VERSION 或 UPDATED")
    return version.group(1), updated.group(1)


def base_version(version: str) -> str:
    """`0.2-dev` → `0.2`：正式版本号（标签、发布说明都用它）。"""
    return version[: -len(DEV_SUFFIX)] if version.endswith(DEV_SUFFIX) else version


def is_dev(version: str) -> bool:
    return version.endswith(DEV_SUFFIX)


def write_version(version: str, today: str, version_file: Path | None = None) -> None:
    path = version_file if version_file is not None else VERSION_FILE
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^VERSION = "[^"]+"', f'VERSION = "{version}"', text, flags=re.MULTILINE)
    text = re.sub(r'^UPDATED = "[^"]+"', f'UPDATED = "{today}"', text, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")


def cmd_check() -> int:
    """发布前预检：**便宜的检查先红就停**，绿了再决定要不要跑全量门禁。

    顺序很要紧：工作区不干净、版本号不对这类问题几毫秒就能查出来，
    以前却要先把整条门禁跑完才报——那是纯粹白跑。
    """
    started = time.perf_counter()
    problems = cheap_problems()
    if problems:
        for item in problems:
            print(f"[FAIL] {item}")
        print("[!] 结构性预检未通过：全量门禁一行没跑（先修上面这些）")
        return 1

    version, updated = read_version()
    if gate_stamp.stamp_matches():
        print(
            f"[ok] 预检通过：版本 {version}（{updated}），"
            f"同一份代码已通过全量门禁（命中门禁戳，跳过重跑，{_elapsed(started)}）"
        )
        return 0

    print("[..] 跑全量门禁：静态检查 + 四档环境矩阵 + 覆盖率 + 并行分片重排")
    if subprocess.run([PY, "-m", "src.python.tools.check_all"], cwd=str(ROOT)).returncode != 0:
        print(f"[FAIL] 全量门禁未通过（{_elapsed(started)}，失败的一档见上方输出）")
        return 1
    print(
        f"[ok] 预检通过：版本 {version}（{updated}），工作区干净，"
        f"全量门禁全绿（{_elapsed(started)}，已写门禁戳）"
    )
    return 0


def cheap_problems() -> list[str]:
    """几毫秒就能查完的结构性预检（不看代码是否真的能跑）。"""
    problems: list[str] = []
    status = sh(["git", "status", "--porcelain"]).stdout.strip()
    if status:
        problems.append("工作区不干净（先提交或 stash）：\n" + status)
    version, updated = read_version()
    commit_date = sh(["git", "log", "-1", "--format=%cs", "--", "src"]).stdout.strip()
    if commit_date and commit_date != updated:
        problems.append(f"UPDATED={updated} 与 src/ 最后提交 {commit_date} 不一致")
    if not re.fullmatch(r"\d+\.\d+(?:-dev)?", version):
        problems.append(f"版本号应为 MAJOR.MINOR 或 MAJOR.MINOR-dev，收到 {version!r}")
    branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if branch == "master" and is_dev(version):
        problems.append(f"master 上是 {version}：发布分支不能带 -dev（先 prepare 成正式号）")
    if branch == "dev" and not is_dev(version):
        problems.append(f"dev 上是 {version}：开发分支的版本必须带 -dev（如 {version}-dev）")
    return problems


def _elapsed(started: float) -> str:
    return f"{time.perf_counter() - started:.1f}s"


def cmd_prepare(version: str) -> int:
    if not re.fullmatch(r"\d+\.\d+(?:-dev)?", version):
        print(f"[FAIL] 版本号应为 MAJOR.MINOR 或 MAJOR.MINOR-dev，收到 {version!r}")
        return 2
    current, _updated = read_version()
    if base_version(current) != base_version(version):
        print(
            f"[FAIL] 跨版本发布：当前 {current}，目标 {version}。"
            "发布只能把当前开发版（X.Y-dev）定版为 X.Y；换小版本请先 devbump"
        )
        return 2
    today = dt.date.today().isoformat()
    write_version(version, today)

    changelog = CHANGELOG.read_text(encoding="utf-8")
    head = f"## v{base_version(version)} — {today}"
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


def series_of(version: str) -> str:
    """`0.1` → `0.1.x`：归档目录与归档文件名都按版本系列分。"""
    return f"{version}.x"


def split_doc(text: str) -> tuple[str, str, str | None]:
    """把一份台账切成（文件头 / 正文 / 归档索引段）。

    文件头 = 第一个 `## ` 标题之前的说明块（含 `> 版本：` 行，守护会核对它）；
    正文 = 第一个 `## ` 到 `## 归档` 之前，也就是要搬进归档的全部内容；
    归档索引 = `## 归档` 到文件末尾，由脚本重新生成，没有则为 None。
    """
    lines = text.splitlines()
    head_end = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
    arch_start = next((i for i, ln in enumerate(lines) if ln.strip() == ARCHIVE_HEADING), None)
    head = "\n".join(lines[:head_end]).rstrip() + "\n"
    body_end = arch_start if arch_start is not None else len(lines)
    body = "\n".join(lines[head_end:body_end]).strip()
    tail = None if arch_start is None else "\n".join(lines[arch_start:])
    return head, body, tail


def archive_header(title: str, series: str, source_rel: str, version: str, today: str) -> str:
    """新建归档文件的固定头部：四个字段由守护「归档」逐项核对。"""
    return (
        f"# {title} — v{series}\n\n"
        f"> 归档时间：{today}（v{version} 发布，本系列首份）\n"
        f"> 原始文件：`{source_rel}`\n"
        f"> 涵盖版本：v{version}\n"
        f"> 归档内容：由 `python -m src.python.tools.release archive` 整块搬运，未改一字\n\n"
        "---\n"
    )


def batch_heading(version: str, today: str) -> str:
    return f"\n## 归档批次 v{version}（{today}）\n"


def parse_meta(text: str) -> tuple[str, str]:
    """从归档文件头部取出（涵盖版本, 归档时间），取不到就给占位符。"""
    covered = re.search(r"^> 涵盖版本：(.+)$", text, re.MULTILINE)
    when = re.search(r"^> 归档时间：(.+)$", text, re.MULTILINE)
    return (covered.group(1).strip() if covered else "—", when.group(1).strip() if when else "—")


def _series_key(name: str) -> tuple[int, ...]:
    m = re.match(r"v(\d+(?:\.\d+)*)", name)
    return tuple(int(part) for part in m.group(1).split(".")) if m else (0,)


def build_index(archive_root: Path, stem: str) -> str:
    """生成 `## 归档` 索引段：列出该台账在各版本系列下的归档文件。

    链接按「从 docs/managements/ 出发」的相对路径算（`../archive/…`）。
    """
    rows: list[str] = []
    if archive_root.is_dir():
        series_dirs = sorted(
            (p for p in archive_root.iterdir() if p.is_dir()),
            key=lambda p: _series_key(p.name),
            reverse=True,
        )
        for series_dir in series_dirs:
            for path in sorted(series_dir.glob(f"{stem}.*.md")):
                series = path.name.removeprefix(f"{stem}.").removesuffix(".md")
                covered, when = parse_meta(path.read_text(encoding="utf-8"))
                rel = f"../archive/{series_dir.name}/{path.name}"
                rows.append(f"| v{series} | [`{path.name}`]({rel}) | {covered} | {when} |")
    block = [
        ARCHIVE_HEADING,
        "",
        "> 已发布版本的旧内容整块搬进 `docs/archive/`，本文件只留当前开发版本的内容；",
        "> 目录与文件命名规则见[归档规范](../archive/README.md)。搬运无损、不改一字，",
        "> 编号 `PLAN-x` / `RF-x` 归档后仍占号，不复用。",
        "",
    ]
    if rows:
        block += [
            "| 系列 | 归档文件 | 涵盖版本 | 归档时间 |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
        ]
    else:
        block += ["（暂无归档文件：本系列首次发布后由 `release.py archive` 写入。）", ""]
    return "\n".join(block)


def cmd_archive(version: str, yes: bool, docs: Path | None = None) -> int:
    """把三份台账的正文整块搬进 `docs/archive/v<系列>/`，主文件只留文件头与归档索引。"""
    docs_dir = docs if docs is not None else DOCS
    archive_root = docs_dir / "archive"
    series = series_of(version)
    today = dt.date.today().isoformat()
    targets: list[tuple[Path, str, str, str, str]] = []
    for name, stem, title in ARCHIVE_DOCS:
        main_path = docs_dir / "managements" / name
        head, body, _tail = split_doc(main_path.read_text(encoding="utf-8"))
        targets.append((main_path, stem, title, head, body))
    if all(not body for _p, _s, _t, _h, body in targets):
        print(f"[ok] 三份台账都没有待归档正文（当前系列 v{series}）")
        return 0
    for main_path, stem, title, head, body in targets:
        shown = main_path.relative_to(ROOT) if main_path.is_relative_to(ROOT) else main_path
        target = archive_root / f"v{series}" / f"{stem}.{series}.md"
        shown_target = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
        rel_source = (
            main_path.relative_to(ROOT).as_posix()
            if main_path.is_relative_to(ROOT)
            else main_path.as_posix()
        )
        state = "追加批次" if target.is_file() else "新建归档"
        print(
            f"[plan] {shown.as_posix()} → {shown_target.as_posix()}"
            f"（{state}，正文 {len(body.splitlines())} 行）"
        )
        if not yes:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            old = target.read_text(encoding="utf-8").rstrip() + "\n"
            target.write_text(
                old + batch_heading(version, today) + "\n" + body + "\n", encoding="utf-8"
            )
        else:
            header = archive_header(title, series, rel_source, version, today)
            target.write_text(header + "\n" + body + "\n", encoding="utf-8")
        index = build_index(archive_root, stem)
        main_path.write_text(
            head + ("" if head.endswith("\n\n") else "\n") + index, encoding="utf-8"
        )
    if not yes:
        print(
            "[plan] 以上为预演；加 --yes 才会真的搬（先确认工作区干净、changelog 已写完本版内容）"
        )
        return 0
    print("[ok] 归档完成；下一步：gen_folders --write 同步目录树，再 prepare → gate")
    return 0


def cmd_gate(force: bool = False) -> int:
    """全量门禁。命中门禁戳（同一份代码已全绿）就直接放行，`--force` 强制重跑。"""
    if not force and gate_stamp.stamp_matches():
        print("[ok] 同一份代码已通过全量门禁（命中门禁戳）；要强制重跑加 --force")
        return 0
    started = time.perf_counter()
    code = subprocess.run([PY, "-m", "src.python.tools.check_all"], cwd=str(ROOT)).returncode
    print(
        f"[{'ok' if code == 0 else 'FAIL'}] 全量门禁{'通过' if code == 0 else '未通过'}（{_elapsed(started)}）"
    )
    return code


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


def cmd_devbump(version: str, version_file: Path | None = None) -> int:
    """切到下一个开发版本：`VERSION = X.Y-dev`（发布后回到 dev 分支的第一步）。"""
    target = base_version(version)
    if not re.fullmatch(r"\d+\.\d+", target):
        print(f"[FAIL] 目标版本应为 MAJOR.MINOR（自动补 -dev），收到 {version!r}")
        return 2
    current, _updated = read_version()
    today = dt.date.today().isoformat()
    write_version(f"{target}{DEV_SUFFIX}", today, version_file)
    print(f"[ok] 版本 {current} → {target}{DEV_SUFFIX}（记得同步各文档的「> 版本：」行）")
    return 0


def cmd_tag(version: str, yes: bool) -> int:
    if is_dev(version):
        print(
            f"[FAIL] {version} 是开发版，不能打标签；先 prepare --version {base_version(version)}"
        )
        return 2
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
    ensure_utf8_stdio()
    version, _updated = read_version()
    ap = argparse.ArgumentParser(description="retype 发布流程")
    ap.add_argument(
        "command",
        choices=["check", "archive", "prepare", "devbump", "gate", "build", "tag", "publish"],
    )
    ap.add_argument("--version", default=version, help=f"目标版本（当前 {version}）")
    ap.add_argument("--yes", action="store_true", help="真的执行有副作用的步骤")
    ap.add_argument("--force", action="store_true", help="gate 忽略门禁戳，强制重跑")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "check":
        return cmd_check()
    if args.command == "archive":
        return cmd_archive(args.version, args.yes)
    if args.command == "prepare":
        return cmd_prepare(args.version)
    if args.command == "devbump":
        return cmd_devbump(args.version)
    if args.command == "gate":
        return cmd_gate(args.force)
    if args.command == "build":
        return cmd_build()
    if args.command == "tag":
        return cmd_tag(args.version, args.yes)
    return cmd_publish(args.version, args.yes)


if __name__ == "__main__":
    sys.exit(main())
