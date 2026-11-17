"""本机字体发现与候选字体池。含中日韩字符时先用 fontconfig 过滤缺字形的字体。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from typing import Any

from PIL import ImageFont

from .errors import CoreError
from .options import _log

CJK_RE = re.compile(
    r"[\u2e80-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)
FONT_EXTS = (".ttf", ".otf", ".ttc", ".otc")


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        return ""


class FontFace:
    __slots__ = ("path", "index", "name")

    def __init__(self, path: str, index: int = 0):
        self.path = path
        self.index = index
        try:
            fam, style = ImageFont.truetype(path, 12, index=index).getname()
        except OSError:
            fam, style = os.path.basename(path), ""
        self.name = f"{fam} {style}".strip() or os.path.basename(path)

    def font(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.path, max(6, int(round(size))), index=self.index)

    def __repr__(self) -> str:
        return f"<{self.name} {os.path.basename(self.path)}#{self.index}>"


def font_dirs() -> list[str]:
    """系统字体目录：Windows 用系统字体目录，其它系统用常见 POSIX 目录。"""
    if os.name == "nt":
        dirs = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
        return dirs
    return ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]


def fc_list_files() -> list[str]:
    out = _run(["fc-list", "--format", "%{file}\n"])
    files = [ln.strip() for ln in out.splitlines() if ln.strip().lower().endswith(FONT_EXTS)]
    if not files:  # 没有 fontconfig（含 Windows）时直接扫字体目录
        for root in font_dirs():
            for dirpath, _dirs, names in os.walk(root):
                files += [os.path.join(dirpath, n) for n in names if n.lower().endswith(FONT_EXTS)]
    return sorted(set(files))


def fc_lang_files(lang: str) -> set[str]:
    out = _run(["fc-list", "--format", "%{file}\n", f":lang={lang}"])
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def fc_charset_files(ch: str) -> set[str]:
    out = _run(["fc-list", "--format", "%{file}\n", f":charset={ord(ch):x}"])
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def ttc_face_count(path: str, limit: int = 16) -> int:
    n = 0
    for i in range(limit):
        try:
            ImageFont.truetype(path, 12, index=i).getname()
            n = i + 1
        except OSError:
            break
    return max(1, n)


CACHE_VERSION = 1
CACHE_ENTRIES = 8


def cache_file() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "img-p", "fonts.json")


def _file_signature(files: list[str]) -> str:
    parts = []
    for path in sorted(files):
        try:
            st = os.stat(path)
            parts.append(f"{path}:{int(st.st_mtime)}:{st.st_size}")
        except OSError:
            parts.append(path)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _read_cache() -> dict:
    try:
        with open(cache_file(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def _write_cache(entries: dict) -> None:
    path = cache_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": CACHE_VERSION, "entries": entries}, f)
        os.replace(tmp, path)
    except OSError:
        pass


def _faces_from_rows(rows: Any) -> list[FontFace] | None:
    faces = []
    try:
        for path, index, _name in rows:
            if not os.path.exists(path):
                return None
            faces.append(FontFace(path, int(index)))
    except (TypeError, ValueError):
        return None
    return faces or None


def build_font_pool(texts: list[str], force_font: str | None, max_faces: int) -> list[FontFace]:
    if force_font:
        if not os.path.exists(force_font):
            raise CoreError(f"字体文件不存在: {force_font}")
        n = ttc_face_count(force_font) if force_font.lower().endswith((".ttc", ".otc")) else 1
        return [FontFace(force_font, i) for i in range(n)]

    joined = "".join(texts)
    files = fc_list_files()
    cache = _read_cache()
    key = hashlib.sha256(
        json.dumps(
            [_file_signature(files), sorted(set(joined)), max_faces], ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    cached = _faces_from_rows(cache.get(key)) if key in cache else None
    if cached:
        _log(f"字体池来自缓存（{len(cached)} 个 face）")
        return cached

    all_files = set(files)
    allowed = all_files
    if CJK_RE.search(joined):
        cjk: set[str] = set()
        for lang in ("zh", "ja", "ko"):
            cjk |= fc_lang_files(lang)
        for ch in sorted({c for c in joined if CJK_RE.match(c)})[:20]:
            have = fc_charset_files(ch) & all_files
            if have:
                cjk &= have
        allowed = cjk or allowed
        _log(f"中文字符候选字体文件 {len(allowed)}")
    if not allowed:
        raise CoreError("找不到可用字体，请用 --font 指定字体文件")

    faces: list[FontFace] = []
    for path in sorted(allowed):
        n = ttc_face_count(path) if path.lower().endswith((".ttc", ".otc")) else 1
        for i in range(n):
            faces.append(FontFace(path, i))
            if len(faces) >= max_faces:
                break
        if len(faces) >= max_faces:
            break

    rows = [[f.path, f.index, f.name] for f in faces]
    cache[key] = rows
    while len(cache) > CACHE_ENTRIES:  # 只留最近若干组
        cache.pop(next(iter(cache)))
    _write_cache(cache)
    return faces
