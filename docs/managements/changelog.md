# 变更记录

> 版本：v0.3-dev

> 按时间倒序记录对代码、用例与文档的实质变更。每条给出：做了什么、动了哪些文件、
> 对应需求与验证方式。只写结论，不贴 diff。

## v0.3-dev — 开发中

### 修复（v0.2 的 windows 作业仍红）

- `src/test/core/layout/test_text_layout.py`：宽字距用例仍拿"另一次 fit 的排版宽度"当期望，
  psipeline 实际用的字体/字号/字距未必相同（Windows 上 msyh 与 Noto 度量不同），
  改为按 `report` 里 pipeline 自己报告的 font/size/tracking 算期望宽度，并以「同字体无字距」为下限。
- CI「失败用例摘要」步自己红了（`UnicodeEncodeError: 'charmap'`，Windows 控制台 cp1252 打印中文）：
  逻辑搬进 `src/python/tools/junit_summary.py`（`ensure_utf8_stdio()`），工作流只留一行 `python -m ...`。

### 修复（windows 作业「类型检查」红）

- `src/python/core/audit.py`：`import fcntl` 在 Windows 的 typeshed 里没有 `flock`/`LOCK_EX` 等属性，
  `mypy` 在 windows 作业上直接红。改为 `fcntl: Any = _fcntl_module` 间接引用（运行时行为不变）。
- `src/test/tui/test_tui_real_terminal.py`：`os.mkfifo` 同样是 POSIX-only 属性，改成 `cast(Any, os).mkfifo(...)`。
- `check_all` 新增「mypy (win32 平台)」一步（`--platform win32`）：这类差异现在本地就红。

### 修复（windows 作业「工程守护」红）

- 四个工具（`check_guards` / `check_perf` / `check_platform_safety` / `gen_folders`）的 `main()` 缺
  `ensure_utf8_stdio()`：Windows 控制台 cp1252 下打印中文 `[ok] 编号-plan` 直接 `UnicodeEncodeError`。
- 五个工具（`check_guards` / `gen_folders` / `release` / `ci_env` / `update_constraints`）的
  `subprocess.run(text=True)` 缺 `encoding=`：Windows 用 cp1252 解码 UTF-8 输出 →
  `UnicodeDecodeError` + `stdout is None`。
- 守护「跨平台」两条规则收紧：`tools/` 里有 `main()` 必须调 `ensure_utf8_stdio()`（+3 例）；
  子进程编码检查改为按「整次调用」判断（原来只看 3 行，跨行写法漏检）。

### 修复（windows 作业「工程守护」红：工作流自检）

- `src/python/tools/check_workflows.py`：以前直接 `bash -n` 每个 `run:` 块；windows-latest 上 `bash`
  是 WSL 存根（退 1、stderr 空），于是逐条报"bash 语法错误"。改为先探测 `bash -c "exit 0"`
  （`BASH_OK`），不可用时跳过 bash 检查，只保留 YAML 与 `python -c` 片段校验。

### 新增

- `src/python/tools/junit_summary.py` + `src/test/tools/test_junit_summary.py`（5 例）：失败/错误用例
  列成 `class::name`，报告缺失不报错。
- 守护「工作流」新增规则：`run:` 块内联 python 脚本（heredoc / `python -c`）一律红——
  那段代码既没有 `ensure_utf8_stdio()` 也写不了用例。
- 版本策略落地：`dev` 分支开发版 `0.3-dev`，正式版 `0.2` 已在 `master` 打标签 `v0.2`；
  `release.py` 新增 `devbump`，`prepare` 只做定版（`X.Y-dev` → `X.Y`），开发版拒绝打标签。
- 界面快照不再含版本串（`v<VER>`）：升版不再产生 40 屏 diff。

### 验证

- `ruff` / `mypy` / `guards 18/18` / `check_workflows` 全绿；`pytest src/test -q` 674 passed。

## v0.2 — 2026-11-18

首个正式发布版本。本版起已发布系列的台账整块归档到 `docs/archive/v0.2.x/`，主台账只留当前开发周期。

### 主要能力

- 替换流程：OCR → 版式分析 → 字体/字号/字距反解 → 擦除重绘 → 写盘审计；`--map` / `--area` 两种输入，
  行内子串替换只动目标字符；原图永不覆盖（同路径拒绝、重名自动编号）。
- 两个渠道：CLI（单图/批量/`--dry-run`/`--report`/日志查询）与 TUI（curses，宽屏双栏/窄屏单栏、
  8 组配色、映射与样式面板、批量进度、Esc 中断、空目录启动 + `Ctrl-R` 重扫）。
- 跨平台：Windows（windows-curses、msyh、msvcrt 加锁、PS 薄壳 BOM）、macOS、Linux；
  配置目录分平台，字体池按文件签名缓存。

### 工程与门禁

- 18 项工程守护（编号 / 分层 / 长度 / 编码 / 测试目录 / 版本 / 名称 / 目录树 / 测试字体 /
  导入方向 / 文档索引 / 归档 / 工作流 / 跨平台 / 依赖锁 / PS 编码 / scripts 薄壳 / 依赖审计）。
- 覆盖率 96.69%，分模块门槛与 skip 上限；三档本地 CI 矩阵（无字体、cp1252+C locale、换字族/字重）。
- 发布流程 7 步：check → archive → prepare → gate → build → tag → publish（见 `releasing.md`）。

### 归档

- 本版完整过程记录（`PLAN-1`~`PLAN-103`、`RF-1`~`RF-148`、全部日期变更段）整块归档：
  [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md)、
  [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md)、
  [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md)。

### 已知限制

- 竖排/旋转文字不识别（`PLAN-12` 待办，随 v0.3 排期）；`--area` 里原文未被 OCR 认全时字体匹配会退回默认字体。

## 归档

> 已发布版本的旧内容整块搬进 `docs/archive/`，本文件只留当前开发版本的内容；
> 目录与文件命名规则见[归档规范](../archive/README.md)。搬运无损、不改一字，
> 编号 `PLAN-x` / `RF-x` 归档后仍占号，不复用。

| 系列 | 归档文件 | 涵盖版本 | 归档时间 |
| --- | --- | --- | --- |
| v0.2.x | [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) | v0.2 | 2026-11-18（v0.2 发布，本系列首份） |
