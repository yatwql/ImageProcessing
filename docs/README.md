# 文档索引

> 版本：v0.4

本仓所有文档的入口。`src/python/tools/check_guards.py` 的「文档索引」会核对：
每份管理文档与手册都必须出现在下面的表里，漏链即红。

## 推荐阅读顺序

| 你是…… | 按这个顺序读 |
| --- | --- |
| 第一次用 | [README](../README.md) → [使用手册](manuals/how-to-use.md) |
| 要改代码 | [CLAUDE.md](../CLAUDE.md) → [技术设计](managements/technical.md) → [架构约束与契约](managements/contracts.md) → [测试计划](managements/testplan.md) |
| 要改界面/交互 | [技术设计](managements/technical.md) §6.2 → [契约](managements/contracts.md) §2.4 → [使用手册](manuals/how-to-use.md) 按键表 |
| 要发版 | [发布流程](managements/releasing.md) → [测试计划](managements/testplan.md) §2 门禁 → [变更记录](managements/changelog.md) |
| 排查历史问题 | [自检记录](managements/review-findings.md)（RF-x）→ [计划](managements/plan.md)（PLAN-x）→ [变更记录](managements/changelog.md) |
| 查已发布版本的旧内容 | [归档规范](archive/README.md) → 对应系列目录 `archive/vX.Y.x/` |

## 1. 入口

| 文档 | 内容 |
| --- | --- |
| [README](../README.md) | 项目简介、快速开始、质量门禁、目录概览 |
| [文档索引](README.md) | 本文件：所有文档的入口与阅读顺序 |
| [CLAUDE.md](../CLAUDE.md) | 给 AI 协作者的约定：架构硬约束、代码/测试/文档纪律、已知坑 |

## 2. 面向使用者

| 文档 | 内容 |
| --- | --- |
| [使用手册](manuals/how-to-use.md) | 安装（含自动装环境）、CLI/TUI 上手、参数与按键、日志查询、常见问题 |

## 3. 面向维护者：设计与约束

| 文档 | 内容 |
| --- | --- |
| [需求](managements/requirements.md) | 范围、功能需求（FR）/非功能需求（NFR）与验收标准 |
| [技术设计](managements/technical.md) | 分层、模块表、算法与阈值、性能与测试策略、扩展点、已知限制 |
| [架构约束与设计契约](managements/contracts.md) | 依赖方向（AR-1..8）、核心 API/CLI/数据/界面契约、版本兼容策略 |

## 4. 面向维护者：质量与发布

| 文档 | 内容 |
| --- | --- |
| [测试计划与质量标准](managements/testplan.md) | 质量目标 QG-1..10、门禁分层 P0/P1/P2、14 类测试职责、用例规范、缺陷分级、合并前清单 |
| [覆盖率与分组统计](managements/test-coverage.md) | 覆盖率报告、模块门槛、场景/单元分组（由 `python -m src.python.tools.test_coverage_report --write` 生成） |
| [发布流程](managements/releasing.md) | `src/python/tools/release.py` 六个子命令、版本策略、发布清单、回滚 |

## 5. 面向维护者：过程记录

| 文档 | 内容 |
| --- | --- |
| [计划任务](managements/plan.md) | `PLAN-x` 任务与验收口径（连续编号，不复用） |
| [自检记录与缺陷](managements/review-findings.md) | `RF-x` 缺陷、技术债与验证记录 |
| [变更记录](managements/changelog.md) | 按时间倒序的实质变更（含验证方式） |

## 6. 参考

| 文档 | 内容 |
| --- | --- |
| [目录结构](managements/folders.md) | 项目统计、整仓目录树与每个文件的职责（守护逐文件核对） |

## 7. 归档

| 文档 | 内容 |
| --- | --- |
| [归档规范](archive/README.md) | `docs/archive/` 的目录与文件命名、归档文件头四项、整块搬运与「编号不复用」规则、发布时的归档步骤 |
| `archive/vX.Y.x/archived_*.md` | 每个已发布系列的 `plan` / `review-findings` / `changelog` 旧内容（发布时由 `release.py archive` 写入） |

## 维护规则

1. 新增/重命名文档：同步本索引（守护「文档索引」会拦）、同步 `folders.md` 的目录树与统计。
2. 文档开头保留 `> 版本：vX.Y` 行（守护「版本号」核对与 `version.py` 一致）。
3. 能由脚本生成的表格不手改：覆盖率/分组用 `python -m src.python.tools.test_coverage_report --write`，
   目录树与项目统计表的数字都用 `python -m src.python.tools.make_folders --write`（说明列自己写）。
4. 历史段落（`plan.md` / `review-findings.md` / `changelog.md` 的旧条目）保持原样，
   不要为了"看起来一致"去改历史记录；当前状态以上面的设计/契约/质量文档为准。
5. 发布新版本时，三份台账的旧内容整块搬进 `docs/archive/vX.Y.x/`（`release.py archive`，规则见
   [归档规范](archive/README.md)）；归档文件不手工编辑，编号归档后仍占号、不复用。
