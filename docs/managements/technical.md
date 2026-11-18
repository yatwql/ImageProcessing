# 技术设计文档（Technical Design）

> 版本：v0.3-dev

- 项目：retype / PNG 文字替换
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

> 完整逐文件说明见 `docs/managements/folders.md`（守护会核对是否漏文件）；本节只列主干。

```text
scripts/                     只放薄壳启动脚本（逻辑在 src/python 或 tools/，守护会拦超 40 行）
  cli.sh / cli.ps1           命令行入口    → python -m src.python.cli
  tui.sh / tui.ps1           交互入口      → python -m src.python.tui
  setup.sh / setup.ps1       环境引导      → python -m src.python.bootstrap（ps1 支持 -Dev）
  runTest.sh / runTest.ps1   测试 + 报告   → src/python/tools/run_tests.py（ps1 支持 -Fast）
  log-query.sh / .ps1        日志查询      → python -m src.python.cli.log_query
    tools/                   工程工具（守护/覆盖率/发布；不进发行包、不计覆盖率）
  check_guards.py            工程守护（18 项，含编号/版本/目录树/文档索引/归档）
  release.py                 发布编排：check → archive → prepare → gate → build → tag → publish
  gen_folders.py             重新生成 folders.md 的目录树与统计表数字（说明列保留）
  junit_summary.py           把 junit 报告里的失败用例列成一行一条（CI 摘要步用它）
  gate_stamp.py              门禁戳：同一份代码已全量通过时，推送前跳过重跑（省 ~7 分钟）
  check_perf.py              耗时守卫：模糊 IoU / inpaint / PNG 读写 / 日志追加
  run_tests.py               测试编排：临时目录、报告、覆盖率、摘要
.githooks/                   仓库自带钩子（core.hooksPath 指向这里，不入 .git/hooks）
  pre-commit                 提交前：ruff + guards + 全量用例
  install-hooks.sh           启用 / --off 关闭
.github/workflows/ci.yml     CI：test×3 / lint / typecheck / guards / perf / windows / audit（+ release 仅在打 tag 时）
pyproject.toml               单一配置源：依赖、可选依赖、ruff、mypy、pytest、coverage
constraints.txt              锁定的依赖组合（pip -c 使用；升级须跑全量用例）
docs/README.md               文档索引（守护「文档索引」核对每份文档都被引用）
docs/managements/            管理文档（plan / review-findings / changelog 是过程台账）
docs/manuals/                使用手册
docs/archive/                归档：已发布系列的台账旧内容（`release.py archive` 整块搬入）
  vX.Y.x/                    一个版本系列一个子目录：archived_{plan,review-findings,changelog}.…md
  README.md                  归档规范：命名、头部四项、编号不复用、发布时怎么搬

启动链路（cli.sh / tui.ps1 等都一样）：
  系统 python -m src.python.launch <渠道> → 探测 .venv 与关键依赖（PIL/numpy/cv2[/pytest]）
  → 缺则自动建 venv 并按 constraints 装依赖 → os.execv 到 venv python 的真实入口。
  `IMG_P_NO_AUTO_SETUP=1` 关闭自动安装（CI/离线/想手动控制时用），只提示不改环境。
src/
  python/                    程序代码
    config.py                路径约定 + /data/config/retype.json 配置读取
    bootstrap.py             环境引导（建 venv、按 constraints 装依赖、写默认配置、--check 探测）
    launch.py                统一启动器：缺环境先自动装，再 exec 到真正的入口
    core/                    核心层（CLI 与 TUI 共用）
    cli/                     命令行渠道（main.py=替换流程，log_query.py=日志查询）
    tui/                     交互渠道
      app.py                 会话状态与动作（不碰 curses）
      ui.py                  入口：启动参数、主循环、窗口初始化（门面）
      ui_base.py             文案（USAGE/HELP）、宽字符、颜色与落字
      ui_draw.py             宽/窄两种布局的绘制
      ui_input.py            按键序列解析与单行输入
  browse.py              目录扫描（父目录/子目录/图片的纯函数层）
      ui_actions.py          按键分发与编辑动作
  test/                      测试用例（pytest / unittest 均可）
    __init__.py              测试包入口：注入仓库根到 sys.path、临时目录指向 /data/tmp
    _support.py              公共设施：字体路径、合成图、OCR 桩、FakeWin、用例基类
    core/                    核心层用例（含 background/color/font/format/layout/pipeline/primitives 子目录）
    cli/  tui/               渠道与交互用例
    tools/                   工程工具用例（发布编排 / 归档流程）
```

## 1.2 依赖方向（硬约束）

`core` 不导入 `cli`/`tui`；`cli` 与 `tui` 互不导入——由 `src/python/tools/check_import_surface.py`
（守护第 14 项）逐文件核对 `src.python.X` 形式的导入。完整契约见 `contracts.md`。

## 2. 模块与职责

| 文件 | 职责 | 关键导出 |
| --- | --- | --- |
| `src/python/config.py` | 路径约定与配置文件 | `default_input()` `default_out_dir()` `log_dir()` `load_config()` `option_defaults()` `apply_to_options()` |
| `src/python/core/ocr.py` | RapidOCR 封装（进程内单例） | `ocr_regions(rgb)` `ocr_crop(rgb, rect)` |
| `src/python/core/style.py` | 版式分析、字体/字号/字距反解 | `analyze` `fit_font` `guess_size` `soft_iou` `stroke_of` |
| `src/python/core/fonts.py` | 本机字体发现（fontconfig 或系统目录）、候选池、ttc 多 face 展开 | `FontFace` `build_font_pool` `font_dirs` |
| `src/python/core/render.py` | 字形渲染与落位 | `render_line` `char_spans` `ink_size` `draw_text` `solve_tracking` |
| `src/python/core/edit.py` | 擦除 + 重绘编排 | `erase` `inpaint_radius` `replace_image` |
| `src/python/core/audit.py` | 写盘日志：组装、追加、回读与汇总 | `record_write` `build_entry` `read_entries` `summarize` `log_path` `ACTION_REPLACE` `ACTION_DEBUG` |
| `src/python/core/match.py` | Job 定义与匹配规则 | `Job` `norm_map` `plan_jobs` |
| `src/python/core/jobs.py` | 各种入口 → Job 列表 | `area_jobs` `make_jobs` `jobs_from_blocks` |
| `src/python/core/image.py` | 读写、元数据与目标占名 | `load_image` `load_meta` `save_image` `reserve_path` `unique_path` `same_file` `IMG_EXTS` |
| `src/python/core/options.py` | 运行选项、字色解析、警告出口 | `Options` `parse_color` `warn` |
| `src/python/cli/main.py` | 参数、两遍流程、批量汇总 | `main` `build_parser` `load_mapping` |
| `src/python/cli/log_query.py` | 日志查询渠道（过滤 + 汇总 + 排版） | `main` `build_parser` |
| `src/python/bootstrap.py` | 环境引导（只用标准库） | `main` `ensure_venv` `write_config` |
| `src/python/tui/app.py` | 会话状态、动作、缓存 | `App` `Block` `ImageItem` |
| `src/python/tui/ui.py` | 入口：启动参数、主循环、窗口初始化 | `loop` `main` `parse_args` |
| `src/python/tui/ui_base.py` | 文案、宽字符处理、颜色与落字 | `USAGE` `HELP` `dwidth` `cut` `pad` `init_colors` `attr` `put` |
| `src/python/tui/ui_draw.py` | 宽/窄两种布局的绘制 | `draw_frame` `draw_main` `draw_wide` `draw_narrow` `draw_map` `draw_settings` |
| `src/python/tui/ui_input.py` | 按键序列解析与单行输入 | `read_key` `edit_line` `KEYMAP` `SEQ_MAP` |
| `src/python/tui/ui_actions.py` | 按键分发与编辑动作 | `handle` `handle_map` `handle_settings` `edit_current` `edit_inline` |

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

`core.replace_image(rgb, alpha, jobs, opts, pool, tag="", memo=None, source=None, should_stop=None)`
逐个 `Job` 执行；`should_stop` 是可选中断回调，每处理一块之前问一次，返回 True 就停手并保留
已完成的块（TUI 的「Esc 取消」靠它，单张图内也能停在块与块之间）：

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
- `cv2.inpaint(..., radius, INPAINT_TELEA)` 修复，半径由 `inpaint_radius(mask)` 按笔画宽度算：
  `stroke = 2 × mean(distanceTransform(mask))`，`radius = clamp(round(stroke × 0.75), 4, 14)`。
  细体停在 4（不糊到邻居），粗体/大标题自动放大（固定 4 会在粗笔画上留模糊边）。
  常量：`INPAINT_RADIUS_MIN=4`、`INPAINT_RADIUS_MAX=14`、`INPAINT_STROKE_FACTOR=0.75`。
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

### 6.0.1 目录扫描与重新扫描

TUI 不在启动时因为"目录里没有图片"退出：空目录照样进界面，消息行提示放图片后按 `Ctrl-R`。
`App.rescan()` 按当前目录（或原始输入）重新收集图片，尽量保住原来的选中项，并给出
「重新扫描完成：N 张图片」的反馈——这是"先开界面、再拖文件进来"的唯一支持路径。

### 6.0 配置文件（`src/python/config.py`）

- 位置：`/data/config/retype.json`（`IMG_P_CONFIG` 可换文件名）；`scripts/setup.sh` 首次会写一份默认值。
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

**标题**：`retype v0.1 (2026-11-18) · 图片文字替换` —— 版本后面跟 `version.UPDATED`
（代码最后更新日期），反馈问题时一眼知道跑的是哪天的代码。写盘日志同样带
`app` / `app_version` / `app_updated` 三个字段。

**布局**（`ui_draw.py`）：外圈一圈 ACS 边框，标题在左上、页码在右上；
主体按宽度分档——`w >= 60` 双栏（左图右字，中间竖线），`24 <= w < 60` 单栏 +
右上角 `[宽x高]`，`w < 24` 或 `h < 10` 走「太窄了」提示页。
底部固定三行：详情（当前块与新文字的对照）/ 状态（输出目录、已保存、批量进度条）/
键位提示；键位提示按 `w < 40`、`w < 60`、其余三档给不同长度。
配色 8 组：title / sel / dim / ok / warn / err / accent / frame（`ui_base.PAIR`）。

**Windows**：TUI 依赖 `windows-curses`（`pyproject` 的平台标记 + `constraints.txt` 锁 2.4.2）；
该实现把 `curses.ACS_*` 暴露成 **int**，正是"线框必须走 addch"的直接原因。
CI 有独立 `windows-latest` 作业跑全量用例 + 类型 + 守护 + 耗时，避免"只在 Linux 绿"。

**绘制注意**：每帧最后必须 `win.refresh()`（只改缓冲区不刷新＝真机黑屏）；
线框一律 `addch`——`curses.ACS_*` 在部分构建里是 **int**，`addstr` 只收 str，
拼字符串会抛 `TypeError` 并被兜底吞掉，表现为整帧空白。

**主循环**：`read_key(win, timeout_ms=120)` 轮询（超时返回空串 → 重画一帧），
OCR 由 `App.start_loading()` 放到后台线程；`App.loading` 期间界面照常收键，
所以 Windows 上模型首次加载十几秒也不会"假死"。

**响应式约束**：所有文字走 `put()`（按显示列裁剪，中文占两列），
边框走 `addch`；`_support.FakeWin.addstr` 同样按显示列模拟，
所以 `test_layout_rendering.ResponsiveLayout` 能在 32~130 列之间断言"不溢出、不丢关键信息"。

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
| 字体池（磁盘） | `~/.cache/retype/fonts.json` | 字体文件签名 + 文本字符集 + 上限 | 跨进程复用，实测 0.137s → 0.018s；字体文件变动自动失效 |
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

性能门禁（`src/python/tools/check_perf.py`，CI 的 `perf` 作业）在合成数据上钉住四步热路径，
阈值 = 本机实测值 × 5 以上（只挡数量级退化，不追求机器间可比）：

| 项目 | 上限 |
| --- | --- |
| `soft_iou` × 50（220×48） | 1.0s |
| `erase`（2000×1500） | 1.5s |
| PNG 读写（2000×1500） | 2.0s |
| 日志追加 × 300 | 1.0s |
| 合计 | 6.0s |

实测后放弃的优化：**多线程并行处理多图**。在 15 张图和 4 张 20 块大图上分别测过
（`thread-local` OCR 引擎 + 两遍流程都并行），1/2/4 线程的耗时为 21.8 / 23.8 / 25.8 秒
与 7.8 / 8.9 / 10.0 秒 —— 并发只会更慢：OCR 的 onnxruntime 与会话本身已多线程，
且每线程一份模型初始化的开销远大于收益。因此保持单线程，代码也不保留这部分复杂度。

## 10. 测试策略

- 门禁（与 CI 同源，`./scripts/runTest.sh` 之外单独可跑）：
  `ruff check src/ scripts/`（零告警）、`python -m mypy`（全树 73 文件；core 严格注解、
  渠道/用例/脚本放宽）、`python -m src.python.tools.check_guards`（编号/分层/文件长度/显式编码/
  测试目录/版本号/名称/依赖锁/PS 编码/scripts 薄壳/目录树/测试字体/导入方向/文档索引/工作流，共 17 项）、`python -m src.python.tools.check_perf`（耗时守卫）。
  覆盖率阈值 `fail_under = 96`（实测约 97%）。
- 依赖可复现：`constraints.txt` 把直接依赖与其传递依赖全部精确固定，`setup.*` 与 CI 都用
  `pip install -c constraints.txt`；升级流程 = 改锁定 → 跑 `test.sh` 全绿 → 提交。
- 核心层：合成图（已知字体/字号/颜色）→ 断言 `fit_font` 选回原字体与字号、`analyze` 取回原字色。
- 渠道层：TUI 的 `App` 可用伪造 `win` 驱动 `handle()` 做无终端单测（整行/行内/映射/批准确认）。
- 端到端：`cli.sh data/demo --dry-run` 与 `cli.sh data/demo --map ...` 出图后人工比对原图。
- 回归样例：`data/demo/` 四张真图（`示例-报告.png` 标题/正文/负责人/日期；`示例-通知1..3.png` 三种标题与不同电话），
  `src/test/cli/test_demo_assets.py` 直接在它们上面跑真实读取、单图替换、行内替换、批量与日志。
- 自动测试：`src/test/` 按 `core/`（含 `primitives/` `layout/` `font/` `color/` `format/` `background/` `pipeline/`）、`cli/`、`tui/` 分目录，用例数随迭代变化（`unittest` 写、`pytest` 与 `unittest` 都能跑），覆盖匹配规则、
  块级任务、渲染与字距、图片读写格式表、合成图端到端（其它区域像素不变、memo 两次结果一致）、输出覆盖保护（`same_file` 与
  CLI 拒绝覆盖）、写盘日志（字段/追加/预演不记/日志失败不毁结果）、TUI 按键归一（转义序列/方向键/数字跳图/单 Esc 不退出）。
- 界面快照：`src/test/tui/test_screen_snapshots.py` 把 5 个尺寸 × 8 种状态的整屏文本存进
  `src/test/snapshots/tui.json`；布局漂移必须显式更新快照（`UPDATE_SNAPSHOTS=1`），
  这是"改界面要留证据"的门槛。
- 属性测试：`src/test/core/test_properties.py`（hypothesis）验证 `norm_map` 下标可回溯、
  `cut/pad` 不超预算、`parse_color` 只有两种结果、`unique_path` 不吞扩展名、`plan_jobs` 的 span 精准。
- 覆盖率门禁：`src/python/tools/check_coverage.py` 校验总量 96%、16 个高风险模块 80~90%、skip ≤15%。
- 入口冒烟：`src/test/cli/test_entry_smoke.py` 用 `runpy` **在本进程内**跑每个入口
  （`--version/--help/launch` 的退出码与帮助文本），不走子进程管道——避免 Windows
  上 cp1252 解码把 stdout 变成空串，从而把"程序坏了"和"测试读不到输出"混为一谈。
- CI 矩阵本地复现：`check_all --ci-matrix` 跑"cp1252 控制台 + C locale"与"无中文字体"两档。
- 变异测试（opt-in）：`src/python/tools/mutation_check.py`；依赖审计：CI `audit` 作业跑 `pip-audit --strict`。
- 字体相关用例统一走 `_support.cjk_font()`（逐候选字体 + 逐 index 探测，找不到就 skip），
  `IMG_P_TEST_NO_CJK_FONT=1 pytest src/test -q` 可在本地模拟"无中文字体"的机器。
- 开发依赖：`pyproject.toml` 的 `[project.optional-dependencies].dev`（pytest、pytest-cov、pytest-html、ruff、mypy）；
  `requirements.txt` = `-e .`、`requirements-dev.txt` = `-e .[dev]`，只为兼容既有脚本。

### 10.0.1 用例对照表（测试文件 → 需求/约束）

| 测试文件 | 守的是什么 |
| --- | --- |
| `core/test_mapping_rules.py` | FR-2 匹配规则：整行 / 行内子串 / 模糊兜底 |
| `core/primitives/test_style_analysis.py` | FR-3 样式沿用：字色、字重、倾斜反解 |
| `core/primitives/test_rendering_primitives.py` | FR-3 渲染与字距（`render_line`/`char_spans`/`solve_tracking`） |
| `core/primitives/test_erasing_and_drawing.py` | FR-2 擦除重绘、行内区间 |
| `core/primitives/test_inpaint_radius.py` | 自适应擦除半径（粗笔画不被糊） |
| `core/layout/test_text_layout.py` | FR-3 多行排版与对位 |
| `core/font/test_font_pool.py` | FR-3 字体发现、缓存路径、ttc 展开 |
| `core/color/test_alpha_channel.py`、`test_text_colors.py` | NFR 透明通道两路修正、字色反解 |
| `core/format/test_image_read_write.py` | FR-6 输出格式表、元数据、质量、覆盖保护 |
| `core/background/test_background_types.py` | FR-2 纯色 / 渐变 / 照片底图擦除 |
| `core/pipeline/test_replace_pipeline.py` | FR-2 端到端 + memo 幂等 |
| `cli/test_bootstrap_launch.py` | 环境引导与启动器：配置目录解析、建 venv、装依赖分支、`--check/--skip-install/--dev`、渠道分派与 `execv` 失败、平台路径 |
| `cli/test_log_query_cli.py` | 日志查询命令：过滤、`--json`、坏日期、无匹配 |
| `core/test_properties.py` | 属性测试：norm_map 下标、cut/pad 预算、颜色、unique_path、plan_jobs span |
| `core/test_feature_edges.py` | 功能边界：映射规则/颜色解析/任务构造/日志轮转/格式表 |
| `core/test_platform_stability.py` | 跨平台默认值（配置目录/解释器路径）、异常契约、规模与幂等 |
| `core/test_config_file.py` | FR-9 配置文件读取、容错、优先级 |
| `core/test_error_contract.py` | NFR-6 错误契约（`CoreError` 不外溢） |
| `core/test_ocr_contract.py` | FR-1 OCR 契约与缺依赖提示 |
| `core/test_write_audit_log.py` | FR-7 写盘日志字段 / 追加 / 并发 / 预演不记 |
| `core/test_log_query.py` | FR-11 日志查询与汇总 |
| `core/test_cancel_pipeline.py` | FR-10.4 单块级中断 |
| `core/test_version_display.py` | FR-12 版本号贯穿（横幅/标题/日志/文档） |
| `cli/test_arguments.py`、`test_single_image.py`、`test_batch_directory.py` | FR-4 参数、单图、批量与坏图跳过 |
| `cli/test_demo_assets.py` | 回归样例：`data/demo/` 真图 |
| `cli/test_entry_smoke.py` | 入口冒烟：`--version/--help/launch` 错误码 + shell 薄壳语法 |
| `cli/test_launch_env.py` | 启动器渠道分派与自动安装开关 |
| `tui/test_keys_and_navigation.py` | FR-5 按键归一、目录浏览 |
| `tui/test_interaction_edges.py` | 交互边界：样式面板非法输入、映射增删改、目录边界、批量取消 |
| `tui/test_key_dispatch.py` | FR-5 三块面板逐键 + 中断 + 非 ASCII 数字 |
| `tui/test_ui_shell.py` | TUI 外壳：参数解析、入口分支（缺路径/空目录/CoreError/中断）、主循环异常与 Esc/KEY_RESIZE、`read_key` 序列、基础绘制件 |
| `tui/test_screen_snapshots.py` | 界面快照：5 尺寸 × 8 状态的整屏文本（布局漂移即红） |
| `tui/test_layout_rendering.py` | FR-5 宽/窄屏响应式布局（32~130 列） |
| `tui/test_mapping_panel.py`、`test_settings_panel.py` | FR-5 映射表 / 样式面板编辑 |
| `tui/test_apply_and_batch.py` | FR-5、FR-10 替换、批量、进度与取消 |
| `tui/test_session_state.py` | FR-5 会话状态与缓存 |
| `tui/test_directory_browsing.py` | FR-5 目录进/退、选中记忆 |
| `tools/test_release_archive.py` | 归档流程：台账切开、整块搬运、主台账留头与索引、幂等与追加批次、索引倒序 |
| `tools/test_platform_safety_rules.py` | 守护「跨平台」的规则自检：写死字体家族 / 裸 bash / 无守卫 fcntl /
绝对像素阈值 / 断言里比 `sys.executable`，以及 `bash_exe()` 探测、字体矩阵候选顺序与换行符规则 |
| `tools/test_release_versions.py` | 版本策略：`0.3-dev`→`0.3` 定版、跨版本拒绝、`devbump` 切下个开发版、开发版不能打标签 |
| `tools/test_perf_limits.py` | 耗时守卫平台档：POSIX 用基准上限，Windows 只放大落盘步骤与总上限，且容得下实测 3.5s |
| `tools/test_gate_stamp.py` | 门禁戳：写/读/损坏戳、指纹随跟踪文件变化、未跟踪文件不影响、命令行退出码 |
| `tools/test_workflow_checks.py` | 工作流自检：bash 不可用时跳过语法检查、heredoc 禁令、合法 `python -m` 放行 |
| `tools/test_junit_summary.py` | CI 失败摘要：`class::name` 列表、失败+错误、报告缺失不报错、用法提示 |
| `tools/test_gen_folders_stats.py` | 目录统计重算：文件数/行数/用例数/示例图与合计行由脚本算，说明列不动 |

## 10.0 测试报告脚本

`scripts/runTest.sh` 是唯一的测试入口：跑 `src/test` 全量用例，生成
`/test-reports/{junit.xml,test-report.html,coverage/index.html,summary.md}`（`--fast` 跳过覆盖率与 HTML）；
目录不可写时退回 `./reports`。测试中间文件统一写 `/data/tmp`（`PYTHONPYCACHEPREFIX`、`TMPDIR`、
`COVERAGE_FILE` 都指过去），脚本结束时清掉仓库里的 `__pycache__` / `.pytest_cache`。
覆盖率基线约 80% 行覆盖，阈值写在 `pyproject.toml` 的 `fail_under`；入口文件（`cli/__main__.py`、`tui/__main__.py`）只有 4 行、不单独覆盖。

## 10.1 自测命令

```bash
./scripts/setup.sh                                            # 建环境（或者已有 .venv；等价 pip install -e ".[dev]"）
sh .githooks/install-hooks.sh                                 # 启用提交前门禁（ruff + guards + 用例）
./scripts/runTest.sh                                             # 全量用例 + 测试报告
.venv/bin/ruff check src/ scripts/                            # 静态检查，应零告警
.venv/bin/python -m mypy                                      # 类型检查，守 core
.venv/bin/python -m src.python.tools.check_all                        # 全量门禁（含覆盖率 + 三档矩阵）
.venv/bin/python -m src.python.tools.check_guards                      # 工程守护（18 项，含版本/依赖锁/归档）
.venv/bin/python -m src.python.tools.check_perf                        # 耗时守卫
.venv/bin/python -m src.python.tools.run_tests --fast                    # 测试编排（scripts/runTest.sh 的实现）
.venv/bin/python scripts/log-query.py --src 报告               # 查某个原图的写盘记录与替换次数
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
