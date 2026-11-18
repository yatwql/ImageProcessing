"""门禁流水线：worker 规划、批次并发、档位选择、收集数核对、发布预检的失败即停。

守的是本次提速改造的三条不变式：
1. worker 数有确定规则（显式 > 环境变量 > 串行开关 > 核数上限 8），不随机器漂移；
2. 并发批次的结果按输入顺序返回，且 `isolated` 步骤（耗时守卫）不参与并发；
3. 门禁不会因为"某档把用例整批跳过"而假绿——各档收集数必须一致。
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.python.tools import _parallel, check_all, release


class WorkerPlan(unittest.TestCase):
    """worker 数规则：上限 8，且三种覆盖方式优先级固定。"""

    def test_big_machine_is_capped_at_eight(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in (_parallel.WORKERS_ENV, _parallel.SERIAL_ENV):
                os.environ.pop(key, None)
            with mock.patch.object(_parallel.os, "cpu_count", return_value=32):
                self.assertEqual(_parallel.worker_count(), _parallel.MAX_WORKERS)

    def test_small_machine_uses_its_cores(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in (_parallel.WORKERS_ENV, _parallel.SERIAL_ENV):
                os.environ.pop(key, None)
            with mock.patch.object(_parallel.os, "cpu_count", return_value=2):
                self.assertEqual(_parallel.worker_count(), 2)

    def test_env_override_wins_over_cores(self):
        with mock.patch.dict(os.environ, {_parallel.WORKERS_ENV: "3"}, clear=False):
            with mock.patch.object(_parallel.os, "cpu_count", return_value=16):
                self.assertEqual(_parallel.worker_count(), 3)

    def test_serial_env_forces_single_process(self):
        with mock.patch.dict(os.environ, {_parallel.SERIAL_ENV: "1"}, clear=False):
            os.environ.pop(_parallel.WORKERS_ENV, None)
            self.assertEqual(_parallel.worker_count(), 0)

    def test_explicit_argument_beats_everything(self):
        with mock.patch.dict(
            os.environ, {_parallel.SERIAL_ENV: "1"}, clear=False
        ), mock.patch.object(_parallel.os, "cpu_count", return_value=16):
            self.assertEqual(_parallel.worker_count(5), 5)

    def test_single_process_adds_no_xdist_flags(self):
        self.assertEqual(_parallel.parallel_args(0), [])
        self.assertEqual(_parallel.parallel_args(1), [])
        self.assertEqual(_parallel.parallel_args(8), ["-n", "8"])


class BatchExecution(unittest.TestCase):
    """并发批次：顺序稳定、失败被捕获、isolated 步骤不并进去。"""

    def run_batch(self, steps: list[_parallel.Step]) -> list[_parallel.Result]:
        with tempfile.TemporaryDirectory() as tmp:
            return _parallel.run_batch(steps, Path(tmp))

    def test_results_keep_input_order(self):
        # 让第一个最慢、最后一个最快：并发下完成顺序与输入顺序必然不同
        steps = [
            _parallel.Step(
                f"s{i}",
                [sys.executable, "-c", f"import time; time.sleep({0.3 - i * 0.1})"],
                {},
            )
            for i in range(3)
        ]
        self.assertEqual([r.name for r in self.run_batch(steps)], ["s0", "s1", "s2"])

    def test_failure_is_reported_not_raised(self):
        steps = [_parallel.Step("bad", [sys.executable, "-c", "raise SystemExit(3)"], {})]
        result = self.run_batch(steps)[0]
        self.assertFalse(result.ok)
        self.assertEqual(result.code, 3)

    def test_missing_command_fails_instead_of_passing(self):
        steps = [_parallel.Step("gone", [sys.executable + "-not-here"], {})]
        self.assertFalse(self.run_batch(steps)[0].ok)

    def test_isolated_step_still_runs(self):
        steps = [_parallel.Step("perf", [sys.executable, "-c", "pass"], {}, isolated=True)]
        self.assertTrue(self.run_batch(steps)[0].ok)

    def test_tail_keeps_only_the_last_lines(self):
        output = "\n".join(f"line{i}" for i in range(100))
        kept = _parallel.tail(output, lines=3).splitlines()
        self.assertEqual(kept, ["line97", "line98", "line99"])


class VariantPlan(unittest.TestCase):
    """档位选择与收集数核对：全量档不跑 stress（它由第 4 步单独跑）。"""

    def test_quick_runs_only_the_default_variant(self):
        picked = check_all.select_variants(check_all.Options(quick=True))
        self.assertEqual([v.key for v in picked], ["plain"])

    def test_quick_with_matrix_flags_adds_those_variants(self):
        opts = check_all.Options(quick=True, matrix=True, no_font=True, font_matrix=True)
        self.assertEqual(
            [v.key for v in check_all.select_variants(opts)], ["plain", "ci", "nofont", "font"]
        )

    def test_full_run_covers_every_environment_variant(self):
        picked = check_all.select_variants(check_all.Options())
        self.assertEqual([v.key for v in picked], ["plain", "ci", "nofont", "font"])

    def test_equal_module_sets_pass(self):
        pairs = [
            (check_all.VARIANTS[0], {"src.test.core.test_x", "src.test.tui.test_y"}),
            (check_all.VARIANTS[1], {"src.test.core.test_x", "src.test.tui.test_y"}),
        ]
        self.assertEqual(check_all.check_collected(pairs), [])

    def test_variant_with_a_missing_module_is_rejected(self):
        # 某档因环境变量把整个文件 deselect：退出码仍是 0，这里必须红
        pairs = [
            (check_all.VARIANTS[0], {"src.test.core.test_x", "src.test.tui.test_y"}),
            (check_all.VARIANTS[2], {"src.test.core.test_x"}),
        ]
        problems = check_all.check_collected(pairs)
        self.assertTrue(problems)
        self.assertIn("少了 1 个用例模块", problems[0])

    def test_variant_with_extra_module_is_rejected(self):
        pairs = [
            (check_all.VARIANTS[0], {"src.test.core.test_x"}),
            (check_all.VARIANTS[3], {"src.test.core.test_x", "src.test.core.test_z"}),
        ]
        self.assertTrue(any("多了" in p for p in check_all.check_collected(pairs)))

    def test_variant_collecting_nothing_is_rejected(self):
        pairs = [(check_all.VARIANTS[0], {"src.test.core.test_x"}), (check_all.VARIANTS[3], set())]
        problems = check_all.check_collected(pairs)
        self.assertTrue(any("没有收集到任何用例" in p for p in problems))

    def test_missing_reports_are_rejected(self):
        self.assertTrue(check_all.check_collected([]))


class GateArgs(unittest.TestCase):
    """门禁自己的开关被摘掉，其余原样透传给 pytest。"""

    def test_pytest_arguments_are_passed_through(self):
        opts = check_all.parse_args(["--quick", "-k", "mapping", "-x"])
        self.assertTrue(opts.quick)
        self.assertEqual(opts.extra, ["-k", "mapping", "-x"])

    def test_jobs_and_workers_accept_both_forms(self):
        self.assertEqual(check_all.parse_args(["--jobs", "3"]).jobs, 3)
        self.assertEqual(check_all.parse_args(["--jobs=3"]).jobs, 3)
        self.assertEqual(check_all.parse_args(["--gate-workers=2"]).workers, 2)

    def test_serial_flag_sets_the_environment_switch(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(_parallel.SERIAL_ENV, None)
            check_all.parse_args(["--serial"])
            self.assertEqual(os.environ.get(_parallel.SERIAL_ENV), "1")

    def test_non_numeric_jobs_is_an_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                check_all.parse_args(["--jobs=abc"])


class ReleaseFailFast(unittest.TestCase):
    """发布预检：结构性预检红了就别跑门禁（白跑几分钟）。"""

    def test_dirty_workspace_stops_before_running_the_gate(self):
        dirty = subprocess.CompletedProcess(args=[], returncode=0, stdout=" M src/x.py\n", stderr="")
        with mock.patch.object(release, "sh", return_value=dirty):  # platform-safe：release.sh 是 Python 函数，不是 shell
            with mock.patch.object(release.subprocess, "run") as gate:
                code = self._capture(release.cmd_check)
        self.assertEqual(code, 1)
        gate.assert_not_called()

    def test_matching_stamp_skips_the_gate(self):
        clean = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(release, "sh", return_value=clean), mock.patch.object(  # platform-safe：release.sh 是 Python 函数，不是 shell
            release, "read_version", return_value=("0.3-dev", "2026-01-01")
        ), mock.patch.object(release.gate_stamp, "stamp_matches", return_value=True), mock.patch.object(
            release.subprocess, "run"
        ) as gate:
            code = self._capture(release.cmd_check)
        self.assertEqual(code, 0)
        gate.assert_not_called()

    def test_stale_stamp_runs_the_full_gate(self):
        clean = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        done = subprocess.CompletedProcess(args=[], returncode=0)
        with mock.patch.object(release, "sh", return_value=clean), mock.patch.object(  # platform-safe：release.sh 是 Python 函数，不是 shell
            release, "read_version", return_value=("0.3-dev", "2026-01-01")
        ), mock.patch.object(
            release.gate_stamp, "stamp_matches", return_value=False
        ), mock.patch.object(release.subprocess, "run", return_value=done) as gate:
            code = self._capture(release.cmd_check)
        self.assertEqual(code, 0)
        # 跑的是全量门禁（含覆盖率与矩阵），不是以前那档 --quick + 两档矩阵
        cmd = gate.call_args.args[0]
        self.assertIn("src.python.tools.check_all", cmd)
        self.assertNotIn("--quick", cmd)

    @staticmethod
    def _capture(func: object) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return func()  # type: ignore[operator]


if __name__ == "__main__":
    unittest.main()
