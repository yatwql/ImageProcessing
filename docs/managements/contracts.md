# 架构约束与设计契约

> 版本：v0.4-dev

本文件把"分层怎么划、谁能依赖谁、对外承诺什么"写成可检查的约束。**约束靠守护与用例落地**，
不是靠记忆：违反即红（见 §5）。

## 1. 分层与依赖方向

```text
            ┌──────────────────────────────┐
            │  channels   cli/  ·  tui/     │  参数/界面/编排，不含任何替换算法
            └───────────────┬──────────────┘
                            │ 只允许 ↓
            ┌───────────────┴──────────────┐
            │  core   OCR/版式/字体/渲染/擦除/审计  │  唯一实现替换逻辑的地方
            └───────────────┬──────────────┘
                            │ 只允许 ↓
            ┌───────────────┴──────────────┐
            │  platform   config · version · bootstrap · launch │
            └──────────────────────────────┘
```

| 编号 | 约束 | 检查方式 |
| --- | --- | --- |
| AR-1 | `core/` 不得导入 `cli/` 或 `tui/`（核心层不认识渠道） | `src/python/tools/check_import_surface.py` |
| AR-2 | `cli/` 与 `tui/` 不得互相导入 | 同上 |
| AR-3 | `core/` 不得 `import argparse` / `curses`，不得 `sys.exit` | `src/python/tools/check_guards.py`（分层） |
| AR-4 | 任何"输入 → 替换"的入口都必须先产出 `core.Job` 再交给 `core.replace_image` | 代码审查 + `core/jobs.py` 契约 |
| AR-5 | 渠道不得重复实现"找字体 / 擦除 / 绘制 / 匹配规则" | 用例断言行为 + 代码审查 |
| AR-6 | 单文件 ≤ 1000 行；`scripts/` 只放 `.sh/.ps1` 薄壳（≤40 行） | `check_guards.py`（文件长度 / scripts 薄壳） |
| AR-7 | 文本 I/O 一律显式 `encoding="utf-8"`；`.ps1` 必须 UTF-8 with BOM | `check_guards.py`（显式编码 / PS 编码） |
| AR-8 | 开发工具放 `src/python/tools/`，不进发行包（`pyproject` 的 `packages.find.exclude`），也不纳入覆盖率；core/渠道**不得**反向依赖它们 | `check_import_surface.py` + `coverage.omit` |

## 2. 设计契约（对外承诺）

### 2.1 核心 API 契约

| 契约 | 内容 | 破坏方式 |
| --- | --- | --- |
| `core.Job` | `rect / src / new / span` 四字段；`span=None` 表示整行，否则为行内区间 | 改字段名/语义 |
| `core.replace_image` | 返回 `(rgb, alpha|None, report)`；报告每条含 `old/new/fragment/span/rect/mode/font/size/tracking/color/align/iou`（`fragment`/`span` 只在行内替换时有值） | 改返回结构 |
| 错误契约 | 可预期失败**只**抛 `CoreError`，由渠道决定提示或退出；核心层不 `sys.exit`、不 `print` | 抛内置异常裸奔 |
| 幂等 | 同图同参数重复执行，输出字节一致 | 引入随机/时间依赖 |
| 覆盖保护 | 输出与输入同路径时拒绝；同目录不同名用 `-1/-2…` 编号 | 静默覆盖原图 |

### 2.2 CLI 契约

- `--help` 与 `--version` 恒退出码 0；`--version` 输出 `retype <版本> (<日期>)`。
- 参数错误（`--quality` 越界、`--color` 非法、`--area` 用于批量等）在**处理图片之前**以退出码 2 结束。
- 单图成功 0、全部失败 3、路径不存在 2；批量"部分失败"仍为 0，失败张数写进摘要与 stderr。
- 预演（`--dry-run`）不写任何文件（含 `--debug` 的 mask），且不产生日志。

### 2.3 数据契约

| 数据 | 位置 | 稳定性 |
| --- | --- | --- |
| 配置文件 | `<配置目录>/retype.json`（兼容旧 `img-p.json`） | 只增键不删键；未知键忽略并提示 |
| 写盘日志 | `<日志目录>/image-writes-YYYYMMDD.log`，一行一个 JSON | 字段只增不减（`app` / `app_version` / `app_updated` / `operations` …） |
| 运行摘要 | `--report FILE` 的 JSON | 只增字段 |
| 映射表 | JSON `{旧: 新}` | 保持简单对象；片段=行内替换 |

### 2.4 界面契约

- TUI 在 `w < 60` 单栏、`w < 44` 表头只留计数、`w < 40` 最短键位提示；任何宽度都不得溢出。
- 每帧必须 `refresh()`；线框只能 `addch`（`ACS_*` 可能是 int）。
- 空目录允许启动；`Ctrl-R` 重新扫描；`Esc` 只返回不退出（退出用 `q`）。

## 3. 版本与兼容策略

- 版本号 `MAJOR.MINOR[-dev]`：开发分支用 `-dev`（如 `0.3-dev`），正式发布去掉后缀（`0.3`）；
  `version.py` 是唯一来源，各文档 `> 版本：` 行与它逐字一致；`UPDATED` 必须等于 `src/` 最后一次提交日期。
- 分支：日常开发在 `dev`，正式发布在 `master`（发布后 `dev` 合并进 `master`，再切下一个 `-dev` 版本）。
- 版本内改动**不破坏**：核心 API 契约、CLI 退出码、日志/摘要字段、配置文件键。
- 破坏性改动必须：提升 `MINOR`、在 `changelog.md` 标「不兼容」、并在 `releasing.md` 的发布说明里写迁移步骤。

## 4. 扩展点（允许加，不允许改契约）

| 需求 | 扩展位置 |
| --- | --- |
| 换 OCR | `core/ocr.py`（保持 `ocr_regions` / `ocr_crop`） |
| 新输出格式 | `core/image.FMT_BY_EXT` + 保存分支 |
| 新渠道（GUI/HTTP） | 新增 `src/python/<渠道>`，复用 `core.jobs` + `core.replace_image` |
| 新日志字段 | `core/audit.build_entry`（只增） |

## 5. 约束怎么被检查

| 约束 | 守护 / 用例 |
| --- | --- |
| AR-1/AR-2 | `src/python/tools/check_import_surface.py`（守护第 14 项） |
| AR-3 | `check_guards.py` 分层（core 禁 argparse/curses/sys.exit） |
| AR-5 | `core/test_feature_edges.py`、`tui/test_*` 断言渠道只编排不实现 |
| AR-6 | `check_guards.py` 文件长度 / scripts 薄壳 |
| AR-7 | `check_guards.py` 显式编码 / PS 编码 |
| §2.1 契约 | `core/test_error_contract.py`、`core/test_cancel_pipeline.py`、`core/test_write_audit_log.py` |
| §2.2 CLI 契约 | `cli/test_arguments.py`、`cli/test_single_image.py`、`cli/test_batch_directory.py`、`cli/test_entry_smoke.py` |
| §2.4 界面契约 | `tui/test_layout_rendering.py`、`tui/test_screen_snapshots.py` |
