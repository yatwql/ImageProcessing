"""目录扫描：把"一个目录里有什么"变成左栏的行（父目录 / 子目录 / 图片）。

从 `app.py` 抽出来的纯函数层：不碰 curses，也不依赖 `App` 状态，
方便单独测"隐藏项跳过、非图片忽略、父目录入口"这类规则。
"""

from __future__ import annotations

import os

from ..core import IMG_EXTS

Row = tuple[str, str]          # ("parent" | "dir" | "img", 绝对路径)


def scan_rows(path: str) -> tuple[list[Row], list[str], str | None]:
    """扫描目录，返回 (左栏行, 图片路径列表, 错误信息)。

    顺序固定：父目录入口 → 子目录 → 图片。隐藏项（`.` 开头）一律跳过；
    子目录先列，便于在手机窄屏上先看到"能进去"的位置。
    """
    rows: list[Row] = []
    parent = os.path.dirname(path)
    if parent and parent != path:
        rows.append(("parent", parent))
    try:
        names = sorted(os.listdir(path))
    except OSError as exc:
        return [], [], f"无法读取目录 {path}: {exc}"

    for name in names:
        if name.startswith("."):
            continue
        full = os.path.join(path, name)
        if os.path.isdir(full):
            rows.append(("dir", full))
    images: list[str] = []
    for name in names:
        if name.startswith(".") or not name.lower().endswith(IMG_EXTS):
            continue
        full = os.path.join(path, name)
        if os.path.isfile(full):
            rows.append(("img", full))
            images.append(full)
    return rows, images, None


def first_image_row(rows: list[Row]) -> int:
    """第一张图片所在的行号；没有图片时回到 0（父目录/首行）。"""
    for index, (kind, _path) in enumerate(rows):
        if kind == "img":
            return index
    return 0
