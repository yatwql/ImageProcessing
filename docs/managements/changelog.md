# 变更记录

> 版本：v0.3-dev

> 按时间倒序记录对代码、用例与文档的实质变更。每条给出：做了什么、动了哪些文件、
> 对应需求与验证方式。只写结论，不贴 diff。

## v0.3-dev — 开发中

### 优化（门禁提速：同一份质量，墙钟减半）

改造前的事实：全量门禁把**同一套 703 个用例串行跑四遍**（本机 / cp1252+C locale / 无字体 / 换字族，
每遍 69s），静态检查也一条接一条；`release.py check` 用 `--quick` 加两档矩阵（三遍）却**不跑覆盖率**，
然后 `gate` 再跑一遍全量——一次发布要跑七遍用例；而且结构性预检红了也照样先把门禁跑完。

- `src/python/tools/_parallel.py`（新增）：门禁并行执行。实测（16 核 / 703 用例）单档串行 69s、
  `-n 8` 25s、`-n 16` 25s（已饱和）、四档并发只快 16% 却要 4 倍进程——因此定成
  **档位串行、档内 `-n min(核数,8)`**；`IMG_P_TEST_WORKERS` / `--gate-workers` / `--serial` 可覆盖。
- `src/python/tools/check_all.py`：静态检查（ruff / mypy / mypy-win32 / guards）**并发**跑，
  耗时守卫 `check_perf` 仍独占 CPU（按墙钟卡阈值，混跑会假红）；用例改四档 `-n 8`，
  每档出 junit 报告，结尾打印总耗时与最慢一步。
- `src/python/tools/release.py`：`check` 先跑秒级结构性预检（工作区/版本/分支），**红了直接停**，
  不再白跑门禁；绿了以后跑的是**全量**门禁（含覆盖率），命中门禁戳则跳过；`gate` 默认复用门禁戳，
  `--force` 强制重跑。
- `src/python/tools/run_tests.py`：`runTest.sh` 也走同一套 worker 规则。
- `.github/workflows/ci.yml`：`test` 作业原来把全量用例跑**两遍**（一遍出 junit、一遍出覆盖率），
  合成一遍（`--cov` + `--junitxml` 同时出）并加 `-n 4`。

### 优化（门禁质量：提速同时把标尺抬高）

- **各档对账**：每档 junit 报告里实际跑到的**用例模块集合必须一致**；某档因 `-k` 打错或环境变量
  把整个文件 deselect 时，退出码仍是 0，以前就是"全绿什么都没测"，现在当场红
  （不比用例总数：`nofont` 档少 132 个跳过是设计如此）。
- **顺序依赖探测**：全量档加一档 `--dist load`（把用例打散到 worker、改变执行顺序），
  并行后才暴露的用例间耦合在这一档红。
- **覆盖率前移到发布预检**：`release.py check` 以前只跑 `--quick`（不含覆盖率门禁），现在跑全量。
- `src/test/tools/test_gate_pipeline.py`（26 例）：worker 规则、批次顺序与 `isolated` 不并发、
  档位选择、模块集合对账、发布预检失败即停与门禁戳跳过。
- 顺手修两处文档：`plan.md` 任务表头缺「领域」列（整表错位）、`requirements.md` 的
  `cli|tui` 未转义（表格多一列）。

实测（16 核）：提交前 `--quick` 约 30s（原 ~80s）；全量门禁 160~176s（原 ~285s，且多了两档检查）；
一次发布从 ~15 分钟降到 ~6 分钟（`check` 全量一次 + `gate` 命中门禁戳）。

### 修复（真终端冒烟用例的 core dump：一轮门禁写 1.8GB 垃圾）

- 现象：`src/test/tui/test_tui_real_terminal.py` 在 pty 里跑 `tui.sh`，TUI 子进程偶发段错误，
  每次落地一个 `core.<pid>`（~800MB）。一轮全量门禁产生 16 个、共 1.8GB，撑磁盘、
  把 `git status` 弄脏（`release.py check` 因此直接红），而用例本身照样"通过"。
- `src/test/conftest.py`：新增会话级 `no_core_dumps` 钩子，把 `RLIMIT_CORE` 清零
  （子进程继承该上限）。根因尚未定位到（curses 退出与后台 OCR 线程的时序），
  先在测试入口止损：崩了也不落地。
- `src/test/tui/test_tui_real_terminal.py`：新增 `preflight()`——先判"这个环境能不能画中文"，
  不能就跳过，不再白起一次必然无效的 pty 子进程（每个非 UTF-8 档省 5s）；
  并检查子进程退出码，被信号打死直接红（以前 `check=False` 把退出码丢掉了，
  段错误也算通过）。"没有真实终端" 的跳过逻辑仍保留在 `assert_usable_terminal`。

### 修复（归档遗留项收尾：行内替换的报告字段）

- `src/python/core/edit.py`：行内替换的报告条目补 `fragment`（命中的原文子串）与 `span`
  （子串在整行里的字符区间 `[起, 止)`）；`old`/`new`/`mode` 语义不变，整行替换时两者为 `None`。
  这解掉了归档 `RF-6` 的“新旧文字不对等”岐义。
- `src/python/core/audit.py`：`OP_FIELDS` 加上 `fragment`/`span`，写盘日志的 `operations[]` 同步落盘；
  字段只增不减，旧日志缺字段读成 `None`。
- `src/test/core/test_report_inline_fragment.py`（5 例）：行内/整行的报告字段、`fragment` 与 `span`
  自洽（原文切片 = 报告的区间）、日志落盘与旧记录兼容。

### 修复（归档遗留项收尾：用例不再写仓库产物目录）

- `src/test/core/test_write_audit_log.py`：四处 `run_cli` 没带 `--out-dir`（偷懒走默认 `data/output`）
  的用例改为统一写临时目录，顺手清掉历史堆积的 961 张 `data/output/report-*.png`。
- 新增 `src/test/conftest.py`：会话级自动钩子，前后对比仓库 `data/output/` 快照，
  有用例写进去就当场红并点名文件（归档 `RF-16` 的真实拦截）。

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

### 修复（windows 作业「耗时守卫」红）

- `src/python/tools/check_perf.py`：`日志追加×300` 在 windows runner 上实测 3.5s（上限 1.0s）——fsync 慢一个量级。
  新增平台档 `limits_for(is_windows)`：Windows 只把**落盘那一步**放大 5 倍、总上限放大 4 倍，其余步骤保持基准
  （无条件放大等于把门禁调松）；`tools/test_perf_limits.py`（3 例）钉住这条口径。

### 新增（流程提速）

- `src/python/tools/gate_stamp.py` + `src/test/tools/test_gate_stamp.py`（8 例）：全量门禁通过后按
  「跟踪文件路径 + 内容」的 sha256 留戳（`.git/retype-gate-stamp.json`）；`pre-push` 先问戳，
  同一份代码再推直接跳过 7 分钟的全量重跑，改任何跟踪文件即失效。

### 新增

- `src/python/tools/junit_summary.py` + `src/test/tools/test_junit_summary.py`（5 例）：失败/错误用例
  列成 `class::name`，报告缺失不报错。
- 守护「工作流」新增规则：`run:` 块内联 python 脚本（heredoc / `python -c`）一律红——
  那段代码既没有 `ensure_utf8_stdio()` 也写不了用例。
- 版本策略落地：`dev` 分支开发版 `0.3-dev`，正式版 `0.2` 已在 `master` 打标签 `v0.2`；
  `release.py` 新增 `devbump`，`prepare` 只做定版（`X.Y-dev` → `X.Y`），开发版拒绝打标签。
- 界面快照不再含版本串（`v<VER>`）：升版不再产生 40 屏 diff。

### 验证

- `ruff` / `mypy` / `guards 18/18` / `check_workflows` 全绿；`pytest src/test -q` 729 passed。
- `check_all` 全量：静态并发 + 四档环境矩阵 × `-n 8` + 覆盖率 96.7% + 分片重排，160~176s 全绿。

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

### 已知问题（已在 v0.3-dev 修复，发布说明同步）

`v0.2` 标签对应的 CI 运行里 `windows` 作业为红，根因是 5 处 Windows 专属差异（用例假设本机事实、
`fcntl`/`os.mkfifo` 在 win32 typeshed 缺失、工具缺 stdio 编码、`check_workflows` 直接 `bash -n`、
耗时守卫未按平台分档），不影响产物与功能；修复记录见 `review-findings.md` RF-140~RF-153。

### 已知限制

- 竖排/旋转文字不识别（`PLAN-12` 待办，随 v0.3 排期）；`--area` 里原文未被 OCR 认全时字体匹配会退回默认字体。

## 归档

> 已发布版本的旧内容整块搬进 `docs/archive/`，本文件只留当前开发版本的内容；
> 目录与文件命名规则见[归档规范](../archive/README.md)。搬运无损、不改一字，
> 编号 `PLAN-x` / `RF-x` 归档后仍占号，不复用。

| 系列 | 归档文件 | 涵盖版本 | 归档时间 |
| --- | --- | --- | --- |
| v0.2.x | [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) | v0.2 | 2026-11-18（v0.2 发布，本系列首份） |
