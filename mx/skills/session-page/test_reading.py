# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "hypothesis", "pyyaml", "markdown-it-py"]
# ///
"""How the renderer reads what a page is made of: which of the user's messages a turn carries,
where a record's links point, and what it refuses. Run: uv run test_reading.py

The seam is test_session_page.py's, `render_session`, over its worked example (conftest.py). The
oracle for the pairing is the Decision on the turn record (a record carries the user's messages
said after the record before it was written and before it was) and the prototype's sample, which
holds, per record, the messages that turn answered.
"""

import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

from session_page import Chat, RecordError, chat_path, chat_record, read_chat, render_session
from test_session_page import sections_of

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


def messages_of(page: str) -> dict[str, list[str]]:
    """Each turn's messages from the user as the page shows them, by the two digits of its record."""
    return {key: [html_text(m) for you in re.findall(r'<details class="said you">(.*?)</details>', section, re.S)
                  for m in re.findall(r'<div class="msg">(.*?)</div>', you, re.S)]
            for key, section in sections_of(page).items()}


def sent_of(page: str) -> dict[str, list[tuple[str, str]]]:
    """Each turn's messages from other sessions as the page shows them: who, and what."""
    return {key: [(html_text(who), html_text(text)) for who, text in re.findall(
                r'<details class="said peer">.*?<span class="v-meta who">(.*?)</span>.*?<div class="msg">(.*?)</div>', section, re.S)]
            for key, section in sections_of(page).items()}


def html_text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).strip()


def written(calls: dict[int, str]) -> list[tuple[str, int, str]]:
    return [("Write", number, at) for number, at in calls.items()]


def test_a_turn_carries_what_the_user_said_since_the_record_before_it(worked_example: Path, transcript: Path) -> None:
    """session-page#P2, which turn a message reaches. The six prompts of the worked example against
    the Write calls of its four records: the first prompt's resubmission stands for it, the slash
    command reads as typed, the queued message joins the turn it was queued in."""
    shown = messages_of(render_session(worked_example, transcript, now=NOW))
    assert {key: [m[: len(s)] for m, s in zip(shown[key], said)] for key, said in SAMPLE.items()} == SAMPLE
    assert {key: len(m) for key, m in shown.items()} == {key: len(said) for key, said in SAMPLE.items()}


def test_a_message_said_after_the_newest_record_is_on_no_turn_yet(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """Record 4 written before the last prompt: that prompt reaches no turn."""
    early = written({4: "2026-09-23T00:40:00Z"})
    page = render_session(worked_example, with_calls(transcript, worked_example, tmp_path / "t.jsonl", early), now=NOW)
    assert [m[:20] for m in messages_of(page)["04"]] == ["okay okay i like it."]
    assert "hey can you please" not in page


def test_reading_or_fixing_an_older_record_leaves_its_messages_where_they_were(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """A later turn reads record 2 for its question tags and edits record 3 when it is sent back:
    neither moves when those records were written."""
    later = [("Read", 2, "2026-09-23T01:40:00Z"), ("Edit", 3, "2026-09-23T01:41:00Z")]
    t = with_calls(transcript, worked_example, tmp_path / "t.jsonl", later)
    shown = messages_of(render_session(worked_example, t, now=NOW))
    assert {key: [m[: len(s)] for m, s in zip(shown[key], said)] for key, said in SAMPLE.items()} == SAMPLE


def test_a_record_the_transcript_shows_no_write_for_carries_no_message_and_says_so(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """Record 3's Write call gone, as from a session whose record was written some other way: turn
    3 pairs no message and says why, and what the user said in it reaches the next written record,
    whatever the file's own modification time says."""
    unwritten = tmp_path / "t.jsonl"
    unwritten.write_text("".join(line for line in transcript.read_text().splitlines(keepends=True) if "/turns/03.md" not in line))
    page = render_session(worked_example, unwritten, now=NOW)
    shown, section = messages_of(page), sections_of(page)["03"]
    assert shown["03"] == [] and "no Write call for this turn's record" in section
    assert [m[: len(s)] for m, s in zip(shown["04"], SAMPLE["03"] + SAMPLE["04"])] == SAMPLE["03"] + SAMPLE["04"]
    assert len(shown["04"]) == len(SAMPLE["03"] + SAMPLE["04"])


def test_a_message_another_session_sent_is_on_its_turn_under_that_sessions_name(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """session-page-pairs-only-the-users-messages: another session's message, wrapped as Claude
    Code wraps one and with no origin that says it is not the user's, delivered in turn 3 as a user
    entry that carries two, one from a sender that gives no `from-name`, and mid-turn in turn 4 as a
    queued command. Each is on the turn it arrived in, under its sender's `from-name`, and on no
    turn as the user's; the user's own messages pair as before."""
    peer = ('<cross-session-message from="uds:/run/user/1000/cc-socks/2118235.sock" from-name="agents-d2"'
            ' from-mode="prompting">\n{}\n</cross-session-message>')
    entries = [
        {"type": "attachment", "timestamp": "2026-09-23T01:05:00.000Z",
         "attachment": {"type": "queued_command", "prompt": peer.format("ruled good to ship, dispatch both")}},
        {"type": "user", "timestamp": "2026-09-23T00:10:00.000Z",
         "message": {"role": "user", "content": [
             {"type": "text", "text": peer.format("merged, the tree is yours")},
             {"type": "text", "text": '<cross-session-message from="uds:/run/user/1000/cc-socks/77.sock">\nme too\n</cross-session-message>'}]}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text(transcript.read_text() + "".join(json.dumps(e) + "\n" for e in entries))
    page = render_session(worked_example, t, now=NOW)
    shown = messages_of(page)
    assert {key: s for key, s in sent_of(page).items() if s} == {
        "03": [("agents-d2", "merged, the tree is yours"), ("another session", "me too")], "04": [("agents-d2", "ruled good to ship, dispatch both")]}
    assert {key: [m[: len(s)] for m, s in zip(shown[key], said)] for key, said in SAMPLE.items()} == SAMPLE
    assert {key: len(m) for key, m in shown.items()} == {key: len(said) for key, said in SAMPLE.items()}


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
    shown = messages_of(render_session(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls), now=NOW))
    assert (shown["01"], shown["02"], shown["03"]) == (["yes"], ["yes"], ["yes, and split it"])


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
    shown = messages_of(render_session(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls), now=NOW))
    assert shown["01"] == ["a", "also, keep the second bank"]


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
    shown = messages_of(render_session(worked_example, with_calls(t, worked_example, tmp_path / "w.jsonl", calls), now=NOW))
    assert shown["01"] == ["fix the header, and the footer"]


def test_a_write_to_another_directorys_turn_record_moves_none_of_this_sessions(
    worked_example: Path, transcript: Path, tmp_path: Path
) -> None:
    """A record is this session's only under this session's directory: a write to the prototype's
    sample `turns/04.md`, before the last prompt, leaves turn 4's messages where they were."""
    call = {"type": "tool_use", "name": "Write", "input": {"file_path": "/elsewhere/agent/prototypes/session-page/sample/turns/04.md"}}
    t = tmp_path / "t.jsonl"
    t.write_text(transcript.read_text() + json.dumps(
        {"type": "assistant", "timestamp": "2026-09-23T00:30:00Z", "message": {"role": "assistant", "content": [call]}}) + "\n")
    shown = messages_of(render_session(worked_example, t, now=NOW))
    assert {key: [m[: len(s)] for m, s in zip(shown[key], said)] for key, said in SAMPLE.items()} == SAMPLE
    assert {key: len(m) for key, m in shown.items()} == {key: len(said) for key, said in SAMPLE.items()}


def test_a_link_in_the_details_is_a_path_from_the_repo_root_too(worked_example: Path, transcript: Path) -> None:
    """The Decision resolves every link a record writes, the ones in its prose as well as its
    Links: followed from the page's directory, it lands on the path the record wrote, in a tab of
    its own. A link to a part of the page stays on the page."""
    root = worked_example.parents[2]
    (worked_example / "turns" / "05.md").write_text(
        "---\ndate: 2026-09-24\n---\n\n# Round 4\n\n## Details\n\n"
        "The [second bank](agent/show/ledger/banks.html) is drawn, and [Q7](#q7) still waits.\n")
    section = sections_of(render_session(worked_example, transcript, now=NOW))["05"]
    ((href, target),) = re.findall(r'<a href="([^"#][^"]*)"[^>]*?target="([^"]+)"', section)
    assert (worked_example / href).resolve().relative_to(root.resolve()).as_posix() == "agent/show/ledger/banks.html"
    assert target == "_blank"
    assert '<a href="#q7">Q7</a>' in section


def test_a_link_is_a_path_from_the_repo_root(worked_example: Path, transcript: Path) -> None:
    """Each link on the page, followed from the page's own directory, lands on the path the record
    wrote, from the root of the repo the session directory sits in."""
    root = worked_example.parents[2]
    page = render_session(worked_example, transcript, now=NOW)
    hrefs = re.findall(r'<a class="link" href="([^"]+)"', page)
    landed = [(worked_example / href).resolve().relative_to(root.resolve()).as_posix() for href in hrefs]
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
    section = sections_of(render_session(worked_example, transcript, now=NOW))["05"]
    assert re.findall(r'<a class="link" href="([^"]+)"', section) == [
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
    assert "your answers" in section and re.search(r">Q7</a> no\b", section)
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
    page = render_session(worked_example, transcript, now=NOW)
    ids = re.findall(r'<(?:details|article) class="turn[^"]*" id="([^"]+)"', page)
    assert ids == ["t04", chat.stem, "t03", "t02", "t01"]
    row = page[page.index(f'id="{chat.stem}"'):]
    row = row[:row.index("</article>")]
    assert html_text(re.findall(r'<div class="msg">(.*?)</div>', row, re.S)[0]).startswith(SAMPLE["04"][0])
    assert [m[:len(SAMPLE["04"][1])] for m in messages_of(page)["04"]] == SAMPLE["04"][1:]


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
    page renders it, titled as the hub's rail titles the session, with no brief, and a resume
    command that changes to the directory the session started in."""
    directory = tmp_path / "agent" / "sessions" / FRESH
    at = datetime(2026, 10, 5, 9, 1, tzinfo=UTC)
    chat = chat_path(directory / "turns", at)
    chat.parent.mkdir(parents=True)
    chat.write_text(chat_record("On it: reading the handoff.", at))
    said = tmp_path / "t.jsonl"
    said.write_text("".join(json.dumps(e) + "\n" for e in [STARTED, *entries]))
    page = render_session(directory, said, now=NOW)
    assert html.unescape(re.search(r'<h1 class="v-title">(.*?)</h1>', page).group(1)) == title
    assert html.unescape(re.search(r"<title>(.*?) · session page</title>", page).group(1)) == title
    assert re.findall(r'<(?:details|article) class="turn[^"]*" id="([^"]+)"', page) == [chat.stem]
    assert '<div class="prose brief"></div>' in page
    assert f'data-cmd="cd &#x27;/srv/help line&#x27; &amp;&amp; claude --resume {FRESH}"' in page
    assert "1 turn · 2026-10-05 · " in html_text(page)


def test_a_session_record_with_no_turn_yet_renders_its_title_and_no_turn(worked_example: Path, transcript: Path) -> None:
    """every-session-gets-a-page#P5's other half: session.md written and the turn ended on no text,
    so neither a numbered record nor a chat turn exists, and the page still renders."""
    for record in (worked_example / "turns").iterdir():
        record.unlink()
    page = render_session(worked_example, transcript, now=NOW)
    assert "Leading words for showing" in re.search(r'<h1 class="v-title">(.*?)</h1>', page).group(1)
    assert re.findall(r'<(?:details|article) class="turn[^"]*" id="([^"]+)"', page) == []
    assert " 0 turns · rendered " in html_text(page)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
