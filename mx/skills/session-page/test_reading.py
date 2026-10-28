# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "hypothesis", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""How the renderer reads what a page is made of: which of the user's messages a turn carries,
where a record's links point, and what it refuses. Run: uv run test_reading.py

The seam is test_session_page.py's, the page as the values `render_session` formats, over its
worked example (conftest.py); what a record's prose renders to is read off the page. The oracle for
the pairing is the Decision on the turn record (a record carries the user's messages said after the
record before it was written and before it was) and the prototype's sample, which holds, per
record, the messages that turn answered.
"""

import html
import json
import os
import re
import shutil
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

import session_page
from session_page import Chat, RecordError, chat_path, chat_record, read_chat, read_turn, render_session
from session_checks import SESSION, SPOKEN_AFTER, followed, messages_of, project_of, rows_of, sections_of, text_of, view_of

NOW = datetime(2026, 9, 23, 2, 30)

# The start of what the user said in each turn of the prototype's sample, `sample/turns/NN.you.md`.
SAMPLE = {
    "01": ["i feel like we need like a leading word"],
    "02": ["/mx:show this is slightly meta now"],
    "03": ["okay so i like the grid you showed"],
    "04": ["okay okay i like it.", "hey can you please disregard"],
}


def with_calls(transcript: Path, directory: Path, out: Path, calls: list[tuple[str, int, str]]) -> Path:
    """The transcript with a tool call per (tool, record, time) added, on that record's path."""
    lines = transcript.read_text().splitlines()
    for tool, number, at in calls:
        call = {"type": "tool_use", "name": tool,
                "input": {"file_path": f"/elsewhere/agent/sessions/{directory.name}/turns/{number:02d}.md"}}
        lines.append(json.dumps({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [call]}}))
    out.write_text("\n".join(lines) + "\n")
    return out


def written(calls: dict[int, str]) -> list[tuple[str, int, str]]:
    return [("Write", number, at) for number, at in calls.items()]


def test_a_turn_carries_what_the_user_said_since_the_record_before_it(worked_example: Path, transcript: Path) -> None:
    """session-page#P2, which turn a message reaches. The six prompts of the worked example against
    the Write calls of its four records: the first prompt's resubmission stands for it, the slash
    command reads as typed, the queued message joins the turn it was queued in."""
    said = messages_of(view_of(worked_example, transcript))
    assert {key: [m[: len(s)] for m, s in zip(said[key], start)] for key, start in SAMPLE.items()} == SAMPLE
    assert {key: len(m) for key, m in said.items()} == {key: len(start) for key, start in SAMPLE.items()}


def test_a_message_said_after_the_newest_record_is_on_no_turn_yet(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """Record 4 written before the last prompt: that prompt reaches no turn."""
    early = written({4: "2026-09-23T00:40:00Z"})
    said = messages_of(view_of(worked_example, with_calls(transcript, worked_example, tmp_path / "t.jsonl", early)))
    assert [m[:20] for m in said["04"]] == ["okay okay i like it."]
    assert [m for messages in said.values() for m in messages if "hey can you please" in m] == []


def test_reading_or_fixing_an_older_record_leaves_its_messages_where_they_were(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """A later turn reads record 2 for its question tags and edits record 3 when it is sent back:
    neither moves when those records were written."""
    later = [("Read", 2, "2026-09-23T01:40:00Z"), ("Edit", 3, "2026-09-23T01:41:00Z")]
    t = with_calls(transcript, worked_example, tmp_path / "t.jsonl", later)
    said = messages_of(view_of(worked_example, t))
    assert {key: [m[: len(s)] for m, s in zip(said[key], start)] for key, start in SAMPLE.items()} == SAMPLE


def test_a_record_the_transcript_shows_no_write_for_carries_no_message_and_says_so(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """Record 3's Write call gone, as from a session whose record was written some other way: turn
    3 pairs no message and says why, and what the user said in it reaches the next written record,
    whatever the file's own modification time says."""
    unwritten = tmp_path / "t.jsonl"
    unwritten.write_text("".join(line for line in transcript.read_text().splitlines(keepends=True) if "/turns/03.md" not in line))
    rows = rows_of(view_of(worked_example, unwritten))
    assert rows["03"].turn.messages == () and rows["03"].silence == "unwritten"
    dates = {key: row.when for key, row in rows.items()}
    assert dates["03"] == "2026-09-23"  # session-page-turns-decluttered: the record's date alone
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", d) for key, d in dates.items() if key != "03")
    said = rows["04"].turn.messages
    assert [m[: len(s)] for m, s in zip(said, SAMPLE["03"] + SAMPLE["04"])] == SAMPLE["03"] + SAMPLE["04"]
    assert len(said) == len(SAMPLE["03"] + SAMPLE["04"])


@pytest.fixture
def new_york(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The local clock four hours behind UTC, where the worked example's 2026-09-23 00:20Z is still
    the evening of the 22nd."""
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_a_turns_date_and_the_pages_span_come_from_the_clock_its_time_does(
    new_york: None, worked_example: Path, transcript: Path
) -> None:
    """session-page-turns-decluttered: record 3 says 2026-09-23 and was written at 00:20Z, which is
    20:20 on the 22nd in New York; its row and the header's span both read the 22nd."""
    page = view_of(worked_example, transcript)
    assert {key: row.when for key, row in rows_of(page).items()} == {
        "01": "2026-09-22 17:00", "02": "2026-09-22 17:40", "03": "2026-09-22 20:20", "04": "2026-09-22 21:30"}
    assert page.span == "2026-09-22"


def test_a_message_another_session_sent_is_on_its_turn_under_that_sessions_name(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """session-page-pairs-only-the-users-messages: another session's message, wrapped as Claude
    Code wraps one, delivered in turn 3 as the meta user entry Claude Code writes for a message that
    starts a turn, carrying two, one from a sender that gives no `from-name`, and mid-turn in turn 4
    as a queued command. Each is on the turn it arrived in, under its sender's `from-name`, and on no
    turn as the user's; the user's own messages pair as before."""
    peer = ('<cross-session-message from="uds:/run/user/1000/cc-socks/2118235.sock" from-name="agents-d2"'
            ' from-mode="prompting">\n{}\n</cross-session-message>')
    entries = [
        {"type": "attachment", "timestamp": "2026-09-23T01:05:00.000Z",
         "attachment": {"type": "queued_command", "prompt": peer.format("ruled good to ship, dispatch both")}},
        {"type": "user", "isMeta": True, "origin": {"kind": "peer", "name": "agents-d2"}, "timestamp": "2026-09-23T00:10:00.000Z",
         "message": {"role": "user", "content": [
             {"type": "text", "text": "Another Claude session sent a message:\n" + peer.format("merged, the tree is yours")},
             {"type": "text", "text": '<cross-session-message from="uds:/run/user/1000/cc-socks/77.sock">\nme too\n</cross-session-message>'}]}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text(transcript.read_text() + "".join(json.dumps(e) + "\n" for e in entries))
    page = view_of(worked_example, t)
    assert {row.key: [(s.name, s.text) for s in row.turn.sent] for row in page.rows if row.turn.sent} == {
        "03": [("agents-d2", "merged, the tree is yours"), ("another session", "me too")], "04": [("agents-d2", "ruled good to ship, dispatch both")]}
    said = messages_of(page)
    assert {key: [m[: len(s)] for m, s in zip(said[key], start)] for key, start in SAMPLE.items()} == SAMPLE
    assert {key: len(m) for key, m in said.items()} == {key: len(start) for key, start in SAMPLE.items()}


def test_the_same_short_answer_in_two_turns_is_on_both(tmp_path: Path, worked_example: Path) -> None:
    """A prompt the next one starts with collapses only as a resubmission within one turn."""
    entries = [
        {"type": "user", "timestamp": "2026-09-22T21:00:00Z", "message": {"role": "user", "content": "yes"}},
        {"type": "user", "timestamp": "2026-09-22T21:30:00Z", "message": {"role": "user", "content": "yes"}},
        {"type": "user", "timestamp": "2026-09-22T22:00:00Z", "message": {"role": "user", "content": "yes, and split it"}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(map(json.dumps, entries)) + "\n")
    calls = written({1: "2026-09-22T21:10:00Z", 2: "2026-09-22T21:40:00Z", 3: "2026-09-22T22:10:00Z", 4: "2026-09-22T22:20:00Z"})
    said = messages_of(view_of(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls)))
    assert (said["01"], said["02"], said["03"]) == (["yes"], ["yes"], ["yes, and split it"])


def test_a_short_answer_the_next_message_happens_to_start_with_is_its_own_message(tmp_path: Path, worked_example: Path) -> None:
    """Only a resubmission collapses: the user answers `a`, then queues a message that starts with
    the same letter, and the turn carries both."""
    entries = [
        {"type": "user", "timestamp": "2026-09-22T21:00:00Z", "message": {"role": "user", "content": "a"}},
        {"type": "attachment", "timestamp": "2026-09-22T21:05:00Z",
         "attachment": {"type": "queued_command", "prompt": "also, keep the second bank"}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(map(json.dumps, entries)) + "\n")
    calls = written({1: "2026-09-22T21:10:00Z", 2: "2026-09-22T21:40:00Z", 3: "2026-09-22T22:10:00Z", 4: "2026-09-22T22:20:00Z"})
    said = messages_of(view_of(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls)))
    assert said["01"] == ["a", "also, keep the second bank"]


def test_a_prompt_resubmitted_with_more_after_a_comma_is_shown_once(tmp_path: Path, worked_example: Path) -> None:
    """The fixture README's resubmission, with the text going on past a comma rather than a line
    break: the turn carries the longer prompt alone."""
    entries = [
        {"type": "user", "timestamp": "2026-09-22T21:00:00Z", "message": {"role": "user", "content": "fix the header"}},
        {"type": "user", "timestamp": "2026-09-22T21:01:00Z", "message": {"role": "user", "content": "fix the header, and the footer"}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(map(json.dumps, entries)) + "\n")
    calls = written({1: "2026-09-22T21:10:00Z", 2: "2026-09-22T21:40:00Z", 3: "2026-09-22T22:10:00Z", 4: "2026-09-22T22:20:00Z"})
    said = messages_of(view_of(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls)))
    assert said["01"] == ["fix the header, and the footer"]


def test_a_command_claude_code_runs_itself_is_nothing_the_user_said(tmp_path: Path, worked_example: Path) -> None:
    """A local command (/reload-plugins, as the container hub types it into an idle session) reaches
    no model, so no turn carries it; a slash command that prompts the model reads as typed. The two
    as Claude Code 2.1.302 writes them: the local one's output under it, the skill's body under the
    other."""
    command = lambda uuid, name, args, at: {
        "type": "user", "uuid": uuid, "timestamp": at, "message": {"role": "user", "content":
            f"<command-name>{name}</command-name>\n<command-message>{name[1:]}</command-message>\n<command-args>{args}</command-args>"}}
    entries = [
        {"type": "user", "uuid": "u1", "timestamp": "2026-09-22T21:00:00Z", "message": {"role": "user", "content": "fix the header"}},
        command("u2", "/reload-plugins", "", "2026-09-22T21:01:00Z"),
        {"type": "system", "subtype": "local_command", "parentUuid": "u2", "timestamp": "2026-09-22T21:01:00Z",
         "content": "<local-command-stdout>Reloaded: 2 plugins</local-command-stdout>"},
        command("u3", "/mx:show", "the grid", "2026-09-22T21:02:00Z"),
        {"type": "user", "uuid": "u4", "parentUuid": "u3", "isMeta": True, "timestamp": "2026-09-22T21:02:00Z",
         "message": {"role": "user", "content": [{"type": "text", "text": "Base directory for this skill: /mx/skills/show"}]}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(map(json.dumps, entries)) + "\n")
    calls = written({1: "2026-09-22T21:10:00Z", 2: "2026-09-22T21:40:00Z", 3: "2026-09-22T22:10:00Z", 4: "2026-09-22T22:20:00Z"})
    said = messages_of(view_of(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls)))
    assert said["01"] == ["fix the header", "/mx:show the grid"]


def test_a_write_to_another_directorys_turn_record_moves_none_of_this_sessions(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """A record is this session's only under this session's directory: a write to the prototype's
    sample `turns/04.md`, before the last prompt, leaves turn 4's messages where they were."""
    call = {"type": "tool_use", "name": "Write", "input": {"file_path": "/elsewhere/agent/prototypes/session-page/sample/turns/04.md"}}
    t = tmp_path / "t.jsonl"
    t.write_text(transcript.read_text() + json.dumps(
        {"type": "assistant", "timestamp": "2026-09-23T00:30:00Z", "message": {"role": "assistant", "content": [call]}}) + "\n")
    said = messages_of(view_of(worked_example, t))
    assert {key: [m[: len(s)] for m, s in zip(said[key], start)] for key, start in SAMPLE.items()} == SAMPLE
    assert {key: len(m) for key, m in said.items()} == {key: len(start) for key, start in SAMPLE.items()}


def test_a_link_in_the_details_is_a_path_from_the_repo_root_too(worked_example: Path, transcript: Path, tmp_path: Path) -> None:
    """The Decision resolves every link a record writes, the ones in its prose as well as its
    Links: followed, it lands on the path the record wrote, in a tab of
    its own. A link to a part of the page stays on the page. Pins the format: the links are in the
    record's prose, which reaches the page as markup. A path markdown would have to encode, and the
    section of the page it names, reach the link as written."""
    (worked_example / "turns" / "05.md").write_text(
        "---\ndate: 2026-09-24\n---\n\n# Round 4\n\n## Details\n\n"
        "The [second bank](<agent/show/ledger/zwei Bänke.html#bank-2>) is drawn, and [Q7](#q7) still waits.\n")
    section = sections_of(render_session(worked_example, transcript, now=NOW))["05"]
    ((href, target),) = re.findall(r'<a href="([^"#][^"]*)"[^>]*?target="([^"]+)"', section)
    assert href == (tmp_path / "agent/show/ledger/zwei Bänke.html").as_uri() + "#bank-2"
    assert target == "_blank"
    assert '<a href="#q7">Q7</a>' in section


def test_a_link_is_a_path_from_the_repo_root(worked_example: Path, transcript: Path, tmp_path: Path) -> None:
    """Each link on the page lands on the path the record wrote, from the root of the repo whose
    agent repo the session directory names, wherever the directory sits: the worked example's
    project, `tmp_path`."""
    root = tmp_path
    hrefs = [link.href for row in view_of(worked_example, transcript).rows for link in row.links]
    landed = [followed(href).relative_to(root).as_posix() for href in hrefs]
    records = sorted((worked_example / "turns").glob("*.md"), reverse=True)
    assert landed == re.findall(r"\]\(([^)]+)\)", "".join(p.read_text() for p in records))


def test_a_link_to_an_artifact_in_another_repo_is_its_absolute_path(
    worked_example: Path, transcript: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An artifact another repo holds is linked by its absolute path, or its path under `~`, which
    reads the same wherever the session directory sits; a path that climbs out of the repo root
    does not."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    record = worked_example / "turns" / "05.md"
    record.write_text(
        "---\ndate: 2026-09-24\n---\n\n# Round 4\n\n## Links\n\n"
        "- [The mail design](/srv/jarvis/agent/show/mail/index.html): the figures\n"
        "- [The tree](~/jarvis/agent/show/tree.html): the other one\n")
    assert [link.href for link in rows_of(view_of(worked_example, transcript))["05"].links] == [
        "file:///srv/jarvis/agent/show/mail/index.html", (home / "jarvis/agent/show/tree.html").as_uri()]
    record.write_text("---\ndate: 2026-09-24\n---\n\n# Round 4\n\n## Links\n\n- [Up](../elsewhere.html): out\n")
    with pytest.raises(RecordError, match=re.escape("../elsewhere.html is neither a path from the repo root")):
        render_session(worked_example, transcript, now=NOW)


def test_a_record_shows_what_it_says_and_marks_up_nothing_of_its_own(worked_example: Path, transcript: Path) -> None:
    """An answer of `no` is the word, a list straight under a sentence is a list, and HTML in the
    prose is text: the page's structure is the renderer's alone."""
    (worked_example / "turns" / "05.md").write_text(
        "---\ndate: 2026-09-24\nanswered:\n  Q7: no\n---\n\n# Round 4\n\n## Details\n\n"
        "The page now:\n- opens <details> in prose\n- lists\n")
    section = sections_of(render_session(worked_example, transcript, now=NOW))["05"]
    assert "your answers Q7 no" in text_of(section)
    assert "<li>opens &lt;details&gt; in prose</li>" in section


@pytest.mark.parametrize("frontmatter, line, reason", [
    ("answered:\n  Q9: a", 4, "Q9 is not a question of an earlier turn"),
    ("answered:\n  Q1: b", 4, "Q1 was already answered in turn 03"),
    ("superseded:\n  Q7: Q8", 4, "names Q8, which no turn asks"),
    ("asked: Q7", 3, "unknown frontmatter field 'asked'"),
])
def test_a_record_that_clears_a_question_it_cannot_is_refused_at_its_line(
    worked_example: Path, transcript: Path, frontmatter: str, line: int, reason: str
) -> None:
    record = worked_example / "turns" / "05.md"
    record.write_text(f"---\ndate: 2026-09-24\n{frontmatter}\n---\n\n# Round 4\n")
    with pytest.raises(RecordError, match=re.escape(reason)) as refused:
        render_session(worked_example, transcript, now=NOW)
    assert str(refused.value).startswith(f"{record}:{line}: ")


def test_a_block_under_a_question_after_its_options_is_refused_and_told_where_it_goes(tmp_path: Path) -> None:
    """session-page-question-continuation-lands-on-last-option: a draft quoted at the question's
    indent after its options once rendered inside the last option; it is refused, pointing at
    Details, while a line wrapped deeper than an option's `-` still continues that option."""
    record = tmp_path / "07.md"
    question = ("---\ndate: 2026-10-23\n---\n\n# Thomas's roles comment\n\n## Questions\n\n"
                "- [Q20] **Post this reply on Thomas's roles comment?**\n"
                "  - (a) As written below. *my pick*\n  - (b) With your\n    changes.\n")
    record.write_text(question)
    assert [o.text for o in read_turn(record).questions[0].options] == ["As written below.", "With your changes."]
    record.write_text(f"{question}\n  > Done across the stack.\n")
    with pytest.raises(RecordError, match=re.escape("goes in ## Details, which the question links as [text](#t07)")) as refused:
        read_turn(record)
    assert str(refused.value).startswith(f"{record}:14: text under Q20 after its sub-items")


# A chat turn's record of any reply. A carriage return is left out: reading a file turns one into a
# line break, so a reply carrying one reads back with a line break in its place.
REPLIES = st.text(st.characters(blacklist_characters="\r", blacklist_categories=("Cs",))).filter(str.strip)


@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(reply=REPLIES)
def test_a_chat_turns_record_reads_back_as_the_reply_it_was_written_from(reply: str, tmp_path: Path) -> None:
    """chat-replies-reach-the-page: the record's body is the reply as it stood, whatever it holds,
    headings, frontmatter fences and markdown included, and its time is the one it was written at."""
    at = datetime(2026, 10, 5, 14, 2, tzinfo=UTC)
    record = chat_path(tmp_path, at)
    record.write_text(chat_record(reply, at))
    assert record.name == "chat-20261005T140200Z.md"
    assert read_chat(record) == Chat(record, "2026-10-05", reply.strip(), at)


def test_a_chat_turn_sits_among_the_records_by_its_time_and_carries_what_was_said_before_it(
    worked_example: Path, transcript: Path
) -> None:
    """chat-replies-reach-the-page's D1: a chat turn written between records 03 and 04 shows between
    them, and the user's message said before it is its own, not 04's."""
    at = datetime(2026, 9, 23, 0, 40, tzinfo=UTC)  # after record 03's write, before 04's and before the second message of SAMPLE["04"]
    chat = chat_path(worked_example / "turns", at)
    chat.write_text(chat_record("Yes, keep the grid.", at))
    said = messages_of(view_of(worked_example, transcript))
    assert list(said) == ["04", chat.stem, "03", "02", "01"]
    assert said[chat.stem][0].startswith(SAMPLE["04"][0])
    assert [m[:len(SAMPLE["04"][1])] for m in said["04"]] == SAMPLE["04"][1:]


@pytest.mark.parametrize("frontmatter, line, reason", [
    ("chat: yesterday", 3, "chat: 'yesterday' is not a time with its zone"),
    ("chat: 2026-10-05T14:02:00", 3, "is not a time with its zone"),
    ("chat: 2026-10-05T14:02:00+00:00\nanswered:\n  Q7: a", 4, "unknown frontmatter field 'answered'"),
])
def test_a_chat_turns_record_that_does_not_read_is_refused_at_its_line(
    worked_example: Path, transcript: Path, frontmatter: str, line: int, reason: str
) -> None:
    record = worked_example / "turns" / "chat-20261005T140200Z.md"
    record.write_text(f"---\ndate: 2026-10-05\n{frontmatter}\n---\n\nYes, the second bank.\n")
    with pytest.raises(RecordError, match=re.escape(reason)) as refused:
        render_session(worked_example, transcript, now=NOW)
    assert str(refused.value).startswith(f"{record}:{line}: ")


# ---- a page with no session.md ----------------------------------------------

FRESH = "8e0f1c22-0000-0000-0000-000000000000"
STARTED = {"type": "user", "message": {"role": "user", "content": "Carry on from the handoff."},
           "timestamp": "2026-10-05T09:00:00.000Z", "cwd": "/srv/help line", "sessionId": FRESH}
AI_TITLE = {"type": "ai-title", "aiTitle": "Helferline <handoff> continued", "sessionId": FRESH}
RENAMED = {"type": "custom-title", "customTitle": "helferline: lost page", "sessionId": FRESH}
# Each is what the transcript holds besides the first prompt, and the title the page shows: a
# `/rename` over Claude Code's own title, whichever came later, the last of each kind, and the
# session id's first eight where it has neither.
TITLES = {
    "Claude Code's own title": ([AI_TITLE], "Helferline <handoff> continued"),
    "a rename before a newer title of its own": ([RENAMED, AI_TITLE | {"aiTitle": "Something newer"}], "helferline: lost page"),
    "the last of two renames": ([RENAMED, RENAMED | {"customTitle": "helferline: found"}], "helferline: found"),
    "no title yet": ([], "session 8e0f1c22"),
}


@pytest.mark.parametrize("entries, title", TITLES.values(), ids=TITLES)
def test_a_session_with_only_chat_turns_and_no_session_record_renders_under_claude_codes_title(
    entries: list[dict], title: str, tmp_path: Path,
) -> None:
    """every-session-gets-a-page#P5: no session.md and no numbered record, one chat turn, and the
    page renders it, titled as the hub's rail titles the session, with a resume command that
    changes to the directory the session started in."""
    directory = tmp_path / "agent" / "sessions" / FRESH
    at = datetime(2026, 10, 5, 9, 1, tzinfo=UTC)
    chat = chat_path(directory / "turns", at)
    chat.parent.mkdir(parents=True)
    chat.write_text(chat_record("On it: reading the handoff.", at))
    said = tmp_path / "t.jsonl"
    said.write_text("".join(json.dumps(e) + "\n" for e in [STARTED, *entries]))
    page = view_of(directory, said)
    assert page.session.title == title
    assert [row.key for row in page.rows] == [chat.stem]
    assert page.resume == f"cd '/srv/help line' && claude --resume {FRESH}"
    rendered = render_session(directory, said, now=NOW)
    assert " 1 turn · 2026-10-05 · " in text_of(rendered)
    # a title Claude Code gave is text, whatever it holds, in the tab and as the page's heading
    assert html.unescape(re.search(r"<title>(.*?) · session page</title>", rendered).group(1)) == title
    assert html.unescape(re.search(r'<h1 class="v-title">(.*?)</h1>', rendered).group(1)) == title


def test_a_run_of_turns_with_no_message_before_them_says_so_once_above_its_newest(tmp_path: Path) -> None:
    """session-page-turns-decluttered: the first chat turn answers the prompt, the two after it have
    no message before them and form a run, whose newest alone carries the hint; each row shows its
    time to the minute."""
    directory = tmp_path / "agent" / "sessions" / FRESH
    (directory / "turns").mkdir(parents=True)
    times = [datetime(2026, 10, 5, 9, m, tzinfo=UTC) for m in (1, 5)] + [datetime(2026, 10, 5, 23, 59, tzinfo=UTC)]
    for at in times:
        chat_path(directory / "turns", at).write_text(chat_record("Still building.", at))
    said = tmp_path / "t.jsonl"
    said.write_text(json.dumps(STARTED) + "\n")
    rows = view_of(directory, said).rows
    assert [row.key for row in rows] == [chat_path(directory / "turns", at).stem for at in reversed(times)]
    assert [row.silence for row in rows] == ["unanswered", "", ""]
    assert [row.when for row in rows] == [f"{at.astimezone():%Y-%m-%d %H:%M}" for at in reversed(times)]


def test_each_run_of_turns_with_no_message_before_them_says_so_once(tmp_path: Path) -> None:
    """session-page-turns-decluttered: two runs, each broken by a message of the user's, and the
    newest turn of each carries the hint."""
    directory = tmp_path / "agent" / "sessions" / FRESH
    (directory / "turns").mkdir(parents=True)
    for minute in (1, 5, 11, 15):
        at = datetime(2026, 10, 5, 9, minute, tzinfo=UTC)
        chat_path(directory / "turns", at).write_text(chat_record("Still building.", at))
    asked = {"type": "user", "message": {"role": "user", "content": "How far along?"}, "timestamp": "2026-10-05T09:10:00.000Z"}
    said = tmp_path / "t.jsonl"
    said.write_text(json.dumps(STARTED) + "\n" + json.dumps(asked) + "\n")
    assert [row.silence for row in view_of(directory, said).rows] == ["unanswered", "", "unanswered", ""]


def test_a_session_whose_transcript_names_no_directory_resumes_from_the_repo_root(tmp_path: Path) -> None:
    """With no session.md and no `cwd` in the transcript, the resume command changes to the root of
    the repo the session's directory is in."""
    directory = tmp_path / "agent" / "sessions" / FRESH
    at = datetime(2026, 10, 5, 9, 1, tzinfo=UTC)
    chat = chat_path(directory / "turns", at)
    chat.parent.mkdir(parents=True)
    chat.write_text(chat_record("On it.", at))
    said = tmp_path / "t.jsonl"
    said.write_text(json.dumps({k: v for k, v in STARTED.items() if k != "cwd"}) + "\n")
    assert view_of(directory, said).resume == f"cd {tmp_path} && claude --resume {FRESH}"


def test_a_session_record_with_no_turn_yet_renders_its_title_and_no_turn(worked_example: Path, transcript: Path) -> None:
    """every-session-gets-a-page#P5's other half: session.md written and the turn ended on no text,
    so neither a numbered record nor a chat turn exists, and the page still renders."""
    for record in (worked_example / "turns").iterdir():
        record.unlink()
    page = view_of(worked_example, transcript)
    assert "Leading words for showing" in page.session.title
    assert page.rows == ()
    assert " 0 turns · rendered " in text_of(render_session(worked_example, transcript, now=NOW))


def test_a_session_record_of_its_h1_alone_reads_as_one_with_frontmatter(worked_example: Path, transcript: Path) -> None:
    """session-page-says-where-the-next-record-goes#P2: the worked example's frontmatter names what
    the reader works out without it."""
    described = worked_example / "session.md"
    before = view_of(worked_example, transcript)
    described.write_text(described.read_text().split("---\n", 2)[2])
    after = view_of(worked_example, transcript)
    assert (after.session.title, after.session.id, after.session.repo, after.resume) == (
        before.session.title, before.session.id, before.session.repo, before.resume)


AT = datetime(2026, 10, 5, 9, 1, tzinfo=UTC)
# How each row changes the worked example's four records and session.md, and the line it then
# prints under the directory.
NEXT = {
    "no records yet": (shutil.rmtree, "01.md · 0 written · session.md not yet written"),
    "a gap and a chat turn": (lambda d: ((d / "turns/04.md").rename(d / "turns/06.md"),
                                         chat_path(d / "turns", AT).write_text(chat_record("On it.", AT))),
                              "07.md · 4 written · session.md written"),
    "a record that does not parse": (lambda d: (d / "turns/04.md").write_text("no frontmatter\n"),
                                     "05.md · 4 written · session.md written"),
}


@pytest.mark.parametrize("made, said", NEXT.values(), ids=NEXT)
def test_session_page_prints_where_the_next_record_goes(
    made: Callable[[Path], object], said: str, worked_example: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """session-page-says-where-the-next-record-goes#P1 and #P3; `main` returning is the exit status 0."""
    project = project_of(worked_example)
    made(worked_example)
    monkeypatch.chdir(project)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    monkeypatch.setattr(sys, "argv", ["session-page"])
    session_page.main()
    assert capsys.readouterr().out == f"{worked_example}\nnext record: {worked_example / 'turns'}/{said}\n"


def test_the_turns_carry_no_heading_and_the_column_heading_no_rule(worked_example: Path, transcript: Path) -> None:
    """Pins the format: the turns open on the first turn, and the timeline's heading is the column's
    first element."""
    page = render_session(worked_example, transcript, now=NOW)
    turns = re.search(r'<section class="turns"[^>]*>(.*?)<(?:details|article)', page, re.S).group(1)
    assert turns.strip() == ""
    assert re.search(r'<aside class="column"[^>]*>\s*<div class="column-head"><h2 class="v-meta" id="column-title">timeline</h2>', page)


def did(at: str, *blocks: dict) -> str:
    """An assistant entry at `at` holding `blocks`, as a transcript line."""
    return json.dumps({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": list(blocks)}})


def call(name: str, id: str, **input: object) -> dict:
    return {"type": "tool_use", "id": id, "name": name, "input": input}


def came_back(at: str, id: str, content: object, error: bool = False) -> str:
    """The user entry carrying a tool call's result, as a transcript line."""
    result = {"type": "tool_result", "tool_use_id": id, "content": content, "is_error": error}
    return json.dumps({"type": "user", "timestamp": at, "message": {"role": "user", "content": [result]}})


def with_work(transcript: Path, out: Path, *lines: str) -> Path:
    out.write_text(transcript.read_text() + "".join(line + "\n" for line in lines))
    return out


def test_a_turns_tool_calls_run_from_its_first_message_to_the_next_turns(worked_example: Path, transcript: Path, tmp_path: Path) -> None:
    """show-a-turns-tool-calls-on-demand: a call belongs to the turn whose messages it follows, as the
    page pairs them, up to the next turn's first message. A call after record 01 was written and
    before turn 02's first prompt (21:25:49) is still turn 01's work; one before every prompt is the
    first turn's too. Each comes with its result and how it ended. The worked example's own calls
    are the Write of each record."""
    worked = with_work(
        transcript, tmp_path / "t.jsonl",
        did("2026-09-22T20:30:00Z", call("Read", "r0", file_path="/repo/AGENTS.md")),
        did("2026-09-22T21:10:00Z", call("Bash", "b1", command="make test", description="Run the suite")),
        came_back("2026-09-22T21:10:30Z", "b1", "2 failed", error=True),
        did("2026-09-22T21:30:00Z", call("Agent", "a2", description="Build the grid figure", prompt="...")),
        came_back("2026-09-22T21:35:00Z", "a2", [{"type": "text", "text": "the figure is at show/grid.html"}]),
        did("2026-09-23T01:25:00Z", call("Edit", "e4", file_path="/repo/page.css", old_string="a", new_string="b")),
    )
    log = session_page.read_session(worked_example, worked).log
    assert {key: [s.tool for s in steps] for key, steps in log.items()} == {
        "t01": ["Read", "Write", "Bash"], "t02": ["Agent", "Write"], "t03": ["Write"], "t04": ["Edit", "Write"]}
    bash = log["t01"][2]
    assert (bash.output, bash.failed, bash.done) == ("2 failed", True, datetime(2026, 9, 22, 21, 10, 30, tzinfo=UTC))
    assert log["t02"][0].output == "the figure is at show/grid.html"
    assert log["t04"][0].done is None, "a call whose result never came back"


def test_thinking_is_a_step_only_where_the_transcript_kept_its_text(worked_example: Path, transcript: Path, tmp_path: Path) -> None:
    """Claude Code stores thinking redacted: a block with no text is no step, one with text is."""
    worked = with_work(
        transcript, tmp_path / "t.jsonl",
        did("2026-09-22T22:05:00Z", {"type": "thinking", "thinking": "", "signature": "x"}),
        did("2026-09-22T22:06:00Z", {"type": "thinking", "thinking": "The grid wants a leading word.", "signature": "x"}),
    )
    [thought, _] = session_page.read_session(worked_example, worked).log["t03"]  # and the Write of record 03
    assert (thought.tool, thought.output) == ("", "The grid wants a leading word.")


def test_work_after_a_message_no_record_answers_yet_is_on_no_turn(worked_example: Path, transcript: Path, tmp_path: Path) -> None:
    """As the message said after the newest record is on no turn until a later record is written,
    so is the work done for it: turn 04 keeps what it did before that message and nothing after."""
    worked = with_work(
        transcript, tmp_path / "t.jsonl",
        did("2026-09-23T01:31:00Z", call("Bash", "b4", command="git status")),
        json.dumps(SPOKEN_AFTER),
        did("2026-09-23T01:40:00Z", call("Bash", "b5", command="make test")),
    )
    assert [s.input.get("command") for s in session_page.read_session(worked_example, worked).log["t04"] if s.tool == "Bash"] == ["git status"]


@pytest.mark.parametrize(("tool", "input", "line"), [
    ("Bash", {"command": "make test\nmake check", "description": "Run the suite"}, ("ran", "Run the suite")),
    ("Bash", {"command": "make test\nmake check"}, ("ran", "make test")),
    ("Read", {"file_path": "/repo/page.js", "offset": 10}, ("read", "/repo/page.js")),
    ("Agent", {"description": "Build the figure", "prompt": "A long brief"}, ("subagent", "Build the figure")),
    ("mcp__browser__navigate", {"url": "https://example.org"}, ("navigate", "https://example.org")),
])
def test_a_steps_line_names_what_it_acted_on(tool: str, input: dict, line: tuple[str, str]) -> None:
    """The ticket's one-line summary: a Bash call's description or command, a file's path, a
    subagent's description."""
    assert session_page.summary(session_page.Step(datetime(2026, 9, 22, tzinfo=UTC), tool, input)) == line


# ---- the sessions a handoff links ------------------------------------------

# A chain of sessions, each picking up the one before's continuation handoff, and one more that
# picked up the first's under another account: the first is continued twice, in two places.
CHAIN = [f"00000000-0000-0000-0000-{n:012d}" for n in range(1, 25)]
SPLIT = "0a0b0c0d-0000-0000-0000-000000000000"


@pytest.fixture
def chain(registry: Path, tmp_path: Path) -> dict[str, Path]:
    """The directory of each session of `CHAIN` and `SPLIT`, each with a page and a `previous`
    naming the session it continued, by id."""
    directories = {s: session_page.pages_directory(registry.parent, s) for s in CHAIN}
    directories[SPLIT] = session_page.pages_directory(tmp_path / ".claude-other", SPLIT)
    for session, previous in [*zip(CHAIN, [None, *CHAIN]), (SPLIT, CHAIN[0])]:
        directories[session].mkdir(parents=True)
        (directories[session] / session_page.PAGE).write_text("<html></html>")
        if previous:
            (directories[session] / session_page.PREVIOUS).write_text(previous + "\n")
    (tmp_path / "t.jsonl").write_text("")
    return directories


def handoffs_of(chain: dict[str, Path], transcript: Path) -> dict[str, tuple[str, tuple[str, ...]]]:
    """What each session's page links across a handoff: the session before it, and those after."""
    return {s: (r.previous, r.following) for s, d in chain.items() for r in [session_page.read_session(d, transcript)]}


@pytest.fixture
def settled(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clock an hour on, so every file the check wrote reads as one written long before."""
    later = time.time_ns() + 3600 * 10**9
    monkeypatch.setattr(session_page, "time_ns", lambda: later)


OPENED: list[str] | None = None  # the files opened while a check counts them (`opened`)
HOOKED = False  # an audit hook, once added, stays for the life of the process


def count_opens(event: str, args: tuple) -> None:
    if OPENED is not None and event == "open" and isinstance(args[0], (str, os.PathLike)):
        OPENED.append(os.fspath(args[0]))


@pytest.fixture
def opened() -> Iterator[list[str]]:
    """Every file this process opens until the check ends, by path, however it opens it."""
    global OPENED, HOOKED
    if not HOOKED:
        sys.addaudithook(count_opens)
        HOOKED = True
    OPENED = []
    yield OPENED
    OPENED = None


def test_sessions_read_in_one_process_read_each_previous_once(
    chain: dict[str, Path], tmp_path: Path, settled: None, opened: list[str],
) -> None:
    """session-successors-read-once#P2: reading every session of the chain finds each one's
    continuations (P1) and opens each `previous` once, not once per session read."""
    assert handoffs_of(chain, tmp_path / "t.jsonl") == {
        CHAIN[0]: ("", tuple(sorted([CHAIN[1], SPLIT]))),
        **{s: (before, (after,)) for before, s, after in zip(CHAIN, CHAIN[1:], CHAIN[2:])},
        CHAIN[-1]: (CHAIN[-2], ()),
        SPLIT: (CHAIN[0], ()),
    }
    reads = Counter(p for p in opened if p.endswith(f"/{session_page.PREVIOUS}"))
    assert set(reads.values()) == {1} and len(reads) == len(chain) - 1


def rewritten(chain: dict[str, Path]) -> Path:
    """The `previous` of `CHAIN[5]` written over in place, naming `CHAIN[1]` where it named
    `CHAIN[4]`: the same file, the same length."""
    moved = chain[CHAIN[5]] / session_page.PREVIOUS
    with moved.open("r+") as f:
        f.write(CHAIN[1])
    return moved


def moved_on(before: dict[str, tuple[str, tuple[str, ...]]]) -> dict[str, tuple[str, tuple[str, ...]]]:
    """What the pages link once `rewritten` has moved `CHAIN[5]` on from `CHAIN[4]` to `CHAIN[1]`."""
    return before | {CHAIN[1]: (CHAIN[0], (CHAIN[2], CHAIN[5])), CHAIN[4]: (CHAIN[3], ()), CHAIN[5]: (CHAIN[1], (CHAIN[6],))}


def test_a_previous_rewritten_in_place_long_after_it_was_read_is_read_anew(
    chain: dict[str, Path], tmp_path: Path, settled: None,
) -> None:
    """session-successors-read-once#P1: a `previous` written over an hour after the pages were read,
    which moves its modification time, names its new session on every page read after, the one it
    named before included."""
    said = tmp_path / "t.jsonl"
    before = handoffs_of(chain, said)
    moved = rewritten(chain)
    later = moved.stat().st_mtime_ns + 3600 * 10**9
    os.utime(moved, ns=(later, later))
    assert handoffs_of(chain, said) == moved_on(before)


def test_a_previous_rewritten_in_place_within_its_filesystems_clock_tick_is_read_anew(
    chain: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """session-successors-read-once#P1 where the rewrite leaves the file's size and times as they
    were, as a filesystem whose clock ticks coarsely does within one tick: the pages read after it
    still name the new session."""
    said = tmp_path / "t.jsonl"
    kept = (chain[CHAIN[5]] / session_page.PREVIOUS).stat()
    monkeypatch.setattr(session_page, "time_ns", lambda: kept.st_ctime_ns + 5 * 10**6)  # 5 ms on
    before = handoffs_of(chain, said)
    moved, stat = rewritten(chain), os.stat
    monkeypatch.setattr(os, "stat", lambda path, *a, **k: kept if os.fspath(path) == os.fspath(moved) else stat(path, *a, **k))
    assert handoffs_of(chain, said) == moved_on(before)

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
