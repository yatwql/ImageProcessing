# 目录结构与项目统计

> 文档版本：v0.3
>
> 项目目录树 — 新增/重命名/删除任何非排除的文件或目录时，**必须同步更新此文档**；
> `src/python/tools/check_guards.py` 的第 12 项「目录树文档」会核对本文件是否覆盖了所有源文件与文档，
> 漏一个就红。

## 项目统计

> 口径：`git ls-files` 的跟踪文件；行数为文件实际行数（末行无换行按 1 行计）。
> 运行期产物（`data/output/`、`logs/`、`reports/`、`test-reports/`、`.venv/`、
> `~/.cache/retype/`）不入库，也不计入统计。

| 类别 | 语言 | 文件数 | 代码行数 | 说明 |
| --- | --- | ---: | ---: | --- |
| 主程序代码 | Python | 32 | 5,053 | `src/python/**/*.py`（不含 `tools/` 与测试）：core 核心层 / cli / tui / 引导与启动器 |
| 测试代码 | Python | 77 | 9,878 | `src/test/**/*.py`：core（7 子目录 + 属性/边界/平台）、cli（含引导/日志查询命令/入口冒烟）、tui（含快照与真终端） |
| 测试用例 | — | — | 742 | `git grep -c "def test_"` 行数口径 |
| 工程工具 | Python | 26 | 3,998 | `src/python/tools/`：守护 / 耗时 / 覆盖率门禁与报告 / 测试编排 / 变异 / 约束升级 / 发布 / 归档 / 导入方向 |
| 启动脚本 | Shell / PowerShell | 10 | 193 | `scripts/`：cli/tui/setup/run-test/log-query 各一对 `.sh` + `.ps1`，全部是薄壳 |
| CI 与钩子 | YAML / Shell | 4 | 351 | CI 八个作业 + 提交前（quick）/推送前（全量）钩子 |
| 管理文档 | Markdown | 10 | 1,880 | 需求 / 技术设计 / 契约 / 测试计划 / 覆盖率 / 发布 / 计划 / 变更 / 自检 / 目录结构 |
| 归档文档 | Markdown | 7 | 1,763 | `docs/archive/`：归档规范 + `v0.1.x/` 三份台账归档（发布时整块搬入） |
| 使用手册 | Markdown | 1 | 432 | `docs/manuals/how-to-use.md` |
| 根文档与配置 | Markdown / TOML / TXT | 7 | 500 | README、CLAUDE、pyproject、constraints、requirements×2、.gitignore |
| 文档索引 | Markdown | 1 | 79 | `docs/README.md`：所有文档的入口、阅读顺序与归档索引 |
| 示例图 | PNG | 4 | — | `data/demo/`：回归样例（报告 + 通知×3） |
| **合计（不含示例图）** | — | **178** | **24,181** | 主程序 : 测试 ≈ 1 : 1.95；仓库共 182 个跟踪文件（含示例图 4 个） |

## 目录树

```text
ImageProcessing/
├── .githooks/                                # git 钩子（core.hooksPath 指向这里）
│   ├── install-hooks.sh                      # 启用/关闭仓库钩子
│   ├── pre-commit                            # 提交前门禁：check_all --quick
│   └── pre-push                              # 推送前门禁：check_all 全量
├── .github/
│   └── workflows/                            # CI 流水线
│       └── ci.yml                            # CI：test×3 / lint / typecheck / guards / perf / windows / audit / release
├── data/
│   └── demo/                                 # 回归样例图
│       ├── 示例-报告.png                     # 回归样例（报告版式）
│       ├── 示例-通知1.png                    # 回归样例（通知版式）
│       ├── 示例-通知2.png                    # 回归样例（通知版式）
│       └── 示例-通知3.png                    # 回归样例（通知版式）
├── docs/                                     # 文档
│   ├── archive/                              # 版本归档：旧版本台账整块搬入（规则见 README）
│   │   ├── v0.2.x/                           # 版本归档系列 v0.2.x
│   │   │   ├── archived_changelog.0.2.x.md
│   │   │   ├── archived_plan.0.2.x.md
│   │   │   └── archived_review-findings.0.2.x.md
│   │   ├── v0.3.x/                           # 版本归档系列 v0.3.x
│   │   │   ├── archived_changelog.0.3.x.md
│   │   │   ├── archived_plan.0.3.x.md
│   │   │   └── archived_review-findings.0.3.x.md
│   │   └── README.md                         # 归档规范：目录/命名、头部四项、搬运与编号不复用规则
│   ├── managements/                          # 管理文档
│   │   ├── changelog.md                      # 管理文档
│   │   ├── contracts.md                      # 管理文档
│   │   ├── folders.md                        # 管理文档
│   │   ├── plan.md                           # 管理文档
│   │   ├── releasing.md                      # 管理文档
│   │   ├── requirements.md                   # 管理文档
│   │   ├── review-findings.md                # 管理文档
│   │   ├── technical.md                      # 管理文档
│   │   ├── test-coverage.md                  # 管理文档
│   │   └── testplan.md                       # 管理文档
│   ├── manuals/                              # 使用手册
│   │   └── how-to-use.md                     # 使用手册
│   └── README.md                             # 文档索引与推荐阅读顺序
├── scripts/                                  # 只放 .sh/.ps1 薄壳
│   ├── cli.ps1                               # → launch cli（Windows）
│   ├── cli.sh                                # → launch cli
│   ├── log-query.ps1                         # → launch log-query（Windows）
│   ├── log-query.sh                          # → launch log-query
│   ├── run-test.ps1                          # → src.python.tools.run_tests（Windows）
│   ├── run-test.sh                           # → src.python.tools.run_tests
│   ├── setup.ps1                             # → src.python.bootstrap（Windows）
│   ├── setup.sh                              # → src.python.bootstrap
│   ├── tui.ps1                               # → launch tui（Windows）
│   └── tui.sh                                # → launch tui
├── src/                                      # 源码包根
│   ├── python/                               # 程序代码
│   │   ├── cli/                              # 命令行渠道
│   │   │   ├── __init__.py                   # 命令行渠道
│   │   │   ├── __main__.py                   # 命令行渠道
│   │   │   ├── batch.py                      # 批量流程：规划遍、替换遍与并发档位
│   │   │   ├── log_query.py                  # 日志查询渠道：按原图名 / 日期 / 渠道过滤写盘记录并汇总
│   │   │   └── main.py                       # 命令行渠道：单图 / 目录批量。所有替换逻辑都在 src.core 里，这里只负责参数与流程
│   │   ├── core/                             # 核心层：唯一实现替换逻辑的地方
│   │   │   ├── __init__.py                   # 核心层：OCR、版式分析、字体匹配、擦除重绘
│   │   │   ├── audit.py                      # 写盘审计：图片每真正落盘一次，就往 logs/ 追加一条 JSON 行记录
│   │   │   ├── edit.py                       # 擦除原字迹并重绘新文字（replace_image 是整条流水线）
│   │   │   ├── errors.py                     # 核心层异常：库代码不直接 sys.exit，交给渠道决定怎么报错
│   │   │   ├── fonts.py                      # 本机字体发现与候选字体池。含中日韩字符时先用 fontconfig 过滤缺字形的字体
│   │   │   ├── image.py                      # 图片读取 / 保存 / 目录扫描
│   │   │   ├── jobs.py                       # 把「映射表 / 手工区域 / TUI 里的块」统一变成 Job 列表
│   │   │   ├── match.py                      # 替换任务（Job）与「映射表 → 任务」的匹配规则
│   │   │   ├── ocr.py                        # OCR（RapidOCR，离线中英文）：整图文字块与区域文字
│   │   │   ├── options.py                    # 运行选项与颜色解析
│   │   │   ├── render.py                     # 文字排版渲染：行渲染、字符横向区间、绘制到画布
│   │   │   └── style.py                      # 版式分析：字迹 mask、字色、笔画粗细、字体/字号/字距反解
│   │   ├── tools/                            # 开发工具（不进发行包、不计覆盖率）
│   │   │   ├── guards/
│   │   │   │   ├── __init__.py               # 工程守护的各项检查，按类别拆开；入口仍是 `tools/check_guards.py`
│   │   │   │   ├── code.py                   # 代码守护：分层方向、单文件长度、显式编码、测试目录与字体、脚本类型与编码（守护第 3~6/10/17~1
│   │   │   │   ├── common.py                 # 守护检查共用：仓库路径、阈值常量/正则与读文件
│   │   │   │   ├── docs.py                   # 文档守护：目录树文档、文档索引、归档目录与台账索引（守护第 9/12/13 项）
│   │   │   │   ├── ids.py                    # 编号守护：台账编号连续唯一、旧前缀不复用、归档编号仍占号（守护第 1~2 项）
│   │   │   │   ├── meta.py                   # 工程元信息守护：版本号与名称、依赖锁、导入方向、工作流、跨平台安全（守护第 7~8/11/14~16 项
│   │   │   │   └── scripts.py                # 脚本与文档链路的守护：脚本命名/契约、文档死链、用例对照表覆盖
│   │   │   ├── __init__.py                   # 开发工具（不进发行包）：守护、覆盖率、测试编排、发布等
│   │   │   ├── _parallel.py                  # 门禁并行执行：worker 数规划与"互不干扰"的批次并发
│   │   │   ├── _paths.py                     # 工具共用的路径常量：仓库根
│   │   │   ├── check_all.py                  # 本地全量门禁：一条命令跑完 CI 跑的所有检查，绿了再推
│   │   │   ├── check_coverage.py             # 覆盖率门禁：总覆盖率 + 高风险模块单独设限 + skip 上限
│   │   │   ├── check_guards.py               # 工程守护：把 `CLAUDE.md` 里的硬性约束变成可执行检查
│   │   │   ├── check_import_surface.py       # 架构约束：模块导入方向（谁可以依赖谁）
│   │   │   ├── check_perf.py                 # 耗时守卫：把最热的几步钉住，退化即红
│   │   │   ├── check_platform_safety.py      # 跨平台安全：把"只在 Windows/macOS 上才炸"的写法在本地拦下来
│   │   │   ├── check_workflows.py            # CI 工作流自检：把"只在 runner 上才炸"的脚本错误搬到本地
│   │   │   ├── ci_env.py                     # CI 环境指纹：把"这次跑在什么环境"落成文件，失败时随 artifact 上传
│   │   │   ├── coverage_report.py            # 生成 `docs/managements/test-coverage.md`：覆盖率报告 + 测试分组统
│   │   │   ├── gate_stamp.py                 # 全量门禁通过戳：同一份代码不重复跑整条全量门禁
│   │   │   ├── gen_folders.py                # 重新生成 `docs/managements/folders.md` 的两个"机器可算"部分：目录树与项
│   │   │   ├── junit_summary.py              # JUnit 报告摘要：把失败用例列成一行一条，CI 里一眼看清红在哪
│   │   │   ├── mutation_check.py             # 变异测试（opt-in）：验证用例真的能"杀死"错误实现，而不只是覆盖到行
│   │   │   ├── release.py                    # 发布流程编排：把"出一次版本"固化成可审阅的子命令，失败即停
│   │   │   ├── run_tests.py                  # 测试入口：跑全量用例并生成 junit / html / 覆盖率报告与摘要
│   │   │   └── update_constraints.py         # 依赖升级助手：列出可升级项，并按当前环境重写 constraints.txt 的非标记部分
│   │   ├── tui/                              # 交互渠道
│   │   │   ├── __init__.py                   # 交互界面渠道（curses）
│   │   │   ├── __main__.py                   # 交互渠道
│   │   │   ├── app.py                        # TUI 渠道的状态层：只维护数据与动作，不碰 curses
│   │   │   ├── browse.py                     # 目录扫描：把"一个目录里有什么"变成左栏的行（父目录 / 子目录 / 图片）
│   │   │   ├── ui.py                         # TUI 渠道的入口：启动参数、主循环、窗口初始化
│   │   │   ├── ui_actions.py                 # TUI 动作层：按键分发与编辑动作（只改 `App` 状态，不画界面）
│   │   │   ├── ui_base.py                    # TUI 基础层：文案、宽字符处理、颜色与落字
│   │   │   ├── ui_draw.py                    # TUI 绘制层：把 `App` 的状态画到窗口上（宽屏双栏 / 窄屏单栏）
│   │   │   └── ui_input.py                   # TUI 输入层：按键序列解析与单行输入
│   │   ├── __init__.py                       # retype：图片文字替换。core=核心逻辑，cli=命令行渠道，tui=交互渠道
│   │   ├── bootstrap.py                      # 环境引导：建 `.venv`、按 `constraints.txt` 装依赖、写默认配置
│   │   ├── config.py                         # 全局路径与配置：默认读 <配置目录>/retype.json（旧 img-p.json 仍兼容），图片在
│   │   ├── launch.py                         # 统一启动器：先确认环境就绪（必要时自动装依赖），再把控制权交给真正的入口
│   │   ├── stdio.py                          # 控制台编码：保证中文提示在非 UTF-8 的终端（Windows cp936/cp1252）上也能打印
│   │   └── version.py                        # 程序名称与版本号：全仓库唯一来源
│   ├── test/                                 # 测试用例
│   │   ├── cli/                              # CLI 用例
│   │   │   ├── __init__.py                   # cli 场景测试
│   │   │   ├── test_arguments.py             # CLI 参数层测试：默认值、参数合并、非法用法与提前报错
│   │   │   ├── test_batch_directory.py       # CLI 目录批量测试：逐图处理、汇总统计、输出命名、dry-run 与过滤规则
│   │   │   ├── test_bootstrap_launch.py      # 环境引导与启动器：`bootstrap.py` / `launch.py` 的分支与错误路径
│   │   │   ├── test_bootstrap_probe_paths.py  # 环境引导与入口壳：探测失败、缺 pip、入口 shim、外部命令缺失
│   │   │   ├── test_cli_failure_paths.py     # CLI 失败路径：读图失败、同名拒绝、占名失败、预演去重、保存清理
│   │   │   ├── test_demo_assets.py           # 用仓库自带示例图（data/demo）跑真实图片流程：读取、单图替换、批量、日志
│   │   │   ├── test_entry_smoke.py           # 入口冒烟：每个对外入口都能起来、给出正确退出码与帮助文本
│   │   │   ├── test_launch_env.py            # 启动器与环境引导：首次运行自动装依赖，设 `IMG_P_NO_AUTO_SETUP=1` 才退回手动
│   │   │   ├── test_log_query_cli.py         # 日志查询入口（`src/python/cli/log_query.py`）：过滤、`--json`、坏参
│   │   │   └── test_single_image.py          # CLI 单图流程测试：--list、输出位置、dry-run、样式覆盖、失败提示
│   │   ├── core/                             # 核心层用例
│   │   │   ├── background/                   # 背景类型用例
│   │   │   │   ├── __init__.py               # 图片处理场景：background
│   │   │   │   └── test_background_types.py  # 背景类型场景：纯色、渐变、带噪声背景上的字迹分析与擦除
│   │   │   ├── color/                        # 颜色与透明用例
│   │   │   │   ├── __init__.py               # 图片处理场景：color
│   │   │   │   ├── test_alpha_channel.py     # 透明通道场景：带 alpha 的图擦除后不留字形轮廓，重绘后新字不透明
│   │   │   │   └── test_text_colors.py       # 文字颜色场景：深色/彩色/浅色文字的取样与还原
│   │   │   ├── font/                         # 字体用例
│   │   │   │   ├── __init__.py               # 图片处理场景：font
│   │   │   │   ├── test_font_matching_edges.py  # 字体匹配与候选池的退化路径：渲染失败、缓存损坏、字号/字距搜索兜底
│   │   │   │   └── test_font_pool.py         # 字体池测试：候选池构建、并发上限、CJK 过滤、落盘缓存与失效
│   │   │   ├── format/                       # 图片格式用例
│   │   │   │   ├── __init__.py               # 图片处理场景：format
│   │   │   │   ├── test_image_io_edges.py    # 图片读写边界：alpha 保留、格式表、元数据读取失败
│   │   │   │   └── test_image_read_write.py  # 图片读写与输出路径测试：格式支持、alpha 处理、目录扫描、重名编号、同文件判定
│   │   │   ├── layout/                       # 排版用例
│   │   │   │   ├── __init__.py               # 图片处理场景：layout
│   │   │   │   └── test_text_layout.py       # 排版形态场景：逐字加宽的标题、多行正文、居中横幅
│   │   │   ├── mapping/
│   │   │   │   └── test_matching_edge_cases.py  # 映射规则的边界：归一化、整行/行内/模糊命中、冲突与低置信过滤
│   │   │   ├── pipeline/                     # 端到端用例
│   │   │   │   ├── __init__.py               # 图片处理场景：pipeline
│   │   │   │   ├── test_edit_pipeline_edges.py  # 替换流水线边界：调试图写失败、span 越界、行内区间无墨迹时的回退
│   │   │   │   └── test_replace_pipeline.py  # 替换流水线测试：行内替换只动目标片段、重复执行结果一致、拒绝覆盖原图
│   │   │   ├── primitives/                   # 渲染/擦除原语用例
│   │   │   │   ├── __init__.py               # 图片处理场景：primitives
│   │   │   │   ├── test_erasing_and_drawing.py  # 擦除与绘制测试：局部擦除、多行绘制、对齐落位、字距与字号估算
│   │   │   │   ├── test_inpaint_radius.py    # 擦除阶段的自适应 inpaint 半径：粗笔画要更大邻域，细笔画不能糊开
│   │   │   │   ├── test_rendering_edges.py   # 绘制与字距的边界：空行、越界裁切、对齐、无墨迹时字距不收敛
│   │   │   │   ├── test_rendering_primitives.py  # 文字渲染测试：单行渲染、字符横向区间、字距求解、模糊 IoU
│   │   │   │   └── test_style_analysis.py    # 版式分析测试：从合成图反解字色、字迹范围、字号与候选字体
│   │   │   ├── __init__.py                   # core 场景测试
│   │   │   ├── test_audit_log_edges.py       # 写盘日志与文件锁：坏行跳过、写入失败、跨平台锁后端、旧日志清理
│   │   │   ├── test_cancel_pipeline.py       # 替换过程中的中断：`replace_image(should_stop=...)` 要在块与块之间能停手
│   │   │   ├── test_config_and_ocr_edges.py  # 配置文件与 OCR 封装的边界：未覆盖项、缺依赖、空结果
│   │   │   ├── test_config_file.py           # 配置文件（<配置目录>/retype.json，兼容旧 img-p.json）：读取、容错与优先级
│   │   │   ├── test_error_contract.py        # 错误契约测试：核心层用 CoreError 报可预期失败，不直接退出进程
│   │   │   ├── test_log_query.py             # 日志查询：按日期/原图/渠道过滤，并汇总替换次数
│   │   │   ├── test_mapping_rules.py         # 映射规则测试：映射表与文字块如何变成替换任务（Job）
│   │   │   ├── test_ocr_contract.py          # OCR 封装测试：结果结构、区域裁剪、引擎缺失时的错误契约
│   │   │   ├── test_platform_stability.py    # 跨平台兼容与稳定性：路径/配置/环境变量、异常契约、幂等与规模
│   │   │   ├── test_properties.py            # 属性测试（hypothesis）：用生成的大量输入验证"永远成立的性质"
│   │   │   ├── test_report_inline_fragment.py  # 行内替换的报告/日志字段：`old` 是整行、`new` 只是片段，必须再记下命中的子串与区间
│   │   │   ├── test_stdio.py                 # 控制台编码：中文提示在非 UTF-8 终端（Windows cp936）上不能崩
│   │   │   ├── test_version_display.py       # 版本号：唯一来源、界面可见、每次运行都报、写盘日志记录、文档开头一致
│   │   │   └── test_write_audit_log.py       # 写盘日志：真实保存图片后必须留下一条可追溯的记录
│   │   ├── snapshots/                        # 界面快照数据
│   │   │   └── tui.json                      # 界面快照数据
│   │   ├── tools/
│   │   │   ├── __init__.py                   # 工程工具用例（发布编排 / 归档流程等）
│   │   │   ├── test_gate_pipeline.py         # 门禁流水线：worker 规划、批次并发、档位选择、收集数核对、发布预检的失败即停
│   │   │   ├── test_gate_stamp.py            # 门禁戳（`gate_stamp`）：同一份代码不重复跑全量门禁
│   │   │   ├── test_gen_folders_stats.py     # `gen_folders` 的统计表重算：数字由脚本算，说明列与表结构一概不动
│   │   │   ├── test_junit_summary.py         # CI 失败摘要工具（`junit_summary`）：把 junit 报告里的红用例列成 `class:
│   │   │   ├── test_perf_limits.py           # 耗时守卫的平台档：Windows runner 的 fsync 慢一个量级，只放大落盘那一步
│   │   │   ├── test_platform_safety_rules.py  # 「跨平台」守护的规则自检：规则本身也要有用例，否则它会悄悄失效
│   │   │   ├── test_release_archive.py       # 归档流程（`release.py archive`）的用例
│   │   │   ├── test_release_versions.py      # 版本号与分支策略（`-dev` 开发版 / 正式版）：`release.py` 的定版与切版
│   │   │   ├── test_tool_entry_contracts.py  # 工程工具的入口契约：每个 CLI 都能 `--help`（不炸）、`--ci` 结论可读
│   │   │   └── test_workflow_checks.py       # 工作流自检（`check_workflows`）：bash 语法检查要在"没有真 bash"时优雅跳过
│   │   ├── tui/                              # 交互用例
│   │   │   ├── __init__.py                   # tui 场景测试
│   │   │   ├── test_apply_and_batch.py       # TUI 执行流程测试：替换当前图、批量确认、重名与覆盖保护
│   │   │   ├── test_directory_browsing.py    # TUI 目录浏览：左栏同时列出「上级目录 / 子目录 / 图片」，可进入、可回上级
│   │   │   ├── test_interaction_edges.py     # 交互边界：样式/映射面板的非法输入、目录浏览的边界、批量与取消的组合
│   │   │   ├── test_key_dispatch.py          # 按键分发：每个键都要落到明确的状态变化，且不越界、不崩
│   │   │   ├── test_keys_and_navigation.py   # TUI 按键测试：转义序列解码、方向键与别名键导航、数字跳图、Esc 语义
│   │   │   ├── test_layout_rendering.py      # TUI 布局渲染测试：双栏/单栏切换、窄屏提示、异常不外溢
│   │   │   ├── test_mapping_panel.py         # TUI 全局映射面板（e 键）：新增、修改、删除、导出 JSON
│   │   │   ├── test_screen_snapshots.py      # TUI 屏幕快照：把固定尺寸 × 固定状态下的整屏文本钉住
│   │   │   ├── test_session_state.py         # TUI 会话状态测试：样式选项校验、映射表读写（不涉及 curses 界面）
│   │   │   ├── test_settings_panel.py        # TUI 样式选项面板（c 键）：逐项编辑、非法值只提示、Esc 返回
│   │   │   ├── test_tui_real_terminal.py     # 真终端冒烟：在伪终端里跑一次真 curses，确认"屏幕上真的有东西"
│   │   │   ├── test_tui_state_edges.py       # TUI 状态与布局边界：面板导航、输入行、状态行、批量取消、窄窗兜底
│   │   │   └── test_ui_shell.py              # TUI 外壳：参数解析、入口分支、主循环异常处理与基础绘制件
│   │   ├── __init__.py                       # 测试用例包：统一仓库根路径与测试临时目录
│   │   ├── _support.py                       # 测试公共设施：字体路径、合成 OCR 结果、TUI 假窗口
│   │   └── conftest.py                       # pytest 全局钩子：用例不许往仓库真实产物目录（`data/output/`）写文件
│   └── __init__.py                           # 项目源码包：src.python 为程序代码，src.test 为测试用例
├── .gitattributes                            # 仓库根
├── .gitignore                                # 忽略虚拟环境 / 缓存 / 输出 / 日志
├── CLAUDE.md                                 # AI 协作者约定：架构硬约束、纪律、已知坑
├── README.md                                 # 项目简介 / 快速开始 / 门禁 / 文档索引
├── constraints.txt                           # 锁定依赖组合（含 3.10 与 Windows 分档）
├── pyproject.toml                            # 唯一配置源：依赖 + dev extra + ruff/mypy/pytest/coverage
├── requirements-dev.txt                      # 兼容壳：`-e .[dev]`
└── requirements.txt                          # 兼容壳：`-e .`
```

## 排除项（不入库、不计入统计）

| 路径 | 说明 |
| --- | --- |
| `.venv/` | 虚拟环境；`scripts/setup.sh` 或任意启动脚本首次运行时自动创建 |
| `data/output/` | 默认输出目录（`-o` / `--out-dir` / `IMG_P_OUT_DIR` 可改） |
| `logs/` | 写盘日志，按天一个 JSONL（`--log-dir` / `IMG_P_LOG_DIR` 可改） |
| `/data/tmp` | 测试中间文件（`IMG_P_TMP_DIR` 可改；不可写时退回系统临时目录） |
| `/test-reports`（或 `reports/`） | 测试报告：junit / html / coverage / summary.md |
| `~/.cache/retype/fonts.json` | 字体池缓存（按字体文件签名失效） |
| `__pycache__/`、`.pytest_cache/`、`.ruff_cache/` | 运行缓存，测试脚本结束时清理 |
| `*.egg-info/`、`build/`、`dist/` | 打包产物 |

## 维护规则

1. 新增/移动/删除文件：改代码的同一次提交里更新本文件（树 + 统计），否则守护会红。
2. 调整分层（例如把逻辑从 `scripts/` 挪到 `src/python/`）：同步 `technical.md` 的「目录结构」与本文件。
3. 统计数字随手更新即可（改动的文件行数不必精确到个位，量级要对）。
4. 运行期产物的新目录：加到上表「排除项」，不要藏进树里。
