"""Where each artefact of the workflow lives is said once, in claude/CLAUDE.md's workflow block,
and dispatch/worker-prompt.md carries the same passage for workers, who never load CLAUDE.md. A
row edited in one file and not the other sends a worker's prototype, show or research somewhere no
session looks, with nothing failing, so the copy is held here. Run: pytest test_artefact_table.py,
or `make check`.
"""

import re
from pathlib import Path

MX = Path(__file__).parent


def artefact_passage(path: Path) -> str:
    """The workflow block's opening paragraphs, up to and including the artefact table and the line after it."""
    block = re.search(r"<workflow>\n(.*?)</workflow>", path.read_text(), re.S).group(1)
    paragraphs = block.split("\n\n")
    table = next(i for i, paragraph in enumerate(paragraphs) if paragraph.startswith("| Artefact |"))
    return "\n\n".join(paragraphs[: table + 2])


def test_the_session_and_the_worker_read_one_artefact_table():
    session = artefact_passage(MX.parent / "claude/CLAUDE.md")
    assert "| Prototype | `agent/prototypes/<slug>/` |" in session
    assert artefact_passage(MX / "skills/dispatch/worker-prompt.md") == session, \
        "dispatch/worker-prompt.md's workflow block does not open with CLAUDE.md's artefact table, word for word"
