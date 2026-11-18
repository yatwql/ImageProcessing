# 文档索引

> 版本：v0.1

本仓所有文档的入口。`src/python/tools/check_guards.py` 的第 15 项「文档索引」会核对：
每份管理文档与手册都必须出现在下表中，否则即红。

## 面向使用者

| 文档 | 内容 |
| --- | --- |
| [使用手册](manuals/how-to-use.md) | 安装（含自动装环境）、CLI/TUI 上手、参数与按键、日志查询、常见问题 |
| [README](../README.md) | 项目简介、快速开始、质量门禁、目录概览 |

## 面向维护者（管理文档）

| 文档 | 内容 |
| --- | --- |
| [需求](managements/requirements.md) | 范围、功能需求（FR）/非功能需求（NFR）与验收标准 |
| [技术设计](managements/technical.md) | 分层、模块表、算法与阈值、性能与测试策略、扩展点 |
| [架构约束与设计契约](managements/contracts.md) | 依赖方向（AR-x）、核心 API/CLI/数据/界面契约、版本兼容策略 |
| [测试计划与质量标准](managements/testplan.md) | 质量目标 QG-1..9、门禁分层 P0/P1/P2、13 类测试职责、用例规范、缺陷分级 |
| [覆盖率与分组统计](managements/test-coverage.md) | 覆盖率报告、模块门槛、场景/单元测试分组（`src/python/tools/coverage_report.py` 生成） |
| [发布流程](managements/releasing.md) | `src/python/tools/release.py` 六个子命令、发布前检查清单、回滚方式 |
| [计划任务](managements/plan.md) | `PLAN-x` 任务与验收口径 |
| [变更记录](managements/changelog.md) | 按时间倒序的实质变更 |
| [自检记录与缺陷](managements/review-findings.md) | `RF-x` 缺陷、技术债与验证记录 |
| [目录结构](managements/folders.md) | 项目统计、整仓目录树与每个文件的职责 |

## 工程约定

| 文档 | 内容 |
| --- | --- |
| [CLAUDE.md](../CLAUDE.md) | 给 AI 协作者的约定：架构硬约束、代码/测试/文档纪律、已知坑 |
| [README](../README.md) | 快速开始与门禁命令 |

## 维护规则

1. 新增/重命名文档：同步本索引（守护会拦）；同步 `folders.md` 的目录树与统计。
2. 文档开头保留 `> 版本：vX.Y` 行（守护「版本号」校验与 `version.py` 一致）。
3. 能由脚本生成的表格（覆盖率、目录树统计）不手改，跑对应工具重新生成。
