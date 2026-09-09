# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "mutmut", "coverage"]
# ///
"""Checks for what harden decides on its own. Run: uv run test_harden.py

The oracle is the two prototype replays under `agent/prototypes/testing-workflow/` in the mx
repository: the shapes below are the ones those runs produced, including the mutant renumbering
that made a prototype report 41 new survivors where 3 were real.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from harden import (
    assemble,
    is_case_flip,
    module_name,
    mutation_targets,
    outside,
    parse_diff,
    with_code,
)

# mutmut reads a project's config when it is imported, so the runner is importable only from a tree
# that has one.
os.chdir(tempfile.mkdtemp(prefix="harden-tests-"))
Path("setup.cfg").write_text("[mutmut]\nsource_paths = src\n")

from mutmut_runner import mutmut_exit_code, tests_in_map

SOURCE = '''
"""A module."""

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


def test_lines_map_to_the_function_that_holds_them() -> None:
    assert mutation_targets(SOURCE, "pkg.mod", {11}) == {"pkg.mod.x_top_level": {11}}
    assert mutation_targets(SOURCE, "pkg.mod", {29}) == {"pkg.mod.xǁHolderǁmethod": {29}}


def test_a_nested_def_belongs_to_the_function_around_it() -> None:
    assert mutation_targets(SOURCE, "pkg.mod", {8}) == {"pkg.mod.x_top_level": {8}}


def test_what_mutmut_cannot_reach_comes_back_unclaimed() -> None:
    """Module level, a decorated function and a property: three shapes that generate no mutant, so
    a change to them is unmeasured rather than clean."""
    assert mutation_targets(SOURCE, "pkg.mod", {4}) == {"": {4}}
    assert mutation_targets(SOURCE, "pkg.mod", {16}) == {"": {16}}
    assert mutation_targets(SOURCE, "pkg.mod", {22}) == {"": {22}}


def test_a_lone_staticmethod_is_reachable() -> None:
    assert mutation_targets(SOURCE, "pkg.mod", {26}) == {"pkg.mod.xǁHolderǁcombine": {26}}


def test_unclaimed_blank_and_comment_lines_are_not_findings() -> None:
    assert with_code(SOURCE, {2, 3, 4, 5}) == {2, 4}


def test_module_names_match_the_ones_mutmut_prints() -> None:
    assert module_name("src/pkg/mod.py") == "pkg.mod"
    assert module_name("pkg/sub/__init__.py") == "pkg.sub"
    assert module_name("pkg/mod.py") == "pkg.mod"


def test_test_files_are_the_python_files_no_source_path_holds() -> None:
    changed = ["src/pkg/mod.py", "tests/test_mod.py", "README.md", "src/pkg/other.py"]
    assert outside(changed, ["src/pkg"]) == ["tests/test_mod.py"]


def test_an_edited_test_file_names_the_targets_its_tests_cover() -> None:
    """A deleted or weakened test is a change harden measures: the tool's own test-to-function map
    is what turns an edited test file into mutation targets."""
    test_map = {
        "pkg.mod.x_scan": {"tests/test_mod.py::test_scan", "tests/test_other.py::test_wide"},
        "pkg.mod.x_untouched": {"tests/test_other.py::test_wide"},
    }
    matched, targets = tests_in_map(["tests/test_mod.py"], test_map)
    assert matched == ["tests/test_mod.py"]
    assert targets == ["pkg.mod.x_scan*"]


def test_a_changed_file_the_map_does_not_know_names_nothing() -> None:
    assert tests_in_map(["scripts/tool.py"], {"pkg.mod.x_scan": {"tests/test_mod.py::test_scan"}}) == ([], [])


def test_a_kill_needs_a_failing_test() -> None:
    """mutmut scores any non-zero pytest exit as a kill; a broken fixture is then indistinguishable
    from a test that caught the mutation."""
    results = Path("junit.xml")
    results.write_text("<testsuites><testsuite><testcase><failure/></testcase></testsuite></testsuites>")
    assert mutmut_exit_code(1, results) == 1
    results.write_text("<testsuites><testsuite><testcase><error/></testcase></testsuite></testsuites>")
    assert mutmut_exit_code(1, results) == 35
    assert mutmut_exit_code(0, results) == 0
    assert mutmut_exit_code(5, results) == 5
    assert mutmut_exit_code(2, Path("no-such-file.xml")) == 35


def test_case_flips_are_recognised() -> None:
    assert is_case_flip("'utf-8' -> 'UTF-8'")
    assert is_case_flip("query = 'SELECT 1' -> query = 'select 1'")
    assert not is_case_flip("limit = 10 -> limit = 11")
    assert not is_case_flip("value.upper() -> value.UPPER()")


def report(**overrides):
    at_base = {"verdicts": {}, "wall_s": 1.0, "test_files_matched": [], "patterns_run": []}
    at_head = {"verdicts": {}, "wall_s": 1.0, "patterns_run": [], "uncovered": [], "unanalysable": {}}
    at_base.update(overrides.pop("at_base", {}))
    at_head.update(overrides.pop("at_head", {}))
    return assemble(
        Path("/repo"),
        "base..head",
        overrides.pop("changed", []),
        overrides.pop("source_paths", ["pkg"]),
        overrides.pop("unmeasured_lines", []),
        at_base,
        at_head,
    )


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
    assert report(changed=["scripts/tool.py"])["verdict"] == "unmeasured"
    assert report(at_head={"unanalysable": {"pkg/mod.py": "NoSource"}})["verdict"] == "unmeasured"
    assert (
        report(
            at_base={"patterns_run": ["pkg.mod.x_scan*"]},
            at_head={"patterns_run": ["pkg.mod.x_scan*"]},
        )["verdict"]
        == "unmeasured"
    )


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


def test_an_uncovered_changed_line_outranks_what_went_unmeasured() -> None:
    result = report(unmeasured_lines=["pkg/mod.py:4"], at_head={"uncovered": ["pkg/mod.py:12"]})
    assert result["verdict"] == "findings"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
