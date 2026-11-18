# 计划任务

> 版本：v0.3-dev

> 范围：`retype`（图片文字替换）。本文件只列任务与验收口径，不写实现细节；
> 实现细节进 `technical.md`，结果进 `changelog.md`，问题进 `review-findings.md`。
> **编号约定**：本文件的任务一律 `PLAN-x`（连续编号，按出现顺序递增，不复用）；
> `review-findings.md` 里的任务一律 `RF-x`。

## 1. 当前目标（v0.3 开发中）

> v0.2 已发布：`PLAN-1`~`PLAN-103` 全部随发布归档（见下方索引）。新任务从 **PLAN-104** 起编号，不复用。
> 立项时在这里按「编号 / 任务 / 验收标准 / 状态」建表；实现细节进 `technical.md`，结果进 `changelog.md`，
> 问题进 `review-findings.md`。

| 编号 | 任务 | 验收标准 | 状态 |
| --- | --- | --- | --- |
| PLAN-104 | CI/测试 | v0.2 的 windows 作业仍红两条：宽字距断言仍依赖平台字体、失败摘要步自身编码崩 | 期望宽度改用 pipeline 报告的 font/size/tracking 并取「同字体无字距」为下限；摘要搬进 `tools/junit_summary.py` 且工作流禁 heredoc；守护与用例同步 | 完成 |

## 归档

> 已发布版本的旧内容整块搬进 `docs/archive/`，本文件只留当前开发版本的内容；
> 目录与文件命名规则见[归档规范](../archive/README.md)。搬运无损、不改一字，
> 编号 `PLAN-x` / `RF-x` 归档后仍占号，不复用。

| 系列 | 归档文件 | 涵盖版本 | 归档时间 |
| --- | --- | --- | --- |
| v0.2.x | [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md) | v0.2 | 2026-11-18（v0.2 发布，本系列首份） |
