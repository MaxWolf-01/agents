#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""What a feature's tests fail to hold: the mutants of its changes that no test notices.

Harden mutates the functions a commit range touched, at the range's head and again at its base,
and reports the survivors the feature added, the changed lines nothing runs, and the changes it
could not measure at all. Python projects using pytest and mutmut: it drives the suite through
`uv run` in the tree, adding mutmut, coverage and pytest-cov to the project's own environment, and
the project's mutmut config (source paths, test selection, timeouts, `mutate_only_covered_lines`)
decides the scope.

What it measures, and how:

- Targets: the mutmut targets (a top-level function, or a method of a top-level class) holding a
  line the range added, changed or deleted, plus, for a range that edits tests, the targets whose
  covering tests live in the edited files, read off mutmut's test-to-function map at the base. A
  deleted or weakened test is a change, so it is measured like any other.
- Survivors are keyed by their target and mutation content, never by mutmut's `__mutmut_N`
  numbering, which shifts whenever the function around it is edited. A survivor already surviving
  at the base is the integration branch's, and is reported apart from the feature's.
- Case-flip survivors (a mutant whose only change is the letter case inside a string literal) are
  equivalent mutants by construction; they are listed apart and never counted as findings.
- Lines: only lines the suite covers are mutated, so a changed line nothing runs is reported on its
  own, as file:line, rather than scoring a silent zero. Coverage is collected with
  `COVERAGE_CORE=sysmon`, the one tracer that records lines after an `await` across a greenlet
  bridge.
- Unmeasured: mutmut mutates nothing at module level and skips decorated functions, so a changed
  line inside one has no mutant to run and is reported as unmeasured, whether the range added it or
  removed it, as are targets that generated no mutants and changed Python files outside the
  project's source paths that no test map knows as tests.
- Unresolved: a mutant left without a verdict (timeout, suspicious, not checked). A kill needs a
  failing test: a mutant whose tests error out (a broken fixture, a collection error) comes back
  unresolved rather than killed.
- Property tests run under the `harden` Hypothesis profile: every test process gets
  `HYPOTHESIS_PROFILE=harden`, which a project registers with a small example budget.

`--whole-repo` measures every target under the source paths at HEAD instead, with no base and so
nothing pre-existing: the report an architecture pass reads, where clustered survivors, uncovered
lines and unreachable code name the modules whose shape resists testing.

The tree has to be clean: harden mutates the tree it measures while reporting commits, so
uncommitted work would be measured without appearing in the range. Its own `mutants/`, `.coverage`
and `.hypothesis/` do not count as dirty.

Exit code: 0 when everything measured came back clean, 1 on findings (a new survivor or an
uncovered changed line), 2 when there are no findings but something could not be measured. `make`
collapses both non-zero codes into its own, so the line to read from `make harden` is the report's
last.

Cost is one full test run per tree plus the touched targets' mutants: seconds on a small CLI,
minutes for a feature's worth of plain logic on a service. It writes `mutants/` and a `.coverage`
file into both trees it measures; gitignore them.

JSON schema (--json):

    {"repo": "str", "range": "str", "targets": ["str"], "mutants": {"head": int, "base": int},
     "new_survivors": [{"mutant": "str", "target": "str", "diff": "str"}],
     "case_flip_survivors": [{"mutant": "str", "target": "str", "diff": "str"}],
     "pre_existing_survivors": ["str"], "uncovered": ["file:line"],
     "unmeasured": {"lines": ["file:line"], "removed_lines": ["file:line at the base"],
                    "targets_without_mutants": ["str"], "files": ["str"],
                    "unanalysable": {"file": "reason"}},
     "unresolved": {"mutant": "status"}, "wall_s": {"base": float, "head": float},
     "verdict": "pass|findings|unmeasured"}

Examples:

    uv run harden.py                            # this repo, since it forked from the integration branch
    uv run harden.py ~/repos/memex --range v2.2.2..HEAD
    uv run harden.py --integration-branch develop --json | jq '.new_survivors'
    uv run harden.py --whole-repo --json | jq '.new_survivors | group_by(.target)'
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
import tempfile
import tokenize
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

RUNNER = Path(__file__).parent / "mutmut_runner.py"
CLASS_SEPARATOR = "ǁ"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NOTHING_MEASURED = {
    "verdicts": {},
    "patterns_run": [],
    "test_files_matched": [],
    "uncovered": [],
    "unanalysable": {},
    "wall_s": 0.0,
}
"""A range with no mutation target and no edited test is reported without running the suite twice
to say so; what it changed, if anything, comes back under unmeasured."""


@dataclass
class Args:
    repo: Annotated[str, tyro.conf.Positional] = "."
    """Repository to measure. Its working tree must be at the range's head, and clean."""
    range: str = ""
    """Commit range `<base>..<head>`. Default: the merge-base with the integration branch, to HEAD."""
    integration_branch: str = ""
    """Branch the feature forked from, for the default range. Default: the remote's head branch, else main, else master."""
    whole_repo: bool = False
    """Measure every target under the source paths, at HEAD, with no base to compare against."""
    json: bool = False
    """Emit the report as JSON on stdout. Pipe to jq for filtering."""


@dataclass
class Changes:
    """What the report is about, and the part of it no mutant can speak for."""

    range: str
    files: list[str]
    unmeasured_lines: list[str]
    removed_lines: list[str]


def main(args: Args) -> None:
    repo = Path(args.repo).resolve()
    require_clean(repo)
    source_paths = source_paths_of(repo)
    report = whole_repo(repo, source_paths) if args.whole_repo else since_base(repo, source_paths, args)
    print(json.dumps(report, indent=2) if args.json else render(report))
    raise SystemExit({"pass": 0, "findings": 1, "unmeasured": 2}[report["verdict"]])


def since_base(repo: Path, source_paths: list[str], args: Args) -> dict:
    """What the range's own changes added to what the tests fail to hold, base measurement and all."""
    base, head = resolve_range(repo, args.range, args.integration_branch)
    if git(repo, "rev-parse", head) != git(repo, "rev-parse", "HEAD"):
        raise SystemExit(f"{head} is not the checked-out tree of {repo}; harden mutates the tree it measures")

    changed = changed_files(repo, base, head)
    new, old = parse_diff(git(repo, "diff", "-U0", f"{base}..{head}", "--", *source_paths))
    targets, unmeasured_lines = collect_targets(new, lambda path: read(repo / path))
    removed_targets, removed_lines = collect_targets(old, lambda path: show(repo, base, path))
    test_files = outside(changed, source_paths)
    changes = Changes(f"{base}..{head}", changed, unmeasured_lines, removed_lines)

    if not (targets or removed_targets or test_files):
        return assemble(repo, changes, source_paths, NOTHING_MEASURED, NOTHING_MEASURED)
    patterns = [f"{name}*" for name in sorted(set(targets) | set(removed_targets))]
    with base_worktree(repo, base) as tree:
        at_base = measure(tree, patterns=patterns, test_files=test_files, derive_targets=True)
    at_head = measure(repo, patterns=at_base["patterns_run"], test_files=test_files, changed_lines=new)
    return assemble(repo, changes, source_paths, at_base, at_head)


def whole_repo(repo: Path, source_paths: list[str]) -> dict:
    """The same three questions over the whole tree, for an architecture pass rather than a feature.

    Nothing is pre-existing when there is no base to compare against, so every survivor is reported.
    """
    files = [path for path in git(repo, "ls-files", "--", *source_paths).splitlines() if path.endswith(".py")]
    lines = {path: set(range(1, len(read(repo / path).splitlines()) + 1)) for path in files}
    targets, unmeasured_lines = collect_targets(lines, lambda path: read(repo / path))
    changes = Changes(f"whole repo at {git(repo, 'rev-parse', '--short', 'HEAD')}", files, unmeasured_lines, [])
    at_head = measure(repo, patterns=[f"{name}*" for name in targets], changed_lines=lines)
    return assemble(repo, changes, source_paths, NOTHING_MEASURED, at_head)


def require_clean(repo: Path) -> None:
    """Harden mutates the tree it measures, and reports commits: uncommitted work would be mutated
    without appearing in the range, and a crashed run would leave the mutants where the edits were."""
    artefacts = ("mutants/", ".coverage", ".hypothesis/")
    dirty = [line[3:] for line in git(repo, "status", "--porcelain").splitlines() if not line[3:].startswith(artefacts)]
    if dirty:
        raise SystemExit(f"{repo} has uncommitted changes ({', '.join(dirty)}); harden measures commits")


# --- the range, and what it changed ---------------------------------------------------------


def git(repo: Path, *argv: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *argv], capture_output=True, text=True, check=True).stdout.strip()


def resolve_range(repo: Path, commit_range: str, integration_branch: str) -> tuple[str, str]:
    if commit_range:
        base, separator, head = commit_range.partition("..")
        if not separator:
            raise SystemExit(f"--range takes `<base>..<head>`, not {commit_range!r}")
        return base, head or "HEAD"
    branch = integration_branch or default_branch(repo)
    return git(repo, "merge-base", branch, "HEAD"), "HEAD"


def default_branch(repo: Path) -> str:
    candidates = ["origin/HEAD", "main", "master"]
    for candidate in candidates:
        if (
            subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", candidate], capture_output=True).returncode
            == 0
        ):
            return candidate
    raise SystemExit(f"no integration branch found (tried {', '.join(candidates)}); pass --integration-branch")


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    return git(repo, "diff", "--name-only", f"{base}..{head}").splitlines()


def outside(changed: list[str], source_paths: list[str]) -> list[str]:
    """Changed Python files under none of the source paths: the test-file candidates, which mutmut's
    own test-to-function map then confirms or ignores."""
    return [path for path in changed if path.endswith(".py") and not under(path, source_paths)]


def under(path: str, source_paths: list[str]) -> bool:
    return any(path == source or path.startswith(source.rstrip("/") + "/") for source in source_paths)


def parse_diff(diff: str) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    """Per-file line numbers a diff touches, on the new side and on the old side.

    The old side is needed because a hunk that only deletes lines still changes the behaviour of
    the function it was deleted from, and that function has no new-side lines to point at.
    """
    new: dict[str, set[int]] = {}
    old: dict[str, set[int]] = {}
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[len("+++ b/") :] if line.startswith("+++ b/") else None
            continue
        match = HUNK.match(line)
        if not match or path is None or not path.endswith(".py"):
            continue
        old_start, old_count, new_start, new_count = match.groups()
        old_count = 1 if old_count is None else int(old_count)
        new_count = 1 if new_count is None else int(new_count)
        if old_count:
            old.setdefault(path, set()).update(range(int(old_start), int(old_start) + old_count))
        if new_count:
            new.setdefault(path, set()).update(range(int(new_start), int(new_start) + new_count))
    return new, old


# --- changed lines to mutation targets ------------------------------------------------------


def collect_targets(lines_by_path: dict[str, set[int]], source_of: Callable[[str], str]) -> tuple[list[str], list[str]]:
    """The targets holding the given lines, and the lines held by no target.

    Both sides of a diff go through this: the new side against the working tree, the old side
    against the base's blobs, so a hunk that only deletes still names its function, and a deleted
    module-level line still comes back as something nothing measured.
    """
    targets: set[str] = set()
    unmeasured: list[str] = []
    for path, lines in sorted(lines_by_path.items()):
        source = source_of(path)
        hits = mutation_targets(source, module_name(path), lines)
        targets |= {name for name in hits if name}
        unmeasured += [f"{path}:{line}" for line in sorted(with_code(source, hits.get("", set())))]
    return sorted(targets), unmeasured


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def show(repo: Path, commit: str, path: str) -> str:
    blob = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], capture_output=True, text=True)
    return blob.stdout if blob.returncode == 0 else ""


def mutation_targets(source: str, module: str, lines: set[int]) -> dict[str, set[int]]:
    """Map changed lines to the mutmut targets that contain them.

    mutmut only mutates top-level functions and methods of top-level classes; a mutation inside a
    nested def is attributed to the enclosing top-level function. Lines outside any such target
    (module level, a method of a nested class, a decorated function) are not mutable and come back
    under the empty key.
    """
    hits: dict[str, set[int]] = {}
    claimed: set[int] = set()

    def claim(name: str, node: ast.AST) -> None:
        inside = lines & set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        if inside:
            hits.setdefault(f"{module}.{name}", set()).update(inside)
            claimed.update(inside)

    for node in ast.parse(source).body if source else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and mutable(node):
            claim(f"x_{node.name}", node)
        elif isinstance(node, ast.ClassDef) and not node.decorator_list:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and mutable(child):
                    claim(f"x{CLASS_SEPARATOR}{node.name}{CLASS_SEPARATOR}{child.name}", child)
    if lines - claimed:
        hits[""] = lines - claimed
    return hits


def with_code(source: str, lines: set[int]) -> set[int]:
    """Of the lines given, the ones carrying code: a blank or comment line changes no behaviour, so
    calling it unmeasured would bury the module-level statements that genuinely are."""
    text = source.splitlines()
    return {
        line
        for line in lines
        if 0 < line <= len(text) and text[line - 1].strip() and not text[line - 1].lstrip().startswith("#")
    }


def mutable(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """mutmut copies a decorated function unmutated: a decorator runs at definition time, and a
    `@property` breaks its trampoline. One `@staticmethod` or `@classmethod` is the exception."""
    if len(node.decorator_list) == 1:
        decorator = node.decorator_list[0]
        return isinstance(decorator, ast.Name) and decorator.id in ("staticmethod", "classmethod")
    return not node.decorator_list


def module_name(path: str) -> str:
    """Dotted module path as mutmut names it (`utils/format_utils.py:get_mutant_name`): the path with
    separators as dots, `__init__` dropped, and a literal leading `src.` stripped. Any other source
    root (`source/`, `lib/`, the package itself) stays in the name, on both sides."""
    dotted = path[: -len(".py")].replace("/", ".").replace(".__init__", "")
    return dotted.split(".", 1)[1] if dotted.startswith("src.") else dotted


# --- measuring a tree -----------------------------------------------------------------------


@contextmanager
def base_worktree(repo: Path, base: str) -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix="harden-base-"))
    git(repo, "worktree", "add", "--detach", str(path), base)
    try:
        yield path
    finally:
        git(repo, "worktree", "remove", "--force", str(path))


def measure(
    tree: Path,
    *,
    patterns: list[str],
    test_files: list[str] | None = None,
    derive_targets: bool = False,
    changed_lines: dict[str, set[int]] | None = None,
) -> dict:
    """Measure one tree. `derive_targets` lets the tree's own test-to-function map add targets, which
    is the base's job: a target the base never measured has nothing to be new against."""
    job = {
        "mode": "measure",
        "patterns": patterns,
        "test_files": test_files or [],
        "derive_targets": derive_targets,
        "changed_lines": {path: sorted(lines) for path, lines in (changed_lines or {}).items()},
        "coverage_file": str(tree / ".coverage"),
    }
    return run_runner(tree, job)


def source_paths_of(repo: Path) -> list[str]:
    return run_runner(repo, {"mode": "config"})["source_paths"]


def run_runner(tree: Path, job: dict) -> dict:
    """The measurement runs in the project's own environment, where its tests can import it."""
    argv = ["uv", "run", "--quiet", "--with", "mutmut~=3.7", "--with", "coverage", "--with", "pytest-cov"]
    argv += ["python", str(RUNNER)]
    with tempfile.NamedTemporaryFile(suffix=".json") as report:
        job = {**job, "report_file": report.name}
        result = subprocess.run(argv, cwd=tree, input=json.dumps(job), stdout=sys.stderr, text=True)
        written = Path(report.name).read_text()
    if result.returncode != 0 or not written:
        raise SystemExit(f"the measurement failed in {tree} (exit {result.returncode}); its output is above")
    return json.loads(written)


# --- the report -----------------------------------------------------------------------------


def assemble(repo: Path, changes: Changes, source_paths: list[str], at_base: dict, at_head: dict) -> dict:
    survivors_at_base = {survivor_key(mutant, verdict["diff"]) for mutant, verdict in survivors(at_base).items()}
    new_survivors, case_flips, pre_existing = [], [], []
    for mutant, verdict in sorted(survivors(at_head).items()):
        entry = {"mutant": mutant, "target": target_of(mutant), "diff": verdict["diff"]}
        if survivor_key(mutant, verdict["diff"]) in survivors_at_base:
            pre_existing.append(mutant)
        elif is_case_flip(verdict["diff"]):
            case_flips.append(entry)
        else:
            new_survivors.append(entry)

    targets = sorted({pattern.rstrip("*") for pattern in at_head["patterns_run"]})
    known_tests = set(at_base["test_files_matched"]) | set(at_head["test_files_matched"])
    unmeasured = {
        "lines": changes.unmeasured_lines,
        "removed_lines": changes.removed_lines,
        "targets_without_mutants": [
            name for name in targets if not any(target_of(m) == name for m in at_head["verdicts"])
        ],
        "files": [path for path in outside(changes.files, source_paths) if path not in known_tests],
        "unanalysable": at_head["unanalysable"],
    }
    unresolved = {
        mutant: verdict["status"]
        for mutant, verdict in sorted(at_head["verdicts"].items())
        if verdict["status"] not in ("survived", "no tests", "killed")
    }
    findings = bool(new_survivors or at_head["uncovered"])
    blind = bool(unresolved or any(unmeasured.values()))
    return {
        "repo": str(repo),
        "range": changes.range,
        "targets": targets,
        "mutants": {"head": len(at_head["verdicts"]), "base": len(at_base["verdicts"])},
        "new_survivors": new_survivors,
        "case_flip_survivors": case_flips,
        "pre_existing_survivors": pre_existing,
        "uncovered": at_head["uncovered"],
        "unmeasured": unmeasured,
        "unresolved": unresolved,
        "wall_s": {"base": at_base["wall_s"], "head": at_head["wall_s"]},
        "verdict": "findings" if findings else "unmeasured" if blind else "pass",
    }


def survivors(report: dict) -> dict[str, dict]:
    return {mutant: verdict for mutant, verdict in report["verdicts"].items() if verdict["diff"] is not None}


def target_of(mutant: str) -> str:
    return mutant.split("__mutmut_")[0]


def survivor_key(mutant: str, diff: str) -> tuple[str, str]:
    """What makes two survivors the same one across trees: the function they live in and the
    mutation they apply. mutmut renumbers a function's mutants whenever the function is edited."""
    return target_of(mutant), diff


def is_case_flip(diff: str) -> bool:
    """True when the mutant changed nothing but the letter case inside a string literal.

    `"utf-8"` -> `"UTF-8"`, `"SELECT ..."` -> `"select ..."`: equivalent mutants by construction,
    since the value they stand for is case-insensitive wherever such a mutant survives at all.
    """
    for change in diff.split(" | "):
        before, separator, after = change.partition(" -> ")
        if not separator or before.lower() != after.lower():
            return False
        before_tokens, after_tokens = tokens(before), tokens(after)
        if before_tokens is None or after_tokens is None or len(before_tokens) != len(after_tokens):
            return False
        for old, new in zip(before_tokens, after_tokens):
            if old.string != new.string and old.type != tokenize.STRING:
                return False
    return True


def tokens(line: str) -> list[tokenize.TokenInfo] | None:
    try:
        return [
            token
            for token in tokenize.generate_tokens(io.StringIO(line.strip()).readline)
            if token.type not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER, tokenize.INDENT)
        ]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None


def by_target(unresolved: dict[str, str]) -> dict[str, str]:
    """Unresolved mutants are read per function, not one by one: what the reader acts on is the
    target whose verdicts are missing."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for mutant, status in unresolved.items():
        counts[target_of(mutant)][status] += 1
    return {
        target: ", ".join(f"{count} {status}" for status, count in sorted(statuses.items()))
        for target, statuses in sorted(counts.items())
    }


def by_file(locations: list[str]) -> dict[str, str]:
    """`file:line` locations as one entry per file: a whole-repo report otherwise prints a screen of
    them, and a reader wants the file before the numbers either way."""
    numbers: dict[str, list[str]] = defaultdict(list)
    for location in locations:
        path, _, line = location.rpartition(":")
        numbers[path].append(line)
    return {path: ", ".join(lines) for path, lines in sorted(numbers.items())}


def render(report: dict) -> str:
    lines = [
        f"repo       {report['repo']}",
        f"range      {report['range']}",
        f"targets    {len(report['targets'])}: {', '.join(report['targets']) or '-'}",
        (
            f"mutants    {report['mutants']['head']} at head, {report['mutants']['base']} at base"
            f" ({report['wall_s']['head']:.0f}s + {report['wall_s']['base']:.0f}s)"
        ),
    ]
    lines += [f"SURVIVED   {entry['mutant']}: {entry['diff']}" for entry in report["new_survivors"]]
    lines += [f"UNCOVERED  {path}: {numbers}" for path, numbers in by_file(report["uncovered"]).items()]
    lines += [f"UNRESOLVED {target}: {count}" for target, count in by_target(report["unresolved"]).items()]
    lines += [
        f"UNMEASURED {path}: no mutation target on {numbers}"
        for path, numbers in by_file(report["unmeasured"]["lines"]).items()
    ]
    lines += [
        f"UNMEASURED {path}: no mutation target on {numbers}, removed"
        for path, numbers in by_file(report["unmeasured"]["removed_lines"]).items()
    ]
    lines += [f"UNMEASURED {name}: no mutants" for name in report["unmeasured"]["targets_without_mutants"]]
    lines += [f"UNMEASURED {path}: outside the source paths" for path in report["unmeasured"]["files"]]
    lines += [f"UNMEASURED {path}: {reason}" for path, reason in report["unmeasured"]["unanalysable"].items()]
    lines += [f"case-flip  {entry['mutant']}: {entry['diff']}" for entry in report["case_flip_survivors"]]
    lines += [f"pre-exists {len(report['pre_existing_survivors'])} survivors the base already had"]
    return "\n".join([*lines, report["verdict"].upper()])


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
