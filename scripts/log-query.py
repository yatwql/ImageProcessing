#!/usr/bin/env python3
"""日志查询入口（薄壳）：实现在 `src/python/cli/log_query.py`。

python scripts/log-query.py --src 报告
python scripts/log-query.py --date 20261110 --json
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.python import launch  # noqa: E402

if __name__ == "__main__":
    sys.exit(launch.main(["log-query", *sys.argv[1:]]))
