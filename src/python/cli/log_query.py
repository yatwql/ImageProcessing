"""日志查询渠道：按原图名 / 日期 / 渠道过滤写盘记录并汇总。

    python -m src.python.cli.log_query                     # 最近日志的汇总
    python -m src.python.cli.log_query --date 20261110     # 只看某一天
    python -m src.python.cli.log_query --src 报告           # 只看这个原图的记录
    python -m src.python.cli.log_query --json              # 机器可读

查询逻辑在 `core.audit.read_entries` / `summarize`，这里只做参数与排版。
`scripts/log-query.py` 只是薄壳入口（与 cli.sh / tui.sh 同样的定位）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from ..config import log_dir
from ..core import CoreError, read_entries, summarize

  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="查询写盘日志")
    ap.add_argument("--log-dir", default=None, help="日志目录（默认 IMG_P_LOG_DIR 或 logs/）")
    ap.add_argument("--date", default=None, help="只看某一天，格式 YYYYMMDD")
    ap.add_argument("--src", default=None, help="原图文件名/路径的子串")
    ap.add_argument("--channel", default=None, choices=("cli", "tui"), help="只看某个渠道")
    ap.add_argument("--limit", type=int, default=20, help="明细最多显示多少条（默认 20）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（含明细与汇总）")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    day = None
    if args.date:
        try:
            day = dt.datetime.strptime(args.date, "%Y%m%d").date()
        except ValueError:
            print(f"--date 需要 YYYYMMDD，收到 {args.date!r}", file=sys.stderr)
            return 2
    directory = args.log_dir or log_dir()
    try:
        entries = read_entries(directory, day=day, src=args.src, channel=args.channel)
    except CoreError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    stats = summarize(entries)
    if args.json:
        print(json.dumps({"reports": entries, "summary": stats}, ensure_ascii=False, indent=2))
        return 0
    if not entries:
        print(f"{directory}：没有匹配的记录")
        return 0
    print(f"目录 {directory}")
    print(
        f"写盘 {stats['writes']} 次，替换操作 {stats['replacements']} 处"
        f"（渠道 {stats['per_channel']}）"
    )
    for name, count in list(stats["per_src"].items())[:10]:
        print(f"  {name}: {count} 次")
    print("最近记录：")
    for entry in entries[-max(1, args.limit) :]:
        ops = entry.get("operations") or []
        pairs = "；".join(f"{o.get('old', '')}→{o.get('new', '')}" for o in ops[:3])
        print(
            f"  {entry.get('time', '')} [{entry.get('channel', '')}] "
            f"{entry.get('src_file', '')} → {entry.get('dst_file', '')} "
            f"（{len(ops)} 处{('：' + pairs) if pairs else ''}）"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
