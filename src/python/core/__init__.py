"""核心层：OCR、版式分析、字体匹配、擦除重绘。

CLI 与 TUI 都只调用这一层，界面/命令行里不再重复实现任何替换逻辑。
"""

from .audit import (
                    ACTION_DEBUG,
                    ACTION_REPLACE,
                    build_entry,
                    log_path,
                    prune_logs,
                    record_write,
)
from .edit import erase, replace_image
from .errors import CoreError
from .fonts import FontFace, build_font_pool
from .image import (
                    IMG_EXTS,
                    collect_images,
                    load_image,
                    load_meta,
                    reserve_path,
                    same_file,
                    save_image,
                    unique_path,
)
from .jobs import area_jobs, jobs_from_blocks, make_jobs
from .match import Job, norm_map, plan_jobs
from .ocr import ocr_crop, ocr_regions
from .options import Options, parse_color, warn
from .render import char_spans, draw_text, ink_size, render_line, solve_tracking
from .style import analyze, fit_font, guess_size

__all__ = [
    "ACTION_DEBUG", "ACTION_REPLACE", "CoreError",
    "FontFace", "IMG_EXTS", "Job", "Options", "analyze", "area_jobs",
    "build_font_pool", "char_spans", "collect_images", "draw_text", "erase",
    "fit_font", "guess_size", "ink_size", "jobs_from_blocks", "load_image", "load_meta",
    "make_jobs", "norm_map", "ocr_crop", "ocr_regions", "parse_color",
    "plan_jobs", "render_line", "replace_image", "reserve_path", "same_file", "save_image",
    "prune_logs", "solve_tracking", "unique_path", "warn", "build_entry", "log_path", "record_write",
]
