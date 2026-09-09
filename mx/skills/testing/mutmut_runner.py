"""Measure one working tree with mutmut, from inside the project's own environment.

`harden.py` is the only caller: it runs this file with `uv run` from the tree being measured,
hands it a job on stdin and reads the report back from the file the job names. Everything mutmut-
and coverage-specific lives here; `harden.py --help` documents what the measurement means. The
report goes to a file because mutmut and the test processes write freely to this one's stdout.

Job (stdin), `mode` selecting one of two:

    {"mode": "config", "report_file": "/tmp/report.json"}
    {"mode": "measure", "report_file": "/tmp/report.json", "patterns": ["pkg.mod.x_fn*"],
     "test_files": ["tests/test_x.py"], "derive_targets": true,
     "changed_lines": {"pkg/mod.py": [12, 13]}, "coverage_file": ".coverage"}

Report (the job's `report_file`):

    {"source_paths": ["pkg/"],                                    # both modes
     "patterns_run": ["pkg.mod.x_fn*"],                           # measure only, below
     "test_files_matched": ["tests/test_x.py"],
     "verdicts": {"pkg.mod.x_fn__mutmut_1": {"status": "survived", "diff": "a -> b"}},
     "uncovered": ["pkg/mod.py:12"], "unanalysable": {"pkg/mod.py": "reason"},
     "wall_s": 12.3}

`test_files_matched` is the candidates this tree's test-to-function map knows as tests; under
`derive_targets`, the targets their tests cover join `patterns_run`, which is how a diff that only
edits tests still names the functions those tests hold in place. `diff` is filled for surviving
mutants only.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path
from xml.etree import ElementTree

import coverage
import mutmut
import mutmut.__main__ as mutmut_main
from mutmut.configuration import Config

PYTEST_ORDER_ARGS = ["-p", "no:randomly", "-p", "no:random-order"]
NO_MUTANT_PATTERN = "*no-mutant-matches-this*"
"""A run whose pattern matches nothing still collects the test-to-function map, which is what the
first pass is for: the map names the targets a test-only diff has to measure."""


def main() -> None:
    job = json.load(sys.stdin)
    source_paths = [str(path) for path in Config.get().source_paths]
    if job["mode"] == "config":
        write_report(job, {"source_paths": source_paths})
        return

    started = time.monotonic()
    coverage_file = job["coverage_file"]
    collect_coverage(source_paths, coverage_file)
    os.environ["MUTMUT_COVERAGE_FILE"] = str(Path(coverage_file).absolute())
    patch_mutmut()

    patterns = list(job["patterns"])
    matched: list[str] = []
    with contextlib.redirect_stdout(sys.stderr):
        if job["test_files"]:
            collect_stats()
            matched, covered_targets = targets_for_test_files(job["test_files"], mutmut.tests_by_mangled_function_name)
            if job["derive_targets"]:
                patterns += covered_targets
        if patterns:
            run_mutmut(patterns)

    report = {
        "source_paths": source_paths,
        "patterns_run": patterns,
        "test_files_matched": matched,
        "verdicts": verdicts(patterns),
        "wall_s": round(time.monotonic() - started, 1),
        **coverage_analysis(job["changed_lines"], coverage_file),
    }
    write_report(job, report)


def write_report(job: dict, report: dict) -> None:
    Path(job["report_file"]).write_text(json.dumps(report))


def collect_coverage(source_paths: list[str], coverage_file: str) -> None:
    """Line coverage for the whole suite, in a subprocess.

    mutmut's own pre-pass runs the suite in-process and then evicts every module it imported, which
    segfaults on single-phase-init C extensions and empties global registries (numpy, PyYAML,
    SQLAlchemy). A subprocess run hands the same map over without touching the importer.
    """
    require_concurrency_config()
    argv = [sys.executable, "-m", "pytest", "-q", *PYTEST_ORDER_ARGS, "--ignore=mutants"]
    argv += [f"--cov={path}" for path in source_paths]
    argv += ["--cov-report=", *test_selection()]
    result = subprocess.run(argv, env=test_env(coverage_file), stdout=sys.stderr)
    if result.returncode not in (0, 5):
        raise SystemExit(f"the coverage pass failed (pytest exit {result.returncode}); fix the suite first")


def test_env(coverage_file: str) -> dict[str, str]:
    return {**os.environ, "COVERAGE_FILE": coverage_file, "HYPOTHESIS_PROFILE": "harden"}


def require_concurrency_config() -> None:
    """A project that has greenlet installed (SQLAlchemy's async engine rides on it) has to name it
    in its coverage config, or coverage records nothing after an `await` into the engine and
    attributes the engine's own lines to the project's files. coverage warns about neither, so this
    is the one place that does; the setting is the project's, in `[tool.coverage.run]`."""
    if project_has_greenlet(Path.cwd()) and greenlet_unnamed(coverage.Coverage().config.concurrency):
        raise SystemExit(
            "greenlet is installed and the coverage config does not name it: set "
            '`[tool.coverage.run] concurrency = ["thread", "greenlet"]` (/mx:project-setup, PYTHON.md)'
        )


def project_has_greenlet(tree: Path) -> bool:
    """Whether greenlet is the project's own, read off its lock or its environment: an importable
    greenlet proves nothing here, since `uv run --with` layers the caller's packages over the
    project's and this runner is started that way."""
    lock = tree / "uv.lock"
    if lock.exists() and re.search(r'^name = "greenlet"$', lock.read_text(), re.MULTILINE):
        return True
    return any((tree / ".venv").glob("lib/python*/site-packages/greenlet"))


def greenlet_unnamed(concurrency: list[str]) -> bool:
    return "greenlet" not in concurrency


def test_selection() -> list[str]:
    return list(Config.get().pytest_add_cli_args_test_selection)


def patch_mutmut() -> None:
    mutmut_main.store_lines_covered_by_tests = load_covered_lines_from_file
    mutmut_main.PytestRunner._pytest_args_regular_run = pytest_args_in_collection_order
    mutmut_main.PytestRunner.run_tests = run_tests_in_subprocess


def load_covered_lines_from_file() -> None:
    """Feed mutmut the coverage map collected by `collect_coverage`, in place of its own pre-pass."""
    if not Config.get().mutate_only_covered_lines:
        return
    data_file = os.environ["MUTMUT_COVERAGE_FILE"]
    data = coverage.CoverageData(basename=data_file)
    data.read()
    mutants = Path("mutants")
    mutmut._covered_lines = {
        str((mutants / source_file).absolute()): set(data.lines(str(Path(source_file).absolute())) or [])
        for source_file in mutmut_main.walk_source_files()
    }


def pytest_args_in_collection_order(self: mutmut_main.PytestRunner, tests: Iterable[str]) -> list[str]:
    """Collection order, not mutmut's duration order: a suite with order-dependent fixtures scores
    mutants killed by a failure the mutation did not cause."""
    return ["-x", "-q", *PYTEST_ORDER_ARGS] + (sorted(tests) or test_selection())


def run_tests_in_subprocess(self: mutmut_main.PytestRunner, *, mutant_name: str | None, tests: Iterable[str]) -> int:
    """A fresh interpreter per mutant, and a kill only where a test failed.

    mutmut forks the child from a process that has already run the suite, and an asyncio loop does
    not survive `fork`: every async mutant then hangs to its wall deadline. And mutmut reads any
    non-zero pytest exit as a kill, so a collection error or a broken fixture scores as one; those
    come back `suspicious`, which harden reports as unresolved.
    """
    with tempfile.TemporaryDirectory() as directory:
        results = Path(directory) / "junit.xml"
        argv = [sys.executable, "-m", "pytest", "--rootdir=.", "--tb=native", f"--junit-xml={results}"]
        argv += [*self._pytest_args_regular_run(tests), *self._pytest_add_cli_args]
        env = {**test_env(os.environ["MUTMUT_COVERAGE_FILE"]), "PYTHONPATH": mutated_source_roots()}
        exit_code = subprocess.run(argv, cwd="mutants", env=env).returncode
        return mutmut_exit_code(exit_code, results)


def mutmut_exit_code(pytest_exit_code: int, results: Path) -> int:
    """Translate a pytest run into the exit code mutmut reads as a verdict: 0 survived, 1 killed,
    5 no tests, 35 suspicious."""
    if pytest_exit_code in (0, 5):
        return pytest_exit_code
    if not results.exists():
        return 35
    outcomes = {
        child.tag
        for case in ElementTree.parse(results).iter("testcase")
        for child in case
        if child.tag in ("failure", "error")
    }
    return 1 if "failure" in outcomes else 35


def mutated_source_roots() -> str:
    """What mutmut puts on its own `sys.path` for the forked child, as a PYTHONPATH for a fresh
    interpreter: the mutated tree ahead of the project's installed package, which would otherwise
    serve every test the unmutated source."""
    roots = [Path("mutants"), Path("mutants/src"), Path("mutants/source")]
    return os.pathsep.join(
        [str(root.absolute()) for root in roots if root.exists()] + [os.environ.get("PYTHONPATH", "")]
    )


def run_mutmut(patterns: list[str]) -> None:
    """mutmut asserts its way out when a name filter matches no mutant, which is an ordinary state
    here: a function added by the range has no mutants at the base, and a decorated one has none
    anywhere. The report says so through the targets that came back without verdicts."""
    sys.argv = ["mutmut", "run", *patterns]
    with contextlib.suppress(SystemExit, AssertionError):
        mutmut_main.cli(standalone_mode=False)


def collect_stats() -> None:
    """Ask for the test-to-function map alone: mutmut builds it on any run, and a filter that matches
    no mutant stops the run right after."""
    run_mutmut([NO_MUTANT_PATTERN])
    if not mutmut.tests_by_mangled_function_name:
        raise SystemExit("mutmut collected no test-to-function map, so a changed test names no target")


def targets_for_test_files(test_files: list[str], test_map: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """Which of the candidate files mutmut knows as test files, and the targets their tests cover."""
    matched: set[str] = set()
    targets: set[str] = set()
    for function, tests in test_map.items():
        hit = {test.split("::")[0] for test in tests} & set(test_files)
        matched |= hit
        if hit:
            targets.add(f"{function}*")
    return sorted(matched), sorted(targets)


def verdicts(patterns: list[str]) -> dict[str, dict[str, str | None]]:
    """Every mutant matching the run's patterns, with its status, read off mutmut's own state.

    `mutmut results` prints the same thing and `mutmut show` one diff per process start; reading the
    state directly keeps a report with twenty survivors to one process instead of twenty-one.
    """
    out: dict[str, dict[str, str | None]] = {}
    for path in mutmut_main.walk_mutatable_files():
        data = mutmut_main.SourceFileMutationData(path=path)
        data.load()
        for mutant, exit_code in data.exit_code_by_key.items():
            if not any(fnmatch(mutant, pattern) for pattern in patterns):
                continue
            status = mutmut_main.status_by_exit_code[exit_code]
            survived = status in ("survived", "no tests")
            out[mutant] = {"status": status, "diff": mutation_diff(mutant, path) if survived else None}
    return out


def mutation_diff(mutant: str, path: Path) -> str:
    raw = mutmut_main.get_diff_for_mutant(mutant, path=path).splitlines()
    removed = [line[1:].strip() for line in raw if line.startswith("-") and not line.startswith("---")]
    added = [line[1:].strip() for line in raw if line.startswith("+") and not line.startswith("+++")]
    return " | ".join(f"{before} -> {after}" for before, after in zip(removed, added)) or "\n".join(raw).strip()


def coverage_analysis(changed_lines: dict[str, list[int]], coverage_file: str) -> dict[str, object]:
    """Which changed lines the suite never ran, and which files it could not be asked about."""
    cov = coverage.Coverage(data_file=coverage_file)
    cov.load()
    uncovered: list[str] = []
    unanalysable: dict[str, str] = {}
    for path, lines in sorted(changed_lines.items()):
        try:
            _, statements, _, missing, _ = cov.analysis2(path)
        except Exception as error:  # coverage raises NoSource, NotPython and friends per file
            unanalysable[path] = f"{type(error).__name__}: {error}"
            continue
        uncovered += [f"{path}:{line}" for line in sorted(set(lines) & set(statements) & set(missing))]
    return {"uncovered": uncovered, "unanalysable": unanalysable}


if __name__ == "__main__":
    main()
