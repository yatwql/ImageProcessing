# 归档规范

> 版本：v0.1

发布新版本后，`plan.md` / `review-findings.md` / `changelog.md` 里属于**已发布系列**的内容
会被整块搬到这里，主台账只留当前开发版本的内容与归档索引。本目录的管理要求参考
`investor-review` 项目的归档约定，按本仓「`MAJOR.MINOR` 版本 + 单系列一次归档」的口径收敛。

守护「归档」逐条核对下面这些规则（`src/python/tools/check_guards.py`）。

## 1. 目录与命名

```text
docs/archive/
├── README.md                              # 本文件：归档规范
└── v0.1.x/                                # 一个版本系列一个子目录（vX.Y.x）
    ├── archived_plan.0.1.x.md             # 计划归档（原 docs/managements/plan.md）
    ├── archived_review-findings.0.1.x.md  # 自检记录归档
    ├── archived_changelog.0.1.x.md        # 变更记录归档
    └── <任务名>/                          # 可选：该系列的设计稿/中间稿，名字不限
```

| 规则 | 说明 |
| --- | --- |
| 目录名 | 只能 `vX.Y.x`；`X.Y` 就是 `src/python/version.py` 的 `VERSION` |
| 归档文件名 | `archived_<plan\|review-findings\|changelog>.<系列>.md`，系列号必须与目录一致 |
| 一份台账一个文件 | 同一系列只追加、不新建；新系列才建新文件 |
| 设计稿 | 已落地的设计稿放 `vX.Y.x/<任务名>/`，按任务建子目录，文件名不限 |

## 2. 归档文件头（四项，缺一项即门禁红）

```markdown
# 计划归档 — v0.1.x

> 归档时间：2026-11-20（v0.1 发布，本系列首份）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.1
> 归档内容：由 `python -m src.python.tools.release archive` 整块搬运，未改一字

---
```

## 3. 对归档文件内容的处理

1. **整块搬运、不改一字**：条目顺序、表格列、错别字、当时的结论一律原样保留，
   不为了"看起来整齐"去重排或删减（历史记录的价值在于当时的样子）。
2. **编号不复用**：`PLAN-x` / `RF-x` 归档后仍然占号，新任务取新号。
   守护「编号-plan」「编号-review」会核对主台账是否复用了归档里的编号。
3. **不写 `> 版本：` 行**：归档文件是历史快照，版本号固定写在文件名与头部，
   不参与「版本号」守护（守护只核对 `VERSION_DOCS` 列表里的现行文档）。
4. **不加结论、不写摘要**：归档段落之后不追加"后来发现…"这类补记；
   后续结论写进当前主台账或新的 `RF-x`，需要交叉引用时用相对链接指过来。
5. **同系列第二批**（同一 `MINOR` 内多次发布）在文件末尾追加
   `## 归档批次 vX.Y（日期）` 再贴正文，不改动头部。

## 4. 什么时候归档、怎么归档

发布流程里归档是独立一步，放在 `prepare` 之前（此时 `VERSION` 还是被发布的系列）：

```bash
.venv/bin/python -m src.python.tools.release archive          # 预演：只打印要搬的内容
.venv/bin/python -m src.python.tools.release archive --yes    # 真搬：写归档 + 重建主台账索引
.venv/bin/python -m src.python.tools.release prepare --version 0.2
```

脚本做的事，与 investor-review 的 `archive-init` + `prepare` 两步等价：

1. 三份台账按「文件头 / 正文 / `## 归档` 段」切开，**正文全部**搬进
   `docs/archive/v<系列>/archived_<台账>.<系列>.md`；
2. 归档文件不存在就先写标准头部，已存在就追加 `## 归档批次` 段；
3. 主台账重写为「文件头 + 重新生成的 `## 归档` 索引」——旧内容不再留在主文件里；
4. 三份台账都没有正文时直接退出 0（幂等，重复跑不会产生空批次）。

归档完记得同步目录树与统计：`.venv/bin/python -m src.python.tools.gen_folders --write`。

## 5. 归档后的主台账长什么样

```markdown
# 计划任务

> 版本：v0.2                      # 头部保留，守护核对版本号
                                   # 正文：只放当前开发版本的任务
## 归档                          # 脚本生成的索引，不要手改
| 系列 | 归档文件 | 涵盖版本 | 归档时间 |
| --- | --- | --- | --- |
| v0.1.x | [`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md) | v0.1 | 2026-11-20 … |
```

## 6. 检索与追溯

```bash
rg -n "PLAN-42" docs/                     # 主台账与归档一起搜，编号全局唯一
rg -n "RF-129" docs/archive/              # 只看历史自检记录
git log --follow docs/archive/v0.1.x/archived_plan.0.1.x.md   # 看得见搬运历史
```

## 7. 维护规则

1. 归档文件只在发布时由脚本写入，**不手工编辑**（要纠错就在主台账开新的 `RF-x`）。
2. 新增归档文件/设计稿目录 → 同一次提交里跑 `gen_folders --write` 同步 `folders.md`，否则守护「目录树文档」会红。
3. 本文件被 `docs/README.md` 索引引用；改名或移动必须同步索引（守护「归档」会核对）。
