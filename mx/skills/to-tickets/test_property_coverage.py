# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro"]
# ///
"""Checks for the coverage check over a tracker. Run: pytest test_property_coverage.py

Three seams: `check`, a tracker on disk in and findings out; `main`, the same with the exit code and
the lines a session reads; and the command a session types, run as a subprocess. The oracle is
`agent/tickets/ticket-file-contract.md` (properties stated once on the ticket they hold for, cited
`<slug>#P<n>`, read through the ancestry) and `tracker --help`: a property is a `- P<n>` bullet under
`## Properties`, a criterion is a checkbox under `## Acceptance criteria`, and a citation that names
no ticket or property is the tracker's refusal, not a finding of this command's.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from property_coverage import Args, check, main

COMMAND = Path(__file__).parent.parent.parent / "bin" / "property-coverage"
PROPERTIES = [
    "P1 A lamp reads cold: the preset says what it is.",
    "P2 No preset blocks on the user naming it.",
    "P3 Every preset is demonstrated lit, never read.",
    "P10 A tenth property, so that an id runs to two digits.",
]
ALL_FOUR = "\n".join(f"- [ ] `lamp#{id}`: this slice's half of it." for id in ("P1", "P2", "P3", "P10"))


@pytest.fixture
def tracker(tmp_path: Path) -> Path:
    """An empty tracker, with the repo around it a caller runs the command in."""
    root = tmp_path / "repo" / "agent" / "tickets"
    root.mkdir(parents=True)
    return root


def ticket(root: Path, slug: str, criteria: str = "", properties: list[str] | None = None,
           parent: str = "", brief: str = "What this ticket is for.") -> Path:
    """One ticket the tracker's rules accept: the properties it states, and the criteria that cite
    them or any others'."""
    front = ["status: proposed"] + ([f"parent: {parent}"] if parent else []) + ["priority: 2", "size: S"]
    stated = "## Properties\n\n" + "\n".join(f"- {one}" for one in properties) + "\n\n" if properties else ""
    path = root / f"{slug}.md"
    path.write_text(
        "---\n" + "\n".join(front) + "\n---\n\n"
        f"# {slug.replace('-', ' ').capitalize()}\n\n## Brief\n\n{brief}\n\n"
        f"{stated}## Acceptance criteria\n\n{criteria}\n\n## Comments\n"
    )
    return path


def lamp(root: Path, properties: list[str] | None = None, **tickets: str) -> Path:
    """The tracker the checks read: a `lamp` ticket stating properties, and one child ticket per
    keyword whose acceptance criteria are the lines passed."""
    ticket(root, "lamp", properties=properties or PROPERTIES)
    for slug, criteria in sorted(tickets.items()):
        ticket(root, slug.replace("_", "-"), criteria, parent="lamp")
    return root


def findings(report) -> list[str]:
    return [f.what for f in report.findings]


def line_of(path: Path, text: str) -> int:
    """Which line of the file says this, counted the way an editor counts."""
    return path.read_text().splitlines().index(text) + 1


def test_every_property_cited_by_a_criterion_passes(tracker: Path) -> None:
    report = check(lamp(tracker, one=ALL_FOUR))
    assert findings(report) == []
    assert report.summary == "4 properties, 4 cited, 0 findings"


def test_a_property_no_criterion_cites_is_a_finding_at_the_line_it_is_stated_on(tracker: Path) -> None:
    lamp(tracker, one=ALL_FOUR.replace("- [ ] `lamp#P2`: this slice's half of it.\n", ""))
    report = check(tracker)
    assert findings(report) == [f"lamp#P2 reached no acceptance criterion: {PROPERTIES[1][3:]}"]
    assert report.findings[0].at.path == tracker / "lamp.md"
    assert report.findings[0].at.line == line_of(tracker / "lamp.md", f"- {PROPERTIES[1]}")
    assert report.summary == "4 properties, 3 cited, 1 finding"


def test_a_property_is_cited_from_any_ticket_of_the_tree(tracker: Path) -> None:
    """A property is stated once and read through the ancestry, so the slice that takes it on is
    rarely the ticket that states it."""
    report = check(lamp(
        tracker,
        one="- [ ] `lamp#P1`: the preset file.\n- [ ] `lamp#P3`: the demo.",
        two="- [ ] `lamp#P2`: the naming.\n- [ ] `lamp#P10`: the tenth.",
    ))
    assert findings(report) == []


def test_a_citation_outside_the_acceptance_criteria_disposes_of_nothing(tracker: Path) -> None:
    """A brief that mentions a property is prose; what takes one on is a criterion."""
    ticket(tracker, "lamp", properties=["P1 A lamp reads cold."])
    ticket(tracker, "one", criteria="- [ ] The brightness slider moves.",
           parent="lamp", brief="Cut from `lamp#P1`, which this is not the check for.")
    assert findings(check(tracker)) == ["lamp#P1 reached no acceptance criterion: A lamp reads cold."]


def test_a_tracker_whose_tickets_state_no_property_passes(tracker: Path) -> None:
    ticket(tracker, "one", criteria="- [ ] The brightness slider moves.")
    report = check(tracker)
    assert report.summary == "0 properties, 0 cited, 0 findings"
    assert findings(report) == []


def test_ids_are_permanent_so_a_gap_where_one_was_retired_is_no_finding(tracker: Path) -> None:
    report = check(lamp(
        tracker,
        ["P1 A lamp reads cold.", "P7 A property whose neighbours were retired."],
        one="- [ ] `lamp#P1`: a.\n- [ ] `lamp#P7`: b.",
    ))
    assert findings(report) == []


def test_a_citation_that_names_no_property_is_the_trackers_refusal_and_not_a_finding(tracker: Path) -> None:
    """One parser: a dangling citation is refused where the text was written, and this command
    exits with that refusal rather than reporting a coverage finding over a tracker no reader can
    read."""
    lamp(tracker, ["P1 A lamp reads cold."], one="- [ ] `lamp#P4`: a property the ticket does not state.")
    with pytest.raises(SystemExit) as stopped:
        check(tracker)
    assert "`lamp#P4` names no property; lamp states P1" in str(stopped.value)


def test_the_findings_come_out_in_the_order_the_properties_are_stated_in(tracker: Path) -> None:
    """A session reads them top down and fixes them in that order, so two uncovered properties on two
    tickets come out as the tracker states them."""
    ticket(tracker, "lamp", properties=["P1 A lamp reads cold.", "P2 No preset blocks on the user."])
    ticket(tracker, "dimmer", properties=["P1 A dimmer never flickers."], parent="lamp")
    report = check(tracker)
    assert [f.at.ref for f in report.findings] == ["dimmer#P1", "lamp#P1", "lamp#P2"]


def test_a_property_is_quoted_whole_up_to_the_width_of_a_line(tracker: Path) -> None:
    sixty = "P1 " + "A lamp reads cold, and says so in the preset file.".ljust(60, ".")
    report = check(lamp(tracker, [sixty], one="- [ ] The brightness slider moves."))
    assert findings(report) == [f"lamp#P1 reached no acceptance criterion: {sixty[3:]}"]


def test_a_property_too_long_to_quote_whole_is_cut_at_a_word(tracker: Path) -> None:
    report = check(lamp(
        tracker,
        ["P1 A lamp reads cold, and every preset it carries says what it is without a conversation."],
        one="- [ ] The brightness slider moves.",
    ))
    assert findings(report) == [
        "lamp#P1 reached no acceptance criterion: A lamp reads cold, and every preset it carries says what it..."
    ]


def test_a_property_with_no_word_break_to_cut_at_is_cut_at_the_width(tracker: Path) -> None:
    report = check(lamp(tracker, ["P1 " + "x" * 80], one="- [ ] The brightness slider moves."))
    assert findings(report) == [f"lamp#P1 reached no acceptance criterion: {'x' * 60}..."]


# ---- what a session reads --------------------------------------------------


def test_a_covered_tracker_exits_zero_and_says_what_it_read(tracker: Path, capsys: pytest.CaptureFixture) -> None:
    lamp(tracker, one=ALL_FOUR)
    with pytest.raises(SystemExit) as stopped:
        main(Args(at=tracker))
    assert stopped.value.code == 0
    said = capsys.readouterr()
    assert said.out == ""
    assert said.err.strip() == "4 properties, 4 cited, 0 findings"


def test_an_uncovered_property_exits_one_with_the_finding_on_stdout(tracker: Path, capsys: pytest.CaptureFixture) -> None:
    lamp(tracker, ["P1 A lamp reads cold."], one="- [ ] The brightness slider moves.")
    with pytest.raises(SystemExit) as stopped:
        main(Args(at=tracker))
    assert stopped.value.code == 1
    said = capsys.readouterr()
    assert said.out.strip() == f"{tracker / 'lamp.md'}:{line_of(tracker / 'lamp.md', '- P1 A lamp reads cold.')}: lamp#P1 reached no acceptance criterion: A lamp reads cold."
    assert said.err.strip() == "1 properties, 0 cited, 1 finding"


def test_a_path_that_is_no_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stopped:
        check(tmp_path / "nowhere")
    assert "no directory at" in str(stopped.value)


def test_the_command_finds_the_tracker_from_the_directory_it_is_run_in(tracker: Path) -> None:
    """What a session types: no argument, and the tracker above the working directory."""
    lamp(tracker, ["P1 A lamp reads cold."], one="- [ ] The brightness slider moves.")
    said = subprocess.run([str(COMMAND)], cwd=tracker.parent.parent, capture_output=True, text=True)
    assert said.returncode == 1
    assert said.stdout.strip().endswith("lamp#P1 reached no acceptance criterion: A lamp reads cold.")
    assert "1 properties, 0 cited, 1 finding" in said.stderr


def test_the_command_exits_with_the_trackers_own_refusal(tracker: Path) -> None:
    (tracker / "broken.md").write_text("no frontmatter here\n")
    said = subprocess.run([str(COMMAND), str(tracker)], capture_output=True, text=True)
    assert said.returncode != 0
    assert "no frontmatter" in said.stderr
