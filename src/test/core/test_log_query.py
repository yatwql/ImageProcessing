"""日志查询：按日期/原图/渠道过滤，并汇总替换次数。

写盘日志是审计凭据，读回时不能因为一行坏掉就整份读不出来，
也不能把别人的记录混进「这张图换过什么」。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest

from src.python.core import audit


class LogQuery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def write(
        self, when: dt.datetime, src: str, dst: str, channel: str = "cli", replaced: int = 1
    ) -> None:
        audit.record_write(
            src=src,
            dst=dst,
            report=[{"old": "2023", "new": "2024"}] * replaced,
            log_dir=self.dir,
            channel=channel,
            when=when,
        )

    def test_reads_all_days_when_day_is_omitted(self):
        self.write(dt.datetime(2026, 11, 9, 10, 0), "a.png", "a1.png")
        self.write(dt.datetime(2026, 11, 10, 10, 0), "b.png", "b1.png")
        entries = audit.read_entries(self.dir)
        self.assertEqual(len(entries), 2)

    def test_filters_by_day(self):
        self.write(dt.datetime(2026, 11, 9, 10, 0), "a.png", "a1.png")
        self.write(dt.datetime(2026, 11, 10, 10, 0), "b.png", "b1.png")
        entries = audit.read_entries(self.dir, day=dt.date(2026, 11, 10))
        self.assertEqual([e["src_file"] for e in entries], ["b.png"])

    def test_filters_by_source_substring(self):
        self.write(dt.datetime(2026, 11, 10, 10, 0), "年度报告.png", "x.png")
        self.write(dt.datetime(2026, 11, 10, 11, 0), "随手拍.png", "y.png")
        entries = audit.read_entries(self.dir, src="报告")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["src_file"], "年度报告.png")

    def test_filters_by_channel(self):
        self.write(dt.datetime(2026, 11, 10, 10, 0), "a.png", "a1.png", channel="cli")
        self.write(dt.datetime(2026, 11, 10, 11, 0), "a.png", "a2.png", channel="tui")
        entries = audit.read_entries(self.dir, channel="tui")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["channel"], "tui")

    def test_broken_line_is_skipped_not_fatal(self):
        self.write(dt.datetime(2026, 11, 10, 10, 0), "a.png", "a1.png")
        path = audit.log_path(self.dir, dt.datetime(2026, 11, 10, 12, 0))
        with open(path, "a", encoding="utf-8") as f:
            f.write("{这不是 JSON\n")
        entries = audit.read_entries(self.dir)
        self.assertEqual(len(entries), 1)

    def test_missing_directory_returns_empty_list(self):
        empty = os.path.join(self.dir, "no-such-day")
        self.assertEqual(audit.read_entries(empty), [])

    def test_summarize_counts_writes_replacements_and_channels(self):
        self.write(dt.datetime(2026, 11, 10, 10, 0), "a.png", "a1.png", replaced=3)
        self.write(dt.datetime(2026, 11, 10, 11, 0), "a.png", "a2.png", channel="tui")
        stats = audit.summarize(audit.read_entries(self.dir))
        self.assertEqual(stats["writes"], 2)
        self.assertEqual(stats["replacements"], 4)
        self.assertEqual(stats["per_src"]["a.png"], 2)
        self.assertEqual(stats["per_channel"], {"cli": 1, "tui": 1})

    def test_entries_are_json_round_trip(self):
        self.write(dt.datetime(2026, 11, 10, 10, 0), "a.png", "a1.png")
        raw = audit.read_entries(self.dir)[0]
        text = json.dumps(raw, ensure_ascii=False)
        self.assertEqual(json.loads(text)["src_file"], "a.png")


if __name__ == "__main__":
    unittest.main()
