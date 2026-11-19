"""测试用例包：统一仓库根路径与测试临时目录。

测试过程中的中间文件一律写到 `/data/tmp`（可用 `IMG_P_TMP_DIR` 覆盖），
不和 `data/output/`、`logs/` 等真实产物混在一起；目录建不出来时退回系统临时目录。
"""

import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

TMP_DIR = os.environ.get("IMG_P_TMP_DIR", "/data/tmp")  # platform-safe
try:
    os.makedirs(TMP_DIR, exist_ok=True)
    tempfile.tempdir = TMP_DIR
except OSError as exc:  # 只读环境：沿用系统临时目录
    print(f"[!] 无法使用测试临时目录 {TMP_DIR}（{exc}），改用系统临时目录", file=sys.stderr)
    TMP_DIR = tempfile.gettempdir()
