"""程序名称与版本号：全仓库唯一来源。

被 `src.python.__init__` 再导出为 `__version__` / `__app_name__`；
命令行横幅与 `--version`、TUI 标题、写盘日志的 `app` 字段、文档开头都引用它，
`tools/check_guards.py` 会核对它们是否一致。
"""

from __future__ import annotations

NAME = "retype"                 # 程序名（命令行、日志、TUI 标题统一用它）
TITLE = "图片文字替换"            # 中文副标题，界面/帮助里跟在名字后面
VERSION = "0.1"
