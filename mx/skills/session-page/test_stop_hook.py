# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pyyaml", "markdown-it-py"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision out,
with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md, its Properties and its Decisions on what the hook does with a turn,
over the worked example in `fixtures/`, whose records a check corrupts one at a time.
The prose reviewer is stubbed at `turn_review.review`, the one call that reaches a model.
"""

import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import session_page
import stop_hook
import turn_review
from session_page import PAGE
from stop_hook import SESSIONS, decide, session_directory

# the sessions the hook leaves alone are marked in the environment, and the suite runs in one of
# them whenever a dispatched worker verifies its branch
UNATTENDED = ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")


@pytest.fixture(autouse=True)
def attended(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Every check here is a turn of a session someone is sitting at, whose record the prose
    reviewer finds nothing in unless the check says otherwise: no check spends a model call. The
    log is the check's own, and handed back."""
    for marker in UNATTENDED:
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.setattr(turn_review, "review", lambda system, prompt: [])
    monkeypatch.setattr(session_page, "LOG", tmp_path / "session-page.jsonl")
    return session_page.LOG


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict], None]:
    """Call the hook the way Claude Code does, on the payload given."""

    def call(payload: dict) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        stop_hook.main()

    return call


def payload(directory: Path, transcript: Path, reply: str = "One line, and the page's link.", **rest: object) -> dict:
    """The Stop hook JSON for a turn of the session whose directory is `directory`."""
    return {
        "session_id": directory.name,
        "cwd": str(directory.parents[len(SESSIONS.parts)]),
        "transcript_path": str(transcript),
        "stop_hook_active": False,
        "last_assistant_message": reply,
        **rest,
    }


def logged(log: Path, key: str) -> list[dict]:
    """The log's lines that carry `key`: `decision` the review's, `verb` the hook's."""
    lines = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return [entry for entry in lines if key in entry]


def git(where: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def test_a_session_keeps_its_page_in_the_agent_repo_whichever_worktree_it_ran_in(tmp_path: Path) -> None:
    """Where the Decisions put a session's records, pinned as literals: `agent/sessions/<id>` in
    the main checkout, which holds the agent repo, from the code repo's main checkout, from a linked
    worktree of it, which holds no `agent/`, and from inside the agent repo. A directory in no
    project with an agent repo has none."""
    main, worktree = tmp_path / "ledger", tmp_path / "ledger-map-columns"
    (main / "agent" / "tickets").mkdir(parents=True)
    git(main, "init", "-q")
    git(main, "commit", "-q", "--allow-empty", "-m", "start")
    git(main, "worktree", "add", "-q", str(worktree))
    git(main / "agent", "init", "-q")
    for cwd in (main, worktree, main / "agent" / "tickets"):
        assert session_directory(cwd, "s1") == tmp_path / "ledger/agent/sessions/s1", cwd
    assert not (worktree / "agent").exists()
    assert session_directory(tmp_path, "s1") is None


# ---- properties -------------------------------------------------------------

# A reply the page would have carried: longer than three lines, which is what sends the agent back
# in a session that has a page.
LONG = "\n".join(f"Line {n} of an answer that belongs on the page." for n in range(1, 6))

TURNS_THAT_NEEDED_NO_PAGE = {
    "a one-line answer": {},
    "an answer that would have needed a page": {"reply": LONG},
    "a turn another hook sent back once already": {"reply": LONG, "stop_hook_active": True},
    "a turn that said nothing": {"reply": ""},
}


@pytest.mark.parametrize("turn", TURNS_THAT_NEEDED_NO_PAGE.values(), ids=TURNS_THAT_NEEDED_NO_PAGE)
def test_a_session_that_never_needed_a_page_writes_nothing_under_the_sessions_directory(
    turn: dict, transcript: Path, tmp_path: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None]
) -> None:
    """session-page#P3: no record has ever been written for this session, so the hook neither
    creates its directory nor asks the agent for anything."""
    sessions = tmp_path / SESSIONS
    sessions.mkdir(parents=True)
    (tmp_path / "agent" / "tickets").mkdir()  # a project with an agent repo, which has never had a record
    run(payload(sessions / "8e0f1c22-0000-0000-0000-000000000000", transcript, **turn))
    assert list(sessions.rglob("*")) == []
    assert capsys.readouterr().out == ""  # nothing is sent back, so the turn ends here


# The record the turn just wrote is 04.md, the one the Decisions have the hook validate; 03.md is
# two rounds back, and a hook that read only the newest record would let it through. Each case is
# what the record says and the line the hook names, None where the shape says only that something
# is missing and not where.
UNPARSEABLE = {
    "frontmatter that is not YAML": (
        "04.md", "---\ndate: 2026-09-23\nanswered: Q1: a\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 3),
    "frontmatter that is not a mapping": (
        "04.md", "---\n- a\n- b\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 2),
    "a question that is not a question item": (
        "04.md", "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n## Questions\n\n- Q7: what reviews the prose?\n", 9),
    "a section the record's shape does not have": (
        "04.md", "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n## Notes\n\nA fourth section.\n", 7),
    "no headline": ("04.md", "---\ndate: 2026-09-23\n---\n\n## Details\n\nThe round.\n", None),
    "a record from an earlier turn": (
        "03.md", "---\ndate: 2026-09-23\n---\n\n# Round 2\n\n## Notes\n\nA fourth section.\n", 7),
}


@pytest.mark.parametrize("name, text, line", UNPARSEABLE.values(), ids=UNPARSEABLE)
def test_a_turn_record_that_does_not_parse_is_sent_back_and_never_rendered(
    name: str, text: str, line: int | None, worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """session-page#P8: the page the turn before rendered still stands, and the reason the agent
    reads names the file and the line the hook gave up on."""
    record = worked_example / "turns" / name
    hook = payload(worked_example, transcript)
    assert decide(hook, worked_example).verb == "render", "a turn whose records read is what renders the page"

    (worked_example / PAGE).write_text(stale_page)
    record.write_text(text)
    decision = decide(hook, worked_example)
    assert decision.verb == "send back"
    assert decision.reason.startswith(f"{record}:{line}: " if line else f"{record}: ")

    run(hook)
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"] == decision.reason
    assert (worked_example / PAGE).read_text() == stale_page, "the page is what the last records that parsed rendered"


def test_a_session_that_needed_a_page_has_one_beside_its_records(
    worked_example: Path, transcript: Path, stale_page: str, run: Callable[[dict], None]
) -> None:
    """The other side of session-page#P3: the turn that wrote a record is what renders the page,
    and the page is that directory's index.html."""
    hook = payload(worked_example, transcript)
    (worked_example / PAGE).write_text(stale_page)
    run(hook)
    assert sorted(path.name for path in worked_example.iterdir()) == ["index.html", "session.md", "turns"]
    assert (worked_example / "index.html").read_text() != stale_page


# ---- the sessions it leaves alone, and the answer in the chat ---------------

LEFT_ALONE = {"a dispatched worker": ("DISPATCH_WORKLOG", "/w/log"), "a print-mode session": ("CLAUDE_CODE_SESSION_ATTENDED", "0")}


@pytest.mark.parametrize("marker, value", LEFT_ALONE.values(), ids=LEFT_ALONE)
def test_a_session_nobody_reads_the_page_of_is_left_alone(
    marker: str, value: str, worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither a broken record nor an answer in the chat sends the agent back, and the page stays
    as it was."""
    monkeypatch.setenv(marker, value)
    (worked_example / PAGE).write_text(stale_page)
    (worked_example / "turns" / "04.md").write_text("no frontmatter\n")
    run(payload(worked_example, transcript, reply=LONG))
    assert capsys.readouterr().out == ""
    assert (worked_example / PAGE).read_text() == stale_page


# The worked example's transcript ends with record 4's Write call, after the last prompt: that
# turn wrote its record. A prompt after it, with the records last touched before it, is a turn
# that wrote none.
SPOKEN_AFTER = {"type": "user", "message": {"role": "user", "content": "And the ledger's second bank?"},
                "timestamp": "2026-09-23T01:35:00.000Z"}
BEFORE_IT = datetime(2026, 9, 23, 1, 31, tzinfo=UTC).timestamp()
FOUR_LINES = "\n".join(LONG.splitlines()[:4])
THREE_LINES = "\n\n".join(LONG.splitlines()[:3])


@pytest.fixture
def unrecorded(worked_example: Path, transcript: Path, tmp_path: Path) -> Path:
    """The worked example's transcript with a prompt after its newest record, which this turn
    answered without writing one."""
    for record in (worked_example / "turns").iterdir():
        os.utime(record, (BEFORE_IT, BEFORE_IT))
    spoken = tmp_path / "spoken.jsonl"
    spoken.write_text(transcript.read_text() + json.dumps(SPOKEN_AFTER) + "\n")
    return spoken


def test_an_answer_in_the_chat_with_no_record_is_sent_back_to_the_page(
    worked_example: Path, unrecorded: Path, stale_page: str, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """session-page's Decision on the Stop hook: in a session that has a page, a reply longer than
    three lines with no record written this turn goes back, naming the record it belongs in and the
    page the reply links, and the page waits for that record."""
    hook = payload(worked_example, unrecorded, reply=FOUR_LINES)
    assert decide(hook, worked_example).verb == "send back"
    (worked_example / PAGE).write_text(stale_page)
    run(hook)
    said = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert str(worked_example / "turns" / "05.md") in said and (worked_example / PAGE).as_uri() in said
    assert (worked_example / PAGE).read_text() == stale_page


RENDERED = {
    "a long answer and a record": (False, LONG, False),
    "three lines and no record": (True, THREE_LINES, False),
    "a long answer sent back once already": (True, LONG, True),
}


@pytest.mark.parametrize("answered_in_chat, reply, again", RENDERED.values(), ids=RENDERED)
def test_every_other_turn_of_a_session_with_a_page_renders_it(
    answered_in_chat: bool, reply: str, again: bool, worked_example: Path, transcript: Path, request: pytest.FixtureRequest,
    stale_page: str, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """The answer in the chat goes back once per turn, and only when it is longer than three lines."""
    turn = request.getfixturevalue("unrecorded") if answered_in_chat else transcript
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, turn, reply=reply, stop_hook_active=again))
    assert capsys.readouterr().out == ""
    assert (worked_example / PAGE).read_text() != stale_page


def test_a_record_written_without_a_write_call_counts_as_written(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """A record written through the shell leaves no write call in the transcript; its modification
    time says it was written this turn, so the long reply beside it renders."""
    (worked_example / "turns" / "05.md").write_text("---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe second bank.\n")
    run(payload(worked_example, unrecorded, reply=LONG))
    assert capsys.readouterr().out == ""
    assert "Round 4" in (worked_example / PAGE).read_text()


# ---- the turn record's review -----------------------------------------------

# Passages of the worked example's record 4, the one its turn wrote, as a reviewer would quote them.
IN_RECORD = ["The session page only holds things", "There is no markup of its own to learn.",
             "costs seconds", "The chat reply is one line and the link"]
NOT_IN_RECORD = "The session page is a pivotal tapestry of links."


def finding(quote: str, rule: str = "7") -> dict:
    return {"rule": rule, "quote": quote, "note": "a note on it"}


def said_back(capsys: pytest.CaptureFixture) -> str:
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


def reviewer(*found: dict) -> Callable[[str, str], list[dict]]:
    return lambda system, prompt: list(found)


def unreachable(system: str, prompt: str) -> list[dict]:
    raise AssertionError("the reviewer was called on a turn that should not spend a model call")


def test_a_record_with_findings_goes_back_with_at_most_three_and_the_page_waits(
    worked_example: Path, transcript: Path, stale_page: str, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """session-page's Decision on Review: the findings go back to the agent, which revises the
    record, and the page renders at the stop after, where no second review runs."""
    monkeypatch.setattr(turn_review, "review", reviewer(*map(finding, IN_RECORD)))
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    said = said_back(capsys)
    assert str(worked_example / "turns" / "04.md") in said
    assert [quote for quote in IN_RECORD if f'"{quote}"' in said] == IN_RECORD[:3]
    assert "**AI vocabulary.**" in said, "a cited rule comes with its text"
    assert (worked_example / PAGE).read_text() == stale_page

    monkeypatch.setattr(turn_review, "review", unreachable)
    run(payload(worked_example, transcript, stop_hook_active=True))
    assert capsys.readouterr().out == ""
    assert (worked_example / PAGE).read_text() != stale_page


FOUND = {
    "one quote in the record and one not": ([finding(NOT_IN_RECORD), finding(IN_RECORD[0])], [IN_RECORD[0]]),
    "only quotes not in the record": ([finding(NOT_IN_RECORD), finding("")], []),
}


@pytest.mark.parametrize("found, kept", FOUND.values(), ids=FOUND)
def test_a_finding_quoting_text_absent_from_the_record_is_dropped(
    found: list[dict], kept: list[str], worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped finding never reaches the agent, and a record whose findings all drop renders.
    An empty quote is in every record, and quotes nothing."""
    monkeypatch.setattr(turn_review, "review", reviewer(*found))
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    out = capsys.readouterr().out
    if kept:
        said = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        assert all(f'"{quote}"' in said for quote in kept) and NOT_IN_RECORD not in said
        assert (worked_example / PAGE).read_text() == stale_page
    else:
        assert out == ""
        assert (worked_example / PAGE).read_text() != stale_page


def broken(system: str, prompt: str) -> list[dict]:
    raise RuntimeError("claude exited 1: overloaded")


def slow(system: str, prompt: str) -> list[dict]:
    raise subprocess.TimeoutExpired(["claude"], turn_review.REVIEWER_TIMEOUT_S)


@pytest.mark.parametrize("failing", [broken, slow], ids=["a failing reviewer", "a slow reviewer"])
def test_a_reviewer_that_fails_lets_the_page_render_and_logs_why(
    failing: Callable[[str, str], list[dict]], worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    monkeypatch.setattr(turn_review, "review", failing)
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert capsys.readouterr().out == ""
    assert (worked_example / PAGE).read_text() != stale_page
    (entry,) = logged(attended, "decision")
    assert (entry["session_id"], entry["decision"]) == (worked_example.name, "failed")


def test_a_record_written_after_the_answer_in_the_chat_was_sent_back_is_reviewed_once(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The review runs once per turn whichever send-back continued it: the record the agent moves
    its answer into is reviewed at the stop the first send-back continued, and its revision renders."""
    run(payload(worked_example, unrecorded, reply=LONG))
    assert "05.md" in said_back(capsys)
    record = worked_example / "turns" / "05.md"
    record.write_text("---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe second bank is a pivotal addition.\n")
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    run(payload(worked_example, unrecorded, stop_hook_active=True))
    assert str(record) in said_back(capsys)
    monkeypatch.setattr(turn_review, "review", unreachable)
    record.write_text(record.read_text().replace("a pivotal addition", "the ledger's overflow"))
    run(payload(worked_example, unrecorded, stop_hook_active=True))
    assert capsys.readouterr().out == ""
    assert "overflow" in (worked_example / PAGE).read_text()


def test_a_turn_that_wrote_no_record_spends_no_model_call(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    monkeypatch.setattr(turn_review, "review", unreachable)
    run(payload(worked_example, unrecorded))
    assert capsys.readouterr().out == ""
    assert logged(attended, "decision") == []


def test_each_review_decision_is_logged_with_the_record_it_read(
    worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The draft's review and the revision that follows it, paired by session id, show which
    flagged passages the agent kept."""
    record = worked_example / "turns" / "04.md"
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0]), finding(NOT_IN_RECORD)))
    run(payload(worked_example, transcript))
    run(payload(worked_example, transcript, stop_hook_active=True))
    capsys.readouterr()
    draft, revision = logged(attended, "decision")
    assert (draft["decision"], draft["findings"], draft["dropped"]) == ("feedback", [finding(IN_RECORD[0])], [finding(NOT_IN_RECORD)])
    assert revision["decision"] == "re-entry"
    assert {draft["record"], revision["record"]} == {str(record)} and draft["text"] == record.read_text()


def test_the_reviewer_reads_what_the_page_shows_and_no_tool_call(
    worked_example: Path, transcript: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reviewer's input carries the earlier turn records and the user's messages, and no tool
    call: the transcript's Write calls and the task notifications that name a tool use carry ids
    starting `toolu_`. The record under review comes last, fenced, and the reviewer runs under
    its own system prompt, bound to the schema."""
    argvs = []

    def claude(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        argvs.append(argv)
        answer = {"type": "result", "result": "", "structured_output": {"findings": [finding(IN_RECORD[0])]}}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(answer), stderr="")

    monkeypatch.setattr(turn_review, "review", REVIEW)
    monkeypatch.setattr(turn_review.subprocess, "run", claude)
    decision = decide(payload(worked_example, transcript), worked_example)
    assert decision.verb == "send back" and IN_RECORD[0] in decision.reason
    (argv,) = argvs
    prompt, system = argv[-1], argv[argv.index("--system-prompt") + 1]
    turns = worked_example / "turns"
    for earlier in ("01.md", "02.md", "03.md"):
        assert (turns / earlier).read_text().strip() in prompt
    assert prompt.endswith(f"<record>\n{(turns / '04.md').read_text().strip()}\n</record>")
    assert "i feel like we need like a leading word" in prompt  # the first prompt
    assert "hey can you please disregard" in prompt  # one the fourth turn answered
    assert "toolu_" not in prompt
    assert "Claude Code" not in system and "**AI vocabulary.**" in system
    assert turn_review.record_shape(turn_review.SHOW.read_text()) in system
    assert json.loads(argv[argv.index("--json-schema") + 1])["properties"]["findings"]["maxItems"] == 3
    assert argv[argv.index("--model") + 1] == "claude-opus-5-5" and argv[argv.index("--effort") + 1] == "low"


REVIEW = turn_review.review  # the real one, which the autouse stub replaces


# ---- the hook's log ---------------------------------------------------------

# Each arrangement takes the worked example, its transcript and the check's fixtures, and returns
# the hook JSON of a turn that takes one path.

def worker(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    fixtures.getfixturevalue("monkeypatch").setenv("DISPATCH_WORKLOG", "/w/log")
    return payload(example, transcript)


def print_mode(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    fixtures.getfixturevalue("monkeypatch").setenv("CLAUDE_CODE_SESSION_ATTENDED", "0")
    return payload(example, transcript)


def in_no_project(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    loose = fixtures.getfixturevalue("tmp_path_factory").mktemp("loose")
    return payload(example, transcript) | {"cwd": str(loose)}


def with_no_directory(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example.parent / "8e0f1c22-0000-0000-0000-000000000000", transcript)


def unparsed(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    (example / "turns" / "04.md").write_text("no frontmatter\n")
    return payload(example, transcript)


def in_the_chat(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, fixtures.getfixturevalue("unrecorded"), reply=LONG)


def found_fault(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    fixtures.getfixturevalue("monkeypatch").setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    return payload(example, transcript)


def no_record(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, fixtures.getfixturevalue("unrecorded"))


def reviewed_earlier(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    """The stop after the review sent the record back."""
    found_fault(example, transcript, fixtures)
    decide(payload(example, transcript), example)
    return payload(example, transcript, stop_hook_active=True)


def found_nothing(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, transcript)


# Each path the hook takes, and the line it logs for it: the verb, why, and whether it resolved a
# session directory. The four that let a turn end are the ones that look the same from outside.
PATHS = {
    "a dispatched worker": (worker, "allow", "dispatched worker", True),
    "a print-mode session": (print_mode, "allow", "print-mode session", True),
    "a directory in no project": (in_no_project, "allow", "no project with an agent repo", False),
    "a session with no directory": (with_no_directory, "allow", "no session directory", True),
    "a record that does not parse": (unparsed, "send back", "record does not parse", True),
    "an answer in the chat": (in_the_chat, "send back", "answer in the chat", True),
    "a record the review finds fault with": (found_fault, "send back", "review findings", True),
    "a turn that wrote no record": (no_record, "render", "no record written this turn", True),
    "a record reviewed at an earlier stop": (reviewed_earlier, "render", "record reviewed this turn", True),
    "a record the review finds nothing in": (found_nothing, "render", "review found nothing", True),
}


@pytest.mark.parametrize("arrange, verb, why, resolved", PATHS.values(), ids=PATHS)
def test_every_decision_is_one_line_in_the_session_pages_log(
    arrange: Callable, verb: str, why: str, resolved: bool, worked_example: Path, transcript: Path,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], request: pytest.FixtureRequest, attended: Path,
) -> None:
    """stop-hook-logs-its-decisions: the verb, why the hook took that path, and the session
    directory it resolved, in the log the review writes to as well."""
    hook = arrange(worked_example, transcript, request)
    before = len(logged(attended, "verb"))
    run(hook)
    capsys.readouterr()
    entries = logged(attended, "verb")[before:]
    directory = str(Path(hook["cwd"]) / SESSIONS / hook["session_id"]) if resolved else None
    assert entries == [{"ts": entries[0]["ts"], "session_id": hook["session_id"], "verb": verb, "why": why, "directory": directory}]


def test_a_log_that_cannot_be_written_leaves_the_turn_as_it_would_have_been(
    worked_example: Path, transcript: Path, stale_page: str, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The log is for diagnosis: a full disk or a read-only home still renders the page."""
    (tmp_path / "not-a-directory").write_text("")
    monkeypatch.setattr(session_page, "LOG", tmp_path / "not-a-directory" / "log.jsonl")
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert capsys.readouterr().out == ""
    assert (worked_example / PAGE).read_text() != stale_page


# ---- the catalogue's chat rules ---------------------------------------------

CATALOGUE_FIXTURE = """# Tells

Prose about the tags.

## Content

- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `51` `artifact` **A rule for files only.** Dropped.

## Style

- `13` `chat` **A rule for replies.** Kept.
"""

SELECTED = """- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `13` `chat` **A rule for replies.** Kept."""


def test_the_rules_selected_are_the_ones_the_catalogue_documents() -> None:
    """The oracle is the awk command CATALOGUE.md's header publishes as its format contract, run
    on the real catalogue: a catalogue whose bullets stop matching fails here rather than turning
    every record clean."""
    catalogue = turn_review.CATALOGUE
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", catalogue.read_text()).group(1)
    awk = subprocess.run(["awk", program, catalogue], capture_output=True, text=True, check=True)
    assert turn_review.chat_rules(catalogue.read_text()) == awk.stdout.rstrip("\n")


def test_selected_rule_blocks_come_whole() -> None:
    assert turn_review.chat_rules(CATALOGUE_FIXTURE) == SELECTED


def test_a_catalogue_with_no_chat_rules_lets_the_page_render(
    worked_example: Path, transcript: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalogue = tmp_path / "CATALOGUE.md"
    catalogue.write_text(CATALOGUE_FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))
    monkeypatch.setattr(turn_review, "CATALOGUE", catalogue)
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    assert decide(payload(worked_example, transcript), worked_example).verb == "render"


SKILL_FIXTURE = """## The session page

Prose before the shape.

### The turn record

The shape's prose.

```markdown
---
date: 2026-09-28
---

# A headline inside the example

## Details

The example's own section.
```

- A rule about the record.

## Who builds it

After the shape.
"""


def test_the_shape_runs_to_the_next_heading_past_the_example_records_own() -> None:
    shape = turn_review.record_shape(SKILL_FIXTURE)
    assert shape.startswith("The shape's prose.") and shape.endswith("- A rule about the record.")
    assert "# A headline inside the example" in shape and "## Details" in shape
    assert "Prose before" not in shape and "After the shape" not in shape


def test_the_turn_record_the_show_skill_gives_the_agent_parses(tmp_path: Path) -> None:
    """The oracle is the renderer's own reader: the example record the agent is shown is a record
    it accepts, and it uses every part a record can hold, so the skill and the parser cannot drift
    apart unnoticed."""
    shape = turn_review.record_shape(turn_review.SHOW.read_text())
    example = re.search(r"```markdown\n(.*?)```", shape, re.S).group(1)
    record = tmp_path / "07.md"
    record.write_text(example)
    turn = session_page.read_turn(record)
    assert turn.headline and turn.details and turn.links and turn.answered and turn.superseded
    (question,) = turn.questions
    assert len(question.options) >= 2 and sum(o.picked for o in question.options) == 1 and question.why


def test_a_show_skill_with_no_turn_record_section_lets_the_page_render(
    worked_example: Path, transcript: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL_FIXTURE.replace("### The turn record", "### Another section"))
    monkeypatch.setattr(turn_review, "SHOW", skill)
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    assert decide(payload(worked_example, transcript), worked_example).verb == "render"
    (entry,) = logged(attended, "decision")
    assert entry["decision"] == "failed" and "The turn record" in entry["why"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
