"""工具共用的路径常量：仓库根。

工具都在 `src/python/tools/`（三层深），各自算一遍 `parents[3]` 容易搬目录时漏改，
集中在这里一处定义。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
