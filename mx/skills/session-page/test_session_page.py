# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis"]
# ///
"""The session renderer's properties. Run: uv run test_session_page.py

The seam is `render_session`: a session directory (`session.md`, `turns/NN.md`) and the session's
transcript in, the page out. The oracle is agent/tickets/session-page.md, its Properties and its
Decisions on the turn record's shape, over two kinds of input: sessions drawn by `sessions()`,
whose open questions come from the draw rather than from any reading of the records, and the
worked example in `fixtures/`, which is the prototype's sample (`agent/prototypes/session-page/
sample/`) with a trimmed copy of that session's transcript.
"""

import itertools
import json
import re
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

from session_page import OPEN_QUESTIONS, PAGE, QUESTION, TURN, render_session

LIFTED = "render_session is a stub; lifted by session-renderer"
NOW = datetime(2026, 9, 23, 2, 30)  # what the page says it was rendered at, so two renders compare
DRAWN = "00000000-0000-0000-0000-000000000000"  # the session id a drawn session carries


# ---- reading the page -------------------------------------------------------


def top_of(page: str) -> str:
    """The block at the top of the page, which holds the questions waiting on the user: from its
    id to the first turn below it, and nothing where a session with none open carries no block."""
    if f'id="{OPEN_QUESTIONS}"' not in page:
        return ""
    top = page[page.index(f'id="{OPEN_QUESTIONS}"') :]
    return top[: top.find(TURN)] if TURN in top else top


def questions_in(fragment: str) -> set[str]:
    """The questions a fragment of the page shows, by tag."""
    return set(re.findall(rf'{QUESTION}="(Q\d+)"', fragment))


def sections_of(page: str) -> dict[str, str]:
    """Each turn's section, keyed by its record's number: the page from one turn's mark to the
    next one's."""
    marks = [(m.group(1), m.start()) for m in re.finditer(rf'{TURN}="(\d+)"', page)]
    bounds = [start for _, start in marks[1:]] + [len(page)]
    return {number: page[start:end] for (number, start), end in zip(marks, bounds)}


# ---- sessions to render -----------------------------------------------------


@st.composite
def sessions(draw: st.DrawFn) -> tuple[list[dict], set[str]]:
    """A session's turns as data, and the questions open at the end of it.

    Each turn draws a fate for every question still open before it — left alone, answered with an
    option's letter or with the user's own words, or superseded by one this turn asks — and then
    asks questions of its own.
    """
    turns: list[dict] = []
    open_tags: list[str] = []
    tags = itertools.count(1)
    for _ in range(draw(st.integers(min_value=1, max_value=5))):
        turn: dict = {"asks": [], "answered": {}, "superseded": {}}
        for tag in list(open_tags):
            fate = draw(st.sampled_from(["open", "answered", "superseded"]))
            if fate == "answered":
                turn["answered"][tag] = draw(st.sampled_from(["a", "b", "neither: split it in two"]))
                open_tags.remove(tag)
            elif fate == "superseded":
                replacement = f"Q{next(tags)}"
                turn["superseded"][tag] = replacement
                turn["asks"].append(replacement)
                open_tags[open_tags.index(tag)] = replacement
        for _ in range(draw(st.integers(min_value=0, max_value=2))):
            tag = f"Q{next(tags)}"
            turn["asks"].append(tag)
            open_tags.append(tag)
        turns.append(turn)
    return turns, set(open_tags)


def record(number: int, turn: dict, headline: str = "", details: str = "") -> str:
    """One `turns/NN.md` in the shape the Decisions give it: frontmatter for what the renderer
    reads as data, an H1, and the sections the turn has."""
    front = [f"date: 2026-09-{20 + number:02d}"]
    for name in ("answered", "superseded"):
        if turn[name]:
            front.append(f"{name}:")
            front += [f"  {tag}: {json.dumps(value)}" for tag, value in turn[name].items()]
    body = [f"# {headline or f'Round {number}'}"]
    if turn["asks"]:
        body += ["", "## Questions", ""]
        for tag in turn["asks"]:
            body += [
                f"- [{tag}] **What about {tag}?** What hangs on it.",
                "  - (a) One way. *my pick*",
                "  - (b) The other way.",
            ]
    body += ["", "## Details", "", details or f"What turn {number} settled."]
    return "---\n" + "\n".join(front) + "\n---\n\n" + "\n".join(body) + "\n"


def write_transcript(path: Path, messages: list[str]) -> Path:
    """A transcript in the shape Claude Code writes one, holding the user's messages and nothing
    else: what the renderer reads a turn's message from."""
    lines, parent = [], None
    for number, text in enumerate(messages, start=1):
        uuid = f"{number:08d}-0000-0000-0000-000000000000"
        lines.append(json.dumps({
            "parentUuid": parent, "isSidechain": False, "type": "user",
            "message": {"role": "user", "content": text}, "uuid": uuid,
            "timestamp": f"2026-09-23T0{number}:00:00.000Z", "sessionId": DRAWN,
        }))
        parent = uuid
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture(scope="session")
def scratch(tmp_path_factory: pytest.TempPathFactory) -> Callable[[], Path]:
    """A fresh directory per drawn session: one example's records must not be read as another's."""
    return lambda: tmp_path_factory.mktemp("session")


def write_session(directory: Path, turns: list[dict]) -> tuple[Path, Path]:
    """A drawn session on disk: its directory, and the transcript whose messages its turns
    answered, one per turn."""
    (directory / "turns").mkdir(parents=True, exist_ok=True)
    (directory / "session.md").write_text(
        f"---\nsession: {DRAWN}\nrepo: {directory.parent}\n---\n\n"
        "# A session with questions\n\n## Brief\n\nWhat it is about.\n"
    )
    for number, turn in enumerate(turns, start=1):
        (directory / "turns" / f"{number:02d}.md").write_text(record(number, turn))
    transcript = write_transcript(
        directory.parent / "transcript.jsonl", [f"What I asked in turn {n}." for n in range(1, len(turns) + 1)]
    )
    return directory, transcript


# ---- properties -------------------------------------------------------------


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@given(drawn=sessions())
def test_the_top_holds_the_open_questions_and_nothing_else(
    drawn: tuple[list[dict], set[str]], scratch: Callable[[], Path]
) -> None:
    """session-page#P1, over sessions whose questions meet every fate in turn."""
    turns, open_tags = drawn
    directory, transcript = write_session(scratch() / DRAWN, turns)
    assert questions_in(top_of(render_session(directory, transcript, now=NOW))) == open_tags


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
def test_the_top_of_the_worked_example_holds_the_one_question_still_open(
    worked_example: Path, transcript: Path
) -> None:
    """session-page#P1, on the four rounds of the prototype's sample: turn 3 answers Q1 to Q3,
    turn 4 answers Q4 and Q6 and replaces Q5 with the Q7 it asks."""
    assert questions_in(top_of(render_session(worked_example, transcript, now=NOW))) == {"Q7"}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@given(drawn=sessions(), which=st.integers(min_value=0))
def test_a_turns_record_is_the_only_source_of_its_section(
    drawn: tuple[list[dict], set[str]], which: int, scratch: Callable[[], Path]
) -> None:
    """session-page#P2: rewriting one record's headline and details moves that turn's section and
    leaves every other one where it was."""
    turns, _ = drawn
    number = which % len(turns) + 1
    directory, transcript = write_session(scratch() / DRAWN, turns)
    before = sections_of(render_session(directory, transcript, now=NOW))
    (directory / "turns" / f"{number:02d}.md").write_text(
        record(number, turns[number - 1], headline="Rewritten", details="Rewritten too.")
    )
    after = sections_of(render_session(directory, transcript, now=NOW))
    key = f"{number:02d}"
    assert after[key] != before[key]
    assert {n: s for n, s in after.items() if n != key} == {n: s for n, s in before.items() if n != key}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
def test_the_page_regenerates_from_the_records_and_the_transcript_alone(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """session-page#P2: the records and the transcript, carried to a directory of their own, give
    back the page the session's own directory did, whatever else was lying beside them."""
    (worked_example / PAGE).write_text("<html>the page the turn before rendered</html>")
    (worked_example / "turns" / "notes.txt").write_text("a scratch file, which is not a record")
    page = render_session(worked_example, transcript, now=NOW)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "turns").mkdir(parents=True)
    shutil.copy(worked_example / "session.md", elsewhere)
    for source in sorted((worked_example / "turns").glob("[0-9][0-9].md")):
        shutil.copy(source, elsewhere / "turns")
    assert render_session(elsewhere, Path(shutil.copy(transcript, tmp_path)), now=NOW) == page


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
