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

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from session_page import PAGE, RecordError, render_session
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
    return re.sub(r"<[^>]+>", " ", fragment).strip()


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
    assert shown["03"] == [] and "never writes this turn's record" in section
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


def test_a_link_is_a_path_from_the_repo_root(worked_example: Path, transcript: Path) -> None:
    """Each link on the page, followed from the page's own directory, lands on the path the record
    wrote, from the root of the repo the session directory sits in."""
    root = worked_example.parents[2]
    page = render_session(worked_example, transcript, now=NOW)
    hrefs = re.findall(r'<a class="link" href="([^"]+)"', page)
    landed = [(worked_example / href).resolve().relative_to(root.resolve()).as_posix() for href in hrefs]
    records = sorted((worked_example / "turns").glob("*.md"), reverse=True)
    assert landed == re.findall(r"\]\(([^)]+)\)", "".join(p.read_text() for p in records))


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
def test_a_record_that_clears_a_question_it_cannot_is_refused_at_its_line_and_no_page_is_written(
    worked_example: Path, transcript: Path, frontmatter: str, line: int, reason: str
) -> None:
    record = worked_example / "turns" / "05.md"
    record.write_text(f"---\ndate: 2026-09-24\n{frontmatter}\n---\n\n# Round 4\n")
    with pytest.raises(RecordError, match=re.escape(reason)) as refused:
        render_session(worked_example, transcript, now=NOW)
    assert str(refused.value).startswith(f"{record}:{line}: ")
    assert not (worked_example / PAGE).exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
