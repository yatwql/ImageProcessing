"""命令行渠道：单图 / 目录批量。所有替换逻辑都在 src.core 里，这里只负责参数与流程。"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import sys

from .. import __version__
from ..config import apply_to_options, default_out_dir, log_dir
from ..core import (
    CoreError,
    Options,
    build_font_pool,
    collect_images,
    load_image,
    load_meta,
    make_jobs,
    ocr_regions,
    parse_color,
    record_write,
    replace_image,
    reserve_path,
    same_file,
    save_image,
    unique_path,
)
from ..core.image import IMG_EXTS

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
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=USAGE,
    )
    ap.add_argument("input", help="输入图片，或图片目录（目录=批量）")
    ap.add_argument("-o", "--output", help="单图：输出文件；批量：输出目录")
    ap.add_argument("--out-dir", help="批量输出目录，默认 data/output")
    ap.add_argument("--map", action="append", default=[], metavar="OLD=NEW", help="替换对，可重复")
    ap.add_argument("--map-file", help='JSON 文件：{"旧文字": "新文字"}')
    ap.add_argument("--area", action="append", default=[], metavar="X,Y,W,H=NEW",
                    help="手工指定区域替换（不依赖 OCR，仅单图）")
    ap.add_argument("--list", action="store_true", help="只列出 OCR 文字块后退出（批量=逐图列出）")
    ap.add_argument("--dry-run", action="store_true", help="只报告会替换什么，不写文件")
    ap.add_argument("--font", help="强制指定字体文件")
    ap.add_argument("--size", type=int, help="强制字号（默认自动匹配）")
    ap.add_argument("--color", help="强制字色，如 #FF0000 或 255,0,0")
    ap.add_argument("--align", choices=["auto", "left", "center", "right"], default="auto",
                    help="对齐基准；auto=居中的标题按居中，其余按左对齐")
    ap.add_argument("--fit-width", action="store_true", help="调字距让新文字宽度贴合原文字")
    ap.add_argument("--tracking", type=float, help="强制额外字距(px)，可负")
    ap.add_argument("--max-fonts", type=int, default=160, help="候选字体上限（默认 160）")
    ap.add_argument("--quality", type=int, help="JPEG/WEBP 输出质量 1-100（默认 95）")
    ap.add_argument("--debug", metavar="DIR", help="输出 mask 等中间图")
    ap.add_argument("--report", metavar="FILE", help="把本次替换摘要写成 JSON 文件")
    ap.add_argument("--log-dir", metavar="DIR",
                    help="写盘日志目录，默认仓库根 logs/（环境变量 IMG_P_LOG_DIR 可覆盖）")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--version", action="version", version=f"text_replace {__version__}")
    return ap


def print_listing(path: str, regions: list[dict]) -> None:
    print(f"== {path}" + (f"（{len(regions)} 块）" if regions else "（无文字）"))
    for i, r in enumerate(regions):
        x, y, w, h = r["rect"]
        print(f"  [{i}] ({x},{y}) {w}x{h}  score={r['score']:.2f}  {r['text']}")


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except CoreError as e:                 # 核心层的可预期失败 → 一句话报错退出
        sys.exit(str(e))


def _run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    files = collect_images(args.input)
    if not files:
        sys.exit(f"{args.input} 里没有找到图片")
    batch = os.path.isdir(args.input) or len(files) > 1
    if batch and args.area:
        sys.exit("--area 只能用于单图")
    if batch and args.output and args.output.lower().endswith(IMG_EXTS):
        sys.exit("批量模式下 -o 要写目录而不是文件名（用 --out-dir 更清楚）")

    if args.color:                      # 先校验，别等跑到图里才发现
        parse_color(args.color)
    if args.font and not os.path.exists(args.font):
        sys.exit(f"字体文件不存在: {args.font}")
    if args.quality is not None and not 1 <= args.quality <= 100:
        sys.exit(f"--quality 应在 1-100 之间: {args.quality}")
    opts = Options(font=args.font, size=args.size, color=args.color, align=args.align,
                   fit_width=args.fit_width, tracking=args.tracking,
                   max_fonts=args.max_fonts, quality=args.quality,
                   debug=None if args.dry_run else args.debug,   # 预演不写文件
                   quiet=args.quiet,
                   log_dir=args.log_dir or log_dir(), channel="cli")
    apply_to_options(opts)                 # 配置文件只填没在命令行指定的项
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

    mapping = load_mapping(args.map_file, args.map)
    if not mapping and not args.area:
        sys.exit("没有替换任务：用 --map / --map-file，或 --list 先看看图里有什么字")

    # ---- 第一遍：规划任务（顺便收集字体匹配要用的原文）
    scans = []
    texts: list[str] = []
    for path in files:
        try:
            rgb, _alpha = load_image(path)
        except OSError as e:
            print(f"! 跳过 {path}: {e}", file=sys.stderr)
            continue
        jobs = make_jobs(rgb, mapping, args.area)
        texts += [j.src or j.new for j in jobs]
        scans.append({"path": path, "jobs": jobs})

    if not scans:
        sys.exit("所有图片都读取失败")
    todo = [s for s in scans if s["jobs"]]
    if not todo:
        sys.exit("所有图片都没有匹配到要替换的文字")

    pool = build_font_pool(texts, args.font, args.max_fonts)
    if not args.quiet:
        print(f"候选字体 {len(pool)} 款 / {len(files)} 张图 / {len(todo)} 张有待替换文字")

    # ---- 第二遍：逐图替换
    out_dir = args.out_dir or args.output or default_out_dir()
    used_names: set[str] = set()

    ok = fail = total = 0
    summary_items: list[dict] = []
    for n, scan in enumerate(todo, 1):
        path = scan["path"]
        try:
            rgb, alpha = load_image(path)
        except OSError as e:
            print(f"! 跳过 {path}: {e}", file=sys.stderr)
            fail += 1
            continue
        meta = load_meta(path)
        tag = f"{os.path.splitext(os.path.basename(path))[0]}_"
        out, new_alpha, report = replace_image(rgb, alpha, scan["jobs"], opts, pool,
                                               tag=tag, source=path)
        if not report:
            print(f"! {path} 没有成功的替换", file=sys.stderr)
            fail += 1
            continue
        if args.output and not batch:
            dst = args.output
        else:
            name = os.path.splitext(os.path.basename(path))[0] + ".png"
            dst = os.path.join(out_dir, name)
        if same_file(dst, path):
            print(f"! {dst} 就是原图，拒绝覆盖（换 --out-dir 或 -o）", file=sys.stderr)
            fail += 1
            continue
        if not (args.output and not batch):
            if args.dry_run:                       # 预演不建文件，只按内存避重名
                dst = unique_path(dst)
                while os.path.basename(dst) in used_names:
                    stem, ext = os.path.splitext(dst)
                    dst = f"{stem}-1{ext}"
            else:
                try:
                    dst = reserve_path(dst)        # 原子占名，并发也不撞
                except CoreError as e:
                    print(f"! {e}", file=sys.stderr)
                    fail += 1
                    continue
            used_names.add(os.path.basename(dst))
        shown = dst

        if same_file(dst, path):
            print(f"! {dst} 就是原图，拒绝覆盖（换 --out-dir 或 -o）", file=sys.stderr)
            fail += 1
            continue

        if not args.dry_run:
            try:
                save_image(out, new_alpha, dst, quality=opts.quality, meta=meta)
            except (OSError, CoreError) as e:
                if dst != (args.output if not batch else None):
                    with contextlib.suppress(OSError):
                        os.remove(dst)             # 清掉占位空文件
                print(f"! 保存失败 {dst}: {e}", file=sys.stderr)
                fail += 1
                continue
            try:                             # 真的写了盘才记日志（预演不记）
                record_write(path, dst, report, log_dir=opts.log_dir or log_dir(),
                             channel=opts.channel, options=opts)
            except CoreError as e:
                print(f"! 已保存但{e}（检查日志目录权限）", file=sys.stderr)

        summary_items.append({
            "src": os.path.abspath(path), "dst": os.path.abspath(dst),
            "saved": not args.dry_run, "replaced": len(report),
            "operations": [{k: r[k] for k in ("old", "new", "mode", "font", "size",
                                              "align", "iou")} for r in report],
        })
        ok += 1
        total += len(report)
        if batch:
            if not args.quiet:
                print(f"[{n}/{len(todo)}] {os.path.basename(path)} → {shown}  ({len(report)} 处)")
                for r in report:
                    print(f"    {str(r['old'])[:22]!r} -> {r['new']!r} | {r['font']} "
                          f"{r['size']}px {r['align']} iou={r['iou']}")
        else:
            print(f"{'预演' if args.dry_run else '已保存'}: {shown}")
            if not args.quiet:
                for r in report:
                    print(f"  [{r['mode']}] {str(r['old'])[:24]!r} -> {r['new']!r} | "
                          f"{r['font']} {r['size']}px 字距{r['tracking']:+.2f} "
                          f"{r['align']} iou={r['iou']}")

    if args.report:
        write_report(args.report, files, todo, summary_items, ok, fail,
                     dry_run=args.dry_run, out_dir=out_dir)
    if batch:
        skipped = len(files) - len(todo)
        print(f"批量完成：成功 {ok} 张 / 失败 {fail} 张 / 无匹配 {skipped} 张，共 {total} 处替换")
        if out_dir and not args.dry_run:
            print(f"输出目录: {out_dir}")
    return 0 if ok else 3


def write_report(path: str, files: list[str], todo: list[dict], items: list[dict],
                 ok: int, fail: int, *, dry_run: bool, out_dir: str) -> None:
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
