# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro"]
# ///
"""Checks for the coverage check over a breakdown. Run: uv run test_property_coverage.py

Two seams: `check`, a feature directory on disk in and findings out, and `main`, the same
with the exit code and the lines a session reads. The oracle is the ticket this was cut
from and the two skills it enforces: every property the spec states is named by some
ticket's criteria; a criterion naming a property the spec does not have fails too; a
property no slice can hold is disposed of where the others are, so absent and unsliceable
stop reading alike; ids are permanent, so a gap in them is not a finding and a repeat is.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from property_coverage import Args, check, main

PROPERTIES = [
    "P1 A lamp reads cold: the preset says what it is.",
    "P2 No preset blocks on the user naming it.",
    "P3 Every preset is demonstrated lit, never read.",
]


def feature(dir: Path, properties: list[str] = PROPERTIES, **tickets: str) -> Path:
    """A feature directory: a spec stating properties, and one ticket per keyword, its
    criteria the lines passed. `p1_reviewed=...` becomes ticket 01-p1-reviewed.md."""
    dir.mkdir(parents=True, exist_ok=True)
    bullets = "\n".join(f"- {p}" for p in properties)
    (dir / "spec.md").write_text(f"---\nstatus: confirmed\n---\n\n# Lamp\n\n## Properties\n\n{bullets}\n\n## Decisions\n\n- P9 is a decision, not a property.\n")
    for number, (name, criteria) in enumerate(sorted(tickets.items()), start=1):
        slug = name.replace("_", "-")
        (dir / f"{number:02d}-{slug}.md").write_text(f"---\nstatus: proposed\n---\n\n# {slug}\n\n## Acceptance criteria\n\n{criteria}\n")
    return dir


def findings(report) -> list[str]:
    return [f.what for f in report.findings]


def test_every_property_named_by_a_ticket_passes(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: the preset file says what it is.\n- [ ] Property P2, reviewed: nothing waits for a name.",
        two="- [ ] Property P3, executable: the seam is the preset renderer.",
    ))
    assert findings(report) == []
    assert report.disposed == {"P1", "P2", "P3"}


def test_a_property_no_ticket_names_fails_and_is_named(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: the preset file says what it is.",
        two="- [ ] Property P3, reviewed: the demo lights the lamp.",
    ))
    assert findings(report) == ["P2 reached no ticket: No preset blocks on the user naming it."]
    assert report.findings[0].at.path.name == "spec.md"


def test_a_criterion_naming_a_property_the_spec_lacks_fails(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P3, reviewed: c.\n- [ ] Property P9, reviewed: the decision it read as a property.",
    ))
    assert [f.what.split(" is not")[0] for f in report.findings] == ["P9"]
    assert report.findings[0].at.path.name == "01-one.md" and report.findings[0].at.number == 12


def test_a_criterion_naming_no_property_fails(tmp_path: Path) -> None:
    """The form the breakdowns used before properties carried ids: it claims a property without saying which."""
    report = check(feature(
        tmp_path / "lamp",
        one="- [x] Property, reviewed: the preset file says what it is.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P3, reviewed: c.",
    ))
    assert "criterion names no property id" in findings(report)
    assert "P1 reached no ticket: A lamp reads cold: the preset says what it is." in findings(report)


def test_a_disposition_that_is_none_of_the_three_fails(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, checked: a.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P3, reviewed: c.",
    ))
    assert findings(report) == ["disposition checked is none of reviewed, executable, unsliced"]


def test_a_property_no_slice_holds_is_disposed_of_where_the_others_are(tmp_path: Path) -> None:
    """An unsliced property passes, so absent and unsliceable stop reading alike."""
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.\n- Property P3, unsliced: every slice's demo shows it; no one slice makes it true.",
    ))
    assert findings(report) == []
    assert report.disposed == {"P1", "P2", "P3"}


def test_a_property_two_tickets_hold_is_named_by_both(tmp_path: Path) -> None:
    """A reviewed property is stamped onto each ticket touching its area, so a repeat is not a finding."""
    report = check(feature(
        tmp_path / "lamp",
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.",
        two="- [ ] Property P1, reviewed: the same property, this slice's half of it.\n- [ ] Property P3, reviewed: c.",
    ))
    assert findings(report) == []


def test_a_spec_whose_properties_carry_no_ids_says_so_once(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["A lamp reads cold.", "No preset blocks."],
        one="- [ ] The preset file says what it is.",
    ))
    assert findings(report) == ["the Properties list carries no ids; number it P1 onward, 2 properties"]


def test_one_property_left_unnumbered_is_named_on_its_own_line(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold.", "A property added in a later round, unnumbered."],
        one="- [ ] Property P1, reviewed: a.",
    ))
    assert findings(report) == ["property with no id"]
    assert report.findings[0].at.number == 10


def test_one_id_on_two_properties_fails(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold.", "P1 A second property that took the same id."],
        one="- [ ] Property P1, reviewed: a.",
    ))
    assert findings(report) == ["P1 is already the id of the property at line 9"]


def test_ids_are_permanent_so_a_gap_where_one_was_retired_is_no_finding(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold.", "P7 A property whose neighbours were retired."],
        one="- [ ] Property P1, reviewed: a.\n- [ ] Property P7, reviewed: b.",
    ))
    assert findings(report) == []


def test_properties_are_read_from_the_properties_section_alone(tmp_path: Path) -> None:
    """The spec's other sections carry bullets and ids of their own."""
    report = check(feature(tmp_path / "lamp", ["P1 A lamp reads cold."], one="- [ ] Property P1, reviewed: a."))
    assert [p.id for p in report.properties] == ["P1"]


def test_a_ticket_with_no_criteria_of_its_own_is_read_without_complaint(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold."],
        one="- [ ] Property P1, reviewed: a.",
        two="- [ ] The brightness slider moves.",
    ))
    assert findings(report) == []


def test_a_property_too_long_to_quote_whole_is_cut_at_a_word(tmp_path: Path) -> None:
    report = check(feature(
        tmp_path / "lamp",
        ["P1 A lamp reads cold, and every preset it carries says what it is without a conversation."],
        one="- [ ] The brightness slider moves.",
    ))
    assert findings(report) == ["P1 reached no ticket: A lamp reads cold, and every preset it carries says what it..."]


def test_a_clean_breakdown_exits_zero_and_counts_what_it_read(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    dir = feature(tmp_path / "lamp", one="- [ ] Property P1, reviewed: a.\n- [ ] Property P2, reviewed: b.\n- [ ] Property P3, reviewed: c.")
    with pytest.raises(SystemExit) as exit:
        main(Args(dir))
    assert exit.value.code == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "3 properties, 3 disposed of, 0 findings"


def test_a_breakdown_that_misses_a_property_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    dir = feature(tmp_path / "lamp", one="- [ ] Property P1, reviewed: a.")
    with pytest.raises(SystemExit) as exit:
        main(Args(dir))
    assert exit.value.code == 1
    out = capsys.readouterr()
    assert out.out.splitlines() == [
        f"{dir / 'spec.md'}:10: P2 reached no ticket: No preset blocks on the user naming it.",
        f"{dir / 'spec.md'}:11: P3 reached no ticket: Every preset is demonstrated lit, never read.",
    ]
    assert out.err.strip() == "3 properties, 1 disposed of, 2 findings"


def test_a_directory_that_is_not_a_breakdown_says_which_half_is_missing(tmp_path: Path) -> None:
    (tmp_path / "chore").mkdir()
    with pytest.raises(SystemExit) as no_spec:
        main(Args(tmp_path / "chore"))
    assert "no spec.md" in str(no_spec.value)
    with pytest.raises(SystemExit) as no_tickets:
        main(Args(feature(tmp_path / "lamp")))
    assert "no NN-<slug>.md tickets" in str(no_tickets.value)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
