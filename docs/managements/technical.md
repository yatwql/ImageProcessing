# 技术设计文档（Technical Design）

- 项目：img-p / PNG 文字替换
- 版本：1.0
- 对应需求：`docs/managements/requirements.md`

## 1. 总体架构

四层三块：`scripts/` 只有启动脚本，业务代码全在 `src/`，其中 `core` 是唯一实现替换逻辑的地方，
`cli` 与 `tui` 是两个并列渠道。

```text
scripts/cli.sh ──► src/python/cli ──┐
  (python -m src.python.cli)       │
                                    ├──► src/python/core ──► 图片 / OCR / 版式分析 / 字体匹配 / 擦除 / 重绘
scripts/tui.sh ──► src/python/tui ──┘
  (python -m src.python.tui)
                 ├── app.py   状态与动作（不依赖 curses，可单测）
                 └── ui.py    curses 绘制与按键（只画、只收键）
```

约束：

- `core` 不 import `argparse`、不 import `curses`，只做纯函数与数据类。
- `cli` / `tui` 不得自行实现“找字体 / 擦除 / 绘制”等逻辑，只能组合 `core` 的 API。
- 两个渠道最终都产出同一种 `Job` 列表，再交给同一个 `core.replace_image` 执行。

## 1.1 目录结构

```text
scripts/                     只有启动脚本，不放业务代码
  cli.sh / cli.ps1           命令行入口  → python -m src.python.cli
  tui.sh / tui.ps1           交互入口    → python -m src.python.tui
  setup.sh / setup.ps1       建 .venv 并安装依赖（ps1 支持 -Dev 装测试依赖）
  test.sh / test.ps1         全量用例 + 报告（ps1 支持 -Fast）
src/
  python/                    程序代码
    config.py                路径约定 + /data/config/img-p.json 配置读取
    core/                    核心层（CLI 与 TUI 共用）
    cli/                     命令行渠道
    tui/                     交互渠道：app.py 状态 + ui.py（curses）
  test/                      测试用例（pytest / unittest 均可）
    __init__.py              测试包入口：注入仓库根到 sys.path、临时目录指向 /data/tmp
data/                        待处理的图片
data/output/                 默认输出目录
logs/                        写盘日志（按天一个 JSONL 文件，不入库）
/data/config/img-p.json      运行时配置文件
/data/config/img-p.example.json  示例配置（setup 生成，含全部可配置键）
/data/tmp                    测试中间文件（不碰 data/output）
/test-reports                测试报告（junit / html / coverage / summary）
docs/                        需求 / 技术设计 / 使用手册
CLAUDE.md                    给 AI 协作者的项目约定（架构约束/测试/文档/纪律）
requirements.txt             运行依赖
requirements-dev.txt         开发依赖（pytest、ruff）
```

## 2. 模块与职责

| 文件 | 职责 | 关键导出 |
| --- | --- | --- |
| `src/python/config.py` | 路径约定与配置文件 | `default_input()` `default_out_dir()` `log_dir()` `load_config()` `option_defaults()` `apply_to_options()` |
| `src/python/core/ocr.py` | RapidOCR 封装（进程内单例） | `ocr_regions(rgb)` `ocr_crop(rgb, rect)` |
| `src/python/core/style.py` | 版式分析、字体/字号/字距反解 | `analyze` `fit_font` `guess_size` `soft_iou` `stroke_of` |
| `src/python/core/fonts.py` | 本机字体发现（fontconfig 或系统目录）、候选池、ttc 多 face 展开 | `FontFace` `build_font_pool` `font_dirs` |
| `src/python/core/render.py` | 字形渲染与落位 | `render_line` `char_spans` `ink_size` `draw_text` `solve_tracking` |
| `src/python/core/edit.py` | 擦除 + 重绘编排 | `erase` `replace_image` |
| `src/python/core/audit.py` | 写盘日志：组装并追加 JSONL 记录 | `record_write` `build_entry` `log_path` `ACTION_REPLACE` `ACTION_DEBUG` |
| `src/python/core/match.py` | Job 定义与匹配规则 | `Job` `norm_map` `plan_jobs` |
| `src/python/core/jobs.py` | 各种入口 → Job 列表 | `area_jobs` `make_jobs` `jobs_from_blocks` |
| `src/python/core/image.py` | 读写、元数据与目标占名 | `load_image` `load_meta` `save_image` `reserve_path` `unique_path` `same_file` `IMG_EXTS` |
| `src/python/core/options.py` | 运行选项、字色解析、警告出口 | `Options` `parse_color` `warn` |
| `src/python/cli/main.py` | 参数、两遍流程、批量汇总 | `main` `build_parser` `load_mapping` |
| `src/python/tui/app.py` | 会话状态、动作、缓存 | `App` `Block` `ImageItem` |
| `src/python/tui/ui.py` | 绘制、按键、输入行、入口 | `loop` `handle` `edit_line` |

## 3. 核心数据结构

```python
@dataclass
class Job:                    # 一处替换
    rect: tuple[int, int, int, int]   # 目标区域（图像坐标 x, y, w, h）
    src: str | None                   # 原文字（用于样式匹配；area 模式由局部 OCR 补）
    new: str                          # 新文字（可含 \n）
    span: tuple[int, int] | None      # 非空 = 行内替换，只动 src[span[0]:span[1]] 这几个字

@dataclass
class Options:                # 渠道无关的运行选项
    font, size, color, align, fit_width, tracking, max_fonts, debug, quiet
```

`Job` 是渠道与核心之间唯一的契约：CLI 由 `make_jobs` 产出，TUI 由静态方法
`core.jobs_from_blocks(blocks, mapping)` 产出，形状一致。

## 4. 替换流水线

`core.replace_image(rgb, alpha, jobs, opts, pool, tag="", memo=None)` 逐个 `Job` 执行：

### 4.1 分析（`style.analyze`）

1. 以目标框为中心外扩 `0.7 × 字高`，取工作区 crop。
2. 背景估计：`cv2.medianBlur`，窗口 `k ≈ 1.3 × 字高`（截断到 crop 尺寸）。窗口必须远大于笔画宽度，否则笔画中心会被当成背景，mask 会变空心。
3. 色差图 `dist = max_c |crop - bg|`，阈值取 `max(14, 0.45·dmax)`；不足 12 像素时依次退化到 `0.3·dmax`、`0.2·dmax`。
   （不用 Otsu：背景占多数时 Otsu 阈值会塌到 0。）
4. mask 与“目标框 + 2px”求交，避免擦掉相邻文字；再做一次 3×3 闭运算。
5. 字色：取 mask 内 `dist ≥ 80 分位` 的像素颜色中位数 —— 抗锯齿像素占比高，直接取中位数会偏亮，腐蚀法在细笔画上会失效。
6. 笔画粗细：`2 × P75(distanceTransform(mask))` 用于擦除半径参考；另用更严格的阈值
   （`0.72·dmax`）再取一次“笔画核心” `stroke_core`，专用于字重判别——抗锯齿会让常规体在宽阈值下
   显得和粗体一样粗，用宽阈值直接判别会把常规体认成粗体。
7. 产出：`mask`（全图 bool）、`ink_box`、`text_color`、`stroke`、`region`。

### 4.2 字体与字号匹配（`style.fit_font`）

对候选池中每个 `FontFace`：

1. 用该字体渲染原文字（100px），反解字号：`size = round(100 × 字迹高 / 该字体在 100px 下的墨迹高)`。
2. 反解字距：`track0 += (目标宽 - 当前宽) / (字数 - 1)`，迭代两次；`|track0| < 0.12em` 直接归零（抗锯齿造成的 1~2px 宽度误差不应变成字距）。
3. 打分：倾斜估计 `slant`（下半部墨迹质心相对上半部的横向偏移 / 字迹高）接近 0 时，
   先从候选池里剔掉 `italic/oblique` 字体，避免正体数字被斜体字体凑上（实测能修正
   纯数字块被匹配成 `C059 Bold Italic` 的问题）。
4. 打分：`sim = soft_iou(原图字迹, 渲染字迹)` —— 双方先按高度归一化，再高斯模糊后求 `min/max` 交并比，允许 ±3px 平移搜索。
5. 取前 8 名做 `字号 ±3 × 字距 ±0.04em` 的局部精修，最终分数
   `score = sim × (min(笔画)/max(笔画))^0.7`（字重惩罚，笔画取 `stroke_core`）。

两轮搜索策略（防止“靠拉大字距强行对上”）：

| 轮次 | 允许字距 | 触发条件 |
| --- | --- | --- |
| 第一轮 | ±0.35em | 总是先跑 |
| 第二轮 | ±1.6em | 第一轮最佳 `sim < 0.5`（典型：逐字加宽的大标题） |

返回 `(score, face, size, tracking, iou)`。`iou < 0.35` 视为不可靠：`replace_image` 退回默认字体、
`guess_size` 猜字号，并在 stderr 提示——这是 `--area` 模式下区域文字未被完整 OCR 时的兜底路径。

### 4.3 候选字体池（`fonts.build_font_pool`）

- 通过 `fc-list` 列字体文件（`.ttf/.otf/.ttc/.otc`），`.ttc` 逐 face 展开。
- 文本含中日韩字符时，先用 `fc-list :lang=zh|ja|ko` 与逐字 `:charset=` 求交，过滤掉缺字形字体，
  避免出现豆腐块；纯拉丁文本则使用全部字体。
- 数量上限 `Options.max_fonts`（默认 160），超出即截断。

### 4.4 擦除（`edit.erase`）

- mask 外扩 1px（`dilate` 3×3），再高斯模糊后二值化，把抗锯齿边缘一起纳入。
- `cv2.inpaint(..., 4, INPAINT_TELEA)` 修复，纯色与渐变背景都能无痕。
- 有 alpha 通道时对 alpha 单独做同样的 inpaint，避免原字形残留成黑色轮廓。

### 4.5 重绘（`render.draw_text`）

- 目标框：整行替换用 `ink_box`；行内替换用 `char_spans()` 反推出的子串横向区间与该区间内的墨迹纵向区间。
- 垂直居中于目标框，水平按 `align` 落位；`auto` 规则：行内替换与“画面居中标题”用 `center`，
  其余用 `left`（判据：块中心与图宽中心偏差 < 4% 图宽）。
- 以 `alpha` 混合写入 RGB；若有 alpha 画布，同时做 `maximum(alpha, 字形覆盖率)`，保证新字不透明。
- `--fit-width` 用 `solve_tracking` 迭代求字距，使新文字墨迹宽度贴合目标框宽度。
- `\n` 触发多行绘制，行距 `1.34 × 字号`，整块垂直居中。

## 5. 匹配规则（`match.plan_jobs`）

对映射表中的每个 key：

1. **整行匹配**：`norm_map(行文字) == norm_map(key)`。`norm_map` 去掉空白与零宽字符，并对每个字符做
   NFKC 归一（逐字归一以保持下标可映射回原文），因此全角 `２０２３` 与 `2023` 等价。命中 → 整行 `Job(span=None)`。
2. **行内子串**：在第 1 步未命中的行里查找 key 的全部出现位置，把归一化下标映射回原文字下标 → `Job(span=(a, b))`。
   同一 key 可同时产生整行 Job 与若干行内 Job（整行命中的行不重复参与子串匹配）。
3. **模糊兜底**：都没命中时用 `difflib.SequenceMatcher` 取最相似行，`ratio ≥ 0.8` 才按整行替换并打印提示。

TUI 的 `core.jobs_from_blocks` 同一套规则：块级 `override` 优先（`find` 非空则算行内 span），
其余启用块作为 regions 交给 `plan_jobs` 应用全局映射。

## 6. 两个渠道的实现要点

### 6.0 配置文件（`src/python/config.py`）

- 位置：`/data/config/img-p.json`（`IMG_P_CONFIG` 可换文件名）；`scripts/setup.sh` 首次会写一份默认值。
- 键：`data_dir` `out_dir` `log_dir` `font` `size` `color` `align` `fit_width` `tracking` `max_fonts` `quality`。
- 优先级：命令行/界面显式设置 > 环境变量（`IMG_P_DATA_DIR`/`IMG_P_OUT_DIR`/`IMG_P_LOG_DIR`）> 配置文件 > 内置默认。
- JSON 解析失败打一句提示后忽略；未知键忽略；`apply_to_options()` 只填「还没设置」的项。

### 6.1 CLI（`src/python/cli`）

- 入口：`python -m src.python.cli`，启动脚本 `scripts/cli.sh`。
- 两遍流程：第一遍逐图 `make_jobs` 并收集原文文本（供字体池）；第二遍逐图 `replace_image` + `save_image`。
- 批量：输入为目录时遍历一层，`IMG_EXTS` 过滤；输出统一 `<out_dir>/<stem>.png`。
- 汇总：成功/失败/无匹配张数与替换总数；至少一处成功返回 0。
- `--report FILE`：同一份汇总再加逐图明细（`src`/`dst`/`replaced`/`operations`）写成 JSON；
  `--dry-run` 时 `dry_run=true`、`saved=false`。
- `--quality N` 透传给 `save_image`；`--log-dir` 覆盖日志目录。

### 6.2 TUI（`src/python/tui`）

`App` 是一个不碰 curses 的状态层：图片列表、块列表、映射表、样式选项与执行动作都在这里，
`ui.py` 只负责绘制与按键。为避免核心层的 `print(stderr)` 冲花 curses 界面，`App` 初始化时
把 `opts.warn` 指向 `App.on_core_warning()`：核心层警告进消息行，不 print 到 stderr。

- 入口：`python -m src.python.tui`，启动脚本 `scripts/tui.sh`（检测到非 tty 直接拒绝并提示用 CLI）。
- 目录浏览：`App` 记住 `dir`，`d` 打开 `panel="browse"`；`refresh_browse()` 列出
  「上级 + 子目录 + 当前目录图片」，`browse_into()` 进入目录或选中图片，`browse_parent()`
  （`Backspace`）回上级；`open_dir()` 重建图片列表。默认入口见 `config.default_input()`
  （`IMG_P_DATA_DIR` > `/data` > 仓库 `data/`）。
- `app.py`：`App` 持有 `images / mapping / out_dir / opts / 选中位置`，动作有
  `ensure_blocks` `jobs_for` `apply_one` `apply_current` `apply_all` `move` `add_to_mapping` `save_map` 等，全部无 curses 依赖。
- `ui.py`：`draw_main / draw_map / draw_help` 渲染，`handle / handle_map` 分发按键，`edit_line` 为底部单行编辑器
  （预填内容首次输入即整体替换，`curses.curs_set` 在编辑期间显示光标）。
- 宽字符：自实现 `dwidth / cut / pad`（按 `east_asian_width` 计算显示宽度），所有绘制先按列宽裁剪再补齐，
  保证中文不串行。
- 布局：顶栏 1 行（输出目录 / 上次保存）+ 栏目标题 1 行 + 正文 + 详情行 + 消息行 + 键位行。
- 图片列表带快捷键序号（前 9 项 `1..9`，第 10 项 `0`），`select_by_digit()` 直接跳转；
  列表按 `image_window()` 跟随选中项滚动（`digit_of()` 只给可见行编号）。
- 面板：`?` 帮助、`e` 全局映射、`c` 样式选项。样式选项直接改 `App.opts`（字体/字号/字色/对齐/
  贴合宽度/字距/字体上限），留空即自动；校验失败只在消息行提示，不抛异常。
- 健壮性（面向手机 / SSH 远端）：
  - `Esc` 只表示“返回上一层”，退出统一走 `q`，避免终端吐 ESC 或误触直接关掉程序；
  - 捕获 `curses.error` 与 `KEY_RESIZE`，尺寸变化时 `update_lines_cols()` 后重画；
  - 绘制与按键动作都包在异常兜底里，出错只更新消息行、不退出进程；
  - 按键统一归一：`read_key()` 里把 curses 能识别的键码、以及手机/SSH 客户端直接吐出的
    `ESC [ A`、`ESC O B`、`ESC [ 5 ~` 等序列都翻译成统一的 token（`KEY_UP`/`KEY_DOWN`/`BTAB`…），
    用 45ms 超时窗口区分“单按 Esc”（=返回）和转义序列；另提供 `,` `.` `<` `>` 与 `t` 作为
    方向键/切栏的替代键；
  - 宽度 < 60 列自动切单栏布局（`draw_narrow`：只画焦点栏，`Tab` 切换，顶栏显示 `[宽x高]`）；
  - 小于 16 列或 8 行时才显示“终端太窄”占位页，不渲染主界面。

### 6.3 共享缓存策略

| 缓存 | 位置 | 键 | 作用 |
| --- | --- | --- | --- |
| 字体池（内存） | `App._pool_cache` | 原文集合签名 | 避免重复 `fc-list` |
| 字体池（磁盘） | `~/.cache/img-p/fonts.json` | 字体文件签名 + 文本字符集 + 上限 | 跨进程复用，实测 0.137s → 0.018s；字体文件变动自动失效 |
| 版式分析 | `ImageItem.memo` | `("a", rect)` | 重复替换跳过 mask/字色计算 |
| 字体匹配 | `ImageItem.memo` | `("f", rect, src)` | 重复替换跳过字形比对 |

实测：首图首次替换 < 1s（单处），同图重复替换 ≈ 0.02s。

## 7. 输出与幂等

- 默认输出 `data/output/<原文件名>.png`；CLI 单图可用 `-o` 指定；TUI 用 `o` 改目录。
- 目标文件已存在时用 `core.image.reserve_path()` 原子占名（`O_CREAT|O_EXCL`）追加 `-1`、`-2`…
  （扩展名保持不变），并发也不会撞名；`unique_path()` 只用于展示与 `--dry-run` 的内存编号。
- TUI 在会话内记住 `ImageItem.saved`：同一张图重复替换覆盖自己刚生成的文件，避免每次按 `r` 都留一份。
- 输入格式由 `IMG_EXTS` 决定：`png/jpg/jpeg/bmp/webp/tif/tiff`（PIL 解码，统一转 RGB + 可选 alpha）。
  alpha 统一从 `convert("RGBA")` 取，因此调色板 PNG 的 `tRNS` 透明也会保留；全不透明时不带 alpha。
- 输出格式跟随扩展名（`FMT_BY_EXT`）：PNG/WEBP/TIFF 保留 alpha；JPEG/BMP 不支持透明，保存时按白底合并 alpha。
  质量由 `save_image(quality=...)` 控制（JPEG/WEBP 生效，默认 95，越界抛 `CoreError`）；
  ICC/EXIF/DPI 由 `load_meta()` 读出后按格式白名单带上。
  扩展名不在表内直接抛 `CoreError`（不交给 PIL 抛难懂的 `ValueError`）。
- 写入前 `makedirs(..., exist_ok=True)`；写入失败抛 `OSError` 并由渠道转成一句话提示。
- 同一张图重复替换是**重新生成**而非叠加：每次执行都从磁盘原图重新读取、重新擦除重绘，因此结果幂等。
- 已有文件不覆盖：真正写盘用 `reserve_path()` 原子占名，`unique_path()` 只服务展示/预演。
- 输出路径与原图是同一个文件时**拒绝写入**（`core.image.same_file` 判定，`-o 原图`、`--out-dir` 指到
  输入目录都会被拦下并提示换个目录），保证“绝不覆盖原图”。

### 7.1 写盘日志（`core.audit`）

- 只要真的写了图片文件，就调一次 `core.audit.record_write()`；`--dry-run` 与保存失败的路径都不记。
  `--debug` 的 mask 图先检查 `cv2.imwrite` 返回值，写失败抛 `CoreError` 且不记日志。
- 记录位置：`config.log_dir()`，默认仓库根 `logs/`；`--log-dir` 或环境变量 `IMG_P_LOG_DIR` 可覆盖。
- 文件名 `image-writes-YYYYMMDD.log`（本地日期），一行一个 JSON 对象，UTF-8、只追加；
  写入时跨进程加锁（POSIX `flock`、Windows `msvcrt.locking`）、`fsync` 落盘，
  `prune_logs()` 自动清理超过 30 天的旧文件。
  `time` `channel` `action` `src_file` `src_path` `src_size` `dst_file` `dst_path` `dst_size`
  `replaced` `operations[]`（`old`/`new`/`mode`/`rect`/`font`/`size`/`tracking`/`color`/`align`/`iou`）、
  `dst_sha256` `dst_width` `dst_height`，
  以及用户显式设置过的样式项 `options`。
- `action` 区分 `替换文字并保存图片` 与 `写出调试图`（`--debug` 的 mask 图同样入日志）。
- 日志写失败抛 `CoreError`，由渠道降级成一句提示，**不影响已保存的图片与退出码**。
- `--dry-run` 不写任何图片：结果图与调试图都不落盘，因此不产生日志；此时 `--debug` 被忽略并提示一句。

## 8. 错误处理

核心层**不直接 `sys.exit`**：可预期的失败统一抛 `core.errors.CoreError`（字体缺失、颜色写错、OCR 未安装、
坐标非法、目录不可读、调试图目录建不了）。由渠道决定表现：CLI 转成一句 `sys.exit(消息)`，
TUI 捕获后只更新消息行、绝不退出进程（`SystemExit` 也一并拦）。

| 场景 | 行为 |
| --- | --- |
| 图片无法打开 | 跳过该图，stderr 提示路径与原因；批量时计入失败 |
| 颜色/字体参数非法 | CLI 启动时立即报错；TUI 在样式面板里提示并保留原值 |
| 区域检测不到文字 | 跳过该 Job，提示区域坐标 |
| 字体匹配不可靠 | 退回默认字体 + `guess_size`，stderr 说明可 `--font` |
| OCR 依赖缺失 | 抛 `SystemExit` 并提示安装命令；TUI 捕获后显示在图片列表 |
| 写盘失败 | 捕获 `OSError`，提示目标路径 |
| 日志写不进 | 捕获 `CoreError`，提示「已保存但无法写日志」，图片照常保留 |
| 映射表非法 | 直接退出并提示 JSON 解析错误 |
| `--area` 用于目录 | 直接拒绝（`--area 只能用于单图`） |

## 9. 性能

| 环节 | 成本 | 备注 |
| --- | --- | --- |
| RapidOCR | ~1s / 图 | 进程内单例，只初始化一次 |
| `fc-list` 查询 | ~几十 ms × N | 含 CJK 时逐字 `:charset=` 查询，代价与字符数线性相关 |
| 字体匹配 | 31 face 约 0.5~1s / 块 | 粗筛 + 前 8 名精修 |
| 擦除重绘 | ~10ms / 块 | 与图幅线性相关 |

已做的优化：`soft_iou` 的模糊从“每个平移位置一次”提到“每张掩码一次”（字体匹配 0.78s → 0.50s/块）；
字体池落盘缓存；`fit_font` 先按宽度比例剪枝再加权打分。

实测后放弃的优化：**多线程并行处理多图**。在 15 张图和 4 张 20 块大图上分别测过
（`thread-local` OCR 引擎 + 两遍流程都并行），1/2/4 线程的耗时为 21.8 / 23.8 / 25.8 秒
与 7.8 / 8.9 / 10.0 秒 —— 并发只会更慢：OCR 的 onnxruntime 与会话本身已多线程，
且每线程一份模型初始化的开销远大于收益。因此保持单线程，代码也不保留这部分复杂度。

## 10. 测试策略

- 静态检查：`ruff check --select E,F,B,I --ignore E501 src/`，要求零告警。
- 核心层：合成图（已知字体/字号/颜色）→ 断言 `fit_font` 选回原字体与字号、`analyze` 取回原字色。
- 渠道层：TUI 的 `App` 可用伪造 `win` 驱动 `handle()` 做无终端单测（整行/行内/映射/批准确认）。
- 端到端：`cli.sh data/demo --dry-run` 与 `cli.sh data/demo --map ...` 出图后人工比对原图。
- 回归样例：`data/demo/` 四张真图（`示例-报告.png` 标题/正文/负责人/日期；`示例-通知1..3.png` 三种标题与不同电话），
  `src/test/cli/test_demo_assets.py` 直接在它们上面跑真实读取、单图替换、行内替换、批量与日志。
- 自动测试：`src/test/` 按 `core/`、`cli/`、`tui/`、`image_processing/` 分目录，236 个用例（`unittest` 写、`pytest` 与 `unittest` 都能跑），覆盖匹配规则、
  块级任务、渲染与字距、图片读写格式表、合成图端到端（其它区域像素不变、memo 两次结果一致）、输出覆盖保护（`same_file` 与
  CLI 拒绝覆盖）、写盘日志（字段/追加/预演不记/日志失败不毁结果）、TUI 按键归一（转义序列/方向键/数字跳图/单 Esc 不退出）。
- 开发依赖：`requirements-dev.txt`（pytest、ruff）。

## 10.0 测试报告脚本

`scripts/test.sh` 是唯一的测试入口：跑 `src/test` 全量用例，生成
`/test-reports/{junit.xml,test-report.html,coverage/index.html,summary.md}`（`--fast` 跳过覆盖率与 HTML）；
目录不可写时退回 `./reports`。测试中间文件统一写 `/data/tmp`（`PYTHONPYCACHEPREFIX`、`TMPDIR`、
`COVERAGE_FILE` 都指过去），脚本结束时清掉仓库里的 `__pycache__` / `.pytest_cache`。
覆盖率基线约 77% 行覆盖；入口文件（`cli/__main__.py`、`tui/__main__.py`）只有 4 行、不单独覆盖。

## 10.1 自测命令

```bash
./scripts/setup.sh                                            # 建环境（或者已有 .venv）
./scripts/test.sh                                             # 全量用例 + 测试报告
.venv/bin/ruff check --select E,F,B,I --ignore E501 src/             # 静态检查，应零告警
./scripts/cli.sh data/demo --list                              # OCR 是否正常（示例图）
./scripts/cli.sh data/demo --map "2023=2024" --dry-run          # 批量预演
./scripts/cli.sh data/demo --map "2023=2024"                  # 出图到 data/output/
printf 'q' | script -qec "./scripts/tui.sh" /dev/null         # TUI 冒烟（非交互环境）
```

## 11. 扩展点

| 需求 | 扩展位置 |
| --- | --- |
| 换 OCR 引擎 | `core/ocr.py`，保持 `ocr_regions` / `ocr_crop` 契约 |
| 支持竖排/旋转 | 在 `Job` 增加 `angle` 字段，`analyze`/`draw_text` 增加旋转分支 |
| 图形界面 | 新增 `src/gui/`，复用 `App` 状态层与 `core.replace_image` |
| 更多输出格式 | `core/image.save_image` 按扩展名分派 |
| 字体缓存持久化 | `core/fonts.build_font_pool` 外包一层 JSON 缓存 |
| 输出质量/元数据 | `core/image.save_image(quality=, meta=)`；新格式只需补 `FMT_BY_EXT` 与元数据白名单 |
| 运行摘要字段 | `cli/main.write_report()`；日志字段在 `core/audit.build_entry` |
| 日志改格式/加字段 | `core/audit.py` 的 `build_entry` / `OP_FIELDS`，渠道无需改动 |

## 12. 已知限制

- 手写体、艺术字、极粗描边字无法从系统字体中选出，需要 `--font`。
- 复杂纹理/照片底图上的 inpaint 效果有限。
- `--area` 模式下若区域文字未被完整 OCR，字体匹配会退化为默认字体。
- 竖排、旋转文字按水平排版处理。
