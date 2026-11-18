# CLAUDE.md · retype

> 版本：v0.1

## 项目

retype（图片文字替换）：把图片里指定的一些字换成别的字，其余文字的内容与排版一个像素不动；
新文字自动沿用原文字的字体、字号、字重、字色、字距与位置，原图永不覆盖。

```text
scripts/                 只放薄壳启动脚本（.sh/.ps1 + log-query.py 壳；超 40 行守护会拦）
tools/                   工程工具：check_guards.py / check_perf.py / run_tests.py
.githooks/               仓库自带钩子：pre-commit（ruff + guards + 用例）、install-hooks.sh
.github/workflows/       ci.yml：test（3.10/3.12/3.13）/ lint / typecheck / guards / perf /
                         windows（windows-latest 跑全量用例）
pyproject.toml           单一配置源：依赖、可选依赖 dev、ruff、mypy、pytest、coverage
src/python/              程序代码
  config.py              路径约定（data/ 输入、data/output 输出）
  bootstrap.py           环境引导（建 venv、装依赖、写配置、--check 探测缺什么）
  launch.py              统一启动器：缺环境先自动装，再 exec 到真正入口
  core/                  核心层：OCR / 版式分析 / 字体匹配 / 擦除重绘 / 写盘审计
  cli/                   命令行渠道（main=替换流程，log_query=日志查询）
  tui/                   交互渠道：app.py 状态；ui.py 入口；browse.py 目录扫描；
                         ui_base/ui_draw/ui_input/ui_actions 分层
src/test/                测试用例
  _support.py            公共设施（字体路径、合成图、OCR 桩、FakeWin、用例基类）
  core/                  核心层用例（primitives/layout/font/color/format/background/pipeline）
  cli/  tui/             渠道与交互用例
data/  data/output/      输入图片 / 默认输出
docs/managements/  docs/manuals/   需求、技术设计 / 使用手册
src/test/__init__.py     测试包入口：把仓库根加入 sys.path，并把临时目录指向 /data/tmp
```

## 环境

- **一律使用项目虚拟环境解释器**：`.venv/bin/python`。**禁止**裸 `python` / `python3` / `pytest`
  （会命中系统解释器，缺 Pillow / numpy / cv2 / rapidocr，报 `ModuleNotFoundError`）。
- 首次准备：**不用手动跑**——任一启动脚本（`cli.sh` / `tui.sh` / `test.sh`）发现缺 `.venv`
  或关键依赖时会自动装（`src/python/launch.py` → `bootstrap.py`）；想手动或离线装依赖时
  `./scripts/setup.sh [--dev]`（= `python -m src.python.bootstrap`），设 `IMG_P_NO_AUTO_SETUP=1`
  可关掉自动安装。
- 依赖与工具配置只在 `pyproject.toml`；`requirements*.txt` 只是 `-e .` / `-e .[dev]` 的兼容壳；
  版本组合由 `constraints.txt` 锁定，安装与 CI 都要带 `-c constraints.txt`。
- 提交前门禁：`sh .githooks/install-hooks.sh` 启用（写 `core.hooksPath`），`IMG_P_SKIP_HOOK=1` 临时跳过。
- 配置文件：`/data/config/retype.json`（模板见 `/data/config/retype.example.json`，可用 `IMG_P_CONFIG` 指定）；
  测试中间文件写 `/data/tmp`，测试报告写 `/test-reports`。
- 入口：`./scripts/cli.sh`（= `python -m src.python.cli`）、`./scripts/tui.sh`（= `python -m src.python.tui`）；
  Windows 用 `scripts\cli.ps1` / `tui.ps1` / `setup.ps1` / `test.ps1`，虚拟环境解释器在 `.venv\Scripts\python.exe`。

```bash
.venv/bin/ruff check src/ scripts/                                 # 静态检查
.venv/bin/python -m mypy                                              # 类型检查（守 core）
.venv/bin/python tools/check_guards.py                              # 编号/分层/长度/编码/测试目录
.venv/bin/python tools/check_perf.py                                # 耗时守卫
.venv/bin/python scripts/log-query.py --src 报告                        # 查写盘记录
.venv/bin/python -m pytest src/test -q                                # 全部用例
./scripts/test.sh                                                     # 全量用例 + 报告
./scripts/cli.sh data --list                                          # OCR 是否正常
./scripts/cli.sh data --map "2023=2024" --dry-run                      # 批量预演
```

## 架构约束（硬性）

1. **`src/python/core` 是唯一实现替换逻辑的地方**。`cli` / `tui` 只做参数解析、编排与呈现，
   不得复制「找字体 / 擦除 / 绘制 / 匹配规则」的任何片段。
2. **`core` 不得 `import argparse` / `import curses`**，也不得 `sys.exit`：
   可预期失败一律抛 `core.errors.CoreError`，由渠道决定是报错退出还是只提示。
3. 任何新入口都必须先产出 `core.Job`（`rect / src / new / span`），再交给 `core.replace_image`
   执行；新增「输入 → Job」的转换放进 `core/jobs.py`。
4. **永不覆盖原图**：输出基路径与原图相同时（`-o 原图`、输出目录==输入目录）必须拒绝并提示；
   其余重名用 `core.image.unique_path()` 追加 `-1`、`-2`…（扩展名不变）。
5. 默认输出目录固定为 `data/output`（`src/python/config.py`），渠道只能通过参数/界面覆盖。
6. 有 alpha 的图，擦除与绘制必须同时修 RGB 与 alpha 两路，否则会留下原字形轮廓。

## 代码约定

- 界面文案、报错、注释、文档一律**中文**；标识符用英文（`Job`、`fit_font`）。
- 所有模块 `from __future__ import annotations`，公共函数写全类型注解；`core` 用纯函数 + 数据类。
- 文本 I/O 显式 `encoding="utf-8"`；不要裸 `open()`，不要依赖 locale。
- 捕获异常要具体（`OSError` / `ValueError` / `CoreError`），禁止 `except Exception: pass`；
  交互层允许顶层兜底，但要更新消息行而不是退出。
- 阈值、权重、窗口大小这类关键常量保持具名，改动后同步 `docs/managements/technical.md`。
- 单文件保持在千行以内；超过就按职责拆到 `core/` 的子模块。

## 测试纪律

- **三档维度都要有覆盖**，不要只盯一条路径：
  1. **图片处理**（`src/test/core/`，含 `primitives/` `layout/` `font/` `color/` `format/` `background/` `pipeline/`）：
     匹配规则、渲染与字距、字色/字号反解、擦除重绘、图片读写；
  2. **交互**（`src/test/tui/`、`src/test/cli/`）：按键归一、面板编辑、布局渲染、参数解析、批量流程与中断；
  3. **稳定**（跨档）：错误契约、幂等重跑、输出覆盖保护、缓存失效、异常不外溢。
- 门禁（本地与 CI 同源）：`ruff` 零告警、`mypy` 全树、`tools/check_guards.py` 十项全过、
  `check-perf.py` 不超阈值、覆盖率不低于 `pyproject.toml` 的 `fail_under`。
- **文件名与用例名必须写出被测内容**：`test_mapping_rules.py::test_fragment_key_only_covers_that_fragment`，
  禁止 `test_core.py`、`test_misc.py` 这类泛化命名。
- **修复缺陷必须补回归用例**（直接断言缺陷场景）；**新增功能必须带用例**；全部用例须保持全绿。
- `pytest` 与 `unittest` 都能跑；依赖 Noto CJK 字体的用例用 `skipUnless` 保护。
- 像素/浮点比较用容差（`assertAlmostEqual(delta=…)`、`assertLess`），不要 `==` 比两张图。
- 测试**不得**写项目里的 `data/`、`data/output/`；临时文件一律 `tempfile.TemporaryDirectory()`。
- 需要 OCR 的用例用 `_support.patch_ocr()` 打桩，别在测试里加载 RapidOCR；
  需要窗口的用 `_support.FakeWin` + `TuiTestCase.drive()`，不要起真终端。

## 文档纪律

- 三份文档随实现同步：
- `docs/managements/plan.md` 的任务编号一律 `PLAN-x`，`docs/managements/review-findings.md`
  的任务/缺陷编号一律 `RF-x`；两者连续编号、不复用，新增任务只在对应文件里追加。
  - `docs/managements/requirements.md`：功能/非功能需求（`FR-x`/`NFR-x`）与验收标准
  - `docs/managements/technical.md`：分层、模块表、算法与阈值、性能、测试文件对照表、扩展点
  - `docs/manuals/how-to-use.md`：安装、CLI/TUI 上手、参数、按键、FAQ、限制
- `README.md` 只保留简介 + 快速开始 + 文档索引，细节放上面三份里。
- 改 CLI 参数 → 同步 `README`/`how-to-use` 与 `src/python/cli/main.py` 的 `--help`；
  改 TUI 按键 → 同步 `src/python/tui/ui.py` 的 `HELP`/`USAGE`/底部键位提示与 `how-to-use.md` 按键表。
- 新增/移动任一源文件或测试文件 → 同步 `technical.md` 的目录结构、模块表与用例对照表。
- 不要主动新建「中间计划文件」「调试笔记」；确实需要就放 `/tmp`，不要入库。

## 已知坑

- `--area` 手工框里的原文若未被 OCR 认全，字体匹配会不准 → 会打印提示并退回默认字体，
  这时用 `--font` 或改用 `--map` 走整行匹配。
- 字体池缓存在 `~/.cache/retype/fonts.json`（按字体文件签名失效）；验证「首次构建」路径要先删缓存。
- Windows 专项：TUI 用 `windows-curses`（约束在 `constraints.txt`），它把 `curses.ACS_*`
  暴露成 int；改动绘制层后至少跑 `src/test/tui/test_layout_rendering.py` 的
  `WindowsStyleAcs`（把 ACS 常量换成 int 的模拟）与 CI 的 windows 作业。
- TUI 绘制两条铁律：① 每帧结尾必须 `win.refresh()`；② 线框只能 `addch`，不能把
  `curses.ACS_*`（可能是 int）拼进 `addstr`——两者出错都表现为真机黑屏，`FakeWin` 已按此收紧，
  另有 `test_tui_real_terminal.py` 用 `script(1)` 跑真 curses 冒烟。
- TUI 允许空目录启动：目录里没有图片时照样进界面，放好图片按 `Ctrl-R`（或 `F5`）重新扫描；
  这个键也是"先开界面、再复制文件进去"的唯一入口。
- 配置目录默认值分平台：POSIX 用 `/data/config`，Windows 用仓库内 `data/config`
  （Windows 没有 `/data`）；`IMG_P_CONFIG_DIR` 给相对路径时按仓库根解析。
- TUI 在手机/窄终端：宽度 < 60 列自动单栏；`Esc` 只返回不退出（退出用 `q`）；
  方向键原始转义序列由 `read_key()` 自己解析。
- **`scripts/*.ps1` 必须存成 UTF-8 with BOM**：Windows PowerShell 5.1 读无 BOM 的脚本按 ANSI
  （GBK）解释，文件里的中文提示会变成「缂哄皯杩愯鐜」这类乱码，用户完全看不懂；
  `check-guards.py` 的「PS 编码」会拦。
- 纯数字块容易被斜体字体凑上，`analyze` 会估倾斜并在正体时剔除 italic 候选。
- 输出重名会自动编号，所以「同一个命令跑两次」会产生 `-1`/`-2` 文件，这是预期行为。

## 交互纪律（同 `~/.pi/agent/AGENTS.md`）

- 一次问题一次收束：给结论就停，不追加确认、不复述历史。
- 不播报「让我看看 / 正在检查」这类中间态；一次回复里工具调用合并成一批。
- 输出精简：结论 → 依据（1~3 条）→ 动作；命令静默（`>/dev/null` 或 `| tail -1`）。
- 改完文件列清单（每行一个文件 + 一句改了什么），末尾给 `diff stat`；不贴 diff/日志除非要求。
- 出错先给原因与下一步，不堆日志、不猜。
