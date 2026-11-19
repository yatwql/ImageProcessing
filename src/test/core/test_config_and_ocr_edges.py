"""配置文件与 OCR 封装的边界：未覆盖项、缺依赖、空结果。"""

from __future__ import annotations

import contextlib
import io
import os
import unittest
from unittest import mock

import numpy as np

from src.python import config
from src.python.core import ocr, options
from src.python.core.errors import CoreError


class ConfigGaps(unittest.TestCase):
    def test_plain_keys_are_applied_via_setattr(self):
        opts = options.Options()
        opts.size = None
        opts.tracking = None
        with mock.patch.object(
            config, "option_defaults", return_value={"size": 30, "tracking": 1.5}
        ):
            config.apply_to_options(opts)
        self.assertEqual(opts.size, 30)
        self.assertAlmostEqual(opts.tracking or 0, 1.5, places=3)


class OcrGaps(unittest.TestCase):
    def test_empty_crop_returns_none(self):
        rgb = np.full((20, 20, 3), 255, np.uint8)
        self.assertIsNone(ocr.ocr_crop(rgb, (5, 5, 0, 0)))


class OptionGaps(unittest.TestCase):
    def test_rgb_component_out_of_range_is_rejected(self):
        with self.assertRaises(CoreError):
            options.parse_color("300,0,0")


class ConfigFitWidth(unittest.TestCase):
    def test_fit_width_default_is_applied_when_unset(self):
        opts = options.Options()
        opts.fit_width = False
        with mock.patch.object(config, "option_defaults", return_value={"fit_width": True}):
            config.apply_to_options(opts)
        self.assertTrue(opts.fit_width)


class WarnOutput(unittest.TestCase):
    def test_warn_prints_when_no_sink(self):
        opts = options.Options()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            options.warn(opts, "字体不可靠")
        self.assertIn("字体不可靠", err.getvalue())


class OcrEmptyResult(unittest.TestCase):
    def test_empty_engine_result_returns_none(self):
        rgb = np.zeros((10, 10, 3), np.uint8)
        fake = mock.Mock(return_value=([], None))
        with mock.patch.object(ocr, "_engine", return_value=fake):
            self.assertIsNone(ocr.ocr_crop(rgb, (0, 0, 10, 10)))


class ConfigAlign(unittest.TestCase):
    def test_align_default_applied_when_auto(self):
        # Options() 的默认 align 就是 "auto"，正好命中"还没显式设置过"的分支
        opts = options.Options()
        with mock.patch.object(config, "option_defaults", return_value={"align": "left"}):
            config.apply_to_options(opts)
        self.assertEqual(opts.align, "left")


class OcrImportFailure(unittest.TestCase):
    def test_missing_ocr_package_raises_core_error(self):
        import builtins
        import threading

        saved = threads = threading.local()
        del saved
        original_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name.startswith("rapidocr"):
                raise ImportError("no rapidocr")
            return original_import(name, *args, **kwargs)

        with (
            mock.patch.object(ocr._LOCAL, "engine", None, create=True),
            mock.patch.object(builtins, "__import__", side_effect=guarded),
            self.assertRaises(CoreError),
        ):
            ocr._engine()
        del threads


class VerboseLog(unittest.TestCase):
    def test_verbose_env_enables_logging(self):
        err = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"TEXT_REPLACE_VERBOSE": "1"}),
            contextlib.redirect_stderr(err),
        ):
            options._log("很啰嗦")
        self.assertIn("很啰嗦", err.getvalue())
