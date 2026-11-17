"""程序版本号：全仓库唯一来源。

被 `src.python.__init__` 再导出为 `__version__`，pyproject 的打包版本也从这里读；
命令行/TUI 启动打印、界面标题、写盘日志字段、文档开头的版本行都引用它，
`scripts/check-guards.py` 会核对它们是否一致。
"""

from __future__ import annotations

VERSION = "0.1"
