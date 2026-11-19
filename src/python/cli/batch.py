"""批量流程：规划遍、替换遍与并发档位。

这里只做**编排**：读图、调 `core` 的规则、算输出名、汇总结果。
替换规则（匹配/字体/擦除/绘制/占名语义）全部在 `core`，本模块不得复制其中任何一段。
"""

from __future__ import annotations

import concurrent.futures as cf
import contextlib
import os
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from ..config import log_dir
from ..core import (
    CoreError,
    Options,
    load_image,
    load_meta,
    make_jobs,
    record_write,
    replace_image,
    reserve_path,
    same_file,
    save_image,
    unique_path,
)

# 规划遍解码过的图先留一份（省掉第二遍重新解码）；超过这个预算就不再缓存
CACHE_BYTES_MAX = 512 * 1024 * 1024

# 并发档位：默认档由实测决定（逐图并发只会更慢，见 technical §9），
# 想放大必须显式开口子——`-j auto` 或环境变量，且 auto 有上限，不随核数无限放大。
WORKERS_ENV = "IMG_P_WORKERS"
WORKERS_AUTO_CAP = 4


def workers_value(raw: str) -> int:
    """把 `1` / `auto` / `N` 解析成 worker 数；非法值当场退出。"""
    text = str(raw).strip().lower()
    if text == "auto":
        return max(1, min(WORKERS_AUTO_CAP, int((os.cpu_count() or 4) * 0.5)))
    try:
        value = int(text)
    except ValueError:
        sys.exit(f"--workers 只能是 1、auto 或正整数: {raw}")
    if value < 1:
        sys.exit(f"--workers 至少为 1: {raw}")
    return value


def resolve_workers(requested: str | None, *, dry_run: bool, batch: bool) -> int:
    """并发度：CLI `-j` > `IMG_P_WORKERS` > 默认 1（预演恒为 1，保证去重有序）。"""
    if dry_run or not batch:
        return 1
    raw = requested if requested is not None else os.environ.get(WORKERS_ENV) or "1"
    return workers_value(raw)


def parallel_map(fn: Callable[[Any], Any], items: list[Any], workers: int) -> Iterator[Any]:
    """保持输入顺序的并发映射；workers≤1 时就地串行（排障看到的就是源码顺序）。"""
    if workers <= 1:
        for item in items:
            yield fn(item)
        return
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(fn, items)


def scan_images(
    files: list[str],
    mapping: dict[str, str],
    areas: list[str],
    opts: Options,
    workers: int,
) -> tuple[list[dict[str, Any]], list[str], dict[str, tuple[Any, Any]]]:
    """规划遍：逐图读入 + 规划任务，并收集字体匹配要用的原文。

    返回 (scans, 原文文本, 已解码缓存)。解码过的图在预算内留一份给替换遍复用。
    """
    cached: dict[str, tuple[Any, Any]] = {}
    cache_bytes = 0

    def scan_one(path: str) -> dict[str, Any]:
        item: dict[str, Any] = {"path": path, "jobs": [], "error": None, "image": None}
        try:
            rgb, alpha = load_image(path)
        except OSError as e:
            item["error"] = str(e)
            return item
        item["jobs"] = make_jobs(
            rgb, mapping, areas, min_score=opts.min_score, fuzzy_min=opts.fuzzy_min
        )
        item["image"] = (rgb, alpha)
        return item

    scans: list[dict[str, Any]] = []
    texts: list[str] = []
    for item in parallel_map(scan_one, files, workers):
        if item["error"]:
            print(f"! 跳过 {item['path']}: {item['error']}", file=sys.stderr)
            continue
        image = item.pop("image")
        if image is not None:
            size = int(image[0].nbytes) + (0 if image[1] is None else int(image[1].nbytes))
            if cache_bytes + size <= CACHE_BYTES_MAX:
                cached[item["path"]] = image
                cache_bytes += size
        texts += [j.src or j.new for j in item["jobs"]]
        scans.append(item)
    return scans, texts, cached


@dataclass
class ReplaceContext:
    """替换遍需要的全部上下文（避免把一堆参数在函数间传来传去）。"""

    opts: Options
    pool: list[Any]
    out_dir: str
    batch: bool
    output: str | None
    cached: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    used_names: set[str] = field(default_factory=set)

    @property
    def quiet(self) -> bool:
        return bool(self.opts.quiet)

    @property
    def dry_run(self) -> bool:
        return bool(self.opts.dry_run)

    def target_for(self, path: str) -> str:
        if self.output and not self.batch:
            return self.output
        return os.path.join(self.out_dir, os.path.splitext(os.path.basename(path))[0] + ".png")

    def log_dir(self) -> str:
        return self.opts.log_dir or log_dir()


def replace_one(scan: dict[str, Any], ctx: ReplaceContext) -> dict[str, Any]:
    """替换一张图：返回 {"ok", "path", "dst", "report"} 或 {"ok": False, "error"}。"""
    path = scan["path"]
    got = ctx.cached.pop(path, None)
    if got is None:
        try:
            got = load_image(path)
        except OSError as e:
            return {"ok": False, "path": path, "error": f"跳过 {path}: {e}"}
    rgb, alpha = got
    meta = load_meta(path)
    tag = f"{os.path.splitext(os.path.basename(path))[0]}_"
    out, new_alpha, report = replace_image(
        rgb, alpha, scan["jobs"], ctx.opts, ctx.pool, tag=tag, source=path
    )
    if not report:
        return {"ok": False, "path": path, "error": f"{path} 没有成功的替换"}
    dst = ctx.target_for(path)
    if same_file(dst, path):
        return {
            "ok": False,
            "path": path,
            "error": f"{dst} 就是原图，拒绝覆盖（换 --out-dir 或 -o）",
        }
    if not (ctx.output and not ctx.batch):
        if ctx.dry_run:  # 预演不建文件，只能靠内存集合避让重名（保证串行）
            dst = unique_path(dst, ctx.used_names)
            ctx.used_names.add(os.path.basename(dst))
        else:
            try:
                dst = reserve_path(dst)  # 原子占名，并发也不撞
            except CoreError as e:
                return {"ok": False, "path": path, "error": str(e)}
    if not ctx.dry_run:
        try:
            save_image(out, new_alpha, dst, quality=ctx.opts.quality, meta=meta)
        except (OSError, CoreError) as e:
            if dst != (ctx.output if not ctx.batch else None):
                with contextlib.suppress(OSError):
                    os.remove(dst)  # 清掉占位空文件
            return {"ok": False, "path": path, "error": f"保存失败 {dst}: {e}"}
        try:  # 真的写了盘才记日志（预演不记）
            record_write(
                path,
                dst,
                report,
                log_dir=ctx.log_dir(),
                channel=ctx.opts.channel,
                options=ctx.opts,
            )
        except CoreError as e:
            print(f"! 已保存但{e}（检查日志目录权限）", file=sys.stderr)
    return {"ok": True, "path": path, "dst": dst, "report": report}


def replace_images(
    todo: list[dict[str, Any]], ctx: ReplaceContext, workers: int
) -> Iterator[dict[str, Any]]:
    """替换遍：按输入顺序产出每张图的结果（并发时仍然保序）。"""
    yield from parallel_map(lambda scan: replace_one(scan, ctx), todo, workers)
