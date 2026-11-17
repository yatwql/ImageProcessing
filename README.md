# PNG 文字替换

> 版本：v0.1

把图片里的指定文字换成别的文字，**其余文字的内容和排版一个像素都不动**；新文字自动沿用原文字的
字体、字号、字重、字色、字距和位置。原图不会被覆盖。

```text
原图：年度销售报告 2023        改成：年度财务总结 2024
      负责人：张三                   负责人：李四
```

```bash
./scripts/setup.sh                                    # 装环境（一次，等价 pip install -e .）
./scripts/cli.sh data/demo --list                     # 看示例图里有哪些文字
./scripts/cli.sh data/demo --map "2023=2024"          # 批量替换 → data/output/
./scripts/tui.sh                                      # 或者用交互界面挑着改
```

Windows（PowerShell）用同名 `.ps1`：

```powershell
.\scripts\setup.ps1                                  # 装环境（一次，-Dev 连测试依赖）
.\scripts\cli.ps1 data --list
.\scripts\cli.ps1 data --map "2023=2024"
.\scripts\tui.ps1                                    # 依赖 windows-curses，已随依赖安装
```

配置在 `/data/config/img-p.json`（模板 `/data/config/img-p.example.json`）。示例图在 `data/demo/`，
自己的图片放 `data/`（或 `/data`），结果写 `data/output/`；每次真实写盘都会在 `logs/` 留一条 JSON 记录
（源/目标文件名与大小、替换了哪些字、时间、输出哈希）。命令行与交互界面共用同一套替换逻辑。

## 质量门禁

本地与 CI 跑同一套检查，提交前钩子也跑前两项：

```bash
sh .githooks/install-hooks.sh                         # 启用提交前门禁（一次）
.venv/bin/ruff check src/ scripts/                    # 静态检查
.venv/bin/python -m mypy                              # 类型检查（守 core）
.venv/bin/python scripts/check-guards.py              # 编号/分层/文件长度/编码/测试目录
.venv/bin/python scripts/check-perf.py                # 耗时守卫
.venv/bin/python -m pytest src/test -q                # 全量用例（覆盖率阈值 75%）
```

GitHub Actions（`.github/workflows/ci.yml`）跑 test（3.10/3.12/3.13）、lint、typecheck、guards、perf 五个作业。

## 文档

| 文档 | 内容 |
| --- | --- |
| [使用手册](docs/manuals/how-to-use.md) | 安装、命令行与交互界面上手、参数、常见问题 |
| [需求文档](docs/managements/requirements.md) | 范围、功能/非功能需求、验收标准 |
| [技术设计](docs/managements/technical.md) | 架构分层、目录结构、算法与阈值、扩展点 |
| [计划任务](docs/managements/plan.md) | 当前目标、功能提升项与待排期任务 |
| [自检记录](docs/managements/review-findings.md) | 缺陷、技术债与验证记录 |
| [变更记录](docs/managements/changelog.md) | 按时间倒序的代码/用例/文档变更 |

## 目录

```text
scripts/    cli/tui/setup/test 启动脚本（.sh + .ps1）+ check-guards/check-perf/log-query
.githooks/  pre-commit 钩子（ruff + guards + 用例）与 install-hooks.sh
.github/    CI 流水线（test / lint / typecheck / guards / perf）
pyproject.toml  依赖与工具配置的唯一来源（ruff / mypy / pytest / coverage）
src/python/ 程序代码（core=核心层，cli=命令行，tui=交互界面 app + ui_* 分层）
src/test/   测试用例（core 含各处理子目录 / cli / tui）
data/       待处理图片   data/output/  输出   logs/  写盘日志
/data/config    配置文件        /data/tmp   测试中间文件        /test-reports  测试报告
docs/       需求 / 技术设计 / 使用手册
CLAUDE.md   给 AI 协作者的项目约定
```
