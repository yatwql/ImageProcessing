"""命令行渠道：单图 / 目录批量。所有替换逻辑都在 src.core 里，这里只负责参数与流程。"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any

from .. import bootstrap
from ..config import apply_to_options, default_out_dir, log_dir
from ..core import (
    CoreError,
    Options,
    build_font_pool,
    collect_images,
    load_image,
    ocr_regions,
    parse_color,
)
from ..core.image import IMG_EXTS
from ..stdio import ensure_utf8_stdio
from ..version import NAME, UPDATED, VERSION
from . import batch as batch_flow

USAGE = """\
示例
  python -m src.cli data/示例.png --list
  python -m src.cli data/示例.png -o out.png --map "旧=新" --map "2023=2024"
  python -m src.cli data --map-file 映射.json            # 目录批量
  python -m src.cli data --map-file 映射.json --dry-run   # 只预演
"""


def load_mapping(map_file: str | None, maps: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if map_file:
        try:
            with open(map_file, encoding="utf-8") as f:
                data = json.load(f)
        except OSError as e:
            sys.exit(f"无法读取映射文件: {e}")
        except json.JSONDecodeError as e:
            sys.exit(f"映射文件不是合法 JSON: {e}")
        if not isinstance(data, dict):
            sys.exit('映射文件应是 {"旧文字": "新文字"} 形式的对象')
        mapping.update({str(k): str(v) for k, v in data.items()})
    for spec in maps:
        if "=" not in spec:
            sys.exit(f"--map 格式错误: {spec}（应为 旧=新）")
        k, v = spec.split("=", 1)
        mapping[k] = v
    return mapping


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="text_replace",
        description="替换图片中的指定文字，保持字体/字号/颜色/排版一致；支持单图与目录批量",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=USAGE,
    )
    ap.add_argument("input", help="输入图片，或图片目录（目录=批量）")
    ap.add_argument("-o", "--output", help="单图：输出文件；批量：输出目录")
    ap.add_argument("--out-dir", help="批量输出目录，默认 data/output")
    ap.add_argument("--map", action="append", default=[], metavar="OLD=NEW", help="替换对，可重复")
    ap.add_argument("--map-file", help='JSON 文件：{"旧文字": "新文字"}')
    ap.add_argument(
        "--area",
        action="append",
        default=[],
        metavar="X,Y,W,H=NEW",
        help="手工指定区域替换（不依赖 OCR，仅单图）",
    )
    ap.add_argument("--list", action="store_true", help="只列出 OCR 文字块后退出（批量=逐图列出）")
    ap.add_argument("--dry-run", action="store_true", help="只报告会替换什么，不写文件")
    ap.add_argument("--font", help="强制指定字体文件")
    ap.add_argument("--size", type=int, help="强制字号（默认自动匹配）")
    ap.add_argument("--color", help="强制字色，如 #FF0000 或 255,0,0")
    ap.add_argument(
        "--align",
        choices=["auto", "left", "center", "right"],
        default="auto",
        help="对齐基准；auto=居中的标题按居中，其余按左对齐",
    )
    ap.add_argument("--fit-width", action="store_true", help="调字距让新文字宽度贴合原文字")
    ap.add_argument("--tracking", type=float, help="强制额外字距(px)，可负")
    ap.add_argument("--max-fonts", type=int, default=160, help="候选字体上限（默认 160）")
    ap.add_argument(
        "-j", "--workers", type=int, help="批量并发数，默认 1（实测逐图并发更慢，只有特殊场景才调）"
    )
    ap.add_argument(
        "--min-score",
        type=float,
        metavar="P",
        help="OCR 置信度下限 0-1：低于它的块不参与匹配（默认 0=不过滤）",
    )
    ap.add_argument(
        "--fuzzy", type=float, metavar="P", help="模糊兑底阈值 0-1（默认 0.8，越低越容易误命中）"
    )
    ap.add_argument("--quality", type=int, help="JPEG/WEBP 输出质量 1-100（默认 95）")
    ap.add_argument("--debug", metavar="DIR", help="输出 mask 等中间图")
    ap.add_argument("--report", metavar="FILE", help="把本次替换摘要写成 JSON 文件")
    ap.add_argument(
        "--log-dir",
        metavar="DIR",
        help="写盘日志目录，默认仓库根 logs/（环境变量 IMG_P_LOG_DIR 可覆盖）",
    )
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--version", action="version", version=f"{NAME} {VERSION} ({UPDATED})")
    return ap


def print_listing(path: str, regions: list[dict]) -> None:
    print(f"== {path}" + (f"（{len(regions)} 块）" if regions else "（无文字）"))
    for i, r in enumerate(regions):
        x, y, w, h = r["rect"]
        print(f"  [{i}] ({x},{y}) {w}x{h}  score={r['score']:.2f}  {r['text']}")


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except CoreError as e:  # 核心层的可预期失败 → 一句话报错退出
        sys.exit(str(e))


def announce_version() -> None:
    """每次运行先报版本（走 stderr，不污染 --list / --report 的正常输出）。"""
    print(f"{NAME} {VERSION} ({UPDATED})", file=sys.stderr)


def warn_outside_venv(quiet: bool = False) -> None:
    """在仓库里用系统解释器裸跑时提醒一句（项目约定所有入口都走 .venv）。"""
    if quiet:
        return
    hint = bootstrap.venv_hint()
    if hint:
        print(hint, file=sys.stderr)


def _ratio(name: str, value: float) -> float:
    """0~1 之间的比例参数：越界当场退出，别带进匹配里。"""
    if not 0.0 <= value <= 1.0:
        sys.exit(f"{name} 应在 0-1 之间: {value}")
    return value


def _plan_inputs(args: argparse.Namespace) -> tuple[list[str], bool]:
    """收集输入并做互斥校验，返回 (图片列表, 是否批量)。"""
    files = collect_images(args.input)
    if not files:
        sys.exit(f"{args.input} 里没有找到图片")
    batch = os.path.isdir(args.input) or len(files) > 1
    if batch and args.area:
        sys.exit("--area 只能用于单图")
    if batch and args.output and args.output.lower().endswith(IMG_EXTS):
        sys.exit("批量模式下 -o 要写目录而不是文件名（用 --out-dir 更清楚）")
    return files, batch


def _build_options(args: argparse.Namespace) -> Options:
    """命令行的值 → Options；能当场校验的都当场退出，别等跑到图里才发现。"""
    if args.color:
        parse_color(args.color)
    if args.font and not os.path.exists(args.font):
        sys.exit(f"字体文件不存在: {args.font}")
    if args.quality is not None and not 1 <= args.quality <= 100:
        sys.exit(f"--quality 应在 1-100 之间: {args.quality}")
    if args.workers is not None:
        batch_flow.workers_value(args.workers)  # 先校验，别等跑到第二遍才发现写错
    opts = Options(
        font=args.font,
        size=args.size,
        color=args.color,
        align=args.align,
        fit_width=args.fit_width,
        tracking=args.tracking,
        max_fonts=args.max_fonts,
        quality=args.quality,
        debug=None if args.dry_run else args.debug,  # 预演不写文件
        quiet=args.quiet,
        log_dir=args.log_dir or log_dir(),
        channel="cli",
        dry_run=args.dry_run,  # 核心层据此跳过擦除/绘制
    )
    apply_to_options(opts)  # 配置文件只填没在命令行指定的项
    if args.min_score is not None:
        opts.min_score = _ratio("--min-score", args.min_score)
    if args.fuzzy is not None:
        opts.fuzzy_min = _ratio("--fuzzy", args.fuzzy)
    if opts.color:
        try:
            parse_color(opts.color)
        except CoreError as e:
            sys.exit(str(e))
    if opts.font and not os.path.exists(opts.font):
        print(f"! 配置文件里的字体不存在，已改为自动匹配: {opts.font}", file=sys.stderr)
        opts.font = None
    if args.dry_run and args.debug:
        print("! --dry-run 不写文件，--debug 已忽略", file=sys.stderr)
    return opts


def _print_result(
    n: int, total: int, result: dict[str, Any], *, batch: bool, quiet: bool, dry_run: bool
) -> None:
    """一张图的结果：批量给逐图一行 + 逐处明细，单图给"存到哪" + 逐处明细。"""
    report = result["report"]
    dst = result["dst"]
    if batch:
        if quiet:
            return
        print(f"[{n}/{total}] {os.path.basename(result['path'])} → {dst}  ({len(report)} 处)")
        for r in report:
            print(
                f"    {str(r['old'])[:22]!r} -> {r['new']!r} | {r['font']} "
                f"{r['size']}px {r['align']} iou={r['iou']}"
            )
        return
    print(f"{'预演' if dry_run else '已保存'}: {dst}")
    if quiet:
        return
    for r in report:
        print(
            f"  [{r['mode']}] {str(r['old'])[:24]!r} -> {r['new']!r} | "
            f"{r['font']} {r['size']}px 字距{r['tracking']:+.2f} "
            f"{r['align']} iou={r['iou']}"
        )


def _run(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    announce_version()

    files, batch = _plan_inputs(args)
    opts = _build_options(args)

    # ---- --list：只看不做
    if args.list:
        for path in files:
            try:
                rgb, _alpha = load_image(path)
            except OSError as e:
                print(f"! 跳过 {path}: {e}", file=sys.stderr)
                continue
            print_listing(path, ocr_regions(rgb))
        return 0

    warn_outside_venv(args.quiet)

    mapping = load_mapping(args.map_file, args.map)
    if not mapping and not args.area:
        sys.exit("没有替换任务：用 --map / --map-file，或 --list 先看看图里有什么字")

    # ---- 第一遍：规划任务（顺便收集字体匹配要用的原文）；每张图互不依赖，可并发
    workers = batch_flow.resolve_workers(args.workers, dry_run=args.dry_run, batch=batch)
    scans, texts, cached = batch_flow.scan_images(files, mapping, args.area, opts, workers)

    if not scans:
        sys.exit("所有图片都读取失败")
    todo = [s for s in scans if s["jobs"]]
    if not todo:
        sys.exit("所有图片都没有匹配到要替换的文字")

    pool = build_font_pool(texts, args.font, args.max_fonts)
    if not args.quiet:
        print(f"候选字体 {len(pool)} 款 / {len(files)} 张图 / {len(todo)} 张有待替换文字")
        if batch and workers == 1:
            # 默认单线程是实测结论，所以要提示"想要更多并发该怎么开"，否则这个开关没人知道
            print(
                f"并发 1（默认档：逐图并发实测更慢）；要更多：-j auto 或设 {batch_flow.WORKERS_ENV}=N"
            )

    # ---- 第二遍：逐图替换（预演不写文件，也不碰像素）
    ctx = batch_flow.ReplaceContext(
        opts=opts,
        pool=pool,
        out_dir=args.out_dir or args.output or default_out_dir(),
        batch=batch,
        output=args.output,
        cached=cached,
    )

    ok = fail = total = 0
    summary_items: list[dict] = []
    for n, result in enumerate(batch_flow.replace_images(todo, ctx, workers), 1):
        if not result["ok"]:
            print(f"! {result['error']}", file=sys.stderr)
            fail += 1
            continue
        path = result["path"]
        report = result["report"]
        dst = result["dst"]
        summary_items.append(
            {
                "src": os.path.abspath(path),
                "dst": os.path.abspath(dst),
                "saved": not args.dry_run,
                "replaced": len(report),
                "operations": [
                    {k: r[k] for k in ("old", "new", "mode", "font", "size", "align", "iou")}
                    for r in report
                ],
            }
        )
        ok += 1
        total += len(report)
        _print_result(n, len(todo), result, batch=batch, quiet=args.quiet, dry_run=args.dry_run)

    if args.report:
        write_report(
            args.report,
            files,
            todo,
            summary_items,
            ok,
            fail,
            dry_run=args.dry_run,
            out_dir=ctx.out_dir,
        )
    if batch:
        skipped = len(files) - len(todo)
        print(f"批量完成：成功 {ok} 张 / 失败 {fail} 张 / 无匹配 {skipped} 张，共 {total} 处替换")
        if ctx.out_dir and not args.dry_run:
            print(f"输出目录: {ctx.out_dir}")
    return 0 if ok else 3


def write_report(
    path: str,
    files: list[str],
    todo: list[dict],
    items: list[dict],
    ok: int,
    fail: int,
    dry_run: bool,
    out_dir: str,
) -> None:
    """把本次运行的摘要写成 JSON，便于批量后核对与归档。"""
    payload = {
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "out_dir": os.path.abspath(out_dir),
        "images": len(files),
        "processed": len(todo),
        "succeeded": ok,
        "failed": fail,
        "skipped": len(files) - len(todo),
        "replaced": sum(item["replaced"] for item in items),
        "items": items,
    }
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"! 写摘要失败 {path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
