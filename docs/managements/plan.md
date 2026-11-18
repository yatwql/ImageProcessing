# 计划任务

> 版本：v0.1

> 范围：`retype`（图片文字替换）。本文件只列任务与验收口径，不写实现细节；
> 实现细节进 `technical.md`，结果进 `changelog.md`，问题进 `review-findings.md`。
> **编号约定**：本文件的任务一律 `PLAN-x`（连续编号，按出现顺序递增，不复用）；
> `review-findings.md` 里的任务一律 `RF-x`。

## 1. 当前目标（2026-11-10）

| 编号 | 任务 | 验收标准 | 状态 |
| --- | --- | --- | --- |
| PLAN-1 | 图片真实写盘后落日志 | 每次保存或写调试图都追加一条记录，含时间、源/目标文件名与大小、替换明细 | 完成 |
| PLAN-2 | 日志目录与格式 | 默认 `logs/`，按天分文件，JSONL 只追加；`--log-dir` / `IMG_P_LOG_DIR` 可覆盖 | 完成 |
| PLAN-3 | 两个渠道都接入 | CLI 与 TUI 保存成功后各写一条，渠道字段可区分；`--dry-run` 不写 | 完成 |
| PLAN-4 | 日志失败不破坏结果 | 日志写不进只提示一句，图片保留、退出码不变 | 完成 |
| PLAN-5 | 用例与文档同步 | 新增 `test_write_audit_log.py`（27 个用例，覆盖记录/CLI/TUI），需求/技术/手册三处更新 | 完成 |
| PLAN-6 | 代码/功能复查与整洿 | 透明格式、输出格式、TUI 屏幕干扰、调试图审计、输出目录比较均修正并有用例 | 完成 |

## 2. 功能提升（2026-11-10 复盘立项）

| 编号 | 方向 | 内容 | 状态 |
| --- | --- | --- | --- |
| PLAN-7 | 图片处理 | 输出保留 ICC/EXIF/DPI 元数据（`load_meta` / `save_image(meta=)`） | 完成 |
| PLAN-8 | 图片处理 | JPEG/WEBP 输出质量可调（`--quality` / TUI 面板） | 完成 |
| PLAN-9 | 可观测 | CLI `--report FILE` 输出运行摘要 JSON（含逐图明细与 `dry_run`） | 完成 |
| PLAN-10 | 交互一致性 | TUI 补齐 `--quality`、`--log-dir` 启动参数 | 完成 |
| PLAN-11 | 图片处理 | 擦除质量：按笔画宽度自适应 inpaint 半径，大块文字减少糊边 | 待办 |
| PLAN-12 | 图片处理 | 竖排/旋转文字识别与按角度重绘 | 待办 |
| PLAN-13 | 交互 | TUI 日志面板（`l` 查看当天写盘记录、按图名过滤） | 待办 |
| PLAN-14 | 交互 | TUI 批量执行进度 + 中途取消（Esc） | 待办 |
| PLAN-15 | 图片处理 | 多行段落整体替换（跨行排版连续） | 待办 |
| PLAN-16 | 工程 | 配置文件 `/data/config/retype.json`、测试临时目录 `/data/tmp`、报告目录 `/test-reports` | 完成 |
| PLAN-17 | 测试/文档 | 用 `data/demo/` 真图做用例与文档示例（含示例图清单） | 完成 |
| PLAN-18 | 交互 | 数据目录浏览：进子目录 / 回上级 / 选中图片；默认目录 `/data`（可 `IMG_P_DATA_DIR` 覆盖） | 完成 |

## 3. 下一批（待排期）

| 编号 | 任务 | 验收标准 | 状态 |
| --- | --- | --- | --- |
| PLAN-19 | 修复宽字距用例断言 | 用例改为与原图宽度比较（原阈值不可满足），已通过 | 完成 |
| PLAN-20 | 日志查询小工具 | 可按原图名/日期过滤日志并汇总替换次数 | 待定 |
| PLAN-21 | 日志轮转 | 已完成：保留最近 30 天，写入时清理更早的按天文件 | 完成 |
| PLAN-22 | 报告字段补齐 | 行内替换同时记录命中子串与坐标范围 | 待定 |
| PLAN-23 | 日志并发安全 | 多进程同时出图时日志行不交错（文件锁或单片事件） | 待定 |
| PLAN-24 | TUI 提示回填 | 核心层警告显示在消息行，而不是只能被 quiet 屏蔽 | 待定 |
| PLAN-25 | JPEG 质量参数 | CLI/TUI 可指定输出质量，默认保持 95 | 待定 |
| PLAN-26 | 日志可校验 | 记录输出图尺寸与哈希，可校验文件未被事后替换 | 待定 |

## 4. 约束提醒

- 写盘日志属于核心能力，实现只能在 `core/audit.py`，渠道不得自己拼 JSON。
- 任何新增写图片的路径（新格式、导出、缩略图）都必须调用同一个 `record_write`。
- 用例不得写仓库 `logs/`、`data/`，一律用临时目录 + `IMG_P_LOG_DIR`。

## 5. 工程化与打磨（2026-11-10 全面评估后落地）

| 编号 | 任务 | 验收标准 | 状态 |
| --- | --- | --- | --- |
| PLAN-27 | 配置单一来源 | `pyproject.toml` 承担依赖、可选依赖 `dev`、ruff、mypy、pytest、coverage；`requirements*.txt` 退化为 `-e .` 兼容壳；`pip install -e .` 可用 | 完成 |
| PLAN-28 | CI 流水线 | `.github/workflows/ci.yml`：test（3.10/3.12/3.13）/ lint / typecheck / guards / perf 五个作业，测试与覆盖率报告按 Python 版本上传 | 完成 |
| PLAN-29 | 提交前钩子 | `.githooks/pre-commit` + `install-hooks.sh`：ruff → guards → 全量用例；`IMG_P_SKIP_HOOK=1` 可跳过 | 完成 |
| PLAN-30 | 工程守护脚本 | `tools/check_guards.py`：编号（PLAN-/RF-）、分层（core 禁 argparse/curses/sys.exit）、单文件 ≤1000 行、文本 I/O 显式 encoding、测试目录与文档一致、无空测试包 | 完成 |
| PLAN-31 | 类型检查 | `mypy` 守 `src/python/core`（`disallow_untyped_defs`），渠道层放宽；`python -m mypy` 零错误 | 完成 |
| PLAN-32 | 覆盖率门禁 | `[tool.coverage.report] fail_under = 75`，CI 跑 `--cov` | 完成 |
| PLAN-33 | 性能门禁 | `tools/check_perf.py` 钉住 soft_iou / erase / PNG 读写 / 日志追加四步，合计 ≤6s | 完成 |
| PLAN-34 | 测试目录收敛 | `src/test/image_processing/**` 并入 `src/test/core/**`，删除空包 `degrade/`；文档结构同步 | 完成 |
| PLAN-35 | TUI 分层 | `ui.py` 856 行拆成 `ui_base` / `ui_draw` / `ui_input` / `ui_actions` + 门面 `ui.py`（每个 <300 行） | 完成 |
| PLAN-36 | 自适应擦除半径 | `edit.inpaint_radius` 按笔画宽度定半径（4~14），粗笔画不再留糊边 | 完成 |
| PLAN-37 | 批量进度与中断 | `app.apply_all(progress, should_stop)`：逐图进度（序号/总数 + 图名）、Esc 中断并显示「已取消，完成 x/n」 | 完成 |
| PLAN-38 | 日志查询 | `core.audit.read_entries/summarize` + `scripts/log-query.py`（按原图/日期/渠道、`--json`） | 完成 |
| PLAN-39 | 环境脚本健壮性 | venv 迁移后 `.venv/bin/pip` 的 shebang 会失效：安装依赖统一走 `.venv/bin/python -m pip` | 完成 |
| PLAN-40 | 版本号单一来源 | `src/python/version.py` 定义 `VERSION`，`pyproject.toml` 用 dynamic 读取，`__init__` 再导出为 `__version__` | 完成 |
| PLAN-41 | 运行时报版本 | CLI 每次运行先打印 `retype 0.1` 到 stderr；TUI 进 curses 前打印同一行 | 完成 |
| PLAN-42 | 界面显示版本 | TUI 标题栏 `文字替换 v0.1`、帮助页首行带版本 | 完成 |
| PLAN-43 | 日志记版本 | 每条写盘日志新增 `app_version` 字段 | 完成 |
| PLAN-44 | 文档与守护 | 8 份文档开头统一 `> 版本：v0.1`；`check-guards.py` 新增版本一致性检查（第 7 项） | 完成 |
| PLAN-45 | 依赖锁定 | `constraints.txt` 固定全部直接/传递依赖；`setup.sh`/`setup.ps1`/CI 均用 `-c constraints.txt`；守护第 8 项校验"精确固定且覆盖直接依赖" | 完成 |
| PLAN-46 | 单图内可中断 | `replace_image(should_stop=)` 每块之前询问，TUI 传入 `self.cancel`；`apply_one` 取消时返回「已取消」 | 完成 |
| PLAN-47 | 交互用例补齐 | 新增 `test_key_dispatch.py`（主界面/映射/样式三块面板 + 批量中断）与 `test_cancel_pipeline.py`（核心中断），覆盖率 80% → 84%，`ui_actions.py` 55% → 88%、`ui.py` 64% → 82% | 完成 |
| PLAN-48 | 契约用例补强 | CLI `--version`、版本横幅只走 stderr、坏图跳过不拖垮整批、日志记录 `app_version` | 完成 |
| PLAN-49 | Windows 脚本编码 | `scripts/*.ps1` 统一改为 UTF-8 with BOM，修掉 PS 5.1 下「缺少运行环境」等中文提示变乱码的问题；守护新增第 9 项「PS 编码」 | 完成 |
| PLAN-50 | 目录归位 | `scripts/` 只留薄壳：`check-guards.py`/`check-perf.py` 移到 `tools/`（check_guards.py / check_perf.py），日志查询逻辑进 `src/python/cli/log_query.py`，`scripts/log-query.py` 变壳；`setup`/`test` 逻辑进 `src/python/bootstrap.py` 与 `tools/run_tests.py`，两端 .sh/.ps1 从 44~149 行降到 13~29 行 | 完成 |
| PLAN-51 | 守护 | `check_guards.py` 新增「scripts 薄壳」（单文件 ≤40 行），防逻辑再堆回 `scripts/` | 完成 |
| PLAN-52 | 自动准备环境 | 新增 `src/python/launch.py`：启动脚本先经它探测 `.venv` 与关键依赖，缺则按 `constraints.txt` 自动安装，再 exec 到真实入口；`IMG_P_NO_AUTO_SETUP=1` 可关闭 | 完成 |
| PLAN-53 | 用具覆盖启动链路 | 新增 `src/test/cli/test_launch_env.py`（12 用例）：渠道分派、参数校验、自动安装开关、缺依赖探测、`--check` 不改环境 | 完成 |
| PLAN-54 | 空目录可启动 | TUI 不再因"目录里没有图片"退出：照样进界面并提示放图片后按 `Ctrl-R`；新增 `App.rescan()`（保留选中项）与 `Ctrl-R`/`F5` 绑定 | 完成 |
| PLAN-55 | 配置目录分平台 | `bootstrap`/`config` 的默认配置目录按平台取（Windows 用仓库 `data/config`），`IMG_P_CONFIG_DIR` 相对路径按仓库根解析，不再抛"需要绝对路径" | 完成 |
| PLAN-56 | 统一名称 | 全程序改名 `retype`：`version.NAME` 为唯一来源，CLI 横幅/`--version`、TUI 标题、写盘日志 `app` 字段、pyproject 包名与控制台脚本、文档标题全部一致；守护新增「名称」检查 | 完成 |
| PLAN-57 | 配置文件改名 | 配置默认读 `retype.json`（模板 `retype.example.json`），旧 `img-p.json` 仍兼容读取；字体缓存目录改为 `~/.cache/retype` | 完成 |
| PLAN-58 | TUI 进阶美化 | 外框+标题/页码、双栏竖线、底部三行（详情/状态/键位）、批量进度条、8 组配色；窄屏三档自适应（44/60 列断点）并给 `[宽x高]` 标记 | 完成 |
| PLAN-59 | 布局用例 | `FakeWin.addstr` 改为按显示列模拟，新增 `ResponsiveLayout`（32~130 列不溢出、关键信息不丢） | 完成 |
| PLAN-60 | 技术债清理 | `App` 的目录扫描抽到 `tui/browse.py`（纯函数）；去掉 `run_tests.py` 里的死条件与 `ui_draw._row` 空壳；面板分发改查表 | 完成 |
| PLAN-61 | 架构核查 | 按 CLAUDE.md 逐条自检：core 无 argparse/curses/sys.exit、cli/tui 无替换逻辑副本、入口都先产出 Job、不覆盖原图、alpha 两路、单文件 <1000 行、文本 I/O 显式编码 | 完成 |
| PLAN-62 | 文档补对照表 | `technical.md` 新增「用例对照表」：测试文件 → 需求/约束 | 完成 |
| PLAN-63 | 文档全面校准 | 全量核对 8 份文档：名称统一 retype、版本 0.1、门禁 11 项、字体缓存 `~/.cache/retype`、目录树含 tools/ 与 browse.py/launch.py/bootstrap.py、用例对照表、TUI 响应式与键位 | 完成 |
| PLAN-64 | 修黑屏 | `draw_main` 补 `refresh`；`hline/vline` 改用 `addch`（ACS 常量在部分构建里是 int） | 完成 |
| PLAN-65 | 测试保真 | `FakeWin.addstr` 只收 str、`refresh/addch` 计数；新增 `RefreshFlush`、`BorderDrawing` | 完成 |
| PLAN-66 | 真终端冒烟 | `test_tui_real_terminal.py`：`script(1)` 伪终端跑真 curses，断言标题/表头/边框字符出现 | 完成 |
| PLAN-67 | Windows 覆盖 | CI 新增 `windows` 作业（windows-latest：全量用例 + mypy + guards + perf）；`windows-curses==2.4.2` 锁进 constraints；新增 `WindowsStyleAcs` 用例（把 ACS 常量换成 int 模拟 Windows 构建） | 完成 |
