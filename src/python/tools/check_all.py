#!/usr/bin/env python3
"""本地全量门禁：一条命令跑完 CI 跑的所有检查，绿了再推。

    python -m src.python.tools.check_all              # 全量（覆盖率 + 四档矩阵 + 并行分片重排）
    python -m src.python.tools.check_all --quick      # 快速：静态检查 + 单档用例（提交前钩子）
    python -m src.python.tools.check_all --ci-matrix  # 额外跑“cp1252 控制台 + C locale”
    python -m src.python.tools.check_all --font-matrix # 额外跑“换字族/字重”
    python -m src.python.tools.check_all --no-font    # 额外跑“没有中文字体”
    python -m src.python.tools.check_all -k mapping   # 其余参数透传给 pytest

速度与质量的两条取向：

1. **档位串行、每档 `-n 8`**（另可 `--jobs N` / `--serial`，见 `_parallel`）。
   实测 703 个用例：串行 69s、`-n 8` 25s；把四档并发反而更慢。
2. **静态检查并发**（ruff / mypy / mypy-win32 / guards 互不冲突），
   唯独耗时守卫 `check_perf` 独占 CPU 跑——它按墙钟卡阈值，混跑会假红。

门禁比“跑一遍用例”多两道保险（只加不减）：

* **各档收集数必须一致**——某档因环境变量把用例整批 deselect 掉时这里会红，
  而不是“跳过一切、退出码 0”的假绿；
* 全量档额外跑一遍 **`--dist load` 重排**——把用例打散到不同 worker、
  改变执行顺序，专抓并行后才暴露的顺序依赖。
"""

from __future__ import annotations

import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .. import bootstrap
from ..stdio import ensure_utf8_stdio
from ._parallel import Result, Step, parallel_args, run_batch, tail, worker_count
from ._paths import ROOT

PY = sys.executable
REPORTS = ROOT / "reports"


@dataclass(frozen=True)
class Variant:
    """一档 pytest：环境不同、命令行其余部分相同。"""

    key: str
    label: str
    env: dict[str, str]
    coverage: bool = False
    dist: str = "loadfile"


#: 环境矩阵。plain 是本机默认环境（并出覆盖率），其余各档模拟一种 CI 机器。
VARIANTS: tuple[Variant, ...] = (
    Variant("plain", "本机默认", {}, coverage=True),
    Variant(
        "ci",
        "cp1252 控制台 + C locale",
        {"PYTHONIOENCODING": "cp1252", "LC_ALL": "C", "LANG": "C"},
    ),
    Variant("nofont", "模拟无中文字体", {"IMG_P_TEST_NO_CJK_FONT": "1"}),
    Variant("font", "换字族/字重", {"IMG_P_TEST_FONT": "alt"}),
    # 只改分片方式：把用例打散到 worker、改变执行顺序，专抓顺序依赖。
    Variant("stress", "并行分片重排（查顺序依赖）", {}, dist="load"),
)
BY_KEY = {v.key: v for v in VARIANTS}
STRESS = BY_KEY["stress"]
PLAIN = BY_KEY["plain"]


def junit_path(variant: Variant) -> Path:
    """该档的 junit 报告路径：本机档仍叫 `junit.xml`，下游工具按这个名字读。"""
    name = "junit.xml" if variant.key == PLAIN.key else f"junit-{variant.key}.xml"
    return REPORTS / name


@dataclass
class Options:
    quick: bool = False
    jobs: int | None = None
    workers: int | None = None
    matrix: bool = False
    no_font: bool = False
    font_matrix: bool = False
    extra: list[str] = field(default_factory=list)


def _int_arg(raw: str, flag: str) -> int:
    """解析正整数参数；非法值直接报错退出（不猜、不用默认值兜）。"""
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"[FAIL] {flag} 需要整数，收到 {raw!r}") from None
    if value < 1:
        raise SystemExit(f"[FAIL] {flag} 需要正整数，收到 {raw!r}")
    return value


def parse_args(argv: list[str]) -> Options:
    """把门禁自己的开关摘出来，其余原样透传给 pytest。"""
    opts = Options()
    pending = list(argv)
    while pending:
        arg = pending.pop(0)
        if arg == "--quick":
            opts.quick = True
        elif arg == "--ci-matrix":
            opts.matrix = True
        elif arg == "--no-font":
            opts.no_font = True
        elif arg == "--font-matrix":
            opts.font_matrix = True
        elif arg == "--serial":
            os.environ["IMG_P_GATE_SERIAL"] = "1"
        elif arg == "--jobs":
            opts.jobs = _int_arg(pending.pop(0) if pending else "", "--jobs")
        elif arg.startswith("--jobs="):
            opts.jobs = _int_arg(arg.partition("=")[2], "--jobs")
        elif arg == "--gate-workers":
            opts.workers = _int_arg(pending.pop(0) if pending else "", "--gate-workers")
        elif arg.startswith("--gate-workers="):
            opts.workers = _int_arg(arg.partition("=")[2], "--gate-workers")
        else:
            opts.extra.append(arg)
    return opts


def _static_steps() -> list[Step]:
    """静态检查：彼此只读，并发跑。"""
    return [
        Step("ruff", [PY, "-m", "ruff", "check", "src/"], {}),
        Step("mypy", [PY, "-m", "mypy"], {}),
        # 同一棵树按 Windows 的 typeshed 再检查一遍：fcntl / os.mkfifo 这类
        # 「Linux 有、Windows 没有」的属性，只有这一档能在本地提前发现。
        # 钉死 win32 时，POSIX 分支天然"不可达"（bootstrap/config 里的平台默认值），
        # 那正是我们要保留的另一条分支，所以这一档关掉不可达检查
        Step(
            "mypy（win32 平台）",
            [PY, "-m", "mypy", "--platform", "win32", "--no-warn-unreachable"],
            {},
        ),
        Step("guards", [PY, "-m", "src.python.tools.check_guards"], {}),
    ]


def _perf_step() -> Step:
    """耗时守卫：按墙钟判阈值，必须独占 CPU（isolated）。"""
    return Step("perf", [PY, "-m", "src.python.tools.check_perf", "--ci"], {}, isolated=True)


def _pytest_step(variant: Variant, opts: Options, workers: int, tmp_hint: str) -> Step:
    """拼出一档 pytest 的命令行；junit 报告用于「各档收集数一致」的核对。"""
    cmd = [
        PY,
        "-m",
        "pytest",
        "src/test",
        "-q",
        "--no-header",
        f"--junitxml={junit_path(variant)}",
        "--dist",
        variant.dist,
        *parallel_args(workers),
    ]
    if variant.coverage and not opts.quick:
        # 覆盖率只在本机默认档上算：矩阵档的目的是环境差异，重复采一份没有新信息。
        cmd += ["--cov", f"--cov-report=xml:{REPORTS / 'coverage.xml'}"]
    env = dict(variant.env)
    if tmp_hint:
        env["IMG_P_TMP_DIR"] = tmp_hint
    return Step(f"pytest（{variant.label}）", [*cmd, *opts.extra], env)


def select_variants(opts: Options) -> list[Variant]:
    """按开关挑出要跑的档位；全量档固定跑前四档（stress 由调用方单独跑）。"""
    if not opts.quick:
        return [v for v in VARIANTS if v.key != STRESS.key]
    picked = [BY_KEY["plain"]]
    if opts.matrix:
        picked.append(BY_KEY["ci"])
    if opts.no_font:
        picked.append(BY_KEY["nofont"])
    if opts.font_matrix:
        picked.append(BY_KEY["font"])
    return picked


def _run(steps: list[Step], jobs: int | None) -> tuple[Result | None, list[tuple[str, float]]]:
    """跑一组步骤并逐条汇报；返回（第一个失败的步骤，各步「名字 + 耗时」）。"""
    results = run_batch(steps, ROOT, jobs=jobs)
    timings: list[tuple[str, float]] = []
    failure: Result | None = None
    for result in results:
        print(f"   {'ok' if result.ok else 'FAIL'}  {result.name}（{result.seconds:.1f}s）")
        timings.append((result.name, result.seconds))
        if not result.ok and failure is None:
            failure = result
    return failure, timings


def _junit_modules(path: Path) -> set[str] | None:
    """从 junit 报告里取「实际跑到的用例模块」集合。

    为什么不用「用例总数」：`nofont` 档本来就跳过 132 个跳不过字体的用例，
    总数天生不同；而"某档把整个文件 deselect 掉"才是要拦的事故。
    junit 的 classname 形如 `src.test.core.test_x.ClassName`，末尾大写段是类名，去掉它。
    """
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    modules: set[str] = set()
    for case in root.iter("testcase"):
        classname = case.get("classname") or ""
        if not classname:
            continue
        head, _, last = classname.rpartition(".")
        modules.add(head if last[:1].isupper() else classname)
    return modules


def check_collected(pairs: list[tuple[Variant, set[str]]]) -> list[str]:
    """各档跑到的用例模块集合必须一致（纯函数，便于用例打桩）。

    退出码 0 不代表"真的跑了"：`-k` 打错、环境变量让整批用例 deselect、
    某个目录没被收集，都会让一档"全绿但什么都没测"。这里按模块集合对账。
    """
    if not pairs:
        return ["没有任何一档跑出 junit 报告：无法对账"]
    empty = [v.key for v, modules in pairs if not modules]
    if empty:
        return [f"以下几档没有收集到任何用例：{', '.join(empty)}"]
    reference = pairs[0][1]
    problems: list[str] = []
    for variant, modules in pairs[1:]:
        missing = sorted(reference - modules)
        extra = sorted(modules - reference)
        if missing:
            problems.append(
                f"{variant.key} 档少了 {len(missing)} 个用例模块：{', '.join(missing[:5])}"
            )
        if extra:
            problems.append(f"{variant.key} 档多了 {len(extra)} 个用例模块：{', '.join(extra[:5])}")
    return problems


def _slowest(timings: list[tuple[str, float]]) -> str:
    if not timings:
        return "—"
    name, seconds = max(timings, key=lambda item: item[1])
    return f"{name} {seconds:.1f}s"


def _run_variants(
    selected: list[Variant], opts: Options, workers: int
) -> tuple[int, list[tuple[str, float]], list[tuple[Variant, set[str]]]]:
    """逐档跑用例（档位串行，档内并行）；返回（退出码，耗时，各档模块集合）。"""
    tmp_hint = ""  # 用例临时目录沿用 src/test/__init__.py 的约定，门禁不覆盖
    how = f"-n {workers}" if workers > 1 else "单进程"
    print(f"== 用例：{len(selected)} 档 × {how}")
    spent: list[tuple[str, float]] = []
    collected: list[tuple[Variant, set[str]]] = []
    for variant in selected:
        failure, used = _run([_pytest_step(variant, opts, workers, tmp_hint)], opts.jobs)
        spent += used
        if failure is not None:
            print(tail(failure.output))
            return 1, spent, collected
        modules = _junit_modules(junit_path(variant))
        if modules is not None:
            collected.append((variant, modules))
    return 0, spent, collected


def _run_full_extras(opts: Options, workers: int, timings: list[tuple[str, float]]) -> int:
    """全量档专属：覆盖率门禁 + 并行分片重排 + 写门禁戳。"""
    cov = Step(
        "覆盖率门禁（总量 / 分模块 / skip 比例）",
        [
            PY,
            "-m",
            "src.python.tools.check_coverage",
            str(REPORTS / "coverage.xml"),
            str(REPORTS / "junit.xml"),
        ],
        {},
    )
    stress = _pytest_step(STRESS, opts, workers, "")
    print("== 覆盖率门禁 + 并行分片重排")
    for group in ([cov], [stress]):
        failure, used = _run(group, opts.jobs)
        timings.extend(used)
        if failure is not None:
            print(tail(failure.output))
            return 1

    # 全量通过就在 git 目录里留个戳：同一份代码再 push 不必重跑。
    from . import gate_stamp

    try:
        gate_stamp.write_stamp()
        print("已记录门禁戳（同一份代码下次推送可跳过重跑）")
    except OSError as exc:  # 只读环境/无 git：不影响结论
        print(f"[!] 无法写门禁戳：{exc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    hint = bootstrap.venv_hint()
    if hint:  # 工具自己也要提示：门禁的意义就是"跑在项目环境里"
        print(hint, file=sys.stderr)
    opts = parse_args(list(sys.argv[1:] if argv is None else argv))
    workers = worker_count(opts.workers)

    REPORTS.mkdir(exist_ok=True)
    for stale in REPORTS.glob("junit*.xml"):
        stale.unlink()
    (REPORTS / "coverage.xml").unlink(missing_ok=True)

    started = time.perf_counter()
    timings: list[tuple[str, float]] = []

    # ── 1) 静态检查（并发；越快越先，失败即停）────────────────────────
    print("== 静态检查（ruff / mypy / mypy-win32 / guards 并发）")
    failure, used = _run(_static_steps(), opts.jobs)
    timings.extend(used)
    if failure is not None:
        print(tail(failure.output))
        return 1

    # ── 2) 耗时守卫（独占 CPU：并发时墙钟会漂，阈值就不准了）───────────
    print("== 耗时守卫（独占 CPU）")
    failure, used = _run([_perf_step()], opts.jobs)
    timings.extend(used)
    if failure is not None:
        print(tail(failure.output))
        return 1

    # ── 3) 用例（档位串行、档内并行）─────────────────────────────────
    code, used, collected = _run_variants(select_variants(opts), opts, workers)
    timings.extend(used)
    if code != 0:
        return code
    problems = check_collected(collected)
    if problems:
        for item in problems:
            print(f"!! {item}")
        return 1

    # ── 4) 全量档：覆盖率门禁、并行分片重排、门禁戳 ───────────────────
    if not opts.quick and _run_full_extras(opts, workers, timings) != 0:
        return 1

    total = time.perf_counter() - started
    print(f"\n全部通过 ✅ 总耗时 {total:.1f}s（最慢一步：{_slowest(timings)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
