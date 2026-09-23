# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro"]
# ///
"""Checks for the coverage check over a breakdown. Run: uv run test_property_coverage.py

Three seams: `check`, a feature directory on disk in and findings out; `main`, the same with the
exit code and the lines a session reads; and the command a to-tickets session types, run as a
subprocess. The oracle is the ticket this was cut from and the two skills it enforces: every
property the spec states is named by some ticket's acceptance criteria; a criterion naming a
property the spec does not have fails too; a property no slice can hold is disposed of where the
others are, so absent and unsliceable stop reading alike; ids are permanent, so a gap in them is
not a finding and a repeat is; a criterion outside the acceptance criteria disposes of nothing.
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
ALL_FOUR = "\n".join(f"- [ ] Property {id}, reviewed: this slice's half of it." for id in ("P1", "P2", "P3", "P10"))


def feature(dir: Path, properties: list[str] | None = None, **tickets: str) -> Path:
    """A feature directory: a spec stating properties, and one ticket per keyword whose acceptance
    criteria are the lines passed. `one=...` becomes ticket 01-one.md."""
    dir.mkdir(parents=True, exist_ok=True)
    bullets = "\n".join(f"- {p}" for p in properties or PROPERTIES)
    (dir / "spec.md").write_text(f"---\nstatus: confirmed\n---\n\n# Lamp\n\n## Properties\n\n{bullets}\n\n## Decisions\n\n- P9 is a decision, not a property.\n")
    for number, (name, criteria) in enumerate(sorted(tickets.items()), start=1):
        ticket(dir, f"{number:02d}-{name.replace('_', '-')}.md", criteria)
    return dir


def ticket(dir: Path, name: str, criteria: str, elsewhere: str = "") -> Path:
    """One ticket: its acceptance criteria, and whatever else its body says."""
    path = dir / name
    path.write_text(f"---\nstatus: proposed\n---\n\n# {name}\n\n## What to build\n\n{elsewhere}\n\n## Acceptance criteria\n\n{criteria}\n\n## Comments\n\n### Closing\n")
    return path


def findings(report) -> list[str]:
    return [f.what for f in report.findings]


def line_of(path: Path, text: str) -> int:
    """Which line of the file says this, counted the way an editor counts."""
    return path.read_text().splitlines().index(text) + 1


def test_every_property_named_by_a_ticket_passes(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: the preset file says what it is.\n- [ ] Property P2, reviewed: nothing waits for a name.",
        two="- [ ] Property P3, executable: the seam is the preset renderer.\n- [ ] Property P10, reviewed: the tenth.",
    ))
    assert findings(report) == []
    assert report.disposed == {"P1", "P2", "P3", "P10"}
    assert report.summary == "4 properties, 4 disposed of, 0 findings"


def test_a_property_no_ticket_names_fails_and_is_named(tmp_path: Path) -> None:
    dir = feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: the preset file says what it is.\n- [ ] Property P3, reviewed: the demo lights the lamp.\n- [ ] Property P10, reviewed: the tenth.",
    )
    report = check(dir)
    assert findings(report) == ["P2 reached no ticket: No preset blocks on the user naming it."]
    assert report.findings[0].at.path.name == "spec.md"
    assert report.findings[0].at.number == line_of(dir / "spec.md", f"- {PROPERTIES[1]}")


def test_a_criterion_naming_a_property_the_spec_lacks_fails(tmp_path: Path) -> None:
    dir = feature(tmp_path / "lamp", one=f"{ALL_FOUR}\n- [ ] Property P9, reviewed: the decision it read as a property.")
    report = check(dir)
    assert [f.what.split(" is not")[0] for f in report.findings] == ["P9"]
    assert report.findings[0].at.path.name == "01-one.md"
    assert report.findings[0].at.number == line_of(dir / "01-one.md", "- [ ] Property P9, reviewed: the decision it read as a property.")
    assert report.disposed == {"P1", "P2", "P3", "P10"}  # the claim on P9 credits nothing


def test_a_criterion_naming_no_property_fails(tmp_path: Path) -> None:
    """The form the breakdowns used before properties carried ids: it claims a property without saying which."""
    report = check(feature(
        tmp_path / "lamp",
        one="- [x] Property, reviewed: the preset file says what it is.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P3, reviewed: c.\n- [ ] Property P10, reviewed: d.",
    ))
    assert "criterion names no property id" in findings(report)
    assert "P1 reached no ticket: A lamp reads cold: the preset says what it is." in findings(report)


def test_a_disposition_that_is_none_of_the_three_fails(tmp_path: Path) -> None:
    report = check(feature(tmp_path / "lamp", one=ALL_FOUR.replace("Property P1, reviewed", "Property P1, checked")))
    assert findings(report) == ["disposition checked is none of reviewed, executable, unsliced"]


def test_a_criterion_naming_neither_is_not_a_claim(tmp_path: Path) -> None:
    """A bullet that merely opens with the word: a domain noun, or a half-written criterion."""
    report = check(feature(
        tmp_path / "lamp",
        one=f"{ALL_FOUR}\n- [ ] Property cards render in a grid.\n- [ ] Property\n- Property.",
    ))
    assert findings(report) == []


def test_a_property_no_slice_holds_is_disposed_of_where_the_others_are(tmp_path: Path) -> None:
    """An unsliced property passes, so absent and unsliceable stop reading alike."""
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P10, reviewed: d.\n- Property P3, unsliced: every slice's demo shows it; no one slice makes it true.",
    ))
    assert findings(report) == []
    assert report.disposed == {"P1", "P2", "P3", "P10"}


def test_a_bolded_criterion_is_a_claim_like_any_other(tmp_path: Path) -> None:
    report = check(feature(tmp_path / "lamp", one=ALL_FOUR.replace("- [ ] Property P1,", "- [ ] **Property P1**,")))
    assert findings(report) == []
    assert report.disposed == {"P1", "P2", "P3", "P10"}


def test_a_claim_outside_the_acceptance_criteria_disposes_of_nothing(tmp_path: Path) -> None:
    """A criterion quoted in the ticket's prose, or in a closing comment, holds no property."""
    dir = feature(tmp_path / "lamp", one=ALL_FOUR.replace("- [ ] Property P2, reviewed: this slice's half of it.\n", ""))
    ticket(dir, "01-one.md", ALL_FOUR.replace("- [ ] Property P2, reviewed: this slice's half of it.\n", ""),
           elsewhere="The slice the format is quoted in:\n\n- [ ] Property P2, reviewed: written where nothing reads it.")
    report = check(dir)
    assert findings(report) == ["P2 reached no ticket: No preset blocks on the user naming it."]


def test_a_property_two_tickets_hold_is_named_by_both(tmp_path: Path) -> None:
    """A reviewed property is stamped onto each ticket touching its area, so a repeat is not a finding."""
    dir = feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.",
        two="- [ ] Property P1, reviewed: the same property, this slice's half of it.\n- [ ] Property P3, reviewed: c.\n- [ ] Property P10, reviewed: d.",
    )
    report = check(dir)
    assert findings(report) == []
    assert report.summary == "4 properties, 4 disposed of, 0 findings"  # the repeat is one property, not two


def test_a_spec_whose_properties_carry_no_ids_says_so_once(tmp_path: Path) -> None:
    """Every criterion of a breakdown cut before the ids would fail too; the list is what to fix first."""
    report = check(feature(
        tmp_path / "lamp",
        ["A lamp reads cold.", "No preset blocks."],
        one="- [ ] Property, reviewed: the preset file says what it is.",
    ))
    assert findings(report) == ["the Properties list carries no ids; number it P1 onward, 2 properties"]


def test_one_property_left_unnumbered_is_named_on_its_own_line(tmp_path: Path) -> None:
    dir = feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold.", "A property added in a later round, unnumbered."],
        one="- [ ] Property P1, reviewed: a.",
    )
    report = check(dir)
    assert findings(report) == ["property with no id"]
    assert report.findings[0].at.number == line_of(dir / "spec.md", "- A property added in a later round, unnumbered.")


def test_a_sub_bullet_under_a_property_continues_it(tmp_path: Path) -> None:
    dir = tmp_path / "lamp"
    feature(dir, ["P1 A lamp reads cold."], one="- [ ] Property P1, reviewed: a.")
    (dir / "spec.md").write_text((dir / "spec.md").read_text().replace("- P1 A lamp reads cold.\n", "- P1 A lamp reads cold.\n  - which the preset file is what says\n"))
    report = check(dir)
    assert findings(report) == []
    assert [p.id for p in report.properties] == ["P1"]


def test_only_the_properties_section_is_read(tmp_path: Path) -> None:
    """A heading that merely starts with the word carries bullets of its own."""
    dir = tmp_path / "lamp"
    feature(dir, ["P1 A lamp reads cold."], one="- [ ] Property P1, reviewed: a.")
    (dir / "spec.md").write_text((dir / "spec.md").read_text().replace("## Decisions", "## Properties of the rendered page\n\n- P5 An id nobody claims.\n\n## Decisions"))
    report = check(dir)
    assert findings(report) == []
    assert [p.id for p in report.properties] == ["P1"]


def test_a_spec_with_no_properties_section_says_so_and_passes(tmp_path: Path) -> None:
    dir = tmp_path / "lamp"
    feature(dir, ["P1 A lamp reads cold."], one="- [ ] Property P1, reviewed: a.")
    (dir / "spec.md").write_text("---\nstatus: confirmed\n---\n\n# Lamp\n\n## Decisions\n\n- Nothing to hold.\n")
    report = check(dir)
    assert report.findings == []
    assert report.summary == f"no ## Properties section in {dir / 'spec.md'}"


def test_an_empty_properties_section_is_a_finding(tmp_path: Path) -> None:
    """The section is there and states nothing: a list someone meant to fill, not a spec without properties."""
    dir = tmp_path / "lamp"
    feature(dir, ["P1 A lamp reads cold."], one="- [ ] Property P1, reviewed: a.")
    (dir / "spec.md").write_text("---\nstatus: confirmed\n---\n\n# Lamp\n\n## Properties\n\n## Decisions\n\n- Nothing to hold.\n")
    report = check(dir)
    assert findings(report) == ["the Properties section states none"]
    assert report.findings[0].at.number == line_of(dir / "spec.md", "## Properties")


def test_one_id_on_two_properties_fails(tmp_path: Path) -> None:
    dir = feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold.", "P1 A second property that took the same id.", "P1 A third, taking it again."],
        one="- [ ] Property P1, reviewed: a.",
    )
    first = line_of(dir / "spec.md", "- P1 A lamp reads cold.")
    assert findings(check(dir)) == [f"P1 is already the id of the property at line {first}"] * 2  # both point at the original


def test_ids_are_permanent_so_a_gap_where_one_was_retired_is_no_finding(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold.", "P7 A property whose neighbours were retired."],
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P7, reviewed: b.",
    ))
    assert findings(report) == []


def test_a_ticket_with_no_criteria_of_its_own_is_read_without_complaint(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold."],
        one="- [ ] Property P1, reviewed: a.",
        two="- [ ] The brightness slider moves.",
    ))
    assert findings(report) == []


def test_a_property_is_quoted_whole_up_to_the_width_of_a_line(tmp_path: Path) -> None:
    sixty = "P1 " + "A lamp reads cold, and says so in the preset file." .ljust(60, ".")
    report = check(feature(tmp_path / "lamp", [sixty], one="- [ ] The brightness slider moves."))
    assert findings(report) == [f"P1 reached no ticket: {sixty[3:]}"]


def test_a_property_too_long_to_quote_whole_is_cut_at_a_word(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold, and every preset it carries says what it is without a conversation."],
        one="- [ ] The brightness slider moves.",
    ))
    assert findings(report) == ["P1 reached no ticket: A lamp reads cold, and every preset it carries says what it..."]


def test_a_property_with_no_word_break_to_cut_at_is_cut_at_the_width(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 " + "a" * 80],
        one="- [ ] The brightness slider moves.",
    ))
    assert findings(report) == [f"P1 reached no ticket: {'a' * 60}..."]


def test_a_clean_breakdown_exits_zero_and_counts_what_it_read(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    dir = feature(tmp_path / "lamp", one=ALL_FOUR)
    with pytest.raises(SystemExit) as exit:
        main(Args(dir))
    assert exit.value.code == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "4 properties, 4 disposed of, 0 findings"


def test_a_breakdown_that_misses_a_property_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """The findings a session works down: the spec's in the order it states them, then the tickets' in order."""
    dir = feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property, reviewed: which one?",
        two="- [ ] Property P3, reviewed: c.\n- [ ] Property P9, reviewed: no such property.",
    )
    spec, one, two = dir / "spec.md", dir / "01-one.md", dir / "02-two.md"
    with pytest.raises(SystemExit) as exit:
        main(Args(dir))
    assert exit.value.code == 1
    out = capsys.readouterr()
    assert out.out.splitlines() == [
        f"{one}:{line_of(one, '- [ ] Property, reviewed: which one?')}: criterion names no property id",
        f"{spec}:{line_of(spec, f'- {PROPERTIES[1]}')}: P2 reached no ticket: No preset blocks on the user naming it.",
        f"{spec}:{line_of(spec, f'- {PROPERTIES[3]}')}: P10 reached no ticket: A tenth property, so that an id runs to two digits.",
        f"{two}:{line_of(two, '- [ ] Property P9, reviewed: no such property.')}: P9 is not a property of {spec}",
    ]
    assert out.err.strip() == "4 properties, 2 disposed of, 4 findings"


def test_a_directory_that_is_not_a_breakdown_says_which_half_is_missing(tmp_path: Path) -> None:
    (tmp_path / "chore").mkdir()
    with pytest.raises(SystemExit) as no_spec:
        main(Args(tmp_path / "chore"))
    assert "no spec.md" in str(no_spec.value)
    with pytest.raises(SystemExit) as no_tickets:
        main(Args(feature(tmp_path / "lamp")))
    assert "no NN-<slug>.md tickets" in str(no_tickets.value)


def test_the_command_a_session_types_takes_the_directory_as_it_stands(tmp_path: Path) -> None:
    """`property-coverage <feature dir>`, the invocation the skill publishes, through the wrapper on PATH."""
    clean = feature(tmp_path / "lamp", one=ALL_FOUR)
    run = subprocess.run([str(COMMAND), str(clean)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stderr.strip() == "4 properties, 4 disposed of, 0 findings"

    missing = feature(tmp_path / "torch", one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P3, reviewed: c.")
    run = subprocess.run([str(COMMAND), str(missing)], capture_output=True, text=True)
    assert run.returncode == 1
    assert run.stdout.splitlines() == [f"{missing / 'spec.md'}:{line_of(missing / 'spec.md', f'- {PROPERTIES[3]}')}: P10 reached no ticket: A tenth property, so that an id runs to two digits."]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
