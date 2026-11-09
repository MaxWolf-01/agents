"""The plan file read back: the steps and what each names, as the page draws them. The oracle is
the grammar session_plan.py's docstring and RULES.md give, written out by hand."""

from pathlib import Path

from session_plan import PLAN, PlanStep, read_plan


def test_a_plan_reads_as_steps_nested_by_indent_with_what_each_names(tmp_path: Path) -> None:
    (tmp_path / PLAN).write_text(
        "# the plan of a session\n"
        "done  Merge the heavy-work line | settles Q14 | see agent/diffviews/heavy.html\n"
        "  wait  Enforce placement beyond it? | waits Q27\n"
        "    next  Write the hook\n"
        "doing Collect the denials | job a local subagent\n"
        "\n"
        "Rename the status, a line with no state | owner max\n")
    assert read_plan(tmp_path) == (
        PlanStep("done", "Merge the heavy-work line", settles=("Q14",), see=("agent/diffviews/heavy.html",), under=(
            PlanStep("wait", "Enforce placement beyond it?", ("Q27",), under=(PlanStep("next", "Write the hook"),)),)),
        PlanStep("doing", "Collect the denials", jobs=("a local subagent",)),
        PlanStep("next", "Rename the status, a line with no state | owner max"),
    )


def test_a_line_indented_past_the_one_above_is_one_level_under_it(tmp_path: Path) -> None:
    """An indent jump of two levels is read as one, so no step is lost to a slip of the agent's."""
    (tmp_path / PLAN).write_text("doing A\n      next B\n  next C\n")
    assert read_plan(tmp_path) == (PlanStep("doing", "A", under=(PlanStep("next", "B"), PlanStep("next", "C"))),)
