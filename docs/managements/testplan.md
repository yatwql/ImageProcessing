# 测试计划与质量标准

> 版本：v0.2

本文件定义 **retype 的质量控制体系与测试标准**：质量目标、门禁分层、测试分层与编写规范、
覆盖率与性能阈值、缺陷分级与回归要求、例外流程。它是"什么算合格"的唯一依据；
具体数字（当前覆盖率、各分组用例数）见 [`test-coverage.md`](test-coverage.md)，
模块与算法见 [`technical.md`](technical.md)，需求与验收口径见 [`requirements.md`](requirements.md)。

## 1. 质量目标（可量化，全部由门禁判定）

| 编号 | 目标 | 判定方式 | 门槛 |
| --- | --- | --- | --- |
| QG-1 | 静态质量 | `ruff check src/ tools/` + `mypy`（全树） | 零告警 / 零错误 |
| QG-2 | 结构约定 | `src/python/tools/check_guards.py` | 17 项全过 |
| QG-3 | 行覆盖率 | `src/python/tools/check_coverage.py` | 总量 ≥ 96%（实测 97%） |
| QG-4 | 高风险模块覆盖率 | 同上（match/options ≥90%；edit/render/image/audit/ui_draw/bootstrap/launch/ui/cli-main/cli-log_query ≥85~90%；app/ui_actions/ui_base/ui_input ≥80%） | 逐项达标 |
| QG-5 | 跳过率 | 同上（正常模式，即机器上有中文字体） | ≤ 15% |
| QG-6 | 行为正确性 | 全量用例（功能/交互/跨平台/稳定性/入口冒烟/快照/属性） | 0 失败 |
| QG-7 | 性能不退化 | `src/python/tools/check_perf.py` | 四步各阈值 + 合计 ≤ 6s |
| QG-8 | 依赖安全 | CI `audit` 作业 `pip-audit --strict` | 无已知漏洞 |
| QG-9 | 缺陷回归 | 每个已修缺陷都有对应用例 | 100%（见 §6） |
| QG-10 | 发布门禁 | `src/python/tools/release.py check/gate`（工作区干净、版本与日期一致、全量门禁） | 全绿才可打标签 |

一条命令自查：`python -m src.python.tools.check_all`（全量）/ `--quick`（提交前用）。

## 2. 门禁分层

| 层级 | 触发点 | 跑什么 | 失败后果 |
| --- | --- | --- | --- |
| P0 提交前 | `git commit` → `.githooks/pre-commit` | `check_all.py --quick`：ruff → mypy → guards → perf → 全量用例 | 拒绝提交 |
| P1 推送前 | `git push` → `.githooks/pre-push` | `check_all.py` 全量：再加覆盖率门禁 + 无字体复跑 | 拒绝推送 |
| P2 CI | push / PR | 八个常驻作业：test（3.10/3.12/3.13）、lint、typecheck、guards、perf、windows、audit（release 只在打 tag 时跑） | 红则不合入 |
| 手工 | 改界面/改依赖后 | `UPDATE_SNAPSHOTS=1` 重生成快照、`src/python/tools/update_constraints.py --write` | 快照/锁文件 diff 随提交 |

**例外**：`IMG_P_SKIP_HOOK=1` 可跳过 P0/P1，但**不允许**跳过 P2；跳过后必须在推送前手动跑
`check_all.py` 全量并在提交信息里写明原因。

## 3. 测试分层（每层的职责与位置）

| 层 | 目的 | 位置 | 关键约束 |
| --- | --- | --- | --- |
| 单元测试 | 单个函数/模块的契约 | `src/test/core/{primitives,layout,font,format,color,background,pipeline}` | 不依赖网络与真终端；字体走 `cjk_font()` |
| 契约测试 | 错误类型、返回结构、幂等 | `core/test_{error_contract,ocr_contract,write_audit_log,log_query}.py` | 断言"只抛 `CoreError`""坏行跳过"等**约定**，不测实现细节 |
| 功能边界 | 非法值、极值、重复键、多行 | `core/test_feature_edges.py`、`tui/test_interaction_edges.py` | 每个非法输入都要断言"行为 + 提示" |
| 属性测试 | 用生成输入验证不变量 | `core/test_properties.py`（hypothesis） | 不写具体期望值，只写性质（如"下标必须能回溯"） |
| 场景测试 | 一条完整用户路径 | `cli/`、`tui/`、`core/test_{write_audit_log,log_query,cancel_pipeline,version_display}.py` | 走真入口或真状态机，打桩只限 OCR/字体 |
| 布局与快照 | 界面排版不漂移 | `tui/test_layout_rendering.py`、`tui/test_screen_snapshots.py` | 5 尺寸 × 8 状态整屏文本；改界面必须显式更新 |
| 跨平台 | 平台差异 | `core/test_platform_stability.py`（`sys.platform` 打桩）、`tui/test_layout_rendering.WindowsStyleAcs` | 不允许"只在 Linux 绿" |
| 稳定性 | 幂等、并发、规模 | `core/test_platform_stability.py`、`core/test_write_audit_log.py`（3 进程并发） | 同输入两次结果字节一致 |
| 入口冒烟 | 对外入口可用 | `cli/test_entry_smoke.py` | `--version/--help` 退出码 + shell 薄壳语法 |
| 真终端 | 真 curses 渲染 | `tui/test_tui_real_terminal.py`（`script(1)` 伪终端） | POSIX + `script` 才跑，其余平台 skip |
| 性能 | 热路径耗时 | `src/python/tools/check_perf.py` | 阈值 = 实测 × 5 以上，只挡数量级退化 |
| 变异（opt-in） | 验证断言强度 | `src/python/tools/mutation_check.py`（mutmut） | 默认试点 `core/match.py`、`core/options.py` |
| 架构约束 | 依赖方向不被破坏 | `src/python/tools/check_import_surface.py`（守护第 14 项） | `core` 不导入渠道、渠道互不导入 |
| 发布 | 发行物可复现 | `src/python/tools/release.py`（check/gate/build/tag/publish） | 见 `releasing.md` |

## 4. 用例编写标准

1. **命名**：`test_<被测行为>_<条件>`，文件名写出被测内容；禁止 `test_core.py` 这类泛化命名。
2. **结构**：Arrange / Act / Assert；一个用例只表达一个行为，失败信息要能直接定位。
3. **隔离**：临时文件一律 `tempfile.TemporaryDirectory()`；**禁止**写仓库 `data/`、`logs/`。
4. **打桩**：OCR 用 `patch_ocr()`；字体用 `cjk_font()`；终端用 `FakeWin`（按显示列写、只收 str、
   统计 refresh）。**不允许**为了让用例通过而放宽替身。
5. **断言**：像素/浮点用容差（`assertAlmostEqual(delta=…)`）；禁止比两张图完全相等；
   异常断言必须指定具体类型（禁止 `assertRaises(Exception)`）。
6. **禁止**：`time.sleep` 轮询等待（用 `Event.wait()`）；`skip` 掩盖问题；
   依赖执行顺序；断言与输入无关的产物名（例如临时路径长度）。
7. **回归**：修缺陷必须补"直接在缺陷场景上断言"的用例；新增功能必须带用例。
8. **平台**：任何平台相关分支都要能在任意系统上跑（用 `sys.platform` 打桩）或显式 skip 并注明原因。

## 5. 覆盖率标准

- 总量 ≥ 96%（实测 97%）；16 个高风险模块单独设限（见 `src/python/tools/check_coverage.py` 的 `MODULE_MIN`）。
  剩余未覆盖行集中在平台分支（msvcrt 锁）与防御性 `except`，逐条在 `review-findings.md` 记录。
- 新增模块：若属于"判断密集/出错代价高"的类别，必须同时加进 `MODULE_MIN`。
- 现有门槛（贴实测下沿，防止回落）：`core/{match,options}` 90%，`core/{edit,render,image,audit}`、
  `tui/ui_draw`、`bootstrap`、`launch`、`tui/ui`、`cli/main` 85~90%，`tui/{app,ui_actions,ui_base,ui_input}` 80%，
  `cli/log_query` 90%。
- 豁免：仅允许"平台条件导入/入口薄壳"这类结构性不可覆盖；豁免要在本文与守卫里写明理由，
  不允许用 `# pragma: no cover` 大面积糊。
- 跳过率：正常模式 ≤ 15%；超出说明环境缺依赖或用例在躲问题。

## 6. 缺陷分级与回归

| 级别 | 定义 | 处理要求 |
| --- | --- | --- |
| P0 | 数据/文件损坏、原图被覆盖、崩溃 | 立即修 + 回归用例 + 记录 `review-findings.md` |
| P1 | 主要功能不可用（替换失败、入口起不来、界面无响应） | 当轮修复 + 回归用例 |
| P2 | 边界行为不符合文档、提示不清、性能退化 | 排期修复；若暂缓，`review-findings.md` 标 `待修` 并给理由 |

所有已修缺陷在 `review-findings.md` 有编号（`RF-x`）与"怎么修的"；对应任务在 `plan.md`（`PLAN-x`）。

## 7. 性能标准

- 四步热路径：`soft_iou×50` ≤ 1.0s、`erase(2000×1500)` ≤ 1.5s、`PNG 读写` ≤ 2.0s、
  日志追加×300 ≤ 1.0s，合计 ≤ 6s。
- 阈值取实测 5 倍以上，只挡数量级退化；**抖动处理**：超限自动重测一次取最小值，
  避免并行任务/冷缓存导致假红。
- 真性能优化（并发、算法）必须先在 `technical.md` 记录实测数据与放弃理由。

## 8. 跨平台标准

- 支持 Linux / macOS / Windows（Python ≥ 3.10）；CI 至少覆盖 ubuntu（3.10/3.12/3.13）+ windows。
- 差异点必须抽象成可打桩用例：无中文字体（`IMG_P_TEST_NO_CJK_FONT=1`）、
  `curses.ACS_*` 为 int、路径长度、平台默认目录、venv 解释器路径。
- 文本 I/O 一律显式 `encoding="utf-8"`（守卫检查）；`.ps1` 必须 UTF-8 with BOM。
- **不要拿本机事实当断言**（本轮 windows 作业四条红都是这一类，现已由守护拦下）：
  ① 字体家族名不能写死（Linux 是 Noto CJK、Windows 是 msyh）——从字体文件 `getname()` 反解，
  或改成与字体无关的比值；
  ② 不要用裸 `bash`/`sh`：windows-latest 上的 `bash` 常是 WSL 存根（`bash -n` 退 1 且 stderr 为空），
  统一走 `_support.bash_exe()`（真探测能不能跑，不能就 skip）；脚本的 LF 另用不依赖 bash 的用例查；
  ③ 不要在无平台守卫时碰 `fcntl`（Windows 无此模块，属性访问直接 `AttributeError`）；
  ④ 路径期望值用 `str(Path(...))` 算，不要手写 `"/x/python"`（Windows 是反斜杠）。
- 换行符由 `.gitattributes` 固定：`*.sh` 必须 LF（CRLF 会让 Windows 上的 `bash -n` 直接报错），
  `*.ps1` 用 CRLF；守护「跨平台」会核对这条规则存在。
- 守护「跨平台」的三条用例卫生规则（会在本地直接红，不等 CI）：写死字体家族 /
  裸 `bash`/`sh` / 无平台守卫的 `fcntl`；豁免写在行尾 `# platform-safe`（如 POSIX-only 的 `script(1)` 冒烟）。
- Windows 上无法用 `script(1)`：真终端冒烟自动 skip，由 ACS int 模拟 + windows 作业兜底。
- **本地 CI 矩阵**（全量模式默认全跑；`--ci-matrix` / `--font-matrix` 可单开）：
  ① 无中文字体（`IMG_P_TEST_NO_CJK_FONT=1`）；
  ② cp1252 控制台 + C locale（`PYTHONIOENCODING=cp1252 LC_ALL=C LANG=C`）——
  专治"子进程/打印按 cp1252 解码"这类只在 Windows runner 炸的问题；
  ③ **换字族/字重**（`IMG_P_TEST_FONT=alt`：粗体槽用常规体、常规槽用粗体）——
  Windows 用 msyh、Linux 用 Noto CJK，度量本来不同；写死像素/字体家族的断言在这一档就红。
  入口冒烟因此改为**本进程内跑**（`runpy` + 重定向），不经子进程管道。
- 断言卫生（守护「跨平台」本地拦，不等 CI）：不许写死字体家族名、不许裸 `bash`/`sh`、
  不许无守卫碰 `fcntl`、不许在 `assertGreater*` 里写绝对像素阈值（名字像尺寸且阈值 ≥20 才报，
  `index >= 0` 这类上下界检查不误报）、不许在断言里直接比 `sys.executable`/`sys.platform`。
  豁免：行尾 `# platform-safe`（人工确认与平台无关）；规则样本文件
  `tools/test_platform_safety_rules.py` 整体豁免——它天生要写违规写法来验证规则还活着。

### 8.1 工具链关键分支（`src/python/tools/` 不计覆盖率，靠这张表兜底）

| 工具 | 关键分支 | 用例 |
| --- | --- | --- |
| `release.py archive` | 预演不落盘 / 整块搬运 / 主台账留头+索引 / 重复跑幂等 / 同系列第二批追加 | `tools/test_release_archive.py` |
| `release.py check` | 矩阵前置（locale + 字体）失败即红 | `testplan` §8 + CI `release` 作业 |
| `check_guards`「归档」/「编号」 | 目录命名、头部四项、索引存在；编号唯一/递增/不复用 | `tools/test_platform_safety_rules.py`、`check_guards --ci` |
| `check_platform_safety` | 五条用例卫生规则 × `# platform-safe` 豁免 | `tools/test_platform_safety_rules.py` |
| `gen_folders` | 目录树生成、统计表数字重算、`alt`/指定字体模式 | `tools/test_gen_folders_stats.py` |

## 9. 质量报告与产物

| 产物 | 生成方式 | 位置 |
| --- | --- | --- |
| 用例与覆盖率原始数据 | `check_all.py` 全量 | `reports/junit.xml`、`reports/coverage.xml` |
| 覆盖率与分组统计（本仓文档） | `src/python/tools/coverage_report.py --write` | `docs/managements/test-coverage.md` |
| 性能读数 | `src/python/tools/check_perf.py` | 终端输出（超限即红） |
| CI 环境指纹 | CI `环境指纹` 步骤 | artifact `ci-env/`（python / platform / pip freeze / 字体清单） |
| windows 失败用例清单 | CI `全量用例` / `失败用例摘要` 步 | artifact `windows-junit/`（junit XML）+ 作业日志里的 `classname::name` 列表 |
| 界面快照 | `UPDATE_SNAPSHOTS=1 pytest src/test/tui/test_screen_snapshots.py` | `src/test/snapshots/tui.json` |

## 10. 合并前检查清单

- [ ] `python -m src.python.tools.check_all` 全绿（或 `--quick` + 推送前全量）
- [ ] 新缺陷有回归用例；新功能有用例；新模块有覆盖率门槛
- [ ] 改了界面 → 快照已更新且 diff 合理
- [ ] 改了依赖 → `constraints.txt` 已更新（`src/python/tools/update_constraints.py --write`）
- [ ] 改了 CLI 参数 / TUI 按键 → `README`、`how-to-use.md`、`--help` 同步
- [ ] 动了文件 → `folders.md` 已更新（守护会核对）
- [ ] 文档三件套与 `test-coverage.md` 已同步
