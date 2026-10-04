# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "hypothesis", "pyyaml", "markdown-it-py"]
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
Claude Code writes as the user reaches none, never which turn a given prompt belongs to, which
test_reading.py checks.
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

from conftest import SESSION
from session_page import ARTEFACT, COLUMN, PAGE, QUESTIONS, render_session

NOW = datetime(2026, 9, 23, 2, 30)  # the clock the page is rendered against, so two renders compare
DRAWN = "00000000-0000-0000-0000-000000000000"  # the session id a drawn session carries
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


# ---- reading the page -------------------------------------------------------


def elements(page: str, pattern: str) -> dict[str, str]:
    """Each element of the page whose id `pattern` matches, whole, keyed by that id: a block is
    read by the anchor that names it, not by where the next one starts, so anything nested inside
    it stays part of it."""
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
            value = dict(attrs).get("id")
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
    return elements(page, QUESTIONS).get(QUESTIONS, "")


def question_anchors(fragment: str) -> list[str]:
    """The questions a fragment of the page shows, by tag, once per time it shows one."""
    return [anchor.upper() for anchor in re.findall(r'\bid="(q\d+)"', fragment)]


def questions_in(fragment: str) -> set[str]:
    """The questions a fragment of the page shows, by tag."""
    return set(question_anchors(fragment))


def sections_of(page: str) -> dict[str, str]:
    """Each turn's section, keyed by the two digits of its record."""
    return {anchor[1:]: section for anchor, section in elements(page, r"t\d+").items()}


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
    """A transcript holding the user's prompts and, half an hour after each, the Write call of the
    record that answered it. A prompt carries what the real one's prompts carry: what tells a
    prompt from the images, task notifications and other sessions' hand-backs Claude Code also
    writes as user entries."""
    lines, parent = [], None
    for number, text in enumerate(messages, start=1):
        uuid = f"{number:08d}-0000-0000-0000-000000000000"
        lines.append(json.dumps({
            "parentUuid": parent, "isSidechain": False, "promptId": f"prompt-{number}", "type": "user",
            "message": {"role": "user", "content": text}, "uuid": uuid,
            "timestamp": f"2026-09-23T0{number}:00:00.000Z", "sessionId": DRAWN,
        }))
        call = {"type": "tool_use", "name": "Write", "input": {"file_path": f"{path.parent}/{DRAWN}/turns/{number:02d}.md"}}
        lines.append(json.dumps({
            "type": "assistant", "message": {"role": "assistant", "content": [call]},
            "timestamp": f"2026-09-23T0{number}:30:00.000Z", "sessionId": DRAWN,
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
    assert (PAGE, QUESTIONS) == ("index.html", "open-questions")


def test_the_hub_finds_an_artefact_by_its_attribute_and_the_column_by_its_id() -> None:
    """The page's side of the hub's contract: dotfiles' `minimize-and-restore` marks a link by
    this attribute and finds the column by this id, so a rename fails here before it reaches the hub."""
    assert (ARTEFACT, COLUMN) == ("data-artefact", "artefacts")


def test_every_link_within_the_page_lands_on_one_part_of_it(worked_example: Path, transcript: Path) -> None:
    """The ids the checks find a turn and a question by are the ones the page's own links jump to,
    and each names one part: an anchor that breaks, or a part shown twice, fails here."""
    page = render_session(worked_example, transcript, now=NOW)
    ids = re.findall(r'\bid="([^"]+)"', page)
    assert [i for i in set(ids) if ids.count(i) > 1] == []
    assert sorted({target for target in re.findall(r'href="#([^"]+)"', page)} - set(ids)) == []


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
    assert len(question_anchors(top)) == len(open_tags)
    assert not re.search(r'\bid="t\d+"', top), "a turn sits below the questions, and a link to one carries its id"
    assert [n for n in range(1, len(turns) + 1) if f"What turn {n} settled." in top] == []


def test_the_top_of_the_worked_example_holds_the_one_question_still_open(
    worked_example: Path, transcript: Path
) -> None:
    """session-page#P1, on the prototype's four records: turn 3 answers Q1 to Q3, turn 4 answers
    Q4 and Q6 and replaces Q5 with the Q7 it asks."""
    assert questions_in(top_of(render_session(worked_example, transcript, now=NOW))) == {"Q7"}


def test_the_turns_run_newest_first_with_only_the_newest_open(worked_example: Path, transcript: Path) -> None:
    """The Decisions' layout: the turns newest first, the newest open and the older ones
    collapsed."""
    turns = re.findall(r'<details class="turn[^"]*" id="t(\d+)"([^>]*)>', render_session(worked_example, transcript, now=NOW))
    assert [key for key, _ in turns] == ["04", "03", "02", "01"]
    assert [key for key, attributes in turns if re.search(r"\bopen\b", attributes)] == ["04"]


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


def test_the_page_regenerates_from_the_records_and_the_transcript_alone(
    worked_example: Path, transcript: Path, stale_page: str, tmp_path: Path
) -> None:
    """session-page#P2: the records and the transcript, carried on their own to a directory of the
    same name and depth, give back the page the session's own directory did, whatever else was
    lying beside them there. The path an artefact link carries for the hub names the repo root the
    page was rendered under, so the two pages compare with that attribute's new root read as the old."""
    (worked_example / PAGE).write_text(stale_page)
    (worked_example / "turns" / "notes.txt").write_text("a scratch file, which is not a record")
    page = render_session(worked_example, transcript, now=NOW)

    elsewhere = tmp_path / "elsewhere" / worked_example.relative_to(tmp_path)
    (elsewhere / "turns").mkdir(parents=True)
    shutil.copy(worked_example / "session.md", elsewhere)
    for source in sorted((worked_example / "turns").glob("[0-9][0-9].md")):
        shutil.copy(source, elsewhere / "turns")
    again = render_session(elsewhere, Path(shutil.copy(transcript, tmp_path)), now=NOW)
    again = again.replace(f'{ARTEFACT}="{tmp_path / "elsewhere"}/', f'{ARTEFACT}="{tmp_path}/')
    assert top_of(again) == top_of(page)  # first, so a failure names the block that moved
    assert sections_of(again) == sections_of(page)
    assert again == page


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


def test_a_code_span_naming_a_file_on_this_machine_opens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path a record writes as code is a link the user clicks rather than text they copy: from
    the repo root, absolute or under `~`, with a `:line` dropped. A path that is not there, a bare
    word, a command, and code already inside a link stay code."""
    root, home = tmp_path / "repo", tmp_path / "home"
    (root / "mx").mkdir(parents=True)
    (root / "mx" / "tool.py").write_text("")
    home.mkdir()
    (home / "notes.md").write_text("")
    elsewhere = tmp_path / "review.html"
    elsewhere.write_text("")
    monkeypatch.setenv("HOME", str(home))
    directory, transcript = write_session(root / "agent" / "sessions" / DRAWN, [{"asks": [], "answered": {}, "superseded": {}}])
    (directory / "turns" / "01.md").write_text(
        "---\ndate: 2026-09-21\n---\n\n# Paths\n\n## Links\n\n- [The `mx/tool.py` listing](mx/tool.py): the code\n\n"
        f"## Details\n\nSee `mx/tool.py:12`, `{elsewhere}`, `~/notes.md`, `mx`, `mx/gone.py`, `claude -p mx/tool.py` "
        "and [`mx/tool.py`](mx/tool.py).\n"
    )
    section = sections_of(render_session(directory, transcript, now=NOW))["01"]
    linked = re.findall(r'<a class="path" href="([^"]+)"[^>]*><code>([^<]*)</code></a>', section)
    assert linked == [
        ("../../../mx/tool.py", "mx/tool.py:12"),
        (elsewhere.as_uri(), str(elsewhere)),
        ((home / "notes.md").as_uri(), "~/notes.md"),
    ]
    assert section.count('class="path"') == 3, "a code span inside a link of its own was linked again"


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


def test_the_page_carries_what_the_user_said_and_none_of_what_claude_code_said_for_them(
    worked_example: Path, transcript: Path
) -> None:
    """session-page#P2, on the session's own transcript: the user's messages are read from it
    whole, the ones queued mid-turn included, and the entries Claude Code writes as user turns are
    not the user's."""
    page = render_session(worked_example, transcript, now=NOW)
    assert [said for said in SAID if said not in page] == []
    assert [noise for noise in NOT_SAID if noise in page] == []


# ---- the artefact column ----------------------------------------------------


def artefacts(fragment: str) -> list[tuple[str, str]]:
    """Each link to an artefact in a fragment of the page, in order: its text and the path the hub
    finds it by."""
    found: list[tuple[str, str]] = []
    inside: list[str] | None = None

    class Reader(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            nonlocal inside
            if tag == "a" and (target := dict(attrs).get(ARTEFACT)) is not None:
                found.append(("", target))
                inside = []

        def handle_data(self, data: str) -> None:
            if inside is not None:
                inside.append(data)

        def handle_endtag(self, tag: str) -> None:
            nonlocal inside
            if tag == "a" and inside is not None:
                found[-1] = (" ".join("".join(inside).split()), found[-1][1])
                inside = None

    Reader().feed(fragment)
    return found


def column_of(page: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """The artefact column, read: each turn's group, in the order the column shows them, by the two
    digits of its record, with its artefacts."""
    column = elements(page, COLUMN).get(COLUMN)
    assert column is not None, f"the page has no element with id {COLUMN!r}"
    groups = elements(column, r"a\d+")
    return [(key, artefacts(groups[f"a{key}"])) for key in re.findall(r'\bid="a(\d+)"', column)]


def keys_of(section: str) -> list[str]:
    """The key shown beside each link in a turn's body, in order, empty for a link no key opens."""
    links = re.search(r'<ol class="links">.*?</ol>', section, re.S).group()
    return [re.sub(r"<[^>]+>", "", item) for item in re.findall(r"<li>(<kbd[^>]*>\d</kbd>|<span class=\"n\"></span>)", links)]


def chips_of(page: str) -> dict[str, list[tuple[str, str]]]:
    """The artefacts each turn's summary line carries, which is what a collapsed turn shows."""
    return {key: artefacts(re.search(r"<summary.*?</summary>", section, re.S).group())
            for key, section in sections_of(page).items()}


def with_links(record_text: str, items: list[str]) -> str:
    """A record with `items` added under its `## Links`, the section opened where it has none."""
    added = "".join(f"{item}\n" for item in items)
    if "\n## Links\n" in record_text:
        return record_text.replace("\n## Links\n\n", f"\n## Links\n\n{added}", 1)
    return record_text.replace("\n## Details\n", f"\n## Links\n\n{added}\n## Details\n", 1)


# The worked example's artefacts, newest turn first, by the text and path its records give them.
SHOWN = [
    ("04", [("How the pages fit together", "agent/show/session-page/round-3/pages.html"),
            ("The spec page", "agent/show/session-page/round-3/spec.html")]),
    ("03", [("Round 2 as a hand-built session page", "agent/show/session-page/round-2/index.html")]),
    ("02", [("The grid, the session page sketch and Q1 to Q3", "agent/show/session-page/round-1/index.html")]),
]
# Links a turn record may carry to ticket files, here and in another repo, which are no artefact.
TICKET_LINKS = [
    "- [The ticket this round grills](agent/tickets/session-page.md): its Decisions",
    "- [The hub's ticket](/home/max/.dotfiles/agent/tickets/one-hub-tab.md#decisions): what it decided",
]


def test_the_column_lists_every_artefact_of_the_worked_example_under_its_turn_and_no_ticket(
    worked_example: Path, transcript: Path
) -> None:
    """session-pages-feed-the-hub#P2, on a real session's records: every artefact under the turn
    whose record links it, newest turn first, a turn with none left out, each carrying the path it
    resolves to on this machine; and a ticket file the newest turn links is not listed, carries
    no attribute the hub marks by, and takes no key, so the keys beside the turn's links are the
    column's."""
    root = worked_example.parents[2]
    shown = [(key, [(text, str(root / path)) for text, path in items]) for key, items in SHOWN]
    assert column_of(render_session(worked_example, transcript, now=NOW)) == shown
    newest = worked_example / "turns" / "04.md"
    newest.write_text(with_links(newest.read_text(), TICKET_LINKS))
    page = render_session(worked_example, transcript, now=NOW)
    assert column_of(page) == shown
    assert [target for _, target in artefacts(page) if "tickets" in target] == []
    assert keys_of(sections_of(page)["04"]) == ["", "", "1", "2"]


def test_a_collapsed_turn_shows_its_artefacts_on_its_summary_line(worked_example: Path, transcript: Path) -> None:
    """A collapsed turn shows its artefacts as chips: its summary line, which is all of it a
    collapsed turn shows, carries the column's group for it."""
    page = render_session(worked_example, transcript, now=NOW)
    assert chips_of(page) == dict(column_of(page)) | {"01": []}


# What a drawn turn links, and the path the hub finds each by from the repo root `root` and the
# home `home`; None for a ticket file, which the column never lists. Near misses of a ticket file
# sit beside them.
POOL: dict[str, Callable[[Path, Path], str | None]] = {
    "agent/show/csv-import/figure.html": lambda root, home: f"{root}/agent/show/csv-import/figure.html",
    "agent/show/csv-import/figure.html#step-2": lambda root, home: f"{root}/agent/show/csv-import/figure.html",
    "agent/tickets/csv-import.html": lambda root, home: f"{root}/agent/tickets/csv-import.html",
    "agent/show/csv-import/ticket.md": lambda root, home: f"{root}/agent/show/csv-import/ticket.md",
    "agent/research/tickets.md": lambda root, home: f"{root}/agent/research/tickets.md",
    "agent/tickets/csv-import/notes.html": lambda root, home: f"{root}/agent/tickets/csv-import/notes.html",
    "~/Downloads/show/ledger/page.html": lambda root, home: f"{home}/Downloads/show/ledger/page.html",
    "/srv/other/agent/show/hub/page.html": lambda root, home: "/srv/other/agent/show/hub/page.html",
    "https://example.com/rfc.html": lambda root, home: "https://example.com/rfc.html",
    "agent/tickets/csv-import.md": lambda root, home: None,
    "agent/tickets/csv-import.md#d4": lambda root, home: None,
    "/srv/other/agent/tickets/one-hub-tab.md": lambda root, home: None,
    "~/.dotfiles/agent/tickets/one-hub-tab.md": lambda root, home: None,
}


def register(registry: Path, pid: int, session: str, name: str, updated: int) -> None:
    """An entry in Claude Code's session registry, in the shape a running process writes it."""
    (registry / f"{pid}.json").write_text(json.dumps(
        {"pid": pid, "sessionId": session, "name": name, "nameSource": "derived", "updatedAt": updated}))


def test_the_session_id_copies_whole_from_the_meta_line(worked_example: Path, transcript: Path) -> None:
    """session-page-copies-the-session-id: the meta line shows the id's first eight characters on
    a button that copies the full id."""
    meta = re.search(r'<p class="v-meta">session (.*?)</p>', render_session(worked_example, transcript, now=NOW)).group(1)
    button = elements(meta, "session-id")["session-id"]
    assert f'data-copy="{SESSION}"' in button and button.endswith(f">{SESSION[:8]}</button>")
    assert re.sub(r"<[^>]+>", "", meta).startswith(f"{SESSION[:8]} · 4 turns · "), meta


def test_the_short_name_shows_beside_the_resume_button_where_the_registry_has_the_session(
    worked_example: Path, transcript: Path, registry: Path
) -> None:
    """session-page-copies-the-session-id: no entry for the session, no name; an entry for another
    session, or one half written, names nothing; of two entries for this session, the one updated
    last names it, beside the copy-resume button."""
    render = lambda: render_session(worked_example, transcript, now=NOW)
    assert "session-name" not in render()
    register(registry, 101, "11111111-2222-3333-4444-555555555555", "agents-12", updated=3)
    (registry / "102.json").write_text('{"sessionId": ')
    assert "session-name" not in render()
    register(registry, 103, SESSION, "agents-9", updated=1)
    register(registry, 104, SESSION, "agents-10", updated=2)
    actions = re.search(r'<div class="actions">(.*?)</div>', render(), re.S).group(1)
    assert re.fullmatch(r'\s*<button [^>]*id="resume".*?</button>\s*<span [^>]*id="session-name"[^>]*>agents-10</span>\s*',
                        actions, re.S), actions


@settings(deadline=None)
@given(linked=st.lists(st.lists(st.sampled_from(sorted(POOL)), max_size=4, unique=True), min_size=1, max_size=5))
def test_the_column_lists_each_turns_artefacts_and_never_a_ticket_file(
    linked: list[list[str]], scratch: Callable[[], Path], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """session-pages-feed-the-hub#P2, over sessions whose turns link artefacts, ticket files and
    paths that only look like one: each turn's artefacts, in the order its record gives them, under
    that turn's number, newest turn first, and nothing else."""
    home = tmp_path_factory.mktemp("home")
    turns = [{"asks": [], "answered": {}, "superseded": {}} for _ in linked]
    directory, transcript = write_session(scratch() / DRAWN, turns)
    for number, paths in enumerate(linked, start=1):
        record_path = directory / "turns" / f"{number:02d}.md"
        record_path.write_text(with_links(record_path.read_text(), [f"- [Link {i}]({p}): why" for i, p in enumerate(paths)]))
    root = directory.parents[2]
    expected = []
    for number, paths in reversed(list(enumerate(linked, start=1))):
        listed = [(f"Link {i}", target) for i, p in enumerate(paths) if (target := POOL[p](root, home)) is not None]
        if listed:
            expected.append((f"{number:02d}", listed))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(home))
        page = render_session(directory, transcript, now=NOW)
    assert column_of(page) == expected
    assert all(chips_of(page)[key] == items for key, items in expected)
    marked = {target for _, items in expected for _, target in items}
    assert {target for _, target in artefacts(page)} == marked, "a ticket file carries the attribute the hub marks by"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
