# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis"]
# ///
"""The session renderer's properties. Run: uv run test_session_page.py

The seam is `render_session`: a session directory (`session.md`, `turns/NN.md`) and the session's
transcript in, the page out. The oracle is agent/tickets/session-page.md, its Properties and its
Decisions on the turn record's shape, over two kinds of input: sessions drawn by `sessions()`,
whose open questions come from the draw rather than from any reading of the records, and the
worked example in `fixtures/`, which is the prototype's sample with a trimmed copy of that
session's transcript.

A drawn session's transcript carries one prompt per turn in the shape the real one carries a
prompt. What the checks ask of a message is that it reaches one turn's section and that the noise
Claude Code writes as the user reaches none, never which turn a given prompt belongs to: the
Decisions do not say, so the pairing is session-renderer's to settle.
"""

import itertools
import json
import re
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

from session_page import PAGE, QUESTION, QUESTIONS, RECORD, render_session

LIFTED = "render_session is a stub; lifted by session-renderer"
NOW = datetime(2026, 9, 23, 2, 30)  # the clock the page is rendered against, so two renders compare
DRAWN = "00000000-0000-0000-0000-000000000000"  # the session id a drawn session carries
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


# ---- reading the page -------------------------------------------------------


def elements(page: str, attribute: str, pattern: str) -> dict[str, str]:
    """Each element of the page that carries `attribute` with a value `pattern` matches, whole,
    keyed by that value: a block is read by what marks it, not by where the next one starts, so
    anything nested inside a marked element stays part of it."""
    starts = list(itertools.accumulate((len(line) for line in page.splitlines(keepends=True)), initial=0))
    found: dict[str, str] = {}
    open_tags: list[tuple[str, str | None, int]] = []

    class Reader(HTMLParser):
        def at(self) -> int:
            line, column = self.getpos()
            return starts[line - 1] + column

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in VOID:
                return
            value = dict(attrs).get(attribute)
            open_tags.append((tag, value if value and re.fullmatch(pattern, value) else None, self.at()))

        def handle_endtag(self, tag: str) -> None:
            while open_tags:
                name, value, start = open_tags.pop()
                if name == tag:
                    if value:
                        found[value] = page[start : self.at() + len(f"</{tag}>")]
                    return

    Reader().feed(page)
    return found


def top_of(page: str) -> str:
    """The block the questions waiting on the user sit in, and nothing where a session with none
    open carries no block."""
    return elements(page, "id", QUESTIONS).get(QUESTIONS, "")


def questions_in(fragment: str) -> set[str]:
    """The questions a fragment of the page shows, by tag."""
    return set(re.findall(rf'{QUESTION}="(Q\d+)"', fragment))


def sections_of(page: str) -> dict[str, str]:
    """Each turn's section, keyed by the two digits of its record."""
    return elements(page, RECORD, r"\d+")


# ---- sessions to render -----------------------------------------------------


@st.composite
def sessions(draw: st.DrawFn) -> tuple[list[dict], set[str]]:
    """A session's turns as data, and the questions open at the end of it.

    Each turn draws a fate for every question still open before it (left alone, answered with an
    option's letter or with the user's own words, or superseded by one this turn asks) and then
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
    """A transcript holding the user's prompts and nothing else, each entry carrying what the real
    one's prompts carry: what tells a prompt from the images, task notifications and other
    sessions' hand-backs Claude Code also writes as user entries."""
    lines, parent = [], None
    for number, text in enumerate(messages, start=1):
        uuid = f"{number:08d}-0000-0000-0000-000000000000"
        lines.append(json.dumps({
            "parentUuid": parent, "isSidechain": False, "promptId": f"prompt-{number}", "type": "user",
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


def prompts(count: int) -> list[str]:
    """What the user said, one prompt per turn of a drawn session."""
    return [f"What I asked in turn {number}." for number in range(1, count + 1)]


def write_session(directory: Path, turns: list[dict]) -> tuple[Path, Path]:
    """A drawn session on disk: its directory, and the transcript whose prompts its turns
    answered, one per turn."""
    (directory / "turns").mkdir(parents=True, exist_ok=True)
    (directory / "session.md").write_text(
        f"---\nsession: {DRAWN}\nrepo: {directory.parent}\n---\n\n"
        "# A session with questions\n\n## Brief\n\nWhat it is about.\n"
    )
    for number, turn in enumerate(turns, start=1):
        (directory / "turns" / f"{number:02d}.md").write_text(record(number, turn))
    transcript = write_transcript(directory.parent / "transcript.jsonl", prompts(len(turns)))
    return directory, transcript


# ---- properties -------------------------------------------------------------


def test_the_page_is_read_by_the_values_its_module_names() -> None:
    """The page's side of the contract, pinned outside the module that states it: renaming one of
    these renames what the checks below and every later reader match on."""
    assert (PAGE, QUESTIONS, RECORD, QUESTION) == (
        "index.html", "open-questions", "data-record", "data-question")


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@settings(deadline=None)  # an example writes a session directory and renders it twice
@given(drawn=sessions())
def test_the_top_holds_the_open_questions_and_nothing_else(
    drawn: tuple[list[dict], set[str]], scratch: Callable[[], Path]
) -> None:
    """session-page#P1, over sessions whose questions meet every fate in turn: the open ones are
    what the top holds, and holding one of them twice, a turn, or a turn's details is holding
    something else."""
    turns, open_tags = drawn
    directory, transcript = write_session(scratch() / DRAWN, turns)
    top = top_of(render_session(directory, transcript, now=NOW))
    assert questions_in(top) == open_tags
    assert len(re.findall(rf"{QUESTION}=", top)) == len(open_tags)
    assert RECORD not in top, "a turn sits below the questions, and a link to one carries its id"
    assert [n for n in range(1, len(turns) + 1) if f"What turn {n} settled." in top] == []


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
def test_the_top_of_the_worked_example_holds_the_one_question_still_open(
    worked_example: Path, transcript: Path
) -> None:
    """session-page#P1, on the prototype's four records: turn 3 answers Q1 to Q3, turn 4 answers
    Q4 and Q6 and replaces Q5 with the Q7 it asks."""
    assert questions_in(top_of(render_session(worked_example, transcript, now=NOW))) == {"Q7"}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@settings(deadline=None)
@given(drawn=sessions(), which=st.integers(min_value=0))
def test_a_turns_record_is_the_only_source_of_its_section(
    drawn: tuple[list[dict], set[str]], which: int, scratch: Callable[[], Path]
) -> None:
    """session-page#P2: rewriting one record's headline and details moves that turn's section and
    leaves every other one where it was."""
    turns, _ = drawn
    number = which % len(turns) + 1
    directory, transcript = write_session(scratch() / DRAWN, turns)
    before_page = render_session(directory, transcript, now=NOW)
    (directory / "turns" / f"{number:02d}.md").write_text(
        record(number, turns[number - 1], headline="Rewritten", details="Rewritten too.")
    )
    after_page = render_session(directory, transcript, now=NOW)
    before, after = sections_of(before_page), sections_of(after_page)
    key = f"{number:02d}"
    assert after[key] != before[key]
    assert {n: s for n, s in after.items() if n != key} == {n: s for n, s in before.items() if n != key}
    assert questions_in(top_of(after_page)) == questions_in(top_of(before_page)), "a headline answers nothing"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
def test_the_page_regenerates_from_the_records_and_the_transcript_alone(
    worked_example: Path, transcript: Path, stale_page: str, tmp_path: Path
) -> None:
    """session-page#P2: the records and the transcript, carried on their own to a directory of the
    same name and depth, give back the page the session's own directory did, whatever else was
    lying beside them there."""
    (worked_example / PAGE).write_text(stale_page)
    (worked_example / "turns" / "notes.txt").write_text("a scratch file, which is not a record")
    page = render_session(worked_example, transcript, now=NOW)

    elsewhere = tmp_path / "elsewhere" / worked_example.relative_to(tmp_path)
    (elsewhere / "turns").mkdir(parents=True)
    shutil.copy(worked_example / "session.md", elsewhere)
    for source in sorted((worked_example / "turns").glob("[0-9][0-9].md")):
        shutil.copy(source, elsewhere / "turns")
    again = render_session(elsewhere, Path(shutil.copy(transcript, tmp_path)), now=NOW)
    assert top_of(again) == top_of(page)  # first, so a failure names the block that moved
    assert sections_of(again) == sections_of(page)
    assert again == page


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@settings(deadline=None)
@given(drawn=sessions(), which=st.integers(min_value=0))
def test_a_message_reaches_one_turns_section_and_no_other(
    drawn: tuple[list[dict], set[str]], which: int, scratch: Callable[[], Path]
) -> None:
    """session-page#P2: the transcript is the page's other source, and one prompt belongs to one
    turn. Which turn is not this check's business."""
    turns, _ = drawn
    directory, transcript = write_session(scratch() / DRAWN, turns)
    before = sections_of(render_session(directory, transcript, now=NOW))
    said = prompts(len(turns))
    said[which % len(said)] = "What I asked instead."
    write_transcript(transcript, said)
    after = sections_of(render_session(directory, transcript, now=NOW))
    moved = [number for number in before if after[number] != before[number]]
    assert moved != [], "the transcript went unread"
    assert len(moved) == 1


# What the user said in each of the worked example's four turns, the last of them queued mid-turn,
# and what Claude Code wrote as the user around them: images, task notifications and another
# session's hand-back, which are nobody's message.
SAID = (
    "which is i guess the same job the term leading word is doing right now",
    "this is slightly meta now but can you create an artifact",
    "okay so i like the grid you showed",
    "but yeah no html being written by the main session at any step makes sense",
    "okay okay i like it. so i definitely like the y for copy the resume command",
)
NOT_SAID = ("[Image: original 1400x3400", "Another Claude session sent a message", "task-notification")


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
def test_the_page_carries_what_the_user_said_and_none_of_what_claude_code_said_for_them(
    worked_example: Path, transcript: Path
) -> None:
    """session-page#P2, on the session's own transcript: the user's messages are read from it
    whole, the ones queued mid-turn included, and the entries Claude Code writes as user turns are
    not the user's."""
    page = render_session(worked_example, transcript, now=NOW)
    assert [said for said in SAID if said not in page] == []
    assert [noise for noise in NOT_SAID if noise in page] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
