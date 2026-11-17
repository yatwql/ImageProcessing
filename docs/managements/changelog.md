# 变更记录

> 按时间倒序记录对代码、用例与文档的实质变更。每条给出：做了什么、动了哪些文件、
> 对应需求与验证方式。只写结论，不贴 diff。

## 2026-11-10 — 工程化整改（配置/CI/门禁/分层/画质/可观测）

### 新增

- `pyproject.toml`：依赖与 `dev` extra、ruff、mypy（守 `core`）、pytest、coverage（`fail_under = 75`）；
  `requirements.txt` / `requirements-dev.txt` 改为 `-e .` / `-e .[dev]`。
- `.github/workflows/ci.yml`：test（3.10/3.12/3.13）/ lint / typecheck / guards / perf。
- `.githooks/pre-commit` + `install-hooks.sh`：提交前 ruff → guards → 全量用例。
- `scripts/check-guards.py`（编号/分层/文件长度/显式编码/测试目录/空包）、`scripts/check-perf.py`（四步热路径）、
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

- `ruff check src/ scripts/` 零告警；`python -m mypy` 零错误；`scripts/check-guards.py` 6/6；
  `scripts/check-perf.py` 合计约 0.6s（上限 6s）；`pytest src/test -q` 全绿。

## 2026-11-10 — 配置、临时目录与仓库清理

### 新增

- 配置文件：`/data/config/img-p.json`、示例 `/data/config/img-p.example.json`（都在配置目录里，
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

- `scripts/setup.ps1`（支持 `-Dev`）、`scripts/cli.ps1`、`scripts/tui.ps1`、`scripts/test.ps1`（支持 `-Fast`），
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
