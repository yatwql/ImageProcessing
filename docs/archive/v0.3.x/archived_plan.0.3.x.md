# 计划归档 — v0.3.x

> 归档时间：2026-11-20（v0.3 发布，本系列首份）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.3
> 归档内容：由 `python -m src.python.tools.release archive` 整块搬运，未改一字

---

## 1. 当前目标（v0.3 开发中）

> v0.2 已发布：`PLAN-1`~`PLAN-103` 全部随发布归档（见下方索引）。新任务从 **PLAN-104** 起编号，不复用。
> 立项时在这里按「编号 / 任务 / 验收标准 / 状态」建表；实现细节进 `technical.md`，结果进 `changelog.md`，
> 问题进 `review-findings.md`。

| 编号 | 领域 | 任务 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| PLAN-104 | CI/测试 | v0.2 的 windows 作业仍红两条：宽字距断言仍依赖平台字体、失败摘要步自身编码崩 | 期望宽度改用 pipeline 报告的 font/size/tracking 并取「同字体无字距」为下限；摘要搬进 `tools/junit_summary.py` 且工作流禁 heredoc；守护与用例同步 | 完成 |
| PLAN-105 | 门禁 | windows 作业「类型检查」红：`fcntl`/`os.mkfifo` 在 Windows 的 typeshed 里不存在 | `audit.py` 用 `Any` 间接引用、真终端冒烟走 `getattr`；`check_all` 新增 `mypy --platform win32` 档，本地即可复现 | 完成 |
| PLAN-106 | 门禁 | windows 作业「工程守护」红：四个工具缺 `ensure_utf8_stdio()`、五个工具子进程 `text=True` 缺 `encoding=` | 全部补齐；守护「跨平台」新增 stdio 规则并把子进程编码检查改成整次调用判定；+3 例 | 完成 |
| PLAN-107 | 门禁 | windows 作业「工程守护」红：`check_workflows` 直接 `bash -n`，在 WSL 存根上逐条报语法错误 | 先探测 `bash -c "exit 0"`（`BASH_OK`），不可用则跳过 bash 检查；汇总到日志说明；+5 例（含 heredoc 禁令） | 完成 |
| PLAN-108 | 流程 | 每轮 push 都重跑 7 分钟全量门禁，反馈太慢 | 新增 `gate_stamp`（跟踪文件指纹戳）并在 `pre-push` 前置检查；`check_all` 全量通过后自动写戳 | 完成 |
| PLAN-109 | 门禁 | windows 作业「耗时守卫」红：`日志追加×300` 实测 3.5s / 上限 1.0s（fsync 慢一档） | 新增平台档 `limits_for`：Windows 只放大落盘步骤（×5）与总上限（×4），其余不动；3 例用例 | 完成 |
| PLAN-110 | 报告字段 | 归档遗留 `RF-6`：行内替换时 `old` 是整行、`new` 只是片段，日志照录看不出对等关系 | 报告与写盘日志每条补 `fragment`（命中的原文子串）与 `span`（在整行里的字符区间）；`old`/`new`/`mode` 不改语义，整行替换时为 `null`；旧日志缺字段读成 `None`；+5 例 | 完成 |
| PLAN-111 | 测试卫生 | 归档遗留 `RF-16`：早期用例不带 `--out-dir`，产物堆在 `data/output/report-*.png` | 四处用例改写临时目录、清掉历史产物；新增 `src/test/conftest.py` 会话级快照钩子，有用例再写仓库产物目录就当场红 | 完成 |
| PLAN-112 | 流程提速 | 提交/推送/发布三处都在白等：门禁四档用例串行跑（四遍全量）、静态检查串行、`release.py check` 拿 `--quick + 两档矩阵` 却把每条定版门禁跑两遍 | 新增 `tools/_parallel.py`（worker 规则：核数上限 8，`IMG_P_TEST_WORKERS` / `--gate-workers` / `--serial` 可覆盖）；`check_all` 改为「静态并发 + 耗时守卫独占 + 档位串行档内 `-n 8`」；`release.py check` 先跑秒级预检（红了直接停）、命中门禁戳则跳过；CI `test` 作业把两遍全量用例合成一遍 | 完成 |
| PLAN-113 | 门禁质量 | 提速会引入新风险：并行后用例之间可能隐性互相影响；一档被 `-k` / 环境变量整批 deselect 时退出码仍是 0（假绿）；`release.py check` 以前完全不跑覆盖率门禁 | 新增「各档跑到的用例模块集合必须一致」对账；全量档加一档 `--dist load` 分片重排专查顺序依赖；`check` 改跑全量门禁（含覆盖率）；`tools/test_gate_pipeline.py`（26 例）钉住这三条 | 完成 |
