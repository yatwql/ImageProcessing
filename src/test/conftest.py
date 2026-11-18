"""pytest 全局钩子：用例不许往仓库真实产物目录（`data/output/`）写文件。

历史遗留（归档 RF-16）：早期用例不带 `--out-dir`，把产物堆在 `data/output/report-*.png`。
用例现在一律写临时目录，这里再加一道真实拦截——整个会话前后对比快照，只要多出文件就红，
并直接点出是哪些文件，避免"再图省事一次"又悄悄堆回来。

`logs/` 不在守卫范围：写盘日志测试本来就用 `--log-dir` 指到临时目录，真实 `logs/` 由用户跑
程序时产生，会话期间被外部追加也不算用例的错。
"""

from __future__ import annotations

import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(_ROOT, "data", "output")


def _snapshot(root: str) -> set[str]:
    """目录下所有文件的相对路径集合；目录不存在时返回空集。"""
    if not os.path.isdir(root):
        return set()
    found: set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            found.add(os.path.relpath(os.path.join(dirpath, name), root))
    return found


@pytest.fixture(scope="session", autouse=True)
def repo_output_stays_clean():
    """会话结束前检查：仓库 `data/output/` 没有用例新写的文件。"""
    before = _snapshot(OUTPUT_DIR)
    yield
    added = sorted(_snapshot(OUTPUT_DIR) - before)
    if added:
        pytest.fail(
            "用例往仓库真实产物目录 data/output/ 写了文件（应改用临时目录 / --out-dir）："
            + "、".join(added[:10]),
            pytrace=False,
        )
