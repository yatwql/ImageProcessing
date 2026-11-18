"""retype：图片文字替换。core=核心逻辑，cli=命令行渠道，tui=交互渠道。

名称与版本号定义在 `version.py`（唯一来源），这里再导出。
"""

from .version import NAME as __app_name__
from .version import VERSION as __version__

__all__ = ["__app_name__", "__version__"]
