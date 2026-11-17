"""图片读取 / 保存 / 目录扫描。"""

from __future__ import annotations

import os
from collections.abc import Mapping

import numpy as np
from PIL import Image

from .errors import CoreError

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")

# 扩展名 → (PIL 格式名, 是否不支持透明)
FMT_BY_EXT = {
    ".png": ("PNG", False),
    ".jpg": ("JPEG", True),
    ".jpeg": ("JPEG", True),
    ".bmp": ("BMP", True),
    ".webp": ("WEBP", False),
    ".tif": ("TIFF", False),
    ".tiff": ("TIFF", False),
}


def collect_images(path: str) -> list[str]:
    """输入可以是单个文件或目录（目录只扫一层）。"""
    if os.path.isdir(path):
        try:
            names = os.listdir(path)
        except OSError as e:
            raise CoreError(f"无法读取目录 {path}: {e}") from e
        return sorted(os.path.join(path, n) for n in names
                      if n.lower().endswith(IMG_EXTS) and not n.startswith("."))
    return [path]


def unique_path(path: str) -> str:
    """目标已存在就在文件名后加 -1、-2 …（扩展名不变），避免覆盖已有文件。

    只用于预演与展示；真正写盘用 reserve_path，避免先查后写的竞态。
    """
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{stem}-{n}{ext}"):
        n += 1
    return f"{stem}-{n}{ext}"


def reserve_path(path: str) -> str:
    """原子地占住一个不存在的目标名：O_CREAT|O_EXCL 占位，并发也不会撞名。"""
    parent = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as e:
        raise CoreError(f"无法创建输出目录 {parent}: {e}") from e
    stem, ext = os.path.splitext(path)
    n = 0
    while True:
        cand = path if n == 0 else f"{stem}-{n}{ext}"
        try:
            fd = os.open(cand, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            n += 1
            continue
        except OSError as e:
            raise CoreError(f"无法创建输出文件 {cand}: {e}") from e
        os.close(fd)
        return cand


def _supported_meta(fmt: str, meta: Mapping[str, object] | None) -> dict[str, object]:
    """只挑目标格式接受的元数据键，避免 Pillow 因未知参数报错。"""
    if not meta:
        return {}
    allowed = {
        "JPEG": ("icc_profile", "exif", "dpi"),
        "PNG": ("icc_profile", "exif", "dpi"),
        "WEBP": ("icc_profile", "exif"),
        "TIFF": ("icc_profile", "dpi"),
    }.get(fmt, ())
    return {k: meta[k] for k in allowed if meta.get(k) not in (None, b"", (), "")}


def same_file(a: str, b: str) -> bool:
    """判断两个路径是不是同一个文件（不要求文件已存在）。"""
    if os.path.abspath(a) == os.path.abspath(b):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def load_meta(path: str) -> dict[str, object]:
    """原图里值得带到输出上的元数据：ICC 色彩配置、EXIF、DPI。"""
    meta: dict[str, object] = {}
    try:
        with Image.open(path) as im:
            for key in ("icc_profile", "exif", "dpi"):
                val = im.info.get(key)
                if val not in (None, b"", (), ""):
                    meta[key] = val
    except OSError:
        return {}
    return meta


def load_image(path: str) -> tuple[np.ndarray, np.ndarray | None]:
    """读成 RGB + 可选 alpha。alpha 来源不限于 RGBA/LA：调色板图的 tRNS 透明也算。"""
    im = Image.open(path)
    im.load()
    rgba = np.array(im.convert("RGBA"))
    alpha = rgba[:, :, 3].copy()
    if not alpha.size or int(alpha.min()) == 255:      # 全不透明就不带 alpha
        alpha = None
    return rgba[:, :, :3].copy(), alpha


def save_image(rgb: np.ndarray, alpha: np.ndarray | None, dst: str,
               quality: int | None = None,
               meta: Mapping[str, object] | None = None) -> None:
    """按扩展名保存；目标格式不支持透明时，用白色底合并 alpha。

    quality: JPEG/WEBP 的输出质量（1-100），None=默认 95；其它格式忽略。
    meta: load_meta() 读到的 ICC/EXIF/DPI，能带就带（格式不支持时自动跳过）。
    """
    if quality is not None and not 1 <= quality <= 100:
        raise CoreError(f"输出质量应在 1-100 之间: {quality}")
    ext = os.path.splitext(dst)[1].lower()
    fmt, lossy = FMT_BY_EXT.get(ext, (None, False))
    if fmt is None:
        raise CoreError(f"不支持的输出格式: {ext or '(无扩展名)'}（用 "
                        f"{'/'.join(sorted(FMT_BY_EXT))} 其中之一）")
    res = Image.fromarray(rgb, "RGB")
    if alpha is not None:
        if lossy or fmt in ("JPEG", "BMP"):
            solid = Image.new("RGB", res.size, (255, 255, 255))
            solid.paste(res, mask=Image.fromarray(alpha))
            res = solid
        else:
            res = res.convert("RGBA")
            res.putalpha(Image.fromarray(alpha))
    parent = os.path.dirname(os.path.abspath(dst))
    try:
        if parent:
            os.makedirs(parent, exist_ok=True)
        kwargs: dict[str, object] = (
            {"quality": quality if quality is not None else 95}
            if fmt in ("JPEG", "WEBP") else {})
        kwargs.update(_supported_meta(fmt, meta))
        res.save(dst, format=fmt, **kwargs)
    except OSError as e:
        raise OSError(f"无法写入 {dst}: {e}") from e
