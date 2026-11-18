# 自检记录与缺陷

> 版本：v0.1

> 记录开发自检时发现的问题、处理方式与遗留风险。编号 `RF-x`；
> **编号约定**：本文件的任务与缺陷一律 `RF-x`（连续编号，不复用；早期 `TD-x` 已并入本系列）；
> `plan.md` 里的任务一律 `PLAN-x`。
> 状态：`已修` / `待办` / `待定` / `不修（有理由）`。

## 2026-11-10 写盘日志（FR-7）

| 编号 | 类型 | 发现 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-1 | 设计缺口 | 只在 `core.audit` 里实现写日志，CLI/TUI 不调用等于没记 | 两个渠道保存成功后各调一次 `record_write`，并传渠道名与显式选项 | 已修 |
| RF-2 | 测试污染 | 默认日志目录是仓库根 `logs/`，用例会把日志写进项目 | `config.log_dir()` 支持 `IMG_P_LOG_DIR` 覆盖；用例全部指向 `TemporaryDirectory` | 已修 |
| RF-3 | 覆盖不全 | `--debug` 写出的 mask 图也是图片写盘，初版没记 | `replace_image` 增加 `source` 参数，调试图按 `action=写出调试图` 记账 | 已修 |
| RF-4 | 契约风险 | 日志写失败若抛到上层，会把「图片已保存」误报成替换失败 | `record_write` 抛 `CoreError`，CLI/TUI 捕获后只提示「已保存但…」 | 已修 |
| RF-5 | 静默风险 | 预演（`--dry-run`）没有写盘，若记日志会误导审计 | 只在 `save_image` 成功之后记录；`dry-run` 分支完全不触碰日志 | 已修 |
| RF-6 | 字段歧义 | 行内替换时报告里 `old` 是整行文字、`new` 只是替换片段，日志照录会看起来不对等 | 暂时如实记录并在手册标注；是否同时记录命中子串与 span 待定 | 待定 |
| RF-7 | 默认值噪声 | `options_summary` 初版把默认值 `max_fonts=160` 也写进日志 | 与 `Options()` 默认值比较，相等即省略 | 已修 |
| RF-10 | 契约冲突 | `--dry-run` 不存结果图，但 `--debug` 仍会写 mask 并记日志，与“预演不写文件”矛盾（补用例时发现） | `--dry-run` 下忽略 `--debug`并在 stderr 提示；已加用例固定该行为 | 已修 |
| RF-11 | 用例污染 | 新用例初版没传 `--out-dir`，输出落到仓库 `data/output/` 且受已有文件影响拿到 `-44` 后缀 | 用例一律指定临时输出目录，并断言日志里的真实目标名 | 已修 |
| RF-12 | 消息被覆盖 | TUI 日志写失败时设置的提示被 `apply_one` 末尾的返回消息覆盖 | 把日志错误拼到返回消息末尾，界面与用例都能看到 | 已修 |
| RF-13 | 用例冗余 | 审计用例里 `record_write` 的渠道字段被 CLI/TUI 用例重复覆盖；调试图记账的 CLI 端到端与核心层单测几乎重合；`options_summary(None)` 单独立一例偏碎 | 删除重复用例，保留端到端用例并补断言（mask 文件真的写出）；None 分支并入相邻用例 | 已修 |
| RF-14 | 命名偏离 | `test_options_summary_skips_default_project_and_channel_fields` 中的 “project” 不存在，语义不清 | 重命名为 `..._skips_defaults_and_runtime_fields` | 已修 |
| RF-23 | 测试卫生 | 新增 CSS 检查发现的遗留：旧用例只删 `report.png`，编号产物越积越多 | 改为目录快照对比并清理新增文件，同时删掉历史堆积 | 已修 |
| RF-15 | 断言不可满足 | 宽字距用例断言替换后宽度 > 200，但测试图本身只能画出 191（阈值错，不是实现回归） | 改为与原图宽度比较（≥ 85%），用例语义回到“字距不被收紧” | 已修 |

## 2026-11-10 代码/功能/债务复查

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-17 | 功能缺陷 | 调色板 PNG（`P` 模式 + `tRNS`）的透明信息在 `load_image` 被丢弃，替换后透明背景变实色 | alpha 统一从 `convert("RGBA")` 取，全不透明才返回 None | 已修 |
| RF-18 | 功能缺陷 | 输出扩展名不在支持表时 `Image.save` 抛 `ValueError`，渠道未捕获→直接 traceback | `save_image` 事先校验并抛 `CoreError`，CLI/TUI 改为一句提示 | 已修 |
| RF-19 | 功能缺陷 | TUI 下 `core` 仍会向 stderr 打印（未识别/字体不可靠），在 curses 里会冲花界面 | `App` 初始化时强制 `opts.quiet=True`，界面只用自己的消息行 | 已修 |
| RF-20 | 审计失真 | `--debug` 的 `cv2.imwrite` 失败时仍写日志，出现“日志说有、磁盘上没有” | 检查返回值，失败抛 `CoreError` 且不记日志 | 已修 |
| RF-21 | 功能缺陷 | `--out-dir` 帮助文本写的是“默认 <输入目录>/replaced”，实际是 `data/output` | 改正帮助文本 | 已修 |
| RF-22 | 功能缺陷 | TUI 复用 `img.saved` 时用字符串比较目录，相对/绝对混用会每次多生成 `-1` 文件 | 改比 `abspath(dirname)`，并抽 `_same_out_dir()` | 已修 |

| RF-24 | 功能缺陷 | `--quality` 只对 JPEG 生效，WEBP 输出仍是默认质量（文档却说两者都支持） | `save_image` 按 `fmt in ("JPEG","WEBP")` 传 quality，并加用例 | 已修 |
| RF-25 | 契约缺口 | 核心层不校验质量范围，库调用方传 0/999 会被 Pillow 静默接受 | `save_image` 校验 1-100，越界抛 `CoreError` | 已修 |
| RF-26 | 交互缺陷 | TUI 质量输入非法时把已设置的值重置为“自动” | 非法输入只提示并保留原值 | 已修 |
| RF-27 | 状态缺陷 | 上一张图的核心层警告会残留到下一张的消息行 | 进入替换流程前清空 `App.warned` | 已修 |
| RF-28 | 平台缺陷 | Windows 上日志写入没有跨进程锁，多开批量可能交错 | 新增 `msvcrt.locking` 分支（与 `flock` 同一出口） | 已修 |

| RF-29 | 测试脆弱 | TUI 用例依赖仓库 `data/` 里恰好有多张图，数据目录一变就误报 | `_support.make_app` 改为在临时目录造图 | 已修 |
| RF-30 | 用例说明 | 并发日志用例用 fork，Python 3.13 在多线程进程里会告警且 Windows 不可用 | 改 `spawn` 上下文，worker 提到模块级 | 已修 |

| RF-31 | 素材缺陷 | `data/demo/示例-报告.png` 是占位图（只有「第0行文字」），文档里的示例输出与它不符 | 重新生成与文档一致的示例图，并加用例锁住内容 | 已修 |

| RF-32 | 仓库卫生 | 根目录 `conftest.py`、散落的 `__pycache__` 与 `.pytest_cache` 属于运行产物，混在源码里 | 删 `conftest.py`（改 `pytest.ini` + `src/test/__init__.py`），清缓存，测试脚本结束自动清理 | 已修 |

### 技术债务（已清偿，保留记录）

| 编号 | 位置 | 说明 | 影响 |
| --- | --- | --- | --- |
| RF-33 | `core/audit.record_write` | 无跨进程锁，仅靠 POSIX 单行 `O_APPEND` 的原子性 | 已修：`flock` 串行写 + 解锁后关闭 |
| RF-34 | `core/image.unique_path` | 先查后写（TOCTOU） | 已修：新增 `reserve_path()`（`O_CREAT\|O_EXCL`），CLI/TUI 均改用；失败清理占位文件 |
| RF-35 | TUI | 核心层警告只能屏蔽、不能显示 | 已修：`Options.warn` 回调 + `App.on_core_warning()`，警告进消息行 |
| RF-36 | `core/image.save_image` | JPEG 质量硬编 95 | 已修：`quality` 参数 + CLI `--quality` + TUI 样式面板 |
| RF-37 | 日志字段 | 不记尺寸/哈希 | 已修：`dst_sha256` `dst_width` `dst_height` |
| RF-38 | `core/audit.record_write` | 不 `fsync` | 已修：写后 `fsync`，失败抛 `CoreError` |
| RF-39 | `data/output/` | 旧用例往仓库输出目录写文件 | 已修：用例改为前后快照并清理；历史 `report-*.png` 已删 |

## 遗留缺陷（非本次引入）

| 编号 | 位置 | 现象 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-9 | `test_text_layout.py` | 导入语句未按 ruff isort 格式化，静态检查告警 | 已用 `ruff --fix` 整理 | 已修 |
| RF-16 | `data/output/` | 早期用例会向仓库默认输出目录生成图片（已用 `report-*` 后缀堆积） | 新用例均指定临时 `--out-dir`；旧用例暂未改动，产物已被 `.gitignore` 忽略 | 待定 |

## 2026-11-10 全面评估（工程化整改）

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-40 | 工程缺口 | 无 `pyproject.toml`：依赖在两份 requirements、ruff/pytest 参数散在脚本里，`pip install -e .` 不可用 | 建 `pyproject.toml` 作为单一配置源（依赖 + `dev` extra + ruff/mypy/pytest/coverage），requirements 退化为 `-e .` / `-e .[dev]` | 已修 |
| RF-41 | 工程缺口 | 无 CI：本地全绿靠自觉，格式/类型/文档漂移无人拦 | 新增 `.github/workflows/ci.yml` 五个作业（test/lint/typecheck/guards/perf） | 已修 |
| RF-42 | 工程缺口 | 无提交前门禁 | `.githooks/pre-commit` + `install-hooks.sh`（`core.hooksPath`，不动 `.git/hooks`） | 已修 |
| RF-43 | 约束失效 | CLAUDE.md 的硬性约束全靠人工复核（core 禁 argparse/curses/sys.exit、单文件 ≤1000 行、文本 I/O 显式 encoding） | `tools/check_guards.py` 十二项自动判定，CI 与钩子都跑；测试目录/空包/文档同步也纳管 | 已修 |
| RF-44 | 质量缺口 | 无类型检查、无覆盖率门禁 | `mypy` 守 `core`（28 处历史 error 全部修掉：补注解、`rendered` 可空标注、dtype 标注）；`fail_under = 75` | 已修 |
| RF-45 | 类型桩冲突 | numpy 2.5 的桩要求 `ndarray.min()/max()` 显式给 axis，`int(arr.min())` 被判成无匹配重载 | 改成内建 `min()/max()`（坐标数组很小，取值方式不影响耗时），不再依赖 `disable_error_code` 兜底 | 已修 |
| RF-46 | 测试结构 | `src/test/image_processing/**` 与 `src/test/core/**` 两套命名并存，`image_processing/degrade/` 是空包，文档只写了 core/tui/cli | 七个测试子目录并入 `src/test/core/**`，删空包，`technical.md`/`CLAUDE.md` 同步 | 已修 |
| RF-47 | 可维护 | `tui/ui.py` 856 行，逼近 1000 行红线，绘制/按键/动作/文案混在一处 | 拆成 `ui_base`（文案+宽字符+颜色）、`ui_draw`（布局）、`ui_input`（按键+输入行）、`ui_actions`（分发+编辑），`ui.py` 只留入口与门面 | 已修 |
| RF-48 | 画质缺陷 | 擦除半径写死 4：粗笔画/大标题 inpaint 后留模糊边 | `edit.inpaint_radius` 按笔画宽度自适应（4~14），细体仍停在 4；补 6 个用例 | 已修 |
| RF-49 | 交互缺陷 | 批量替换无进度、不可中断，等半天不知道做到哪张 | `apply_all(progress, should_stop)`：逐图进度 + Esc 中断，状态行显示「已取消，完成 x/n」；`_poll_cancel` 只认 Esc（q 不误停） | 已修 |
| RF-50 | 可观测缺口 | 日志只能写不能查，核对「这张图被换过几次」只能 `grep` | `core.audit.read_entries/summarize`（坏行跳过、目录缺失返回空）+ `scripts/log-query.py`（原图/日期/渠道、`--json`） | 已修 |
| RF-51 | 可测性 | `record_write` 不接受显式时间，按历史日期补录/用例无法固定落哪个按天文件 | 加 `when` 参数并透传给 `log_path`/`build_entry` | 已修 |
| RF-52 | 环境缺陷 | 目录从 `img-p` 改名后 `.venv/bin/pip` 的 shebang 仍指向旧路径，任何 `pip install` 直接“无法执行” | setup 脚本统一用 `.venv/bin/python -m pip` | 已修 |

## 2026-11-17 版本号（FR-12）

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-53 | 可追溯 | 版本号只出现在 `pyproject.toml` 与 `__version__` 两处，且互不校验；日志里看不出是哪一版写的 | 新增 `src/python/version.py` 作为唯一来源，pyproject 改 dynamic，写盘日志加 `app_version` | 已修 |
| RF-54 | 用户体验 | 运行时不报版本，反馈问题时无法确认跑的是哪一版 | CLI 每次运行先打 `retype 0.1` 到 stderr（stdout 留给清单/摘要），TUI 进 curses 前打印并写进标题栏与帮助页 | 已修 |
| RF-55 | 文档 | 8 份文档没有版本行，容易拿旧文档对照新行为 | 各文档开头统一 `> 版本：v0.1`，`check-guards.py` 第 7 项校验代码/打包/文档三处一致 | 已修 |

## 2026-11-17 稳定性与交互补强

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-56 | 可复现性 | 依赖只有下界：`opencv`/`rapidocr`/`onnxruntime` 大版本漂移会静默改变像素结果，CI 与本地也可能跑在不同版本上 | 新增 `constraints.txt` 精确固定直接与传递依赖；setup 与 CI 统一 `pip install -c`；守护第 8 项校验"全部 `==` 且覆盖 pyproject 的直接依赖" | 已修 |
| RF-57 | 交互缺陷 | 批量取消只在两张图之间生效：单张图里 OCR + 字体匹配最慢的几秒按 Esc 完全没反应 | `replace_image(should_stop=)` 每块之前询问回调，`App.apply_one` 传入 `self.cancel`；取消时返回「已取消」并保留已完成块 | 已修 |
| RF-58 | 测试覆盖 | `ui_actions.py` 55%、`ui.py` 64%、`app.py` 78%：交互路径最可能坏却测最少 | 新增 `test_key_dispatch.py`（三块面板逐键）+ `test_cancel_pipeline.py`（核心中断）+ CLI 契约用例；总覆盖率 80% → 84% | 已修 |

## 2026-11-17 Windows 脚本乱码

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-59 | 平台缺陷 | `.ps1` 存成 UTF-8 无 BOM，Windows PowerShell 5.1 按 ANSI(GBK) 解析，中文提示变成「缂哄皯杩愯鐜」这类乱码，用户看不懂报错 | 四个脚本一律改 UTF-8 with BOM；`check-guards.py` 新增「PS 编码」（第 9 项）拦截回退；手册补 Windows 注意事项 | 已修 |

## 2026-11-17 目录归位

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-60 | 结构偏离 | `scripts/` 写着"只放启动脚本"，却堆了 515 行程序代码（check-guards 309、check-perf 124、log-query 82），且 setup/test 两端各有一份 130+ 行的编排脚本 | 工程工具移到 `tools/`（check_guards.py / check_perf.py / run_tests.py），日志查询实现进 `src/python/cli/log_query.py`，环境引导进 `src/python/bootstrap.py`；四个 .sh/.ps1 全部变薄壳（13~29 行） | 已修 |
| RF-61 | 守护缺口 | "scripts 只放启动脚本"没有检查，所以能一路堆到 515 行 | `check_guards.py` 新增第 10 项「scripts 薄壳」（单文件 ≤40 行），超出即红 | 已修 |

## 2026-11-17 首次运行不再需要手动 setup

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-62 | 上手成本 | 直接跑 `tui.ps1` 只会得到「缺少运行环境，请先执行 setup.ps1」（还因编码问题显示成乱码），用户必须读懂并照着做一遍 | 新增 `src/python/launch.py`：所有启动脚本先经它探测 `.venv` 与关键依赖，缺则自动建 venv + 按 constraints 装依赖，再 `execv` 到真实入口；`IMG_P_NO_AUTO_SETUP=1` 保留手动/离线路径 | 已修 |
| RF-63 | 静默风险 | 自动安装若无声进行，用户会以为程序卡住 | 安装前固定提示「首次运行，正在准备环境（装依赖，可能需要一两分钟）…」；`--check` 只探测不改环境 | 已修 |

## 2026-11-17 空目录启动与配置目录分平台

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-64 | 交互限制 | 目录里没有图片时 TUI 直接退出（`return 2`），用户想"先开界面再把图片拖进来"完全做不到 | 空目录照样进界面，消息行与左栏提示「放好图片后按 Ctrl-R 重新扫描」；新增 `App.rescan()`（尽量保留选中项）与 `Ctrl-R`/`F5` 绑定；补 3 个用例 | 已修 |
| RF-65 | 跨平台缺陷 | Windows 上默认配置目录写死 `/data/config`，`Path.is_absolute()` 为假 → 启动即 `IMG_P_CONFIG_DIR 需要绝对路径，收到 '/data/config'` | `bootstrap`/`config` 的默认目录按平台取（Windows → 仓库内 `data/config`）；环境变量给相对路径时按仓库根解析而不是报错 | 已修 |

## 2026-11-17 改名与界面美化

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-66 | 品牌一致性 | 程序名散落（`img-p`、`text_replace`、界面里的「文字替换」），日志只能靠版本号猜 | 统一为 `retype`：`version.NAME` 唯一来源，CLI 横幅/`--version`、TUI 标题、日志 `app` 字段、pyproject 包名与控制台脚本、文档标题全部引用它；守护新增「名称」项 | 已修 |
| RF-67 | 迁移风险 | 更名会让老用户的 `img-p.json` 配置与新桌面缓存找不到 | 配置优先读 `retype.json`，旧 `img-p.json` 自动回退；环境变量 `IMG_P_*` 保留（新增 `RETYPE_CONFIG`）；字体缓存迁到 `~/.cache/retype` | 已修 |
| RF-68 | 界面可用性 | 两侧只有标题、无边框与状态栏；手机窄屏键位提示被截断，看不出能按什么 | 外框+标题+页码、双栏竖线、底部详情/状态/键位三行、批量进度条；窄屏按 44/60 列两档断点收缩表头与键位提示，并显示 `[宽x高]` | 已修 |
| RF-69 | 测试保真度 | `FakeWin.addstr` 按字符下标写，中文占两列导致布局测试查不出真实溢出 | 改为按显示列写（与 curses 一致），新增 32~130 列的溢出与信息覆盖用例 | 已修 |

## 2026-11-17 技术债与架构核查

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-70 | 技术债 | `App`（637 行）里塞着目录扫描这种纯逻辑，难单独测 | 抽出 `tui/browse.py`（`scan_rows` / `first_image_row`），`App` 只保留状态与动作 | 已修 |
| RF-71 | 技术债 | `tools/run_tests.py` 里 `shutil.which("true") and has_module(...)` 是无意义死条件 | 删掉，只判断 pytest-cov / pytest-html 是否装 | 已修 |
| RF-72 | 技术债 | `ui_draw._row()` 只是 `put()` 的空壳转发 | 删除，四处调用直接走 `put()` | 已修 |
| RF-73 | 缺陷 | 按键用 `key.isdigit()` 判断数字：上标「²」也返回 True，`int("²")` 抛 ValueError，界面会因一次误触报错 | 改成 ASCII 白名单 `key in "0123456789"`，并补回归用例（含正常数字仍可跳图） | 已修 |
| RF-74 | 技术债 | 三块面板的分发是三条 if 分支，新增面板要改两处 | 改为 `PANEL_HANDLERS` 查表（表放在模块末尾，避免引用未定义函数） | 已修 |
| RF-75 | 文档债 | `technical.md` 只有目录名清单，没写"哪个测试文件守哪条需求" | 补「用例对照表」：28 个测试文件 → FR/NFR 映射 | 已修 |

## 2026-11-17 文档校准

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-76 | 文档漂移 | 更名与门禁增项后，文档里仍留着旧字样：字体缓存写成 `~/.cache/img-p`（2 处）、门禁写成"六项"（2 处）、NFR-4 还写"mypy 守 core" | 全量校准 8 份文档：缓存路径、门禁项数、mypy 范围、目录树（tools/、browse.py、launch.py、bootstrap.py）、命令路径（tools/check_guards.py） | 已修 |
| RF-77 | 需求缺口 | FR-12 只写版本，没写"名称"；TUI 响应式（窄屏断点）只在技术文档里描述，需求侧无验收口径 | requirements 补 FR-12.6（名称一致）与 FR-13（界面自适应：宽屏双栏/窄屏单栏/极窄收缩/状态可见） | 已修 |

## 2026-11-18 TUI 黑屏事故（真机）

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-78 | 严重缺陷（真机） | `./scripts/tui.sh` 在真终端一片黑：`draw_main` 重写时丢了 `win.refresh()`，缓冲区内容从不刷到屏幕 | `draw_main` 末尾补 `win.refresh()`；`FakeWin` 增加 `refresh_count`，新增 `RefreshFlush` 用例锁住"每个面板每帧都刷新" | 已修 |
| RF-79 | 严重缺陷（真机） | 修完刷新仍黑：`curses.ACS_*` 在本机构建里是 **int**，`hline()` 用 `addstr` 拼 ACS 字符 → `TypeError`，`draw_frame` 兜底吞掉后整帧什么都没画 | `hline`/`vline` 改为一格格 `addch`（curses 的 addch 同时接受 str 与 ACS int）；`box()` 只画线不拼字符串 | 已修 |
| RF-80 | 测试保真度 | 两个真机问题单测都没抓到：`FakeWin.addstr` 接受任意对象、`refresh()` 是空实现 | `FakeWin.addstr` 与真 curses 一致只收 str（传 ACS int 立刻 TypeError）；`refresh` 计数；新增 `BorderDrawing`（addch 计数 > 20）与 `test_tui_real_terminal.py`（`script(1)` 伪终端跑真 curses，断言标题/表头/边框字符真的出现） | 已修 |

## 2026-11-18 Windows 覆盖

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-81 | 测试盲区 | CI 只有 ubuntu 作业：Windows 上 `windows-curses` 的行为（ACS 常量是 int、路径/编码差异）从未被验证，而黑屏正是在这类差异里发生 | CI 新增 `windows-latest` 作业（全量用例 + mypy + guards + perf）；`constraints.txt` 锁 `windows-curses==2.4.2` | 已修 |
| RF-82 | 回归覆盖 | 没有断言"ACS 常量是 int 时布局仍能画"的用例 | 新增 `WindowsStyleAcs`：临时把 `curses.ACS_*` 换成 int，断言布局正常、边框确实经 `addch` 画出、无绘制错误 | 已修 |

## 2026-11-18 脚本目录与命名

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-83 | 一致性 | `scripts/` 里还留着一个 `.py` 薄壳（`log-query.py`），与"只放 .sh/.ps1 启动脚本"的约定不符；守护也没拦 | 删 `.py`，改为 `log-query.sh` / `log-query.ps1`；守护「scripts 薄壳」收紧为只允许 `.sh`/`.ps1` | 已修 |
| RF-84 | 可读性 | `scripts/test.sh` 名字像"测试框架"，实际只是 `tools/run_tests.py` 的壳 | 更名 `runTest.sh` / `runTest.ps1`，全仓库引用与文档同步 | 已修 |
| RF-85 | CI 缺陷（Windows） | windows 作业里用反斜杠续行写 pip 安装，PowerShell 把 `\` 当路径参数，报 `Directory '\' is not installable` | 该步骤显式 `shell: bash`（与 Ubuntu 作业同款写法），并保留注释说明原因 | 已修 |

## 2026-11-18 目录树文档

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-86 | 文档缺口 | 目录结构只有 `technical.md` 的主干摘要，没有"每个文件是干什么的"清单；新人（和 AI）找入口只能靠猜，文件移动后也无人察觉 | 新增 `docs/managements/folders.md`（对齐 investor-review 的写法）：项目统计表 + 逐行注释的目录树 + 排除项 + 维护规则；守护新增「目录树文档」（第 12 项），直接解析树里的层级还原完整路径，任何源文件/文档缺失即红 | 已修 |

## 2026-11-18 Windows 用例批量失败（字体）

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-87 | 测试缺陷（Windows） | 用例硬编码 `ImageFont.truetype(FONT_CJK, size, index=2)`：假设了 Noto 的 ttc 布局。Windows 的 `msyh.ttc` 没有 index 2 → `OSError: invalid argument`，31 个用例连带失败 | `_support` 新增 `cjk_font()` / `cjk_font_spec()`：逐候选字体、逐 index（0..9）试，找不到就 `SkipTest`；所有用例与 `make_text_image` 统一改走它 | 已修 |
| RF-88 | 本地不可复现 | 上述失败只在 Windows runner 出现，本地（有 Noto）永远绿，导致"推上去才发现" | 新增 `IMG_P_TEST_NO_CJK_FONT=1`：本地强制模拟无字体环境，`pytest src/test -q` 应 0 失败（字体用例全 skip）；守护新增第 13 项「测试字体」禁止再硬编码 index | 已修 |
| RF-89 | 平台假设 | `test_posix_falls_back_to_common_font_dirs` 在 Windows 上断言 `/usr/share/fonts` | 加 `skipUnless(os.name == "posix")` | 已修 |

## 2026-11-18 代码更新日期

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-90 | 可追溯 | 界面与日志只显示版本号 `0.1`，反馈问题时无法判断跑的是哪一天的代码（同一版本号可能有多次修改） | `version.UPDATED` 为唯一来源：TUI 标题/帮助页、CLI 横幅与 `--version` 都显示，写盘日志加 `app_updated` 字段；守护核对它与 `src/` 最后一次提交日期一致 | 已修 |

## 2026-11-18 本地门禁与窄屏回归

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-91 | 流程缺陷 | "本地绿、CI 红"反复出现：本地没有一条能覆盖 CI 六个作业的命令，靠人记着跑哪几条 | 新增 `tools/check_all.py`（ruff → mypy → guards → perf → 用例+覆盖率 → 无字体复跑），提交前钩子改调 `--quick`；推送前只跑这一条 | 已修 |
| RF-92 | 界面回归 | 标题加上版本与日期后变长，窄屏 44/50 列放不下右上角 `[宽x高]`，两个布局用例失败 | 尺寸标记改放底部状态行，标题行不再与它抢位置；布局用例恢复 | 已修 |
| RF-93 | 守护有效性 | 新增 `tools/check_all.py` 后守护立刻报「目录树文档未覆盖」——说明第 12 项确实拦得住漂移 | 同步 `folders.md` 的树与统计 | 已修 |

## 2026-11-18 Windows TUI 假死

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-94 | 交互缺陷（Windows） | 主循环 `get_wch()` 死等，而首帧里同步跑 OCR；Windows 首次加载 onnxruntime 十几秒，期间按 q / 方向键完全没反应 | `read_key(win, timeout_ms=120)` 超时轮询 + OCR 放后台线程（`App.start_loading()` / `loading` / `loaded_event`）；输入行同源复用 | 已修 |
| RF-95 | 测试盲区 | 旧用例的 `FakeWin` 在"队列空"时按 timeout 状态抛不同异常，改成轮询后测试会永久转圈；也没有"识别中按 q"的用例 | `FakeWin.get_wch` 语义收紧（`None`＝无输入、队列空＝结束）；新增 `NonBlockingInput` / `BackgroundLoading` 共 6 例 | 已修 |

## 2026-11-18 扩测（功能 / 交互 / 跨平台 / 稳定）

| 编号 | 类别 | 问题 | 处理 | 状态 |
| --- | --- | --- | --- | --- |
| RF-96 | 缺陷（新用例发现） | `parse_color("#12345")` 被静默截成 `(0x12,0x34,0x05)`；`"300,0,0"` 也照收，颜色完全不对却没有任何提示 | 校验十六进制长度只能是 3/6、字符集必须是十六进制、三分量必须在 0~255，越界抛 `CoreError` | 已修 |
| RF-97 | 缺陷（新用例发现） | TUI 样式面板设字号时先赋值再校验，`-3` 会被写进 `Options.size`，只留一句提示 | 改为先校验后赋值，非法值保留原设置并提示下限 | 已修 |
| RF-98 | 健壮性 | 字体池为空（系统无字体 / `--font` 指向坏文件）时 `replace_image` 裸抛 `IndexError`，违反"核心层只抛 CoreError" | 明确抛 `CoreError("没有可用字体…")`，渠道提示一句即可 | 已修 |
| RF-99 | 测试覆盖 | 功能边界、交互边界、跨平台默认值与稳定性（规模/幂等）几乎空白，只有主流程用例 | 新增 3 个文件 70 例：`core/test_feature_edges.py`、`tui/test_interaction_edges.py`、`core/test_platform_stability.py`（平台分支用 `sys.platform` 打桩，任何系统都能跑） | 已修 |

## 已验证项

- `ruff check src/ scripts/`：零告警；`python -m mypy`：零错误；`tools/check_guards.py`：6/6 通过。
- `pytest src/test -q`：全绿（用例数随迭代增长）。
- 冗余/无效用例复查：全用例均含断言；无重复用例名；无法满足的断言仅 RF-15 一处，已改正。
