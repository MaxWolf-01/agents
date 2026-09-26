"""How the renderer reads what a page is made of: which of the user's messages a turn carries, and
where a record's links point. Run with the suite; the fixtures are conftest.py's.

The oracle for the pairing is the Decision on the turn record (a record carries the user's
messages said after the record before it was written and before it was) and the prototype's
sample, which holds, per record, the messages that turn answered.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from session_page import PAGE, RecordError, read_session, render_session

NOW = datetime(2026, 9, 23, 2, 30)

# When each of the worked example's records was written, between the prompts the prototype's sample
# pairs it with, as the Write call the session made would stamp it.
WRITTEN = {1: "2026-09-22T21:00:00Z", 2: "2026-09-22T21:40:00Z", 3: "2026-09-23T00:20:00Z", 4: "2026-09-23T01:30:00Z"}
# The start of what the user said in each turn of the prototype's sample, `sample/turns/NN.you.md`.
SAMPLE = {
    1: ["i feel like we need like a leading word"],
    2: ["/mx:show this is slightly meta now"],
    3: ["okay so i like the grid you showed"],
    4: ["okay okay i like it.", "hey can you please disregard"],
}


def with_writes(transcript: Path, directory: Path, out: Path, written: dict[int, str]) -> Path:
    """The transcript with the Write call of each record in `written` added, at the time given."""
    lines = transcript.read_text().splitlines()
    for number, at in written.items():
        write = {"type": "tool_use", "name": "Write",
                 "input": {"file_path": f"/elsewhere/agent/sessions/{directory.name}/turns/{number:02d}.md", "content": ""}}
        lines.append(json.dumps({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [write]}}))
    out.write_text("\n".join(lines) + "\n")
    return out


def test_a_turn_carries_what_the_user_said_since_the_record_before_it(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """The six prompts of the worked example against its four records: the first prompt's
    resubmission stands for it, the slash command reads as typed, the queued message joins the
    turn it was queued in."""
    session = read_session(worked_example, with_writes(transcript, worked_example, tmp_path / "t.jsonl", WRITTEN))
    carried = {t.number: [m[: len(s)] for m, s in zip(t.messages, SAMPLE[t.number])] for t in session.turns}
    assert carried == SAMPLE
    assert [len(t.messages) for t in session.turns] == [len(SAMPLE[n]) for n in SAMPLE]


def test_a_message_said_after_the_newest_record_waits_for_the_record_that_answers_it(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """Record 4 written before the last prompt: that prompt reaches no turn yet."""
    early = {**WRITTEN, 4: "2026-09-23T00:40:00Z"}
    session = read_session(worked_example, with_writes(transcript, worked_example, tmp_path / "t.jsonl", early))
    assert [m[:20] for m in session.turns[-1].messages] == ["okay okay i like it."]
    assert not any("hey can you please" in m for t in session.turns for m in t.messages)


def test_a_link_is_a_path_from_the_repo_root(worked_example: Path, transcript: Path) -> None:
    """Each link on the page, followed from the page's own directory, lands on the path the record
    wrote, from the root of the repo the session directory sits in."""
    root = worked_example.parents[2]
    page = render_session(worked_example, transcript, now=NOW)
    hrefs = re.findall(r'<a class="link" href="([^"]+)"', page)
    landed = [(worked_example / href).resolve().relative_to(root.resolve()).as_posix() for href in hrefs]
    written = re.findall(r"\]\(([^)]+)\)", "".join(p.read_text() for p in sorted((worked_example / "turns").glob("*.md"), reverse=True)))
    assert landed == written


@pytest.mark.parametrize("frontmatter, reason", [
    ("answered:\n  Q9: a", "Q9 is not a question of an earlier turn"),
    ("answered:\n  Q1: b", "Q1 was already answered in turn 03"),
    ("superseded:\n  Q7: Q8", "names Q8, which no turn asks"),
])
def test_a_record_that_clears_a_question_it_cannot_is_refused_and_no_page_is_written(
    worked_example: Path, transcript: Path, frontmatter: str, reason: str
) -> None:
    record = worked_example / "turns" / "05.md"
    record.write_text(f"---\ndate: 2026-09-24\n{frontmatter}\n---\n\n# Round 4\n")
    with pytest.raises(RecordError, match=re.escape(reason)) as refused:
        render_session(worked_example, transcript, now=NOW)
    assert str(refused.value).startswith(f"{record}:2: ")
    assert not (worked_example / PAGE).exists()
