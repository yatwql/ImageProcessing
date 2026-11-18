# 变更记录

> 版本：v0.2

> 按时间倒序记录对代码、用例与文档的实质变更。每条给出：做了什么、动了哪些文件、
> 对应需求与验证方式。只写结论，不贴 diff。

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
