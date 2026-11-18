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
| PLAN-105 | 门禁 | windows 作业「类型检查」红：`fcntl`/`os.mkfifo` 在 Windows 的 typeshed 里不存在 | `audit.py` 用 `Any` 间接引用、真终端冒烟走 `getattr`；`check_all` 新增 `mypy --platform win32` 档，本地即可复现 | 完成 |
| PLAN-106 | 门禁 | windows 作业「工程守护」红：四个工具缺 `ensure_utf8_stdio()`、五个工具子进程 `text=True` 缺 `encoding=` | 全部补齐；守护「跨平台」新增 stdio 规则并把子进程编码检查改成整次调用判定；+3 例 | 完成 |
| PLAN-107 | 门禁 | windows 作业「工程守护」红：`check_workflows` 直接 `bash -n`，在 WSL 存根上逐条报语法错误 | 先探测 `bash -c "exit 0"`（`BASH_OK`），不可用则跳过 bash 检查；汇总到日志说明；+5 例（含 heredoc 禁令） | 完成 |
| PLAN-108 | 流程 | 每轮 push 都重跑 7 分钟全量门禁，反馈太慢 | 新增 `gate_stamp`（跟踪文件指纹戳）并在 `pre-push` 前置检查；`check_all` 全量通过后自动写戳 | 完成 |
| PLAN-109 | 门禁 | windows 作业「耗时守卫」红：`日志追加×300` 实测 3.5s / 上限 1.0s（fsync 慢一档） | 新增平台档 `limits_for`：Windows 只放大落盘步骤（×5）与总上限（×4），其余不动；3 例用例 | 完成 |
| PLAN-110 | 报告字段 | 归档遗留 `RF-6`：行内替换时 `old` 是整行、`new` 只是片段，日志照录看不出对等关系 | 报告与写盘日志每条补 `fragment`（命中的原文子串）与 `span`（在整行里的字符区间）；`old`/`new`/`mode` 不改语义，整行替换时为 `null`；旧日志缺字段读成 `None`；+5 例 | 完成 |
| PLAN-111 | 测试卫生 | 归档遗留 `RF-16`：早期用例不带 `--out-dir`，产物堆在 `data/output/report-*.png` | 四处用例改写临时目录、清掉历史产物；新增 `src/test/conftest.py` 会话级快照钩子，有用例再写仓库产物目录就当场红 | 完成 |

## 归档

> 已发布版本的旧内容整块搬进 `docs/archive/`，本文件只留当前开发版本的内容；
> 目录与文件命名规则见[归档规范](../archive/README.md)。搬运无损、不改一字，
> 编号 `PLAN-x` / `RF-x` 归档后仍占号，不复用。

| 系列 | 归档文件 | 涵盖版本 | 归档时间 |
| --- | --- | --- | --- |
| v0.2.x | [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md) | v0.2 | 2026-11-18（v0.2 发布，本系列首份） |
