# 发布流程

> 版本：v0.3

发布 = 七个可单独重试的步骤，全部由 `src/python/tools/release.py` 编排。**每次发布前必须全绿**，
不靠人记；`gate` 会跑与 CI 完全相同的检查。

```bash
.venv/bin/python -m src.python.tools.release check                  # 1. 预检
.venv/bin/python -m src.python.tools.release archive                # 2. 预演归档（三份台账的旧内容）
.venv/bin/python -m src.python.tools.release archive --yes          #    真搬进 docs/archive/vX.Y.x/
.venv/bin/python -m src.python.tools.release prepare --version 0.2   # 3. 起版本
#   4. 手写 changelog（prepare 只插入标题与占位）
.venv/bin/python -m src.python.tools.release gate                    # 5. 全量门禁
.venv/bin/python -m src.python.tools.release build                   # 6. 打产物
.venv/bin/python -m src.python.tools.release tag --yes               # 7. 打标签（推标签触发 CI 发布）
```

## 0. 分支与版本号（`dev` / `master`）

| 项 | 规则 |
| --- | --- |
| 开发分支 | `dev`：**日常开发都在这里**，`VERSION` 带后缀，如 `0.3-dev` |
| 发布分支 | `master`：只放正式发布的版本号（`0.3`），发布后由 `dev` 合并进来 |
| 开发版本号 | 正式版本号 + `-dev`（`0.3-dev`）；`check_guards` 核对各文档 `> 版本：` 行与之一致 |
| 正式版本号 | 无后缀（`0.3`）；`release.py prepare --version 0.3` 去掉 `-dev` |
| 标签 | 只给正式版本打（`v0.3`）；开发版调 `tag` 会被拒绝 |
| 发布后 | `master` 上打标签并发布 → 回到 `dev` 跑 `release.py devbump --version 0.4` 切下一个开发版 |

```bash
# 日常（dev 分支）
git switch dev
.venv/bin/python -m src.python.tools.check_all --quick

# 发布（仍在 dev 上定版，再合并进 master）
.venv/bin/python -m src.python.tools.release check
.venv/bin/python -m src.python.tools.release archive --yes
.venv/bin/python -m src.python.tools.release prepare --version 0.3   # 0.3-dev → 0.3
#   同步各文档的「> 版本：」行 → gen_folders --write → 提交
.venv/bin/python -m src.python.tools.release gate
.venv/bin/python -m src.python.tools.release build
git switch master && git merge --no-ff dev
.venv/bin/python -m src.python.tools.release tag --yes && git push origin master v0.3
git switch dev
.venv/bin/python -m src.python.tools.release devbump --version 0.4   # → 0.4-dev
```

> 为什么开发版也写进 `VERSION`：界面标题、CLI 横幅、写盘日志的 `app_version` 都要能一眼看出
> "跑的是开发版还是正式版"；`-dev` 后缀就是最便宜的标记，不用另开字段。

## 1. 版本策略

| 项 | 规则 |
| --- | --- |
| 版本格式 | `MAJOR.MINOR[-dev]`（开发版带 `-dev`），定义在 `src/python/version.py`（唯一来源） |
| `UPDATED` | 等于 `src/` 最后一次提交日期，守护「版本号」会核对 |
| 何时升 `MINOR` | 新增能力、**或**任何破坏 §契约 的改动（见 `contracts.md` §3） |
| 何时只发补丁 | 同一 `MINOR` 内修缺陷不打新版本号；直接随下一次发布合入 |
| 兼容承诺 | 核心 API、CLI 退出码、日志/摘要字段、配置文件键只在升 `MINOR` 时可破坏 |

## 2. 各步骤做什么、失败怎么办

| 步骤 | 内容 | 失败时 |
| --- | --- | --- |
| `check` | 工作区干净、`UPDATED` 与 `src/` 最后提交一致、版本格式合法（这三项秒级、红了就停，不再白跑门禁），然后跑**全量门禁** `check_all`（四档环境矩阵 + 覆盖率 + 分片重排）；同一份代码已有门禁戳则直接放行 | 按提示修；**不要**用 `--no-verify` 硬推 |
| `prepare` | 改 `version.py` 的 `VERSION`/`UPDATED`，在 `changelog.md` 顶部插入 `## vX.Y — 日期` 与「变更」占位 | 手写 changelog 内容；标题重复时脚本会跳过 |

> 时间分布（16 核，703 用例）：`check` 约 3 分钟；`prepare` 改了 `version.py` 会让门禁戳失效，
> 所以 `gate` 会再跑一次全量（约 3 分钟）；`archive` / `build` / `tag` 都是秒级。
> 总时长从改造前的 ~15 分钟降到 ~6 分钟，且 `check` 现在把覆盖率门禁也一起过了（以前只跑 quick 三遍）。
| `archive` | 把 `plan.md` / `review-findings.md` / `changelog.md` 的正文整块搬进 `docs/archive/v<系列>/`，主台账重写为「文件头 + 重新生成的 `## 归档` 索引」；不带 `--yes` 只预演 | 先看预演行数是否合理；搬完跟一句 `gen_folders --write` 同步目录树；规则见 `docs/archive/README.md` |
| `gate` | 跑 `src/python/tools/check_all.py`（含覆盖率门禁、四档环境矩阵、并行分片重排）；命中门禁戳就跳过，`--force` 强制重跑 | 必须修到全绿；这步与 CI 等价 |
| `build` | `pip wheel` 出 wheel，`python -m build --sdist` 出 sdist（没装 `build` 则跳过），写 `dist/SHA256SUMS` | 清理 `dist/` 重跑；打包配置问题看 `pyproject.toml` |
| `tag` | 打附注标签 `vX.Y`（不带 `--yes` 只打印命令） | 标签已存在则先确认是否发错；删除：`git tag -d vX.Y && git push origin :refs/tags/vX.Y` |
| `publish` | 推标签后由 CI 生成 GitHub Release（附 wheel/sdist/SHA256SUMS） | 看 CI `release` 作业日志；可手动 `gh release create vX.Y dist/* --verify-tag` |

## 3. 发布前检查清单

- [ ] `src/python/tools/release.py check` 通过（工作区干净、版本一致、全量门禁绿）
- [ ] `changelog.md` 的本版本段落写清：新增 / 变更 / 修复 / 不兼容项与迁移步骤
- [ ] `release.py archive --yes` 已跑：`docs/archive/vX.Y.x/` 有三份归档，主台账只剩当前开发版本 + `## 归档` 索引
- [ ] `folders.md` 与归档后的目录树一致（`gen_folders --write` 跑过，守护会核对）
- [ ] `requirements.md` 的 FR/NFR、`technical.md` 的算法与阈值、`contracts.md` 的契约都已同步
- [ ] `folders.md` 与实际文件一致（守护会核对）
- [ ] `test-coverage.md` 已重新生成（`src/python/tools/coverage_report.py --write`）
- [ ] `src/python/tools/release.py gate` 全绿（覆盖率、四档环境矩阵、性能、依赖审计相关检查均通过）
- [ ] `src/python/tools/release.py build` 产物齐全且 `SHA256SUMS` 有内容

## 4. CI 侧的发布

- 推送形如 `v*` 的标签时，CI 的 `release` 作业会：完整安装依赖 → `check_all` → 构建 wheel/sdist
  → 用 `gh release create --verify-tag --generate-notes` 建 Release 并附产物。
- 任何门禁红的发布都会被拒绝；**没有"跳过 CI 直接发"的路径**。
- 发布后回归：装 wheel 跑一次 `retype --version` 与 `retype <示例目录> --list`（离线可用）。

## 5. 回滚

| 情况 | 处理 |
| --- | --- |
| 刚打标签、未发布 | `git tag -d vX.Y` + `git push origin :refs/tags/vX.Y` |
| 已发布但发现致命缺陷 | 不移动标签（会破坏校验）；打 `vX.(Y+1)` 补丁版本并在 changelog 写明原因 |
| 依赖/约束回退 | `git revert` 对应提交 + `src/python/tools/update_constraints.py --write` + `gate` 全绿再发 |

## 6. 与其它文档的关系

- 质量标准与门禁分层：`testplan.md`（QG-1..9、P0/P1/P2）
- 契约与兼容承诺：`contracts.md`（§2 契约、§3 版本策略）
- 变更记录：`changelog.md`；缺陷与回归：`review-findings.md`；任务：`plan.md`
- 已发布系列的旧内容：`docs/archive/vX.Y.x/`（规范见 `docs/archive/README.md`）
