"""核心层异常：库代码不直接 sys.exit，交给渠道决定怎么报错。"""

from __future__ import annotations


class CoreError(RuntimeError):
    """核心层可预期的失败（字体缺失、颜色写错、OCR 未安装、目录不可读……）。"""
