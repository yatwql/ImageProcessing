"""守护检查共用：仓库路径、阈值常量/正则与读文件。"""

from __future__ import annotations

import re
from pathlib import Path

from .._paths import ROOT

ARCHIVE = ROOT / "docs" / "archive"
ARCHIVE_FILE = re.compile(r"^archived_(plan|review-findings|changelog)\.(\d+\.\d+\.x)\.md$")
ARCHIVE_HEADING = "## 归档"
ARCHIVE_LEDGERS = ("plan.md", "review-findings.md", "changelog.md")
ARCHIVE_META = ("归档时间：", "原始文件：", "涵盖版本：", "归档内容：")
ARCHIVE_SERIES_DIR = re.compile(r"^v\d+\.\d+\.x$")
DOCS = ROOT / "docs" / "managements"
LAUNCHER_MAX_LINES = 40
LEGACY_ID = re.compile(r"\b(?:TD|P|F|N)-\d+\b")
MAX_FILE_LINES = 1000
PIN_LINE = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)(?:\s*;\s*.+)?$")
ROW_ID = re.compile(r"^\|\s*([A-Z]+-\d+)\s*\|")
SRC = ROOT / "src"
TREE_FENCE = "```text"
TREE_LINE = re.compile(r"^((?:│   |    )*)(?:├── |└── )(.+)$")
VERSION_DOCS = [
    "README.md",
    "CLAUDE.md",
    "docs/managements/requirements.md",
    "docs/managements/technical.md",
    "docs/managements/plan.md",
    "docs/managements/changelog.md",
    "docs/managements/review-findings.md",
    "docs/managements/testplan.md",
    "docs/managements/test-coverage.md",
    "docs/manuals/how-to-use.md",
]
VERSION_LINE = re.compile(r"^>\s*版本：v(\S+)\s*$", re.MULTILINE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
