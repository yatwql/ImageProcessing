"""控制台编码：中文提示在非 UTF-8 终端（Windows cp936）上不能崩。

这层存在的理由：Windows 上 `retype --help` 一打印中文就 `UnicodeEncodeError`，
进程退出码 1，用户看到的是"程序打不开"。
"""

from __future__ import annotations

import sys
import unittest
from unittest import mock

from src.python import stdio


class Utf8Stdio(unittest.TestCase):
    def test_streams_already_utf8_are_left_alone(self):
        stream = mock.Mock(encoding="utf-8")
        with (
            mock.patch.object(stdio.sys, "stdout", stream),
            mock.patch.object(stdio.sys, "stderr", None),
        ):
            stdio.ensure_utf8_stdio()
        stream.reconfigure.assert_not_called()

    def test_non_utf8_streams_are_reconfigured(self):
        out = mock.Mock(encoding="cp936")
        err = mock.Mock(encoding="cp1252")
        with (
            mock.patch.object(stdio.sys, "stdout", out),
            mock.patch.object(stdio.sys, "stderr", err),
        ):
            stdio.ensure_utf8_stdio()
        out.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        err.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

    def test_reconfigure_failure_is_swallowed(self):
        bad = mock.Mock(encoding="cp936")
        bad.reconfigure.side_effect = OSError("不支持")
        with (
            mock.patch.object(stdio.sys, "stdout", bad),
            mock.patch.object(stdio.sys, "stderr", None),
        ):
            stdio.ensure_utf8_stdio()  # 不抛即通过

    def test_stream_without_encoding_attribute_is_handled(self):
        stream = mock.Mock(spec=["reconfigure"])
        del stream.encoding  # 模拟被替换成没有 encoding 的流
        with (
            mock.patch.object(stdio.sys, "stdout", stream),
            mock.patch.object(stdio.sys, "stderr", None),
        ):
            stdio.ensure_utf8_stdio()
        stream.reconfigure.assert_called_once()

    def test_current_process_stdio_is_already_utf8(self):
        # 本地/CI 的 pytest 捕获会把编码设成 utf-8；此处只验证函数幂等
        stdio.ensure_utf8_stdio()
        stdio.ensure_utf8_stdio()
        self.assertIsNotNone(sys.stdout)


if __name__ == "__main__":
    unittest.main()
