"""耗时守卫的平台档：Windows runner 的 fsync 慢一个量级，只放大落盘那一步。

守的原因：windows 作业连续在「耗时守卫」上红（日志追加×300 实测 3.5s / 上限 1.0s），
而其余步骤两平台同量级。无条件放大等于把门禁调松，必须按步骤分别放。
"""

from __future__ import annotations

import unittest

from src.python.tools import check_perf


class PerfLimits(unittest.TestCase):
    def test_posix_uses_base_limits(self):
        limits, total = check_perf.limits_for(False)
        self.assertEqual(limits, check_perf.LIMITS)
        self.assertEqual(total, check_perf.TOTAL_LIMIT)

    def test_windows_scales_only_disk_step_and_total(self):
        limits, total = check_perf.limits_for(True)
        factor = check_perf.WINDOWS_SCALE["日志追加×300"]
        self.assertEqual(limits["日志追加×300"], round(check_perf.LIMITS["日志追加×300"] * factor, 2))
        for name in ("soft_iou×50", "erase(2000×1500)", "PNG 读写(2000×1500)"):
            self.assertEqual(limits[name], check_perf.LIMITS[name], f"{name} 不该被放大")
        self.assertGreater(total, check_perf.TOTAL_LIMIT)

    def test_scaled_limits_cover_measured_windows_reading(self):
        """实测 3.5s：Windows 档必须容得下，否则门禁在 runner 上必然假红。"""
        limits, _total = check_perf.limits_for(True)
        self.assertGreater(limits["日志追加×300"], 3.5)


if __name__ == "__main__":
    unittest.main()
