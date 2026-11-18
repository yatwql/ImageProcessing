"""写盘审计：图片每真正落盘一次，就往 logs/ 追加一条 JSON 行记录。

记录内容：发生时间、渠道、源文件（名/路径/大小）、目标文件（名/路径/大小）、
具体做了什么（哪些旧文字换成了哪些新文字，以及用的字体/字号/字距/颜色/对齐）。
日志按天分文件，一行一个 JSON 对象，UTF-8 编码，只追加不改写。
"""

from __future__ import annotations

import datetime as dt
import glob
import hashlib
import importlib
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from PIL import Image

from ..version import NAME, UPDATED, VERSION
from .errors import CoreError
from .options import Options

try:                                    # POSIX
    import fcntl
except ImportError:                     # pragma: no cover - 平台差异
    fcntl = None                        # type: ignore[assignment]

def _winlock() -> Any:
    """Windows 的 msvcrt 模块（非 Windows 返回 None），只在用到时才导入。"""
    try:
        return importlib.import_module("msvcrt")
    except ImportError:                 # pragma: no cover - 平台差异
        return None

LOG_PREFIX = "image-writes-"
LOG_KEEP_DAYS = 30                       # 只保留最近 30 天，避免日志无限增长
ACTION_REPLACE = "替换文字并保存图片"
ACTION_DEBUG = "写出调试图"

# 报告里需要落到日志中的字段
OP_FIELDS = ("old", "new", "mode", "rect", "font", "size", "tracking", "color", "align", "iou")

# Options 里代表「用户显式指定过」的样式项
OPTION_FIELDS = ("font", "size", "color", "align", "fit_width", "tracking", "max_fonts")


def log_path(log_dir: str, when: dt.datetime | None = None) -> str:
    """当天日志文件的路径：<日志目录>/image-writes-YYYYMMDD.log。"""
    day = (when or dt.datetime.now()).strftime("%Y%m%d")
    return os.path.join(log_dir, f"{LOG_PREFIX}{day}.log")


def prune_logs(log_dir: str, keep_days: int = LOG_KEEP_DAYS,
               today: dt.date | None = None) -> list[str]:
    """删掉超过保留期的按天日志，返回被删掉的文件名（失败静默跳过）。"""
    if keep_days <= 0:
        return []
    cutoff = (today or dt.date.today()) - dt.timedelta(days=keep_days)
    try:
        names = os.listdir(log_dir)
    except OSError:
        return []
    removed: list[str] = []
    for name in names:
        if not (name.startswith(LOG_PREFIX) and name.endswith(".log")):
            continue
        try:
            day = dt.datetime.strptime(name[len(LOG_PREFIX):-4], "%Y%m%d").date()
        except ValueError:
            continue
        if day >= cutoff:
            continue
        try:
            os.remove(os.path.join(log_dir, name))
        except OSError:
            continue
        removed.append(name)
    return removed


def _lock(fd: int) -> bool:
    """跨进程串行写：POSIX 用 flock，Windows 用 msvcrt 锁首字节。"""
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return True
    win = _winlock()
    if win is not None:                  # pragma: no cover - Windows 分支
        os.lseek(fd, 0, os.SEEK_SET)
        win.locking(fd, win.LK_LOCK, 1)
        return True
    return False                         # pragma: no cover - 其它平台


def _unlock(fd: int, locked: bool) -> None:
    if not locked:
        return
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
        else:
            win = _winlock()
            if win is None:              # pragma: no cover - 其它平台
                return
            os.lseek(fd, 0, os.SEEK_SET)
            win.locking(fd, win.LK_UNLCK, 1)
    except OSError:
        pass


def _size_of(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _digest_of(path: str) -> str | None:
    """目标文件的 sha256，用于事后校验「日志说写的就是磁盘上的这份」。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _pixels_of(path: str) -> tuple[int, int] | None:
    try:
        with Image.open(path) as im:
            return im.size
    except OSError:
        return None


def _op_of(item: Mapping[str, Any]) -> dict[str, Any]:
    return {k: item.get(k) for k in OP_FIELDS}


def options_summary(opts: object | None) -> dict[str, Any]:
    """把用户显式设置过的样式项整理成字典（默认值不写，保持日志干净）。"""
    if opts is None:
        return {}
    base = Options()
    out: dict[str, Any] = {}
    for key in OPTION_FIELDS:
        val = getattr(opts, key, None)
        if val is None or val is False or val == "" or val == getattr(base, key, None):
            continue
        out[key] = val
    return out


def app_version() -> str:
    """当前程序版本（日志字段用；与 --version、界面标题同源）。"""
    return VERSION


def app_updated() -> str:
    """代码最后更新日期（日志字段用；与界面标题同源）。"""
    return UPDATED


def build_entry(src: str, dst: str, report: Sequence[Mapping[str, Any]] = (), *,
                action: str = ACTION_REPLACE, channel: str = "cli",
                options: object | None = None, when: dt.datetime | None = None) -> dict[str, Any]:
    """组装一条写盘记录（不落盘，便于测试与外部复用）。"""
    stamp = when or dt.datetime.now().astimezone()
    pixels = _pixels_of(dst)
    entry: dict[str, Any] = {
        "time": stamp.isoformat(timespec="seconds"),
        "app": NAME,
        "app_version": app_version(),
        "app_updated": app_updated(),
        "channel": channel,
        "action": action,
        "src_file": os.path.basename(src),
        "src_path": os.path.abspath(src),
        "src_size": _size_of(src),
        "dst_file": os.path.basename(dst),
        "dst_path": os.path.abspath(dst),
        "dst_size": _size_of(dst),
        "dst_sha256": _digest_of(dst),
        "dst_width": pixels[0] if pixels else None,
        "dst_height": pixels[1] if pixels else None,
        "replaced": len(report),
        "operations": [_op_of(r) for r in report],
    }
    summary = options_summary(options)
    if summary:
        entry["options"] = summary
    return entry


def record_write(src: str, dst: str, report: Sequence[Mapping[str, Any]] = (), *,
                 log_dir: str, action: str = ACTION_REPLACE, channel: str = "cli",
                 options: object | None = None,
                 when: dt.datetime | None = None) -> str:
    """追加一条写盘记录，返回写入的日志文件路径。

    when: 记录时间与落哪个按天文件，默认取当前时间（测试与补录历史时显式传入）。
    写日志失败抛 CoreError：图片已经存好，由渠道提示一句即可，不算替换失败。
    """
    when = when or dt.datetime.now().astimezone()
    path = log_path(log_dir, when)
    entry = build_entry(src, dst, report, action=action, channel=channel,
                        options=options, when=when)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    try:
        os.makedirs(log_dir, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    except OSError as e:
        raise CoreError(f"无法写入日志 {path}: {e}") from e
    locked = False
    try:
        locked = _lock(fd)                 # 多进程串行写，避免超长行交错
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)                       # 断电也不丢最后一条
    except OSError as e:
        raise CoreError(f"无法写入日志 {path}: {e}") from e
    finally:
        _unlock(fd, locked)
        os.close(fd)
    prune_logs(log_dir)
    return path


def read_entries(log_dir: str, day: dt.date | None = None, src: str | None = None,
                 channel: str | None = None) -> list[dict[str, Any]]:
    """读回写盘记录（新→旧顺序不重要，按文件与写入顺序返回）。

    day: 只读某一天（None = 该目录下所有按天日志）。
    src: 原图文件名或路径的子串，用于"这张图都被换过什么"。
    channel: 渠道精确匹配（cli / tui）。
    坏行（被外部截断、手工编辑坏了）跳过，不因为一行坏掉整份日志读不出来。
    """
    if day is not None:
        paths = [log_path(log_dir, dt.datetime.combine(day, dt.time()))]
    else:
        paths = sorted(glob.glob(os.path.join(log_dir, f"{LOG_PREFIX}*.log")))
    entries: list[dict[str, Any]] = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(entry, dict):
                        continue
                    if src and src not in str(entry.get("src_file", "")) \
                            and src not in str(entry.get("src_path", "")):
                        continue
                    if channel and entry.get("channel") != channel:
                        continue
                    entries.append(entry)
        except OSError as e:
            raise CoreError(f"无法读取日志 {path}: {e}") from e
    return entries


def summarize(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """汇总一批记录：条数、替换操作总数、每张原图被写了多少次。"""
    per_src: dict[str, int] = {}
    per_channel: dict[str, int] = {}
    replacements = 0
    for entry in entries:
        name = str(entry.get("src_file") or "?")
        per_src[name] = per_src.get(name, 0) + 1
        chan = str(entry.get("channel") or "?")
        per_channel[chan] = per_channel.get(chan, 0) + 1
        replacements += int(entry.get("replaced") or 0)
    return {
        "writes": len(entries),
        "replacements": replacements,
        "per_src": dict(sorted(per_src.items(), key=lambda kv: -kv[1])),
        "per_channel": dict(sorted(per_channel.items())),
    }
