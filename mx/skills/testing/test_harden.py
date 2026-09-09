# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "mutmut~=3.7", "coverage"]
# ///
"""Checks for harden. Run: uv run test_harden.py

Two layers: what harden decides on its own, and what it reports when driven at its command line
against a fixture repository, which is the seam the spec names. The oracle is the two prototype
replays under `agent/prototypes/testing-workflow/` in the mx repository, replayed here at fixture
scale: a function the tests do not pin comes back as a survivor, a deleted test brings its function
back into the measurement, and the mutant renumbering that made a prototype report 41 new survivors
where 3 were real stays filtered.

The end-to-end checks drive `uv`, mutmut and pytest in a temporary git repository; they take a
minute or two, and they are the only ones that exercise `main`.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from harden import (
    Changes,
    assemble,
    by_file,
    is_case_flip,
    keep,
    module_name,
    mutation_targets,
    outside,
    parse_diff,
    render,
    resolve_range,
    with_code,
)

HARDEN = Path(__file__).parent / "harden.py"

# mutmut reads a project's config when it is imported, so the runner is importable only from a tree
# that has one; the working directory this file was run from is the caller's, and goes back.
HERE = Path.cwd()
os.chdir(tempfile.mkdtemp(prefix="harden-tests-"))
Path("setup.cfg").write_text("[mutmut]\nsource_paths = src\n")

from mutmut_runner import greenlet_unnamed, mutmut_exit_code, targets_for_test_files

os.chdir(HERE)

SOURCE = '''
"""A module."""

# The bound every caller shares.
THRESHOLD = 3


def top_level(x):
    def nested(y):
        return y + 1

    return nested(x)


@decorated
def entry_point(request):
    return request


class Holder:
    @property
    def size(self):
        return 1

    @staticmethod
    def combine(a, b):
        return a + b

    def method(self, a):
        return a
'''


def tmp(name: str) -> Path:
    """A directory of this test's own: nothing here reads another test's leftovers."""
    directory = Path(tempfile.mkdtemp(prefix=f"harden-{name}-"))
    return directory


# --- what harden decides on its own ----------------------------------------------------------


def test_diff_gives_both_sides_of_every_hunk() -> None:
    diff = (
        "--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -10,2 +10,3 @@\n-old\n-old\n+new\n+new\n+new\n@@ -40,0 +42 @@\n+added\n"
    )
    new, old = parse_diff(diff)
    assert new == {"pkg/mod.py": {10, 11, 12, 42}}
    assert old == {"pkg/mod.py": {10, 11}}


def test_a_deletion_only_hunk_still_names_its_old_lines() -> None:
    """A hunk that only deletes has no new-side line to point at, and the function it was deleted
    from still changed behaviour."""
    new, old = parse_diff("--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -7,3 +6,0 @@\n-a\n-b\n-c\n")
    assert old == {"pkg/mod.py": {7, 8, 9}}
    assert new == {}


def test_an_insertion_only_diff_claims_nothing_on_the_old_side() -> None:
    new, old = parse_diff("--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -40,0 +41,2 @@\n+one\n+two\n")
    assert new == {"pkg/mod.py": {41, 42}}
    assert old == {}


def test_a_deleted_file_does_not_lend_its_lines_to_the_previous_one() -> None:
    """`+++ /dev/null` ends the file it belongs to; carrying the previous path forward turns a
    deletion's line numbers into targets in whatever file sorted before it."""
    diff = (
        "--- a/pkg/kept.py\n+++ b/pkg/kept.py\n@@ -4 +4 @@\n-old\n+new\n"
        "--- a/pkg/gone.py\n+++ /dev/null\n@@ -1,200 +0,0 @@\n-everything\n"
    )
    new, old = parse_diff(diff)
    assert new == {"pkg/kept.py": {4}}
    assert old == {"pkg/kept.py": {4}}


def test_lines_map_to_the_function_that_holds_them() -> None:
    assert mutation_targets(SOURCE, "pkg.mod", {12}) == {"pkg.mod.x_top_level": {12}}
    assert mutation_targets(SOURCE, "pkg.mod", {30}) == {"pkg.mod.xǁHolderǁmethod": {30}}


def test_a_nested_def_belongs_to_the_function_around_it() -> None:
    assert mutation_targets(SOURCE, "pkg.mod", {9}) == {"pkg.mod.x_top_level": {9}}


def test_what_mutmut_cannot_reach_comes_back_unclaimed() -> None:
    """Module level, a decorated function and a property: three shapes that generate no mutant, so
    a change to them is unmeasured rather than clean."""
    assert mutation_targets(SOURCE, "pkg.mod", {5}) == {"": {5}}
    assert mutation_targets(SOURCE, "pkg.mod", {17}) == {"": {17}}
    assert mutation_targets(SOURCE, "pkg.mod", {23}) == {"": {23}}


def test_a_lone_staticmethod_is_reachable() -> None:
    assert mutation_targets(SOURCE, "pkg.mod", {27}) == {"pkg.mod.xǁHolderǁcombine": {27}}


def test_unclaimed_blank_and_comment_lines_are_not_findings() -> None:
    """Line 4 is a comment, 3 and 6 are blank, 5 is the assignment: only the assignment is a change
    a mutant could have spoken for."""
    assert with_code(SOURCE, {3, 4, 5, 6}) == {5}


def test_module_names_match_the_ones_mutmut_prints() -> None:
    """mutmut strips one literal `src.` and nothing else (`utils/format_utils.py:get_mutant_name`),
    so any other source root stays in the name."""
    assert module_name("src/pkg/mod.py") == "pkg.mod"
    assert module_name("source/pkg/mod.py") == "source.pkg.mod"
    assert module_name("lib/pkg/mod.py") == "lib.pkg.mod"
    assert module_name("pkg/sub/__init__.py") == "pkg.sub"
    assert module_name("pkg/mod.py") == "pkg.mod"


def test_test_files_are_the_python_files_no_source_path_holds() -> None:
    """mutmut's source paths carry their trailing slash (`src/`, `yapit/`), which is the shape the
    prefix match has to survive."""
    changed = ["src/pkg/mod.py", "tests/test_mod.py", "README.md", "src/pkg/other.py"]
    assert outside(changed, ["src/"]) == ["tests/test_mod.py"]
    assert outside(changed, ["src/pkg/"]) == ["tests/test_mod.py"]


def test_an_edited_test_file_names_the_targets_its_tests_cover() -> None:
    """A deleted or weakened test is a change harden measures: the tool's own test-to-function map
    is what turns an edited test file into mutation targets."""
    test_map = {
        "pkg.mod.x_scan": {"tests/test_mod.py::test_scan", "tests/test_other.py::test_wide"},
        "pkg.mod.x_untouched": {"tests/test_other.py::test_wide"},
    }
    matched, targets = targets_for_test_files(["tests/test_mod.py"], test_map)
    assert matched == ["tests/test_mod.py"]
    assert targets == ["pkg.mod.x_scan*"]


def test_a_changed_file_the_map_does_not_know_names_nothing() -> None:
    assert targets_for_test_files(["scripts/tool.py"], {"pkg.mod.x_scan": {"tests/test_mod.py::test_scan"}}) == (
        [],
        [],
    )


def test_a_project_with_greenlet_has_to_name_it_in_its_coverage_config() -> None:
    """coverage's default is `thread`; naming greenlet replaces the default, and not naming it drops
    every line after an `await` into SQLAlchemy's engine without a warning."""
    assert greenlet_unnamed(None)
    assert greenlet_unnamed(["thread"])
    assert not greenlet_unnamed(["thread", "greenlet"])
    assert not greenlet_unnamed(["greenlet"])


def test_a_kill_needs_a_failing_test() -> None:
    """mutmut scores any non-zero pytest exit as a kill; a broken fixture is then indistinguishable
    from a test that caught the mutation."""
    directory = tmp("junit")
    results = directory / "junit.xml"
    case = "<testsuites><testsuite>{}</testsuite></testsuites>"
    results.write_text(case.format("<testcase><failure/></testcase>"))
    assert mutmut_exit_code(1, results) == 1
    results.write_text(case.format("<testcase><error/></testcase>"))
    assert mutmut_exit_code(1, results) == 35
    results.write_text(case.format("<testcase><error/></testcase><testcase><failure/></testcase>"))
    assert mutmut_exit_code(1, results) == 1, "a failure among the errors is still a kill"
    results.write_text(case.format("<testcase/>"))
    assert mutmut_exit_code(0, results) == 0
    assert mutmut_exit_code(5, results) == 5
    assert mutmut_exit_code(2, directory / "no-such-file.xml") == 35


def test_case_flips_are_recognised() -> None:
    assert is_case_flip("'utf-8' -> 'UTF-8'")
    assert is_case_flip("query = 'SELECT 1' -> query = 'select 1'")
    assert is_case_flip("'a' -> 'A' | 'b' -> 'B'"), "every change of a multi-change mutant is a flip"
    assert not is_case_flip("'a' -> 'A' | limit = 10 -> limit = 11")
    assert not is_case_flip("limit = 10 -> limit = 11")
    assert not is_case_flip("value.upper() -> value.UPPER()")
    assert not is_case_flip("'a' -> 'A' 'B'"), "the sides must hold the same tokens"


def test_locations_are_read_one_file_at_a_time() -> None:
    assert by_file(["pkg/a.py:4", "pkg/b.py:9", "pkg/a.py:12"]) == {"pkg/a.py": "4, 12", "pkg/b.py": "9"}


# --- the report ------------------------------------------------------------------------------


def report(**overrides):
    at_base = {"verdicts": {}, "wall_s": 1.0, "test_files_matched": [], "patterns_run": []}
    at_head = {
        "verdicts": {},
        "wall_s": 1.0,
        "patterns_run": [],
        "test_files_matched": [],
        "uncovered": [],
        "unanalysable": {},
    }
    at_base.update(overrides.pop("at_base", {}))
    at_head.update(overrides.pop("at_head", {}))
    changes = Changes(
        range="base..head",
        files=overrides.pop("changed", []),
        unmeasured_lines=overrides.pop("unmeasured_lines", []),
        removed_lines=overrides.pop("removed_lines", []),
    )
    return assemble(Path("/repo"), changes, overrides.pop("source_paths", ["pkg"]), at_base, at_head)


def test_a_survivor_the_base_already_had_is_not_the_features_finding() -> None:
    """Harden compares a feature against the point it branched from, and it compares by mutation
    content: editing a function renumbers every mutant in it."""
    survivor = {"status": "survived", "diff": "a > b -> a >= b"}
    result = report(
        at_base={"verdicts": {"pkg.mod.x_scan__mutmut_3": survivor}, "patterns_run": ["pkg.mod.x_scan*"]},
        at_head={"verdicts": {"pkg.mod.x_scan__mutmut_9": survivor}, "patterns_run": ["pkg.mod.x_scan*"]},
    )
    assert result["new_survivors"] == []
    assert result["pre_existing_survivors"] == ["pkg.mod.x_scan__mutmut_9"]
    assert result["verdict"] == "pass"


def test_the_same_mutation_in_another_function_is_not_the_same_survivor() -> None:
    """The key is the function and the mutation together: `a > b -> a >= b` is the commonest
    mutation there is, and one function's pre-existing survivor cannot excuse another's."""
    survivor = {"status": "survived", "diff": "a > b -> a >= b"}
    result = report(
        at_base={"verdicts": {"pkg.mod.x_scan__mutmut_1": survivor}, "patterns_run": ["pkg.mod.x_scan*"]},
        at_head={
            "verdicts": {"pkg.mod.x_scan__mutmut_1": survivor, "pkg.mod.x_sort__mutmut_1": survivor},
            "patterns_run": ["pkg.mod.x_scan*", "pkg.mod.x_sort*"],
        },
    )
    assert [entry["mutant"] for entry in result["new_survivors"]] == ["pkg.mod.x_sort__mutmut_1"]


def test_a_survivor_the_feature_added_is_a_finding() -> None:
    result = report(
        at_base={"patterns_run": ["pkg.mod.x_scan*"]},
        at_head={
            "verdicts": {"pkg.mod.x_scan__mutmut_9": {"status": "survived", "diff": "a > b -> a >= b"}},
            "patterns_run": ["pkg.mod.x_scan*"],
        },
    )
    assert [entry["diff"] for entry in result["new_survivors"]] == ["a > b -> a >= b"]
    assert result["verdict"] == "findings"


def test_a_case_flip_survivor_is_listed_apart() -> None:
    result = report(
        at_base={"patterns_run": ["pkg.mod.x_scan*"]},
        at_head={
            "verdicts": {"pkg.mod.x_scan__mutmut_1": {"status": "survived", "diff": "'utf-8' -> 'UTF-8'"}},
            "patterns_run": ["pkg.mod.x_scan*"],
        },
    )
    assert result["new_survivors"] == []
    assert len(result["case_flip_survivors"]) == 1
    assert result["verdict"] == "pass"


def test_a_change_that_could_not_be_measured_never_reads_as_clean() -> None:
    assert report(unmeasured_lines=["pkg/mod.py:4"])["verdict"] == "unmeasured"
    assert report(removed_lines=["pkg/mod.py:4"])["verdict"] == "unmeasured"
    assert report(changed=["scripts/tool.py"])["verdict"] == "unmeasured"
    assert report(at_head={"unanalysable": {"pkg/mod.py": "NoSource"}})["verdict"] == "unmeasured"
    assert (
        report(
            at_base={"patterns_run": ["pkg.mod.x_scan*"]},
            at_head={"patterns_run": ["pkg.mod.x_scan*"]},
        )["verdict"]
        == "unmeasured"
    )


def test_a_test_file_either_tree_knows_is_measured() -> None:
    """A test file the feature adds cannot be in the base's map, and a test file it deletes cannot be
    in the head's; a file either tree knows as a test is one harden measured."""
    added = report(changed=["tests/test_new.py"], at_head={"test_files_matched": ["tests/test_new.py"]})
    assert added["unmeasured"]["files"] == []
    deleted = report(changed=["tests/test_old.py"], at_base={"test_files_matched": ["tests/test_old.py"]})
    assert deleted["unmeasured"]["files"] == []
    stranger = report(changed=["scripts/tool.py"])
    assert stranger["unmeasured"]["files"] == ["scripts/tool.py"]


def test_an_unresolved_mutant_never_reads_as_clean() -> None:
    result = report(
        at_base={"patterns_run": ["pkg.mod.x_scan*"]},
        at_head={
            "verdicts": {
                "pkg.mod.x_scan__mutmut_1": {"status": "suspicious", "diff": None},
                "pkg.mod.x_scan__mutmut_2": {"status": "killed", "diff": None},
            },
            "patterns_run": ["pkg.mod.x_scan*"],
        },
    )
    assert result["unresolved"] == {"pkg.mod.x_scan__mutmut_1": "suspicious"}
    assert result["verdict"] == "unmeasured"


def test_a_range_that_changed_no_behaviour_is_clean() -> None:
    assert report(changed=["README.md"])["verdict"] == "pass"


def test_an_uncovered_changed_line_outranks_what_went_unmeasured() -> None:
    result = report(unmeasured_lines=["pkg/mod.py:4"], at_head={"uncovered": ["pkg/mod.py:12"]})
    assert result["verdict"] == "findings"


def test_the_report_reads_as_the_lines_the_human_acts_on() -> None:
    rendered = render(
        report(
            unmeasured_lines=["pkg/mod.py:4"],
            at_base={"patterns_run": ["pkg.mod.x_scan*"]},
            at_head={
                "verdicts": {"pkg.mod.x_scan__mutmut_9": {"status": "survived", "diff": "a > b -> a >= b"}},
                "patterns_run": ["pkg.mod.x_scan*"],
                "uncovered": ["pkg/mod.py:12", "pkg/mod.py:13"],
            },
        )
    )
    assert "targets    1: pkg.mod.x_scan" in rendered
    assert "mutants    1 at head, 0 at base" in rendered
    assert "SURVIVED   pkg.mod.x_scan__mutmut_9: a > b -> a >= b" in rendered
    assert "UNCOVERED  pkg/mod.py: 12, 13" in rendered
    assert "UNMEASURED pkg/mod.py: no mutation target on 4" in rendered
    assert rendered.endswith("\nFINDINGS")


def test_a_report_is_kept_where_the_workflow_keeps_its_artefacts() -> None:
    """Measuring costs minutes; reading the same measurement again should cost nothing."""
    directory = tmp("keep")
    result = report(unmeasured_lines=["pkg/mod.py:4"])
    assert keep(directory, result) is None, "a repository with no agent/ directory has nowhere to put one"

    (directory / "agent").mkdir()
    kept = keep(directory, result)
    assert kept.parent == directory / "agent" / "harden"
    assert kept.name.endswith("-base..head.txt")
    assert kept.read_text().strip() == render(result)

    whole = dict(result, range="whole repo at abc1234")
    assert keep(directory, whole).name.endswith("-whole-repo-abc1234.txt")


# --- driven at the command line, against a fixture repository ----------------------------------

BASE_MODULE = '''"""Clamp a value into a range."""


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def fits(value, limit):
    return value < limit
'''

HEAD_MODULE = '''"""Clamp a value into a range."""

STEP = 2


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def fits(value, limit):
    return value < limit


def scale(value):
    if value < 0:
        raise ValueError("scale takes a positive value")
    return value * STEP
'''

BASE_TESTS = """from pkg.mod import clamp, fits


def test_below_the_low_bound():
    assert clamp(-1, 0, 10) == 0


def test_above_the_high_bound():
    assert clamp(11, 0, 10) == 10


def test_inside_the_bounds():
    assert clamp(5, 0, 10) == 5


def test_a_value_under_the_limit_fits():
    assert fits(2, 3) is True


def test_the_limit_itself_does_not_fit():
    assert fits(3, 3) is False
"""

HEAD_TESTS = (
    BASE_TESTS.replace("import clamp, fits", "import clamp, fits, scale")
    + """

def test_scale_returns_a_number():
    assert isinstance(scale(3), int)
"""
)


def fixture_repo(directory: Path) -> None:
    """A repository harden can measure: a flat package, a suite that pins `clamp` and not `scale`.

    Two commits. The head adds a function whose only test asserts nothing about its result, a
    module-level constant, and a branch no test reaches: one of each thing the report distinguishes.
    """
    (directory / "pkg").mkdir(parents=True)
    (directory / "tests").mkdir()
    (directory / "conftest.py").write_text("")
    (directory / "setup.cfg").write_text(
        "[mutmut]\nsource_paths = pkg/\npytest_add_cli_args_test_selection =\n    tests\nmutate_only_covered_lines = true\n"
    )
    (directory / ".gitignore").write_text("mutants/\n.coverage\n__pycache__/\n")
    (directory / "pkg" / "__init__.py").write_text("")
    (directory / "pkg" / "mod.py").write_text(BASE_MODULE)
    (directory / "tests" / "test_mod.py").write_text(BASE_TESTS)
    git(directory, "init", "-q")
    git(directory, "add", "-A")
    git(directory, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (directory / "pkg" / "mod.py").write_text(HEAD_MODULE)
    (directory / "tests" / "test_mod.py").write_text(HEAD_TESTS)
    git(directory, "add", "-A")
    git(directory, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "scale")


def git(directory: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *argv], capture_output=True, text=True, check=True
    ).stdout.strip()


def drive_harden(directory: Path, *argv: str) -> tuple[int, dict | str]:
    """Harden at its command line, the seam the spec names. Returns its exit code and its report."""
    result = subprocess.run(
        [sys.executable, str(HARDEN), str(directory), "--json", *argv],
        capture_output=True,
        text=True,
    )
    try:
        return result.returncode, json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.returncode, result.stdout + result.stderr[-2000:]


def test_end_to_end_a_function_the_tests_do_not_pin() -> None:
    directory = tmp("e2e")
    fixture_repo(directory)
    code, report = drive_harden(directory, "--range", "HEAD~1..HEAD")
    assert isinstance(report, dict), report

    assert "pkg.mod.x_scale" in report["targets"], "the function the range added"
    assert report["new_survivors"], "no test tells `value * STEP` from `value / STEP`"
    assert {entry["target"] for entry in report["new_survivors"]} == {"pkg.mod.x_scale"}, (
        "clamp is unchanged, and whatever survives in it survived at the base too"
    )
    assert report["pre_existing_survivors"], "the untouched functions the edited test file pulled in"
    assert not any(m.startswith("pkg.mod.x_scale") for m in report["pre_existing_survivors"]), (
        "nothing in the new function existed at the base to be pre-existing"
    )
    assert report["uncovered"] == ["pkg/mod.py:20"], "the raise no test reaches"
    assert report["unmeasured"]["lines"] == ["pkg/mod.py:3"], "the module-level constant"
    assert report["unmeasured"]["files"] == [], "the edited test file is one the map knows"
    assert report["unresolved"] == {}
    assert code == 1, "findings"


def test_end_to_end_a_deleted_test_brings_its_function_back() -> None:
    """The prototype's second replay: no source line changes, and the function the deleted test held
    in place is measured anyway, off the base's test-to-function map."""
    directory = tmp("e2e-deleted")
    fixture_repo(directory)
    tests = directory / "tests" / "test_mod.py"
    tests.write_text(
        tests.read_text().replace("def test_the_limit_itself_does_not_fit():\n    assert fits(3, 3) is False", "")
    )
    git(directory, "add", "-A")
    git(directory, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "drop a clamp test")

    code, report = drive_harden(directory, "--range", "HEAD~1..HEAD")
    assert isinstance(report, dict), report
    assert "pkg.mod.x_fits" in report["targets"], "the deleted test's function is measured"
    assert [entry["target"] for entry in report["new_survivors"]] == ["pkg.mod.x_fits"], (
        "`value < limit` -> `value <= limit` was the deleted test's alone to catch"
    )
    assert code == 1


def test_end_to_end_whole_repo_needs_no_range() -> None:
    directory = tmp("e2e-whole")
    fixture_repo(directory)
    code, report = drive_harden(directory, "--whole-repo")
    assert isinstance(report, dict), report
    assert report["range"].startswith("whole repo at")
    assert set(report["targets"]) == {"pkg.mod.x_clamp", "pkg.mod.x_fits", "pkg.mod.x_scale"}
    assert report["mutants"]["base"] == 0, "nothing is pre-existing when there is no base"
    assert code == 1


def test_end_to_end_a_dirty_tree_is_refused() -> None:
    directory = tmp("e2e-dirty")
    fixture_repo(directory)
    (directory / "pkg" / "mod.py").write_text(HEAD_MODULE + "\n# an uncommitted edit\n")
    code, output = drive_harden(directory, "--range", "HEAD~1..HEAD")
    assert code != 0
    assert "uncommitted changes" in str(output)
    assert not (directory / "mutants").exists(), "refused before anything was measured"


def test_end_to_end_a_range_with_no_python_in_it_measures_nothing() -> None:
    directory = tmp("e2e-docs")
    fixture_repo(directory)
    (directory / "README.md").write_text("a readme\n")
    git(directory, "add", "-A")
    git(directory, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "docs")
    code, report = drive_harden(directory, "--range", "HEAD~1..HEAD")
    assert isinstance(report, dict), report
    assert report["verdict"] == "pass"
    assert code == 0
    assert not (directory / "mutants").exists(), "no suite was run to say so"


def test_the_default_range_starts_where_the_branch_forked() -> None:
    directory = tmp("fork")
    fixture_repo(directory)
    git(directory, "branch", "-m", "main")
    git(directory, "checkout", "-qb", "feature")
    (directory / "pkg" / "mod.py").write_text(HEAD_MODULE + "\n\ndef late():\n    return 1\n")
    git(directory, "add", "-A")
    git(directory, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "late")
    fork_point = git(directory, "rev-parse", "HEAD~1")

    base, head = resolve_range(directory, "", "")
    assert base == fork_point, "the merge-base with the integration branch, not its tip"
    assert head == "HEAD"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
