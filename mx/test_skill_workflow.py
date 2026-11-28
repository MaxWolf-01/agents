"""A skill's WORKFLOW.md is read only where something points at it. Run: pytest
test_skill_workflow.py, or `make check`.

The convention is writing-for-agents' SKILL-MECHANICS.md, Knowledge and workflow: one line in
claude/CLAUDE.md's workflow block says a skill's WORKFLOW.md is read with it, and
dispatch/worker-prompt.md carries the same line for workers, who never load CLAUDE.md. Other
documents name a section in one as "`/mx:<skill>`'s `WORKFLOW.md`, <heading>". The line dropped
from either file, or a reference to a heading that moved, leaves the rules behind it unread with
nothing failing, so both are held here.

The same workflow block carries the table of where each artefact lives, and the worker prompt the
same table: a row edited in one file and not the other sends a worker's prototype, show or research
somewhere no session looks, so that copy is held here too.
"""

import re
from pathlib import Path

import pytest

MX = Path(__file__).parent
SKILLS = MX / "skills"
REFERENCE = re.compile(r"/mx:([\w-]+)`'s `WORKFLOW\.md`, ([^)]+)\)")


def headings(path: Path) -> set[str]:
    return {line.lstrip("#").strip() for line in path.read_text().splitlines() if line.startswith("#")}


def pointer(path: Path) -> list[str]:
    return [sentence for sentence in re.split(r"(?<=\.) ", path.read_text()) if "`WORKFLOW.md`" in sentence]


def test_the_session_and_the_worker_are_told_alike_to_read_a_skills_workflow_file():
    session, worker = pointer(MX.parent / "claude/CLAUDE.md"), pointer(SKILLS / "dispatch/worker-prompt.md")
    assert len(session) == 1, f"claude/CLAUDE.md carries {len(session)} sentences naming `WORKFLOW.md`, not one"
    assert worker == session, "dispatch/worker-prompt.md does not carry CLAUDE.md's line on WORKFLOW.md"



def artefact_table(path: Path) -> str:
    """The workflow block's artefact table, with the line after it and the paragraph that introduces it
    from "Its artefacts" on: the sentence before that names `/mx:orient`, which only a session loads."""
    block = re.search(r"<workflow>\n(.*?)</workflow>", path.read_text(), re.S).group(1)
    paragraphs = block.split("\n\n")
    tables = [i for i, paragraph in enumerate(paragraphs) if paragraph.startswith("| ")]
    assert len(tables) == 1, f"{path.name}'s workflow block holds {len(tables)} tables, not the one artefact table"
    intro = paragraphs[tables[0] - 1]
    return "\n\n".join([intro[intro.index("Its artefacts"):], *paragraphs[tables[0] : tables[0] + 2]])


def test_the_session_and_the_worker_read_one_artefact_table():
    session, worker = artefact_table(MX.parent / "claude/CLAUDE.md"), artefact_table(SKILLS / "dispatch/worker-prompt.md")
    assert worker == session, "dispatch/worker-prompt.md does not carry CLAUDE.md's artefact table word for word"

@pytest.mark.parametrize("workflow", sorted(SKILLS.rglob("WORKFLOW.md")), ids=lambda p: str(p.relative_to(SKILLS)))
def test_every_workflow_file_sits_beside_its_skill(workflow):
    assert workflow.parent.parent == SKILLS and (workflow.parent / "SKILL.md").exists(), \
        f"{workflow.relative_to(SKILLS)} is not beside a skill's SKILL.md, where the pointer reaches it"


def test_every_named_workflow_section_exists():
    references = [(path, *match.groups()) for path in sorted(SKILLS.rglob("*.md"))
                  for match in REFERENCE.finditer(path.read_text())]
    assert references, "no reference of the form `/mx:<skill>`'s `WORKFLOW.md`, <heading>) was found"
    missing = [f"{path.relative_to(SKILLS)}: {skill} has no WORKFLOW.md heading {heading!r}"
               for path, skill, heading in references
               if not (SKILLS / skill / "WORKFLOW.md").exists() or heading not in headings(SKILLS / skill / "WORKFLOW.md")]
    assert not missing, "\n".join(missing)
