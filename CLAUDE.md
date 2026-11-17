# CLAUDE.md

## 项目

PNG 文字替换：把图片里指定的一些字换成别的字，其余文字的内容与排版一个像素不动；
新文字自动沿用原文字的字体、字号、字重、字色、字距与位置，原图永不覆盖。

```text
scripts/                 只有启动脚本：cli/tui/setup/test 的 .sh 与 .ps1（Windows）
src/python/              程序代码
  config.py              路径约定（data/ 输入、data/output 输出）
  core/                  核心层：OCR / 版式分析 / 字体匹配 / 擦除重绘
  cli/                   命令行渠道（参数、批量流程、输出汇总）
  tui/                   app.py 状态 + ui.py（curses 界面）
src/test/                测试用例
  _support.py            公共设施（字体路径、合成图、OCR 桩、FakeWin、用例基类）
  core/  tui/  cli/      按场景分类的用例
data/  data/output/      输入图片 / 默认输出
docs/managements/  docs/manuals/   需求、技术设计 / 使用手册
src/test/__init__.py     测试包入口：把仓库根加入 sys.path，并把临时目录指向 /data/tmp
```

## 环境

- **一律使用项目虚拟环境解释器**：`.venv/bin/python`。**禁止**裸 `python` / `python3` / `pytest`
  （会命中系统解释器，缺 Pillow / numpy / cv2 / rapidocr，报 `ModuleNotFoundError`）。
- 首次准备：`./scripts/setup.sh`；开发依赖：`.venv/bin/pip install -r requirements-dev.txt`。
- 配置文件：`/data/config/img-p.json`（模板见 `/data/config/img-p.example.json`，可用 `IMG_P_CONFIG` 指定）；
  测试中间文件写 `/data/tmp`，测试报告写 `/test-reports`。
- 入口：`./scripts/cli.sh`（= `python -m src.python.cli`）、`./scripts/tui.sh`（= `python -m src.python.tui`）；
  Windows 用 `scripts\cli.ps1` / `tui.ps1` / `setup.ps1` / `test.ps1`，虚拟环境解释器在 `.venv\Scripts\python.exe`。

```bash
.venv/bin/ruff check --select E,F,B,I --ignore E501 src/             # 静态检查
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
  1. **图片处理**（`src/test/core/`）：匹配规则、渲染与字距、字色/字号反解、擦除重绘、图片读写；
  2. **交互**（`src/test/tui/`、`src/test/cli/`）：按键归一、面板编辑、布局渲染、参数解析、批量流程；
  3. **稳定**（跨档）：错误契约、幂等重跑、输出覆盖保护、缓存失效、异常不外溢。
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
- 字体池缓存在 `~/.cache/img-p/fonts.json`（按字体文件签名失效）；验证「首次构建」路径要先删缓存。
- TUI 在手机/窄终端：宽度 < 60 列自动单栏；`Esc` 只返回不退出（退出用 `q`）；
  方向键原始转义序列由 `read_key()` 自己解析。
- 纯数字块容易被斜体字体凑上，`analyze` 会估倾斜并在正体时剔除 italic 候选。
- 输出重名会自动编号，所以「同一个命令跑两次」会产生 `-1`/`-2` 文件，这是预期行为。

## 交互纪律（同 `~/.pi/agent/AGENTS.md`）

- 一次问题一次收束：给结论就停，不追加确认、不复述历史。
- 不播报「让我看看 / 正在检查」这类中间态；一次回复里工具调用合并成一批。
- 输出精简：结论 → 依据（1~3 条）→ 动作；命令静默（`>/dev/null` 或 `| tail -1`）。
- 改完文件列清单（每行一个文件 + 一句改了什么），末尾给 `diff stat`；不贴 diff/日志除非要求。
- 出错先给原因与下一步，不堆日志、不猜。
