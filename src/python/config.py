"""全局路径与配置：默认读 <配置目录>/retype.json（旧 img-p.json 仍兼容），图片在 /data。"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from .core.options import Options

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")
DEFAULT_OUT_DIR = os.path.join(DATA_DIR, "output")
LOG_DIR = os.path.join(ROOT, "logs")

# 配置目录：Linux/macOS 用 /data/config；Windows 没有 /data，用仓库内 data/config
CONFIG_DIR = (
    os.path.join(ROOT, "data", "config") if sys.platform == "win32" else "/data/config"
)
CONFIG_NAME = "retype.json"
LEGACY_CONFIG_NAME = "img-p.json"

# 配置文件里允许的键（其余忽略）
CONFIG_KEYS = (
    "data_dir",
    "out_dir",
    "log_dir",
    "font",
    "size",
    "color",
    "align",
    "fit_width",
    "tracking",
    "max_fonts",
    "quality",
)


def config_file() -> str:
    """配置文件路径：IMG_P_CONFIG / RETYPE_CONFIG > <配置目录>/retype.json。

    旧版本用的是 img-p.json：新文件不存在而旧文件在时，继续读旧文件（不静默丢配置）。
    """
    explicit = os.environ.get("RETYPE_CONFIG") or os.environ.get("IMG_P_CONFIG")
    if explicit:
        return explicit
    new = os.path.join(CONFIG_DIR, CONFIG_NAME)
    legacy = os.path.join(CONFIG_DIR, LEGACY_CONFIG_NAME)
    if not os.path.exists(new) and os.path.exists(legacy):
        return legacy
    return new


def load_config() -> dict[str, object]:
    """读取 JSON 配置；文件不存在返回空，格式不对打一句提示后忽略。"""
    path = config_file()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"[!] 配置文件无法使用，已忽略 {path}: {e}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"[!] 配置文件应是 JSON 对象，已忽略 {path}", file=sys.stderr)
        return {}
    return {k: v for k, v in data.items() if k in CONFIG_KEYS}


def conf_str(key: str) -> str | None:
    val = load_config().get(key)
    return str(val) if isinstance(val, (str, int, float)) and str(val) else None


def option_defaults() -> dict[str, Any]:
    """配置文件里的样式默认值（只保留类型正确的键）。"""
    conf = load_config()
    out: dict[str, Any] = {}
    for key in ("font", "color", "align"):
        if isinstance(conf.get(key), str) and conf[key]:
            out[key] = conf[key]
    for key in ("size", "max_fonts", "quality", "tracking"):
        val = conf.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            out[key] = int(val) if key != "tracking" else float(val)
    if isinstance(conf.get("fit_width"), bool):
        out["fit_width"] = conf["fit_width"]
    return out


def apply_to_options(opts: Options) -> None:
    """把配置文件里的样式默认值填到还没设置的选项上（渠道/参数优先）。"""
    defaults = option_defaults()
    for key, val in defaults.items():
        current = getattr(opts, key, None)
        if key == "align":
            if current in (None, "auto"):
                opts.align = val
        elif key == "max_fonts":
            if current in (None, 160):
                opts.max_fonts = val
        elif key == "fit_width":
            if not current:
                opts.fit_width = bool(val)
        elif current is None:
            setattr(opts, key, val)


def default_input() -> str:
    """浏览入口：IMG_P_DATA_DIR > 配置 data_dir > /data（容器） > 仓库 data/。"""
    env = os.environ.get("IMG_P_DATA_DIR")
    if env:
        return env
    conf = conf_str("data_dir")
    if conf:
        return conf
    return "/data" if os.path.isdir("/data") else DATA_DIR


def default_out_dir() -> str:
    """输出目录：IMG_P_OUT_DIR > 配置 out_dir > 仓库 data/output。"""
    return os.environ.get("IMG_P_OUT_DIR") or conf_str("out_dir") or DEFAULT_OUT_DIR


def log_dir() -> str:
    """写盘日志目录：IMG_P_LOG_DIR > 配置 log_dir > 仓库 logs/。"""
    return os.environ.get("IMG_P_LOG_DIR") or conf_str("log_dir") or LOG_DIR


DEFAULT_INPUT = default_input()
