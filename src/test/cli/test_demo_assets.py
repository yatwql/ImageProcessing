"""用仓库自带示例图（data/demo）跑真实图片流程：读取、单图替换、批量、日志。

OCR 仍用桩（区域和坐标取自真实图片），但像素、尺寸、文件名、写盘都是真的，
避免只靠合成图而漏掉真实素材上的问题。

运行：.venv/bin/python -m pytest src/test -q
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

from src.python import config
from src.python.cli.main import main
from src.python.core.image import load_image
from src.python.tui.app import App
from src.test._support import patch_ocr

DEMO_DIR = os.path.join(config.ROOT, "data", "demo")
REPORT = os.path.join(DEMO_DIR, "示例-报告.png")
NOTICE1 = os.path.join(DEMO_DIR, "示例-通知1.png")
NOTICE2 = os.path.join(DEMO_DIR, "示例-通知2.png")
NOTICE3 = os.path.join(DEMO_DIR, "示例-通知3.png")
DEMO_FILES = (REPORT, NOTICE1, NOTICE2, NOTICE3)

# 真实图片上的 OCR 结果（坐标取自原图，文字取自图片内容）
BODY = ("本页内容保持不变，排版一致。", (64, 150, 341, 24))
BOXES_BY_NAME = {
    "示例-报告.png": [
        ("年度销售报告2023", (64, 58, 362, 39)),
        BODY,
        ("负责人：张三", (64, 214, 152, 23)),
        ("日期：2023-12-31", (65, 270, 207, 24)),
    ],
    "示例-通知1.png": [
        ("年度报告", (249, 26, 140, 33)),
        ("2023", (382, 30, 88, 26)),
        ("本页内容保持不变，排版一致。", (61, 138, 317, 23)),
        ("电话：400-800-1234", (63, 188, 217, 22)),
    ],
    "示例-通知2.png": [
        ("季度总结", (250, 26, 139, 32)),
        ("2023", (377, 29, 93, 27)),
        ("本页内容保持不变，排版一致。", (61, 138, 317, 23)),
        ("电话：400-800-5678", (63, 188, 219, 22)),
    ],
    "示例-通知3.png": [
        ("项目复盘2023", (247, 25, 226, 35)),
        ("本页内容保持不变，排版一致。", (61, 138, 317, 23)),
        ("电话：400-800-9999", (63, 188, 218, 22)),
    ],
}


def _digest(rgb: np.ndarray) -> str:
    return hashlib.sha256(rgb.tobytes()).hexdigest()


DIGEST_TO_NAME: dict[str, str] = {}
if all(os.path.exists(p) for p in DEMO_FILES):
    for _path in DEMO_FILES:
        DIGEST_TO_NAME[_digest(np.array(Image.open(_path).convert("RGB")))] = os.path.basename(_path)


def boxes_for(rgb: np.ndarray) -> list[tuple[str, tuple[int, int, int, int]]]:
    """按图片内容返回各自的 OCR 结果，避免不同示例图共用一套坐标。"""
    return BOXES_BY_NAME[DIGEST_TO_NAME[_digest(rgb)]]


def demo_available() -> bool:
    return all(os.path.exists(p) for p in DEMO_FILES)


@unittest.skipUnless(demo_available(), "缺少 data/demo 示例图")
class DemoAssets(unittest.TestCase):
    def test_demo_images_are_readable_rgb(self):
        for path in DEMO_FILES:
            with self.subTest(os.path.basename(path)):
                with Image.open(path) as im:
                    self.assertEqual(im.size[0], 720)
                    self.assertIn(im.mode, ("RGB", "RGBA"))
                _rgb, alpha = load_image(path)
                self.assertIsNone(alpha)             # 示例图不带透明

    def test_tui_lists_all_demo_images(self):
        app = App([DEMO_DIR])
        self.assertEqual([img.name for img in app.images], sorted(
            os.path.basename(p) for p in DEMO_FILES))
        kinds = [kind for kind, _path in app.rows]
        self.assertEqual(kinds.count("img"), len(DEMO_FILES))


@unittest.skipUnless(demo_available(), "缺少 data/demo 示例图")
class DemoCliFlows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()      # noqa: SIM115
        self.addCleanup(self.tmp.cleanup)
        self.log_dir = os.path.join(self.tmp.name, "logs")

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with patch_ocr(boxes_for), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, {"IMG_P_LOG_DIR": self.log_dir}):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def logs(self) -> list[dict]:
        if not os.path.isdir(self.log_dir):
            return []
        entries: list[dict] = []
        for name in sorted(os.listdir(self.log_dir)):
            with open(os.path.join(self.log_dir, name), encoding="utf-8") as f:
                entries += [json.loads(line) for line in f if line.strip()]
        return entries

    def test_demo_report_replaces_only_the_title(self):
        out = os.path.join(self.tmp.name, "out", "report.png")
        code, _text, _err = self.run_cli(REPORT, "-o", out, "--quiet",
                                         "--map", "年度销售报告2023=年度财务总结2024")
        self.assertEqual(code, 0)
        before = np.array(Image.open(REPORT))
        after = np.array(Image.open(out))
        self.assertEqual(before.shape, after.shape)
        self.assertFalse(np.array_equal(before[40:110], after[40:110]))   # 标题变了
        self.assertTrue(np.array_equal(before[130:], after[130:]))        # 其余像素没动
        entry = self.logs()[0]
        self.assertEqual(entry["src_file"], "示例-报告.png")
        self.assertEqual(entry["operations"][0]["new"], "年度财务总结2024")

    def test_demo_notice_whole_block_replacement_keeps_rest(self):
        out = os.path.join(self.tmp.name, "out", "notice.png")
        code, _text, _err = self.run_cli(NOTICE1, "-o", out, "--quiet", "--map", "2023=2024")
        self.assertEqual(code, 0)
        before = np.array(Image.open(NOTICE1))
        after = np.array(Image.open(out))
        self.assertFalse(np.array_equal(before[20:65, 370:480], after[20:65, 370:480]))
        self.assertTrue(np.array_equal(before[120:], after[120:]))
        self.assertEqual(self.logs()[0]["operations"][0]["mode"], "整行")

    def test_demo_body_fragment_replacement_is_inline(self):
        out = os.path.join(self.tmp.name, "out", "body.png")
        code, _text, _err = self.run_cli(REPORT, "-o", out, "--quiet",
                                         "--map", "本页=页面")
        self.assertEqual(code, 0)
        before = np.array(Image.open(REPORT))
        after = np.array(Image.open(out))
        self.assertFalse(np.array_equal(before[145:180], after[145:180]))  # 正文变了
        self.assertTrue(np.array_equal(before[200:], after[200:]))          # 其余行没动
        self.assertEqual(self.logs()[0]["operations"][0]["mode"], "行内")

    def test_demo_batch_logs_every_image(self):
        out_dir = os.path.join(self.tmp.name, "out")
        code, text, _err = self.run_cli(DEMO_DIR, "--out-dir", out_dir, "--quiet",
                                        "--map", "2023=2024")
        self.assertEqual(code, 0)
        self.assertEqual(len(os.listdir(out_dir)), len(DEMO_FILES))
        self.assertIn("批量完成", text)
        self.assertEqual(sorted(e["src_file"] for e in self.logs()),
                         sorted(os.path.basename(p) for p in DEMO_FILES))

    def test_demo_dry_run_writes_nothing(self):
        out_dir = os.path.join(self.tmp.name, "dry")
        code, text, _err = self.run_cli(NOTICE2, "--out-dir", out_dir, "--dry-run",
                                        "--map", "季度总结=年度总结")
        self.assertEqual(code, 0)
        self.assertIn("预演", text)
        self.assertFalse(os.path.isdir(out_dir))


if __name__ == "__main__":
    unittest.main()
