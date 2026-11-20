# 变更记录

> 版本：v0.4

> 按时间倒序记录对代码、用例与文档的实质变更。每条给出：做了什么、动了哪些文件、
> 对应需求与验证方式。只写结论，不贴 diff。

## v0.4 — 2026-11-20

### 变更

- **工具按活动类型归类命名**（守护「脚本契约」强制前缀）：`check_` 门禁检查 / `test_` 测试工程 /
  `eval_` 离线评测 / `make_` 资产生成 / `probe_` 环境探测 / `hook_` 钩子接线，共享设施用 `_` 前缀。
  重命名 8 个工具（`run_tests→test_runner`、`gen_folders→make_folders`、`gate_stamp→hook_gate_stamp` 等），
  白名单之外的前缀直接红。
- **测试工程能力**：`check_perf --record/--history`（性能台账 `logs/perf.jsonl`，只观察不进门槛）、
  `test_coverage_report --collect-only`（只收集不执行，秒级按目录数用例）、
  `test_runner --keep N`（运行摘要写 `reports/history/`，只留最近 N 次）。
- **测试排障工具**：`test_failures`（junit → 节点 ID/类型/消息 + 单跑命令）、
  `test_order_dependent`（二分定位顺序依赖的污染源与最小复现集）。
- **技术债清理**：输出命名规则收进 `core.image.output_name/debug_tag`（cli/tui 不再各写一遍）；
  全树圈复杂度降到 **≤15**（`replace_image` 30、`fit_font` 27/18、`edit_line` 17 逐个拆开），
  守护「复杂度上限」红线从 50 收到 15。
- **测试债清理**：删 2 条跨文件完全重复的用例；`test_unlock_without_lock_is_a_noop` 补显式断言。
- **文档**：新增「工具命名与分类」表（technical §1.3）、需求补 FR-14（7 条对外行为）、
  「守护第 N 项」位置序号一律改为守护名字并新增守护「守护引用」防漂移。
- **新守护**：脚本契约、文档链接、用例对照表、复杂度上限、守护引用（守护总数 18 → 23）。

## v0.4-dev — 开发中

### 修复（v0.3 发布暴露的两处「拿本机事实当断言」）

- `src/test/tools/test_release_versions.py`：`cmd_tag("0.3")` 原来**真去问 git**「标签是否已存在」，
  于是 v0.3 一发完这条用例必红。改为桩掉标签查询，只验「标签名不带 `-dev`」这条规则；
  另补一条「同名标签已存在 → 拒绝」(退出码 2) 的用例，把真实行为钉住。
- 同一次发布还暴露了 `prepare` 的盲区：它只改 `version.py` 与 changelog，13 份文档的
  `> 版本：` 头仍是 `v0.3-dev`，被守护「版本号」拦下才发现。本轮起版本切换一律走
  「全链同步 + 守护核对」，`devbump` 后必须重跑 `check_guards`。

### 修复（守护误报：裸 `bash`/`sh`）

- `src/python/tools/check_platform_safety.py`：裸 shell 规则原先把 `mock.patch.object(release, "sh")`
  里的属性名字面量当成命令行。改为只认「当命令用」的写法（`["bash", "-n", …]` / `run("sh", …)`），
  属性名与参数名不再误报；规则样本见 `src/test/tools/test_platform_safety_rules.py`。

### 加固（XML 解析的信任边界）

- `src/python/tools/check_coverage.py`、`check_all.py`：解析 `reports/coverage.xml` / `junit*.xml`
  用标准库 `xml.etree` 会命中 XXE 安全检查。这里**只解析本机 pytest 刚生成的报告**（不接受外部输入），
  故在调用点行内写明信任边界并加 `# nosemgrep`，而不是为整条工具链引入 `defusedxml` 依赖。

### 版本

- v0.3 已发布并合并进 `master`（标签 `v0.3`，门禁 203s 全绿）；`dev` 切到 `0.4-dev`，
  14 份文档版本头与 40 屏界面快照同步。

## 归档

> 已发布版本的旧内容整块搬进 `docs/archive/`，本文件只留当前开发版本的内容；
> 目录与文件命名规则见[归档规范](../archive/README.md)。搬运无损、不改一字，
> 编号 `PLAN-x` / `RF-x` 归档后仍占号，不复用。

| 系列 | 归档文件 | 涵盖版本 | 归档时间 |
| --- | --- | --- | --- |
| v0.3.x | [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) | v0.3 | 2026-11-20（v0.3 发布，本系列首份） |
| v0.2.x | [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) | v0.2 | 2026-11-18（v0.2 发布，本系列首份） |
