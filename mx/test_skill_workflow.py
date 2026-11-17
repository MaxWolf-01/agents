"""A skill's WORKFLOW.md is read only where something points at it. Run: pytest
test_skill_workflow.py, or `make check`.

The convention is writing-for-agents' SKILL-MECHANICS.md, Knowledge and workflow: a workflow
session reaches a skill's WORKFLOW.md by the one line in its SKILL.md that links it, and other
documents name a section in it as "`/mx:<skill>`'s `WORKFLOW.md`, <heading>". A pointer line
deleted, or a reference to a heading that moved, leaves the rule behind it unread with nothing
failing, so both are held here.
"""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).parent / "skills"
REFERENCE = re.compile(r"/mx:([\w-]+)`'s `WORKFLOW\.md`, ([^)]+)\)")


def headings(path: Path) -> set[str]:
    return {line.lstrip("#").strip() for line in path.read_text().splitlines() if line.startswith("#")}


@pytest.mark.parametrize("workflow", sorted(SKILLS.glob("*/WORKFLOW.md")), ids=lambda p: p.parent.name)
def test_every_workflow_file_is_linked_from_its_skill(workflow):
    assert "](WORKFLOW.md)" in (workflow.parent / "SKILL.md").read_text(), \
        f"{workflow.parent.name}/SKILL.md has no line linking WORKFLOW.md"


def test_every_named_workflow_section_exists():
    references = [(path, *match.groups()) for path in sorted(SKILLS.rglob("*.md"))
                  for match in REFERENCE.finditer(path.read_text())]
    assert references, "no reference of the form `/mx:<skill>`'s `WORKFLOW.md`, <heading>) was found"
    missing = [f"{path.relative_to(SKILLS)}: {skill} has no WORKFLOW.md heading {heading!r}"
               for path, skill, heading in references
               if heading not in headings(SKILLS / skill / "WORKFLOW.md")]
    assert not missing, "\n".join(missing)
