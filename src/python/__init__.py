"""PNG 文字替换。core=核心逻辑，cli=命令行渠道，tui=交互渠道。

版本号定义在 `version.py`（唯一来源），这里再导出为 `__version__`。
"""

from .version import VERSION as __version__

__all__ = ["__version__"]
