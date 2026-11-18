# 变更记录

> 版本：v0.1

> 按时间倒序记录对代码、用例与文档的实质变更。每条给出：做了什么、动了哪些文件、
> 对应需求与验证方式。只写结论，不贴 diff。

## 2026-11-18 — 覆盖率冲刺：84% → 96%

### 新增测试（83 例，6 个文件）

`src/test/core/test_coverage_gaps{,2,3}.py`：逐条对准"只有出错才走到"的分支——
- 引导与入口：`pip_install` 调用、`missing_modules` 的 OSError/非零退出、`python -m` 薄壳（runpy）
- CLI：读图失败跳过（第一/第二遍）、占名失败、保存失败后的占位文件清理、预演同名去重、摘要写失败
- core：日志打开/写入失败、坏 JSON 与坏日期日志名、缓存版本不符/不可读、调试图目录不可建、
  `reserve_path` 父目录不可建、`collect_images` 目录不可读、`fit_font` 渲染失败/空白渲染、
  `solve_tracking` 无墨迹、`ocr_crop` 空结果、`_winlock` 缺 msvcrt、`_run` 缺 fc-list
- tui：`image_window(0)`、滚动块列表、行内详情、窄屏加载提示/图片错误、`_status_text` 进度条、
  `_int` 脏数字、`put` 越界裁剪、`hline` 零列、`box` 过小、`init_colors` 失败退化、
  Ctrl-U / KEY_DC / KEY_HOME / ESC 取消、`apply_current` 无任务与进度、`apply_one` 保存/占名/读图失败

### 变更

- 删除 `cli/main.py` 中 `reserve_path` 之后重复的 `same_file` 判断（不可达的死代码）。
- 覆盖率门槛：`fail_under` 75 → **96**，`tools/check_coverage.py` 与 `coverage_report.py` 的
  `TOTAL_MIN` 同步；`coverage` 改为只统计行覆盖（分支覆盖在平台分支上无法收敛，仍可 `--cov-branch` 查看）。

### 未覆盖残余（4 行，已记录）

`core/style.py` 粗筛渲染失败的 `except` 日志、`core/audit.py` 的 msvcrt 缺失分支、
`tui/ui_actions.py` 的 Enter 整行编辑入口、`cli/main.py` 的"全部读取失败"退出。
这些需要刻意构造平台/异常环境才能命中，是否加 `pragma` 或继续补测见 `testplan.md` §5。

## 2026-11-18 — 参考 investor-review：架构约束 / 设计契约 / 发布流程 / 文档索引

### 新增

- `docs/managements/contracts.md`：AR-1..7 架构约束（依赖方向、分层、入口契约、文件长度、编码）、
  §2 核心 API / CLI / 数据 / 界面四类契约、§3 版本与兼容策略、§4 扩展点、§5 约束与守护对照。
- `docs/managements/releasing.md`：六步发布流程（check/prepare/gate/build/tag/publish）、
  版本策略、发布前清单、CI 侧发布、回滚方式。
- `tools/release.py`：上述六步的可执行编排；`tag`/`publish` 等有副作用的步骤必须 `--yes`。
- `tools/check_import_surface.py`：AST 检查导入方向——`core` 不导入 `cli`/`tui`，`cli`/`tui` 互不导入。
- `docs/README.md`：全仓文档索引。
- CI `release` 作业：推 `v*` 标签时跑全量门禁 → 构建 wheel/sdist + SHA256SUMS → `gh release create --verify-tag`。

### 变更

- 守护新增第 14 项「导入方向」、第 15 项「文档索引」（共 15 项）。
- `technical.md` 增 §1.2 依赖方向；`CLAUDE.md` 增导入方向硬约束与发布/文档索引纪律；
  `testplan.md` 增 QG-10 发布门禁与两类测试层（架构约束、发布）；README 文档索引补齐。

## 2026-11-18 — 补测薄弱模块，覆盖率 84% → 88.8%

### 新增测试（57 例）

- `src/test/cli/test_bootstrap_launch.py`（27 例）：配置目录解析（绝对/相对/平台默认）、
  建 venv 复用与新建、`missing_modules` 探测、`ensure_dependencies` 的自动/关闭/dev 三条分支、
  `write_config` 写入/不覆盖/不可写、`main --check|--skip-install|--dev`、
  渠道分派与 `execv` 失败退化、`IMG_P_NO_AUTO_SETUP` 开关、平台解释器路径。装依赖全部打桩，
  只验证"调了哪些命令"，不联网。
- `src/test/tui/test_ui_shell.py`（30 例）：`parse_args` 全量取值/非法值/`--help`、
  `main` 的缺路径/空目录提示/CoreError/KeyboardInterrupt→130/版本横幅、
  主循环的 Esc 归一/KEY_RESIZE/终端持续报错主动退出/单次与连续 Ctrl-C、
  `read_key` 的单字符/功能键/独立 Esc/转义序列/超时恢复阻塞、
  `progress_bar` 边界、`cut/pad` 极小预算、`box/divider` 小窗口、HELP/USAGE 关键项。

### 覆盖率变化

| 模块 | 之前 | 现在 |
| --- | ---: | ---: |
| `bootstrap.py` | 57.8% | 94.1% |
| `launch.py` | 71.9% | 93.8% |
| `tui/ui.py` | 60.5% | 95.0% |
| `tui/ui_base.py` | 78.1% | 81.2% |
| `tui/ui_input.py` | 81.0% | 81.0% |
| **总量** | 84.0% | **88.8%** |

### 变更

- `tools/check_coverage.py` 与 `tools/coverage_report.py` 的 `MODULE_MIN` 新增 7 项
  （bootstrap/launch/ui/ui_base/ui_input/cli-main/log_query），贴实测下沿防回落。
- `testplan.md` 的 QG-4 与门槛说明同步；`technical.md` 用例对照表补两个文件。

## 2026-11-18 — 测试计划与覆盖率报告

### 新增

- `docs/managements/testplan.md`：质量控制与测试标准——QG-1..9 可量化质量目标、P0/P1/P2 门禁分层、
  13 类测试的职责与位置、用例编写十条规范、覆盖率/性能/跨平台标准、缺陷分级（P0/P1/P2）、
  质量产物清单、合并前检查清单。
- `docs/managements/test-coverage.md`：覆盖率与分组统计（总览、模块覆盖率带门槛、包级汇总、
  场景测试分组、单元测试分组、薄弱点 top10），由 `tools/coverage_report.py --write` 生成。
- `tools/coverage_report.py`：读 `reports/{coverage,junit}.xml` 输出上述报告；
  `--write` 落盘，不带参数只打印。
- `src/test/cli/test_log_query_cli.py`：8 例覆盖日志查询命令（过滤/`--json`/坏日期/无匹配/`--help`）。

### 修复

- `audit.read_entries`：`--date` 指定某天而当天没有日志文件时，原来抛 `CoreError`（退出码 2），
  现在当作"没有记录"返回空列表。
- `cli/log_query.py` 覆盖率 0% → 92%（此前只有 core 层回读用例）。

### 变更

- `check_guards.py` 的版本一致性检查把 `testplan.md`、`test-coverage.md` 纳入。
- `technical.md`/`CLAUDE.md`/`README.md` 指向两份新文档；用例对照表补日志查询命令一行。

## 2026-11-18 — 文档全面校准（质量加固之后）

### 变更

- `folders.md`：统计表按实测重算（116 个代码/文档文件共 14,097 行，含示例图 122 个跟踪文件；436 个 `def test_`），
  测试一栏说明含属性/快照/入口冒烟；CI 一栏写七个作业与两类钩子。
- `technical.md`：用例对照表补 `test_properties.py`、`test_screen_snapshots.py`、
  `test_entry_smoke.py` 三行；测试策略写清快照/属性/覆盖率门禁/变异/审计的分工。
- `requirements.md`：新增 NFR-12（质量门禁分层：静态→结构→覆盖率→行为→快照→性能→审计）
  与 NFR-13（可复现的失败：平台差异都有本地模拟用例，CI 失败上传环境指纹）。
- `README.md`：门禁命令区补"提交前 quick / 推送前全量"与快照更新命令。
- `CLAUDE.md`：补覆盖率阈值清单、快照工作流、变异测试入口。

## 2026-11-18 — 质量管理加固（快照 / 属性 / 门禁 / 变异 / 审计）

### 新增

- 界面快照 `src/test/snapshots/tui.json`：5 尺寸 × 8 状态（正常/文字块/长路径/识别中/空目录/
  映射面板/样式面板/帮助）整屏文本；`UPDATE_SNAPSHOTS=1` 更新，diff 随代码提交。
- 属性测试 `src/test/core/test_properties.py`（hypothesis）：`norm_map` 下标可回溯、
  `cut/pad` 不超预算、`parse_color` 只有合法三元组或 `CoreError`、`unique_path` 不吞扩展名、
  `plan_jobs` 的 span 精准切片。
- `tools/check_coverage.py`：总量 ≥75%，`core/match|options` ≥90%，`core/edit|render|image|audit`
  与 `tui/ui_draw` ≥85%，`tui/app|ui_actions` ≥80%，正常模式 skip ≤15%；接入 `check_all`。
- `.githooks/pre-push`：推送前跑 `check_all` 全量（含覆盖率与无字体复跑）。
- `tools/mutation_check.py`：mutmut 试点脚本（opt-in），先跑 `core/match.py`。
- `tools/update_constraints.py`：`--check` 看可升级项、`--write` 按当前环境重写锁定（保留分档标记）。
- `src/test/cli/test_entry_smoke.py`：11 例入口冒烟（`--version/--help/launch` 错误码、tools `--help`、
  shell 薄壳语法检查）。
- CI：新增 `audit` 作业（`pip-audit --strict`）、环境指纹（python/platform/pip freeze/字体清单）
  与失败产物归档。

### 变更

- `pyproject.toml`：dev 依赖加 `hypothesis`、`pip-audit`；`coverage.fail_under` 70 → 75。
- `tools/{check_guards,check_coverage,check_perf}.py` 支持 `--help`（入口冒烟要求）。

## 2026-11-18 — 扩测：功能 / 交互 / 跨平台 / 稳定性

### 新增测试（70 例，3 个文件）

- `core/test_feature_edges.py`：`norm_map` 下标映射、`plan_jobs` 的整行/行内/多命中/模糊提示、
  `area_jobs` 非法输入、颜色三种写法与非法值、日志轮转（只删过期日志、不动别的文件）、
  `options_summary` 默认值省略、格式表与质量范围、alpha 压平 JPEG。
- `tui/test_interaction_edges.py`：样式面板留空=自动 / 全角数字 / 越界与非法值保留原设置、
  映射增删改与坏 JSON、目录浏览边界（不可读目录、隐藏文件、父目录行）、
  批量全无匹配与取消后重跑、翻页键与 `,`/`.` 等价键、`0`=第 10 张、帮助页任意键返回。
- `core/test_platform_stability.py`：平台默认值（`sys.platform` 打桩：POSIX `/data/config`、
  Windows 仓库内 `data/config`、venv 解释器路径）、配置解析（新名优先/旧名回退/环境变量/中文值/
  坏 JSON）、路径处理（相对与绝对同一文件、原子占名编号、目录尾斜杠）、
  `CoreError` 契约、40 块规模、字节级幂等、1×1 图不炸。

### 修复（新用例当场发现的缺陷）

- `parse_color`：`#12345` 被静默截断、`300,0,0` 照收 → 现在校验长度/字符集/0~255，越界抛 `CoreError`。
- TUI 样式面板字号：先赋值后校验，`-3` 会写进 `Options.size` → 改为先校验再赋值。
- `replace_image`：字体池为空时裸 `IndexError` → 改为 `CoreError("没有可用字体…")`。

## 2026-11-18 — 修 Windows TUI"按 q 没反应"

### 修复

- 主循环原来死等 `get_wch()`，而首帧里同步跑 `App.ensure_blocks()`（OCR）。
  Windows 上 onnxruntime 首次加载要十几秒，这段时间界面完全不收键。
- 改为：`read_key(win, timeout_ms=120)` 超时轮询（没键就重画一帧），
  OCR 由 `App.start_loading()` 放后台线程，`App.loading` / `loaded_event` 供界面与用例使用。
- 输入行 `edit_line` 也走同一套 `_read_one`，不再受窗口 timeout 状态残留影响。

### 测试（"小白鼠"换成自测）

- `NonBlockingInput`：超时返回空串且恢复阻塞模式、按 q 能拿到、无输入时每轮都重画、
  **识别中按 q 立即退出**。
- `BackgroundLoading`：后台线程真的跑起来并发出完成事件、重复调用只跑一次。
- `FakeWin.get_wch` 语义收紧：`None`＝本轮无输入，队列空＝用例结束；
  避免主循环带超时轮询后测试被"空队列当超时"卡死。

## 2026-11-18 — 本地一条命令对齐 CI（check_all）

### 新增

- `tools/check_all.py`：本机跑完 CI 的全部检查——ruff → mypy → guards → perf →
  用例（含覆盖率）→ "无中文字体"复跑；`--quick` 跳过后两项。失败即停，最后打印"全部通过 ✅"。
- 提交前钩子改为执行 `tools/check_all.py --quick`：提交一次就等于跑了一遍 CI 的静态与用例部分。

### 修复（本轮真实暴露）

- 标题加上版本与日期后变长，窄屏（44/50 列）右上角的 `[宽x高]` 放不下而被裁掉，
  两个布局用例失败。改为把尺寸标记放进底部状态行，标题行不再抢位置。

## 2026-11-18 — 界面与日志展示代码更新日期

### 新增

- `src/python/version.py` 新增 `UPDATED = "2026-11-18"`（代码最后更新日期）：
  TUI 标题 `retype v0.1 (2026-11-18) · 图片文字替换`、帮助页首行、CLI 横幅与 `--version`
  都带上它。
- 写盘日志新增 `app_updated` 字段（与 `app` / `app_version` 并列）。
- `tools/check_guards.py`：`UPDATED` 必须与 `git log -1 --format=%cs -- src` 一致，
  改了代码忘了改日期即红（无 git 时跳过）。
- 新增 5 个用例：标题 / 帮助页 / 日志字段 / `--version` / 日期格式。

## 2026-11-18 — 修 Windows 用例批量失败（字体探测）

### 修复

- 用例硬编码 `ImageFont.truetype(FONT_CJK, size, index=2)` 假设了 Noto 的 ttc 布局；
  Windows 的 `msyh.ttc` 无 index 2 → `OSError: invalid argument`，31 个用例失败。
- `_support` 新增 `cjk_font_spec()` / `cjk_font()`：逐候选字体、逐 index（0..9）探测可加载的
  组合并缓存；找不到就 `SkipTest`。`make_text_image()` 与所有遗留硬编码一并改走它。
- `test_posix_falls_back_to_common_font_dirs` 加 POSIX 条件。

### 可复现性

- 新增 `IMG_P_TEST_NO_CJK_FONT=1`：本地模拟"机器上没有中文字体"，
  `IMG_P_TEST_NO_CJK_FONT=1 pytest src/test -q` → 230 passed / 104 skipped / 0 failed。
- `tools/check_guards.py` 新增第 13 项「测试字体」：AST 扫描用例里的
  `ImageFont.truetype(FONT_CJK…)` 调用，出现即红（文档串里的示例不会误报）。

## 2026-11-18 — 目录树文档 folders.md

### 新增

- `docs/managements/folders.md`（对齐 investor-review 的写法）：项目统计表（按类别：主程序 /
  测试 / 工具 / 脚本 / CI / 文档 / 示例图，含文件数与行数）+ 逐行注释的目录树（109 个跟踪文件）
  + 排除项表（`data/output`、`logs`、`/data/tmp`、`/test-reports`、字体缓存、`.venv`）+ 维护规则。
- `tools/check_guards.py` 第 12 项「目录树文档」：解析树状图的缩进还原完整路径，逐个核对
  `src/`、`tools/`、`scripts/`、`docs/`、`.githooks/`、`.github/` 与根文件，缺一个即红。

### 变更

- `technical.md` 的「目录结构」加指引入口；README 文档索引新增「目录结构」一行；
  门禁项数文档同步 11 → 12。

## 2026-11-18 — scripts/ 只留 .sh/.ps1；test 更名 runTest

### 变更

- `scripts/` 里不留 `.py`：`scripts/log-query.py` 删除，改由 `scripts/log-query.sh` /
  `log-query.ps1` 调用 `python -m src.python.launch log-query`（逻辑仍在 `src/python/cli/log_query.py`）。
- `scripts/test.sh` / `test.ps1` 更名为 `scripts/runTest.sh` / `runTest.ps1`（实际执行的是
  `tools/run_tests.py`，避免"脚本名=测试框架名"的误导）。
- 守护 `scripts 薄壳` 收紧：`scripts/` 只允许 `.sh` / `.ps1`，出现 `.py` 直接报错。
- CI windows 作业的安装步骤改用 `shell: bash`：Windows 默认 PowerShell 把反斜杠续行当成参数，
  会报 `Directory '\' is not installable`。

## 2026-11-18 — Windows 覆盖

### 新增

- CI `windows` 作业（`windows-latest`）：全量用例 + `mypy` + `check_guards.py` + `check_perf.py`，
  避免"只在 Linux 绿"。
- `constraints.txt`：`windows-curses==2.4.2; sys_platform == "win32"`（TUI 在 Windows 的 curses 实现）。
- 用例 `WindowsStyleAcs`：把 `curses.ACS_*` 临时换成 int（Windows / 部分 Linux 构建的行为），
  断言布局正常、边框经 `addch` 逐格画出、无"界面绘制出错"。

### 说明

- Windows 没有 `script(1)`，真终端冒烟用例自动跳过；Windows 侧的保障是
  "全量用例 + ACS int 模拟 + 守护/类型/耗时在 windows-latest 上跑"。

## 2026-11-18 — 修复 TUI 黑屏（真机），补齐真终端冒烟

### 修复

- `ui_draw.draw_main` 漏了 `win.refresh()`：重写布局时只改缓冲区、从不刷屏，真终端一片黑。
- `ui_base.hline/vline` 用 `addstr` 拼 `curses.ACS_*`：本机构建的 ACS 常量是 **int**，
  `addstr` 只收 str → `TypeError` → `draw_frame` 兜底吞掉 → 整帧空白。改为一格格 `addch`。

### 测试

- `FakeWin` 提高保真度：`addstr` 只接受 str（传 ACS int 立即 TypeError）、`refresh()` 计数、
  `addch` 计数；新增 `RefreshFlush`（每个面板每帧必须刷新）与 `BorderDrawing`（边框确实画了）。
- 新增 `src/test/tui/test_tui_real_terminal.py`：用 `script(1)` 开伪终端跑真 curses，
  去掉转义序列后断言 `retype v`、`图片`、`识别到的文字` 与边框字符真的出现在屏幕上
  （POSIX + `script` 才跑，其余平台自动跳过）。

### 验证

- `ruff` 零告警、`mypy` 80 文件零错误、`check_guards.py` 12/12、369 用例全绿
  （含 2 个真终端冒烟用例）。

## 2026-11-17 — 文档全面校准（retype / v0.1）

### 变更

- 8 份文档统一到当前状态：程序名 `retype`、版本 `v0.1`、门禁 11 项
  （编号 / review 编号 / 分层 / 文件长度 / 显式编码 / 测试目录 / 版本 / 名称 / 依赖锁 / PS 编码 / scripts 薄壳）。
- 修正历史残留：字体缓存路径 `~/.cache/img-p` → `~/.cache/retype`（CLAUDE.md、technical.md）；
  门禁"六项" → "十二项"（requirements NFR-4、review-findings RF-43）；
  `mypy 守 core` → `mypy 全树`。
- 目录结构补全新分层：`tools/`（check_guards / check_perf / run_tests）、
  `src/python/{bootstrap,launch}.py`、`src/python/cli/log_query.py`、`src/python/tui/browse.py`、
  `ui_base/ui_draw/ui_input/ui_actions`；命令示例同步为 `tools/check_guards.py`。
- requirements 新增 FR-12.6（名称一致）与 FR-13（界面自适应：宽屏双栏 / 窄屏单栏 /
  极窄收缩 / 状态可见），验收口径补到需求侧。
- technical 补「用例对照表」：28 个测试文件 → 需求/约束。

### 验证

- `tools/check_guards.py` 12/12（含「版本号」与「名称」一致性检查）、
  `ruff` 零告警、`mypy` 79 文件零错误、全量用例 357 passed。

## 2026-11-17 — 技术债清理与架构核查

### 变更

- 新增 `src/python/tui/browse.py`：目录扫描/首张图定位抽成纯函数，`App` 从 637 行降到 615 行且只留状态与动作。
- `tools/run_tests.py`：删掉 `shutil.which("true")` 死条件；`ui_draw` 删掉 `_row` 空壳转发。
- `ui_actions`：面板分发改 `PANEL_HANDLERS` 查表（表在模块末尾定义）。
- 修缺陷：数字键判断从 `str.isdigit()` 改为 ASCII 白名单——上标「²」会通过 `isdigit()` 但
  `int("²")` 抛异常，一次误触就能把界面打崩；补回归用例。
- `technical.md` 补「用例对照表」：28 个测试文件 → 需求/约束。

### 架构核查（逐条对 CLAUDE.md）

- core 无 `argparse` / `curses` / `sys.exit`（守护第 3 项）；替换逻辑只在 core（`cli`/`tui` 无副本，
  已 grep `inpaint`/`fit_font`/`render_line`/`soft_iou` 零命中）。
- 新入口都先产出 `Job` 再走 `replace_image`；`launch`/`bootstrap`/`log_query` 不含替换逻辑。
- 不覆盖原图、默认输出 `data/output`、alpha 两路修正、单文件 <1000 行、文本 I/O 显式编码：均有守护或用例。

### 验证

- `ruff` 零告警、`mypy` 78 文件零错误、`check_guards.py` 12/12、全量用例全绿。

## 2026-11-17 — 更名 retype + TUI 进阶美化

### 变更

- 全程序更名 `retype`：`src/python/version.py` 的 `NAME` 为唯一来源，CLI 横幅与 `--version`、
  TUI 标题（`retype v0.1 · 图片文字替换`）、写盘日志 `app` 字段、pyproject 包名与控制台脚本
  `retype`、文档标题统一引用；守护新增「名称」检查。
- 配置默认读 `retype.json` / `retype.example.json`，旧 `img-p.json` 仍兼容；
  字体缓存目录改为 `~/.cache/retype`；环境变量保留 `IMG_P_*`，新增 `RETYPE_CONFIG`。
- TUI 界面重做：ACS 外框 + 左上标题 + 右上页码；双栏之间竖线；底部三行
  （详情 / 状态（输出目录、已保存、批量进度条）/ 键位提示）；8 组配色。
  窄屏三档自适应：`< 60` 单栏、`< 44` 表头只留计数、`< 40` 最短键位提示，并显示 `[宽x高]`。
- `_support.FakeWin.addstr` 改为按显示列写，布局用例能查出中文真实溢出。

### 验证

- 新增 7 个响应式布局用例（32~130 列不溢出、窄屏断点、键位提示长度）；
  `ruff` 零告警、`mypy` 78 文件零错误、`check_guards.py` 12/12、全量用例全绿。

## 2026-11-17 — 空目录可启动、配置目录分平台

### 新增

- `App.rescan()`：按当前目录（或原始输入）重新收集图片，尽量保住原选中项。
- TUI 键位 `Ctrl-R` / `F5`：重新扫描目录（先开界面、再放图片进目录的场景）。

### 变更

- TUI 不再因"目录里没有图片"退出：空目录照样进界面，消息行与左栏都会提示按 `Ctrl-R` 重新扫描。
- 默认配置目录按平台：POSIX `/data/config`，Windows 仓库内 `data/config`；
  `IMG_P_CONFIG_DIR` 的相对路径按仓库根解析（不再抛「需要绝对路径」）。

### 验证

- 新增 3 个用例（空目录启动、rescan 收新文件、`Ctrl-R` 走 `handle`）；
  `ruff` 零告警、`mypy` 78 文件零错误、`check_guards.py` 10/10、全量用例全绿。

## 2026-11-17 — 启动脚本自动准备环境

### 新增

- `src/python/launch.py`：统一启动器。`scripts/*` 先用系统 Python 调它，它探测 `.venv` 与
  关键依赖（PIL / numpy / cv2，跑测试时还要 pytest），缺则按 `constraints.txt` 自动安装，
  然后 `os.execv` 到 venv 里的真实入口。
- `bootstrap.py`：新增 `missing_modules()` / `ensure_dependencies()` / `--check`（只探测不改环境）。
- `src/test/cli/test_launch_env.py`：12 个用例固定渠道分派、自动安装开关、依赖探测与 `--check`。

### 变更

- 四个启动脚本不再要求"先跑 setup"：`cli` / `tui` / `test` / `log-query` 一律经 `launch`，
  首次运行自动装依赖并打印「首次运行，正在准备环境…」。
- `IMG_P_NO_AUTO_SETUP=1` 关闭自动安装：只提示缺什么，不改动环境（CI、离线、想手动控制时用）。

### 验证

- `./scripts/cli.sh --version`、`./scripts/log-query.py` 直接可用（未先跑 setup）；
  `ruff` 零告警、`mypy` 零错误、`check_guards.py` 10/10、`pytest` 全绿。

## 2026-11-17 — 目录归位：scripts 只留薄壳

### 变更

- `tools/`（新增）：`check_guards.py`（原 `scripts/check-guards.py`）、`check_perf.py`
  （原 `scripts/check-perf.py`）、`run_tests.py`（从 `scripts/runTest.sh` 抽出的编排逻辑）。
- `src/python/cli/log_query.py`（新增）：日志查询实现，`scripts/log-query.py` 变薄壳。
- `src/python/bootstrap.py`（新增）：环境引导（建 venv、按 constraints 装依赖、写默认配置），
  只用标准库，可被系统 Python 直接调用。
- `scripts/{setup,test}.sh`、`scripts/{setup,test}.ps1`：132/149/44/68 行 → 13/29/14/26 行，
  只负责找解释器与转交。
- `tools/check_guards.py` 新增第 10 项「scripts 薄壳」：单文件 >40 行即红。
- `pyproject.toml` 的 mypy 覆盖范围加上 `tools`。

### 验证

- `ruff` 零告警、`mypy` 75 文件零错误、`check_guards.py` 10/10、`run_tests.py` 与两个薄壳
  入口手工跑通（`./scripts/runTest.sh --fast -k test_version_display` → 8 passed + 摘要）。

## 2026-11-17 — Windows 脚本乱码修复

### 变更

- `scripts/{cli,setup,test,tui}.ps1` 全部改为 UTF-8 with BOM：PowerShell 5.1 对无 BOM 文件按
  ANSI 解码，中文提示会显示成「缂哄皯杩愯鐜」这类乱码。
- `tools/check_guards.py` 新增第 9 项「PS 编码」。
- 手册补「Windows 注意事项」：先跑 `setup.ps1`、BOM 要求、`windows-curses` 由平台标记安装。

## 2026-11-17 — 依赖锁定、单图内中断、交互用例补齐

### 新增

- `constraints.txt`：精确固定直接与传递依赖；`setup.sh` / `setup.ps1` / CI 全部改用
  `pip install -c constraints.txt`，升级路径写进文件头注释。
- `core.replace_image(should_stop=...)`：每处理一块之前询问回调，停手时保留已完成块。
- `tools/check_guards.py` 第 8 项：依赖锁（全部 `==` 且覆盖 pyproject 的直接依赖）。
- `src/test/tui/test_key_dispatch.py`：主界面 / 全局映射 / 样式选项三块面板的逐键用例 +
  批量中断；`src/test/core/test_cancel_pipeline.py`：核心层中断语义。

### 变更

- `App.apply_one` 接入 `should_stop`，`App.cancel` 在单张图内也生效；取消时返回「已取消」，
  `apply_all` 状态行显示「已取消，完成 x/n」。
- CLI 契约用例补强：`--version` 输出、版本横幅只走 stderr、坏图跳过不拖垮整批、
  日志记录 `app_version`。

### 验证

- `ruff` 零告警、`mypy` 73 文件零错误、`check-guards.py` 8/8、`check-perf.py` 通过；
  `pytest src/test -q` 297 passed，覆盖率 84%（`ui_actions.py` 55% → 88%，`ui.py` 64% → 82%）。

## 2026-11-17 — 版本号贯穿（v0.1）

### 新增

- `src/python/version.py`：`VERSION = "0.1"` 为唯一来源；`__init__` 再导出为 `__version__`；
  `pyproject.toml` 改为 `dynamic = ["version"]` + `attr = "src.python.version.VERSION"`。
- CLI：每次运行先往 stderr 打印 `retype 0.1`（`--version` 同步改为 `retype <版本>`）。
- TUI：进 curses 前打印同一行；标题栏显示 `文字替换 v0.1`，帮助页首行带版本。
- 写盘日志：每条记录新增 `app_version` 字段。
- 8 份文档（README、CLAUDE.md、三份管理文档、手册）开头统一 `> 版本：v0.1`。
- `tools/check_guards.py` 新增第 7 项：版本一致性（version.py / pyproject / 文档）。
- `src/test/core/test_version_display.py`：8 个用例固定上述链路。

### 变更

- `config.py` 的 `option_defaults()` 返回 `dict[str, Any]`、`apply_to_options()` 收窄参数类型；
  `cli/main.py` 的 `scans` 显式标注为 `list[dict[str, Any]]` —— 全树 mypy 覆盖后暴露的类型缺口。

### 验证

- `ruff check src/ scripts/` 零告警；`python -m mypy` 全树 71 文件零错误；
  `tools/check_guards.py` 7/7；`pytest src/test -q` 全绿（含新增版本用例）。

## 2026-11-10 — 工程化整改（配置/CI/门禁/分层/画质/可观测）

### 新增

- `pyproject.toml`：依赖与 `dev` extra、ruff、mypy（守 `core`）、pytest、coverage（`fail_under = 75`）；
  `requirements.txt` / `requirements-dev.txt` 改为 `-e .` / `-e .[dev]`。
- `.github/workflows/ci.yml`：test（3.10/3.12/3.13）/ lint / typecheck / guards / perf。
- `.githooks/pre-commit` + `install-hooks.sh`：提交前 ruff → guards → 全量用例。
- `tools/check_guards.py`（编号/分层/文件长度/显式编码/测试目录/空包）、`tools/check_perf.py`（四步热路径）、
  `scripts/log-query.py`（按原图/日期/渠道查写盘记录，支持 `--json`）。
- `core.audit.read_entries/summarize`（坏行跳过）、`record_write(when=)` 显式时间。
- `core.edit.inpaint_radius` 与常量 `INPAINT_RADIUS_MIN/MAX/STROKE_FACTOR`（4 / 14 / 0.75）。
- `App.apply_all(progress, should_stop)`：逐图进度 + Esc 中断；`App.cancel` 中断标志。

### 变更

- TUI 拆分：`ui.py`（入口/主循环/门面）+ `ui_base.py`（文案/宽字符/颜色）+ `ui_draw.py`（布局）+
  `ui_input.py`（按键/输入行）+ `ui_actions.py`（分发/编辑动作）；用例改为按层引用。
- 测试目录收敛：`src/test/image_processing/**` → `src/test/core/**`，删除空包 `degrade/`。
- 擦除半径从固定 4 改为按笔画宽度自适应（粗笔画不再留糊边）。
- 源码里所有 `int(arr.min())` / `arr.max()` 改为内建 `min()/max()`，不再依赖 numpy 类型桩的 axis 重载。

### 验证

- `ruff check src/ scripts/` 零告警；`python -m mypy` 零错误；`tools/check_guards.py` 6/6；
  `tools/check_perf.py` 合计约 0.6s（上限 6s）；`pytest src/test -q` 全绿。

## 2026-11-10 — 配置、临时目录与仓库清理

### 新增

- 配置文件：`/data/config/retype.json`、示例 `/data/config/retype.example.json`（都在配置目录里，
  由 `setup.sh`/`setup.ps1` 生成，`IMG_P_CONFIG` 可覆盖实际读取的文件）；
  `config.load_config()` / `option_defaults()` / `apply_to_options()`，优先级为
  命令行/界面 > 环境变量 > 配置文件 > 内置默认；`setup.sh`/`setup.ps1` 首次写默认值。
- 环境变量：`IMG_P_OUT_DIR` 新增，另有 `IMG_P_DATA_DIR`、`IMG_P_LOG_DIR`。

### 变更

- 测试中间文件统一写 `/data/tmp`（`TMPDIR`、`PYTHONPYCACHEPREFIX`、`COVERAGE_FILE`、`tempfile.tempdir`）。
- 测试报告改写到 `/test-reports`（不可写时退回 `./reports`）。
- 删除根目录 `conftest.py` 与 `pytest.ini`：仓库根不再放任何配置文件，
  `src/test/__init__.py` 负责 sys.path 与临时目录；清理所有 `__pycache__`，
  `scripts/test.{sh,ps1}` 结束自动清理仓库缓存。

### 用例

- `src/test/core/test_config_file.py`：缺失/非法/未知键、优先级、类型过滤、只填未设置项。

### 验证

- `ruff check ... src/` 零告警；`pytest src/test -q`：236 passed。

## 2026-11-10 — 示例图用于测试与文档

### 新增

- `src/test/cli/test_demo_assets.py`：直接拿 `data/demo/` 四张真图跑真实流程（读取、整行替换、
  行内替换、批量、预演不写盘、日志字段），OCR 仍用与真图一致的坐标桩。
- 文档补示例图清单与真实 `--list` 输出，示例命令改用 `data/demo/`。

### 修复

- `data/demo/示例-报告.png` 之前是占位图（只有「第0行文字」），与文档描述不符；
  已重新生成：标题「年度销售报告2023」+ 正文 + 负责人 + 日期。

### 验证

- `ruff` 零告警；`pytest src/test -q`：225 passed。

## 2026-11-10 — 目录浏览与默认数据目录（FR-5.13 / FR-5.14）

### 新增

- TUI 目录浏览：`d` 打开浏览面板，列出上级、子目录与当前目录图片；`Enter` 进目录/选图，
  `Backspace` 回上级，`Esc` 返回。`App` 新增 `dir / browse_entries / browse_sel` 与
  `refresh_browse()` `open_dir()` `browse_into()` `browse_parent()`。
- 默认数据目录：`config.default_input()`（`IMG_P_DATA_DIR` > `/data` > 仓库 `data/`），TUI 无参数时使用。

### 修复

- TUI 用例不再依赖仓库 `data/` 的实际内容（`_support.make_app` 自带临时图片），避免目录变动导致误报；
  并发日志用例改用 `spawn` 子进程，Windows 也能跑。

### 用例

- 新增 `src/test/tui/test_directory_browsing.py`（10 个：列表内容、进子目录、回上级、选图、
  隐藏项过滤、选择越界、按键驱动、默认目录优先级）。

### 验证

- `ruff` 零告警；`pytest src/test -q`：218 passed。

## 2026-11-10 — 缺陷复查（质量/锁/TUI 状态）

### 修复

- `core/image.save_image`：`--quality` 之前只作用于 JPEG，WEBP 被忽略；改为 JPEG/WEBP 都生效，
  并在核心层校验 1-100（越界抛 `CoreError`，不再只靠渠道校验）。
- `core/audit`：Windows 上日志写入没有锁；新增 `msvcrt.locking` 分支，POSIX 仍用 `flock`。
- `tui/app.py`：质量填错时会把已设的值重置成自动 → 改为保留原值并提示；
  应用上一张图时的核心层警告会残留到下一张 → 进入替换流程前清空。

### 用例

- WEBP 质量改变体积、核心层拒绝非法质量、三进程并发写日志不撕行、
  TUI 非法质量保留旧值、警告按图清理。

### 验证

- `ruff` 零告警；`pytest src/test -q`：208 passed。

## 2026-11-10 — Windows / PowerShell 支持

### 新增

- `scripts/setup.ps1`（支持 `-Dev`）、`scripts/cli.ps1`、`scripts/tui.ps1`、`scripts/runTest.ps1`（支持 `-Fast`），
  与 `.sh` 版功能对齐：UTF-8 控制台、参数原样透传、非终端拒绝 TUI、测试报告汇总复用同一段 Python。
- `requirements.txt`：`windows-curses; sys_platform == "win32"`，Windows 上 TUI 才能跑起来。

### 修复

- `core/fonts.py`：无 fontconfig 时（Windows）也能找到字体——`font_dirs()` 区分系统，
  Windows 读 `%WINDIR%\Fonts` 与 `%LOCALAPPDATA%\Microsoft\Windows\Fonts`；缓存目录改用 `%LOCALAPPDATA%`。

### 用例

- 字体目录/缓存路径：POSIX 与 Windows 两个分支（`test_font_pool.py`）。

### 文档

- README、`how-to-use.md`、`technical.md`、`CLAUDE.md` 补 Windows 入口与环境说明。

## 2026-11-10 — 技术债清偿与功能提升（FR-6.7 / 6.8 / 7.6 / 7.7 / 8）

### 技术债

- 日志：`flock` 串行 + `fsync` 落盘（不再怕并发交错与断电丢记录）；`prune_logs()` 自动清理 30 天前日志。
- 输出占名：新增 `core.image.reserve_path()`（`O_CREAT|O_EXCL`），替换先查后写的 `unique_path` 竞态；
  CLI/TUI 都改用它，失败时清理占位空文件。
- TUI 警告：`Options.warn` 回调 + `core.options.warn()`，核心层提示进消息行而不是 stderr 冲屏。
- 输出质量：`Options.quality`、`save_image(quality=)`、CLI `--quality`、TUI 样式面板「JPEG 质量」。
- 日志可校验：每条记录新增 `dst_sha256`、`dst_width`、`dst_height`。
- 用例不再往仓库 `data/output/` 留产物（改为前后快照 + 清理），历史测试产物已删除。

### 新功能

- FR-6.7 元数据保留：`load_meta()` 读 ICC/EXIF/DPI，`save_image(meta=)` 按格式白名单带上。
- FR-8 运行摘要：CLI `--report FILE` 输出 JSON 摘要（含 `dry_run`、逐图操作明细）。
- TUI 参数补齐：`--quality`、`--log-dir`。

### 用例

- 新增：reserve_path 原子占名与自动建目录、JPEG 质量改变体积、ICC/DPI 读取与带出、
  日志轮转与可关闭、sha256/尺寸入日志、`--report` 摘要、`--quality` 越界、TUI 参数解析与质量设置。

### 验证

- `ruff check --select E,F,B,I --ignore E501 src/ conftest.py`：零告警。
- `pytest src/test -q`：201 passed。

## 2026-11-10 — 图片写盘日志（FR-7）

### 新增

- `src/python/core/audit.py`：写盘日志核心。`record_write()` 追加 JSONL，
  `build_entry()` 组装记录，`log_path()` 按天给文件名，`options_summary()` 只保留显式设置项。
- `logs/` 目录约定：`image-writes-YYYYMMDD.log`，一行一个 JSON 对象，UTF-8、只追加。
- 记录字段：`time` `channel` `action` `src_file` `src_path` `src_size` `dst_file` `dst_path`
  `dst_size` `replaced` `operations[]` `options`。
- `src/test/core/test_write_audit_log.py`：27 个用例（去重后）。记录层（字段完整性、多操作、按天命名、目录自建、
  JSONL 逐行可解析、时间带时区、默认选项与运行期字段不写成噪声、不可写时的错误契约）；
  CLI（真实保存记账、预演不记、二次保存追加、调试图单独记账、`--dry-run` 忽略 `--debug`、
  `--log-dir` 优先于环境变量、保存失败不记、日志失败不影响退出码与出图、批量逐图记账）；
  TUI（保存记账、重跑追加、拒绝覆盖不记、无新文字不记、日志失败仍报保存成功、批量逐图记账）。

### 修改

- `src/python/config.py`：新增 `LOG_DIR` 与 `log_dir()`（`IMG_P_LOG_DIR` 可覆盖）。
- `src/python/core/options.py`：`Options` 增加 `log_dir`、`channel` 字段。
- `src/python/core/edit.py`：`replace_image` 增加 `source` 参数；`--debug` 的 mask 图写入后记账。
- `src/python/core/__init__.py`：导出 `record_write` / `build_entry` / `log_path` / 动作常量。
- `src/python/cli/main.py`：新增 `--log-dir`，保存成功后记账，日志失败只提示不失败；
  `--dry-run` 下忽略 `--debug`（预演不写任何文件，包括调试图）。
- `src/python/tui/app.py`：默认日志目录 `logs/`、渠道标记 `tui`，保存成功后记账。
- `src/test/image_processing/layout/test_text_layout.py`：导入按 ruff 规则整理；宽字距用例
  的阈值改为与原图宽度比较（原阈值 200 大于测试图片本身能画出的 191，属于不可满足的旧断言）。
- `.gitignore`：忽略 `logs/`。

### 文档

- `docs/managements/requirements.md`：新增 FR-7（5 条）并补充 NFR-6 可追溯性。
- `docs/managements/technical.md`：模块表新增 `core/audit.py`，目录结构补 `logs/`，新增 §7.1 写盘日志，
  错误处理表补「日志写不进」，扩展点补日志格式调整。
- `docs/manuals/how-to-use.md`：新增 §6.1 写盘日志（位置、字段示例、覆盖方式）与 `--log-dir` 参数。
- 新增 `docs/managements/plan.md`、`docs/managements/review-findings.md`、本文件。

### 修复（代码/功能复查）

- `src/python/core/image.py`：`load_image` 的 alpha 改为从 `convert("RGBA")` 统一取（调色板 `tRNS` 不再丢透明），
  全不透明才返回 `None`；`save_image` 对不支持的扩展名抛 `CoreError`。
- `src/python/core/edit.py`：`--debug` 的 `cv2.imwrite` 检查返回值，失败抛 `CoreError` 且不记日志。
- `src/python/tui/app.py`：初始化强制 `opts.quiet=True`（避免核心层 stderr 冲花 curses）；
  `img.saved` 复用改为 `abspath` 比较目录；保存失败同时捕 `CoreError`。
- `src/python/cli/main.py`：修正 `--out-dir` 帮助文本；保存失败同时捕 `CoreError`。
- 用例：`test_image_read_write.py` +3（不支持格式、调色板透明、全不透明 RGBA）、
  `test_single_image.py` +1（非法输出扩展名给一句话）、`test_apply_and_batch.py` +1（TUI 必须 quiet），
  并收窄该文件的 Optional 类型告警。

### 验证

- `ruff check --select E,F,B,I --ignore E501 src/ conftest.py`：零告警。
- `pytest src/test -q`：188 passed，全部用例通过。
