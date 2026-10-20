# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "hypothesis", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""The session renderer's properties. Run: uv run test_session_page.py

The seam is the page as the values `render_session` formats (`session_page.view`): a session
directory (`session.md`, `turns/NN.md`) and the session's transcript in, the turns, questions and
artefacts the page shows out. What only the HTML carries, the anchors the page's links jump to, the
attribute the hub finds an artefact by, the prose a record's markdown renders to, is read off the
page, by checks that say they pin the format. The oracle is agent/tickets/session-page.md, its
Properties and its Decisions on the turn record's shape, over two kinds of input: sessions drawn
by `sessions()`, whose open questions come from the draw rather than from any reading of the
records, and the worked example in `fixtures/`, which is the prototype's sample with a trimmed
copy of that session's transcript.

A drawn session's transcript carries one prompt per turn in the shape the real one carries a
prompt. What the checks ask of a message is that it reaches one turn and that the noise Claude Code
writes as the user reaches none, never which turn a given prompt belongs to, which
test_reading.py checks.
"""

import html
import itertools
import json
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from session_checks import SESSION, TURN_ANCHOR, elements, rows_of, sections_of, text_of, turns_on, view_of
from session_page import ARTEFACT, COLUMN, PAGE, QUESTIONS, Turn, View, block, chat_path, chat_record, inline, render_session

NOW = datetime(2026, 9, 23, 2, 30)  # the clock the page is rendered against, so two renders compare
DRAWN = "00000000-0000-0000-0000-000000000000"  # the session id a drawn session carries


def waiting(page: View) -> list[str]:
    """The questions the top shows, by tag, once per time it shows one."""
    return [q.tag for _, q in page.waiting]


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
        "# A session with questions\n"
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
def test_the_top_holds_the_open_questions_each_once(
    drawn: tuple[list[dict], set[str]], scratch: Callable[[], Path]
) -> None:
    """session-page#P1, over sessions whose questions meet every fate in turn: the open ones are
    what the top holds, each once, and the page's top block holds nothing a turn settled."""
    turns, open_tags = drawn
    session = write_session(scratch() / DRAWN, turns)
    top = waiting(view_of(*session))
    assert set(top) == open_tags
    assert len(top) == len(open_tags)
    block = text_of(elements(render_session(*session, now=NOW), QUESTIONS).get(QUESTIONS, ""))
    assert [n for n in range(1, len(turns) + 1) if f"What turn {n} settled." in block] == []


def test_the_top_of_the_worked_example_holds_the_one_question_still_open(
    worked_example: Path, transcript: Path
) -> None:
    """session-page#P1, on the prototype's four records: turn 3 answers Q1 to Q3, turn 4 answers
    Q4 and Q6 and replaces Q5 with the Q7 it asks."""
    assert waiting(view_of(worked_example, transcript)) == ["Q7"]


def test_a_blind_question_waits_at_the_top_with_its_test_and_no_pick(tmp_path: Path) -> None:
    """A blind question is one the user answers on its test page, which holds the options and the
    agent's pick: the top shows it with a link to that page, and no option or pick of its own."""
    directory = tmp_path / "agent" / "sessions" / DRAWN
    (directory / "turns").mkdir(parents=True)
    (directory / "turns" / "01.md").write_text(
        "---\ndate: 2026-10-13\n---\n\n# Round 1\n\n## Questions\n\n"
        "- [Q1] **How does a refusal read?** five refusals, written both ways\n"
        "  - Blind: agent/show/refusals/blind-q1.html\n"
    )
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("")
    assert waiting(view_of(directory, transcript)) == ["Q1"]
    top = elements(render_session(directory, transcript, now=NOW), QUESTIONS)[QUESTIONS]
    assert 'href="../../../agent/show/refusals/blind-q1.html"' in top
    assert "my pick" not in text_of(top)


def test_the_turns_run_newest_first_with_only_the_newest_open(worked_example: Path, transcript: Path) -> None:
    """The Decisions' layout: the turns newest first, the newest open and the older ones
    collapsed."""
    rows = view_of(worked_example, transcript).rows
    assert [row.key for row in rows] == ["04", "03", "02", "01"]
    assert [row.key for row in rows if row.open] == ["04"]


def test_the_page_shows_each_turns_date_the_count_and_span_and_where_no_message_of_yours_is(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """session-page-turns-decluttered, read off the page as text: each turn's date, the number of
    turns and the dates they span, a turn that links no artefact under its headline in the
    timeline, and the line that stands in for the user's messages on record 3, whose write the
    transcript lacks, and on a chat turn after the newest record with nothing said before it; on no
    other turn."""
    unwritten = tmp_path / "t.jsonl"
    unwritten.write_text("".join(line for line in transcript.read_text().splitlines(keepends=True) if "/turns/03.md" not in line))
    at = datetime(2026, 9, 23, 2, 0, tzinfo=UTC)
    chat = chat_path(worked_example / "turns", at)
    chat.write_text(chat_record("Still building.", at))
    page = view_of(worked_example, unwritten)
    rendered = render_session(worked_example, unwritten, now=NOW)
    turns = turns_on(rendered)
    text = {row.key: turns[f"t{row.key}" if isinstance(row.turn, Turn) else row.key] for row in page.rows}
    assert {key: "no message of yours" in t for key, t in text.items()} == {
        chat.stem: True, "04": False, "03": True, "02": False, "01": False}
    assert [row.key for row in page.rows if row.when not in text[row.key]] == []
    assert f" 5 turns · {page.span} · " in text_of(rendered)
    assert text_of(elements(rendered, "a01")["a01"]) == "01 Round 1, as text: two axes, and a page per session"
    assert text_of(elements(rendered, f"a-{chat.stem}")[f"a-{chat.stem}"]) == "Still building.", "a chat turn is a row of the timeline"
    # when each turn ended, to the second, which the hub reads; none for record 3, whose write the transcript lacks
    ended = dict(re.findall(r'id="(t\d+|chat-[^"]+)"[^>]*?data-at="([^"]+)"', rendered))
    assert sorted(ended) == sorted(f"t{row.key}" if isinstance(row.turn, Turn) else row.key for row in page.rows if row.key != "03")
    assert all(datetime.fromisoformat(at) == row.turn.written for row in page.rows
               for at in [ended.get(f"t{row.key}" if isinstance(row.turn, Turn) else row.key)] if at)


@settings(deadline=None)
@given(drawn=sessions(), which=st.integers(min_value=0))
def test_a_turns_record_is_the_only_source_of_its_section(
    drawn: tuple[list[dict], set[str]], which: int, scratch: Callable[[], Path]
) -> None:
    """session-page#P2: rewriting one record's headline and details changes that turn and leaves
    every other one as it was."""
    turns, _ = drawn
    number = which % len(turns) + 1
    directory, transcript = write_session(scratch() / DRAWN, turns)
    before_page = view_of(directory, transcript)
    (directory / "turns" / f"{number:02d}.md").write_text(
        record(number, turns[number - 1], headline="Rewritten", details="Rewritten too.")
    )
    after_page = view_of(directory, transcript)
    before, after = rows_of(before_page), rows_of(after_page)
    key = f"{number:02d}"
    assert after[key] != before[key]
    assert {n: s for n, s in after.items() if n != key} == {n: s for n, s in before.items() if n != key}
    assert set(waiting(after_page)) == set(waiting(before_page)), "a headline answers nothing"


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
    assert again == page


@settings(deadline=None)
@given(drawn=sessions(), which=st.integers(min_value=0))
def test_a_message_reaches_one_turn_and_no_other(
    drawn: tuple[list[dict], set[str]], which: int, scratch: Callable[[], Path]
) -> None:
    """session-page#P2: the transcript is the page's other source, and one prompt belongs to one
    turn. Which turn is not this check's business."""
    turns, _ = drawn
    directory, transcript = write_session(scratch() / DRAWN, turns)
    before = rows_of(view_of(directory, transcript))
    said = prompts(len(turns))
    said[which % len(said)] = "What I asked instead."
    write_transcript(transcript, said)
    after = rows_of(view_of(directory, transcript))
    moved = [number for number in before if after[number] != before[number]]
    assert moved != [], "the transcript went unread"
    assert len(moved) == 1


def test_a_code_span_naming_a_file_on_this_machine_opens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path a record writes as code is a link the user clicks rather than text they copy: from
    the repo root, absolute or under `~`, with a `:line` dropped. A path that is not there, a
    `~name` that names no user, a bare word, a command, and code already inside a link stay code.
    Pins the format: the links are in the record's prose, which reaches the page as markup."""
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
        f"## Details\n\nSee `mx/tool.py:12`, `{elsewhere}`, `~/notes.md`, `mx`, `mx/gone.py`, `~ubuntu.26.04~resolute`, `claude -p mx/tool.py` "
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


def test_a_bare_url_and_a_file_url_are_links() -> None:
    """A URL a reply writes bare is a link, and so is a markdown link to a `file:` URL, such as a
    chat reply's PDF in `~/Downloads`. A file name that only looks like a domain stays text, a
    `javascript:` link stays text, and text shown inside a link of its own gets no link."""
    rendered = block("See https://example.com/a, [the PDF](file:///tmp/x.pdf), page.py and [no](javascript:alert(1)).")
    assert re.findall(r'<a href="([^"]+)"', rendered) == ["https://example.com/a", "file:///tmp/x.pdf"]
    assert "<a" not in inline("Stage at https://example.com/a", paths=False)


def test_text_between_double_tildes_renders_struck_through() -> None:
    """A grilling round shows the sentences its answers dropped from a ticket's brief struck through,
    beside the ones that replaced them; a lone tilde stays a tilde."""
    rendered = block("The goal is ~~one note per repo~~ one note per feature, ~5 lines long.")
    assert re.findall(r"<s>(.*?)</s>", rendered) == ["one note per repo"]
    assert "~5 lines" in rendered


def test_a_session_record_that_still_has_a_brief_renders_without_it(tmp_path: Path) -> None:
    """A session.md written while the page still carried a brief renders as it is, its title on the page and its
    brief nowhere the reader sees, so committed sessions need no rewrite."""
    directory, transcript = write_session(tmp_path / DRAWN, [{"asks": [], "answered": {}, "superseded": {}}])
    described = directory / "session.md"
    described.write_text(described.read_text() + "\n## Brief\n\nWhat the session was about, in a few sentences.\n")
    page = text_of(re.sub(r"<script\b.*?</script>", "", render_session(directory, transcript, now=NOW), flags=re.S))
    assert "A session with questions" in page
    assert "What the session was about" not in page


def test_a_code_block_sits_in_a_box_with_its_copy_button() -> None:
    """A fenced and an indented code block each render in a box holding the block and the button
    page.js copies it with, the code as it was; a code span gets no button. Pins the format: the
    box and the button are what page.js and page.css find the code by."""
    rendered = block("Run `ls` or:\n\n```sh\nmake test\n```\n\n    uv run x.py\n")
    boxes = re.findall(r'<div class="code">(<pre>.*?</pre>)\s*<button class="copy-code"', rendered, re.S)
    assert boxes == ['<pre><code class="language-sh">make test\n</code></pre>', "<pre><code>uv run x.py\n</code></pre>"]
    assert rendered.count('class="copy-code"') == 2


def test_each_turn_and_the_whole_session_copy_as_the_markdown_they_were_written_in(worked_example: Path, transcript: Path) -> None:
    """Each turn's block, a chat turn's too, holds the button that copies it, and the page carries what it copies:
    every record as written, under the block's id, and the whole session, its session.md and then every record in the
    order the turns happened. A record quoting `</script>`, or a comment's opening before a `<script>`, stays inside
    the data. Pins the format: page.js reads the
    data by its script's id and a turn's text by its block's."""
    at = datetime.now(UTC)
    chat = chat_path(worked_example / "turns", at)
    chat.write_text(chat_record("A reply quoting `<!--<script>` and `</script>`, which must not end the page's data.", at))
    page = render_session(worked_example, transcript, now=NOW)
    data = json.loads(re.search(r'<script type="application/json" id="sources">(.*?)</script>', page, re.S)[1])
    records = sorted((worked_example / "turns").glob("[0-9][0-9].md"))
    turns = {**{f"t{p.stem}": p.read_text() for p in records}, chat.stem: chat.read_text()}
    assert {k: v for k, v in data.items() if k != "session"} == turns
    assert data["session"] == "\n\n".join(p.read_text().strip() for p in [worked_example / "session.md", *records, chat]) + "\n"
    blocks = elements(page, TURN_ANCHOR)
    assert set(blocks) == set(turns) and all('class="copy-turn"' in b for b in blocks.values())


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


def column_of(page: View) -> list[tuple[str, list[tuple[str, str]]]]:
    """The timeline: each numbered turn, in the order it shows them, with the text of each artefact
    the turn links and the path the hub finds it by."""
    return [(row.key, [(s.link.text, s.artefact) for s in row.artefacts]) for row in page.column]


def marked(page: str) -> set[str]:
    """The paths the page's links carry for the hub, which finds an artefact by that attribute."""
    return {html.unescape(target) for target in re.findall(rf'\b{ARTEFACT}="([^"]*)"', page)}


def chips_of(page: str) -> dict[str, list[str]]:
    """Pins the format: the paths each turn's summary line carries for the hub, by the two digits
    of its record. The summary line is what shows of a collapsed turn."""
    return {key: [html.unescape(target) for target in re.findall(
                rf'\b{ARTEFACT}="([^"]*)"', re.search(r"<summary.*?</summary>", section, re.S).group())]
            for key, section in sections_of(page).items()}


def with_links(record_text: str, items: list[str]) -> str:
    """A record with `items` added under its `## Links`, the section opened where it has none."""
    added = "".join(f"{item}\n" for item in items)
    if "\n## Links\n" in record_text:
        return record_text.replace("\n## Links\n\n", f"\n## Links\n\n{added}", 1)
    return record_text.replace("\n## Details\n", f"\n## Links\n\n{added}\n## Details\n", 1)


# The worked example's turns, newest first, with the text and path its records give each artefact.
LISTED = [
    ("04", [("How the pages fit together", "agent/show/session-page/round-3/pages.html"),
            ("The spec page", "agent/show/session-page/round-3/spec.html")]),
    ("03", [("Round 2 as a hand-built session page", "agent/show/session-page/round-2/index.html")]),
    ("02", [("The grid, the session page sketch and Q1 to Q3", "agent/show/session-page/round-1/index.html")]),
    ("01", []),
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
    whose record links it, newest turn first, a turn with none listed bare, each carrying the path it
    resolves to on this machine; and a ticket file the newest turn links is not listed, carries
    no attribute the hub marks by, and takes no key, so the keys beside the turn's links are the
    column's."""
    root = worked_example.parents[2]
    listed = [(key, [(text, str(root / path)) for text, path in items]) for key, items in LISTED]
    assert column_of(view_of(worked_example, transcript)) == listed
    newest = worked_example / "turns" / "04.md"
    newest.write_text(with_links(newest.read_text(), TICKET_LINKS))
    page = view_of(worked_example, transcript)
    assert column_of(page) == listed
    assert [link.key for link in rows_of(page)["04"].links] == [None, None, 1, 2]
    rendered = render_session(worked_example, transcript, now=NOW)
    assert marked(rendered) == {target for _, items in listed for _, target in items}
    assert chips_of(rendered) == {key: [target for _, target in items] for key, items in listed}, "a collapsed turn's summary line"



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
    button = elements(render_session(worked_example, transcript, now=NOW), "session-id")["session-id"]
    assert f'data-copy="{SESSION}"' in button and button.endswith(f">{SESSION[:8]}</button>")


def test_the_short_name_shows_beside_the_resume_button_where_the_registry_has_the_session(
    worked_example: Path, transcript: Path, registry: Path
) -> None:
    """session-page-copies-the-session-id: no entry for the session, no name; an entry for another
    session, or one half written, names nothing; of two entries for this session, the one updated
    last names it, beside the copy-resume button."""
    name = lambda: view_of(worked_example, transcript).session.name
    assert name() == ""
    register(registry, 101, "11111111-2222-3333-4444-555555555555", "agents-12", updated=3)
    (registry / "102.json").write_text('{"sessionId": ')
    assert name() == ""
    register(registry, 103, SESSION, "agents-9", updated=1)
    register(registry, 104, SESSION, "agents-10", updated=2)
    assert name() == "agents-10"
    shown = elements(render_session(worked_example, transcript, now=NOW), "resume|session-name")
    assert text_of(shown["session-name"]) == "agents-10" and "resume" in shown, "the page shows the name the view holds"



@settings(deadline=None)
@given(linked=st.lists(st.lists(st.sampled_from(sorted(POOL)), max_size=4, unique=True), min_size=1, max_size=5))
def test_the_column_lists_each_turns_artefacts_and_never_a_ticket_file(
    linked: list[list[str]], scratch: Callable[[], Path], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """session-pages-feed-the-hub#P2, over sessions whose turns link artefacts, ticket files and
    paths that only look like one: each turn's artefacts, in the order its record gives them, under
    that turn's number, newest turn first, and nothing else; a turn that links none has its row."""
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
        expected.append((f"{number:02d}", listed))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(home))
        page, rendered = view_of(directory, transcript), render_session(directory, transcript, now=NOW)
    assert column_of(page) == expected
    targets = {target for _, items in expected for _, target in items}
    assert marked(rendered) == targets, "a ticket file carries the attribute the hub marks by"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
