# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision out,
with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md, its Properties and its Decisions on what the hook does with a turn,
over the worked example in `fixtures/`, whose records a check corrupts one at a time.
The prose reviewer is stubbed at `turn_review.review`, the one call that reaches a model, or runs
through run-log against a stand-in `claude` first on PATH. The browser is a stand-in
`claude-browser` first on PATH that records what it was asked to open.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import session_page
import stop_hook
import turn_review
from session_page import PAGE, SESSIONS, render_session
from stop_hook import decide
from test_reading import messages_of

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
    monkeypatch.setattr(turn_review, "LOG", tmp_path / "session-page.jsonl")
    return turn_review.LOG


@pytest.fixture(autouse=True)
def browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A `claude-browser` first on PATH that appends each path it is asked to open to the file
    handed back, so no check starts a browser."""
    where = tmp_path / "browser"
    where.mkdir()
    (where / "claude-browser").write_text(f'#!/usr/bin/env bash\necho "$@" >> "{where}/opened"\n')
    (where / "claude-browser").chmod(0o755)
    monkeypatch.setenv("PATH", f"{where}{os.pathsep}{os.environ['PATH']}")
    return where / "opened"


def opened(record: Path) -> list[str]:
    """What the stand-in browser has opened, once it has opened anything or five seconds have
    passed: the hook starts it and does not wait on it."""
    deadline = time.monotonic() + 5
    while not record.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    return record.read_text().splitlines() if record.exists() else []


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict], None]:
    """Call the hook the way Claude Code does, on the payload given."""

    def call(payload: dict) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        stop_hook.main()

    return call


def payload(directory: Path, transcript: Path, reply: str = "", **rest: object) -> dict:
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


def shown(capsys: pytest.CaptureFixture) -> str:
    """The line the hook showed the user as the turn ended, empty where it showed none. A turn the
    hook sent back fails the check."""
    out = capsys.readouterr().out
    if not out:
        return ""
    said = json.loads(out)
    assert "hookSpecificOutput" not in said, f"the turn was sent back: {said}"
    return said["systemMessage"]


def git(where: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def test_a_session_keeps_its_page_in_the_agent_repo_whichever_worktree_it_ran_in(
    worked_example: Path, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, transcript: Path,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Where the Decisions put a session's records, pinned as literals: `agent/sessions/<id>` in
    the main checkout, which holds the agent repo, from the code repo's main checkout, from a linked
    worktree of it, which holds no `agent/`, and from inside the agent repo. The command the show
    skill has the agent run prints that directory from each, and the hook renders the page there.
    A directory in no project with an agent repo has none, and the command says so."""
    main, worktree = tmp_path / "ledger", tmp_path / "ledger-map-columns"
    (main / "agent" / "tickets").mkdir(parents=True)
    git(main, "init", "-q")
    git(main, "commit", "-q", "--allow-empty", "-m", "start")
    git(main, "worktree", "add", "-q", str(worktree))
    git(main / "agent", "init", "-q")
    directory = tmp_path / "ledger/agent/sessions" / worked_example.name
    shutil.copytree(worked_example, directory)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", worked_example.name)
    monkeypatch.setattr(sys, "argv", ["session-page"])
    for cwd in (main, worktree, main / "agent" / "tickets"):
        monkeypatch.chdir(cwd)
        session_page.main()
        assert capsys.readouterr().out == f"{directory}\n", cwd
        (directory / PAGE).unlink(missing_ok=True)
        run(payload(directory, transcript) | {"cwd": str(cwd)})
        assert (directory / PAGE).is_file(), cwd
        assert shown(capsys).endswith((directory / PAGE).as_uri()), cwd
    assert not (worktree / "agent").exists()
    monkeypatch.chdir(tmp_path_factory.mktemp("loose"))
    with pytest.raises(SystemExit, match="in no project with an agent repo"):
        session_page.main()
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    with pytest.raises(SystemExit, match="no session id"):
        session_page.main()


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
ROUND_3 = "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n"  # lines 1 to 6; the section's first item is line 9
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
    "a question with one option": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n", 9),
    "a question with no pick": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review.\n  - (b) None.\n", 9),
    "a question with two picks": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n"
                 "  - (b) None. *my pick*\n", 9),
    "an option letter twice": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n  - (a) None.\n", 9),
    "a second Why": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n  - (b) None.\n"
                 "  - Why: seconds.\n  - Why: again.\n", 13),
    "a question an earlier turn asked": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q1] **One feature or two?**\n  - (a) Two. *my pick*\n  - (b) One.\n", None),
    "a link from the filesystem root": ("04.md", f"{ROUND_3}## Links\n\n- [The round](/home/max/round.html): it\n", 9),
    "a link that climbs out of the repo": ("04.md", f"{ROUND_3}## Links\n\n- [The round](../round.html): it\n", 9),
    "a link item that is no link": ("04.md", f"{ROUND_3}## Links\n\n- the round's page\n", 9),
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


# ---- the page opening on its first render -----------------------------------


def test_the_render_that_writes_the_page_first_opens_it_and_no_later_one_does(
    worked_example: Path, transcript: Path, browser: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], attended: Path,
) -> None:
    """stop-hook-opens-the-page-on-its-first-render: the first render opens the page with
    `claude-browser`; later turns rewrite the same file and leave the open tab to a manual reload."""
    for _ in range(3):
        run(payload(worked_example, transcript))
        assert shown(capsys)
    assert [entry["page"] for entry in logged(attended, "opened")] == [str(worked_example / PAGE)]
    assert opened(browser) == [str(worked_example / PAGE)]


def test_a_page_already_there_is_rendered_and_not_opened(
    worked_example: Path, transcript: Path, stale_page: str, run: Callable[[dict], None], attended: Path,
) -> None:
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert (worked_example / PAGE).read_text() != stale_page
    assert logged(attended, "opened") == []


# ---- the sessions directory kept out of the agent repo's status -------------


def status(where: Path) -> list[str]:
    return subprocess.run(["git", "-C", str(where), "status", "--porcelain", "--untracked-files=all"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def exclude_file(repo: Path) -> Path:
    return repo / ".git" / "info" / "exclude"


def test_an_agent_repo_that_does_not_ignore_sessions_shows_none_of_them_after_the_first_render(
    worked_example: Path, transcript: Path, run: Callable[[dict], None], attended: Path,
) -> None:
    """The oracle is the ticket agent/tickets/agent-repos-exclude-sessions.md: the first render adds
    the line to the clone's exclude file, and a later render adds no second one."""
    agent = worked_example.parents[1]
    git(agent, "init")
    (agent / ".gitignore").write_text("transcripts/\n")
    assert any("sessions/" in line for line in status(agent))
    for _ in range(2):
        run(payload(worked_example, transcript))
    assert [line for line in status(agent) if "sessions/" in line] == []
    assert exclude_file(agent).read_text().count("/sessions/") == 1
    assert [entry["excluded"] for entry in logged(attended, "excluded")] == [f"added /sessions/ to {exclude_file(agent)}"]


ALREADY_IGNORED = {
    "by its .gitignore": ".gitignore",
    "by its exclude file": ".git/info/exclude",
}


@pytest.mark.parametrize("where", ALREADY_IGNORED.values(), ids=ALREADY_IGNORED)
def test_an_agent_repo_that_already_ignores_sessions_gets_no_line_added(
    where: str, worked_example: Path, transcript: Path, run: Callable[[dict], None], attended: Path,
) -> None:
    agent = worked_example.parents[1]
    git(agent, "init")
    (agent / where).parent.mkdir(parents=True, exist_ok=True)
    (agent / where).write_text("reviews/\nsessions/\n")
    before = exclude_file(agent).read_text() if exclude_file(agent).exists() else None
    run(payload(worked_example, transcript))
    assert (exclude_file(agent).read_text() if exclude_file(agent).exists() else None) == before
    assert [entry["excluded"] for entry in logged(attended, "excluded")] == ["already ignored"]


def test_an_agent_repo_that_tracks_session_records_gets_no_line_added(
    worked_example: Path, transcript: Path, run: Callable[[dict], None], attended: Path,
) -> None:
    """A repo that commits its session records keeps committing them: a later session's directory
    still shows in its status."""
    agent = worked_example.parents[1]
    git(agent, "init")
    git(agent, "add", "sessions")
    git(agent, "commit", "-m", "session records")
    (worked_example.parent / "a-later-session").mkdir()
    (worked_example.parent / "a-later-session" / "session.md").write_text("")
    run(payload(worked_example, transcript))
    assert [line for line in status(agent) if "sessions/" in line] == ["?? sessions/a-later-session/session.md", f"?? sessions/{worked_example.name}/index.html"]
    assert [entry["excluded"] for entry in logged(attended, "excluded")] == ["tracked, so not excluded"]


def test_an_agent_repo_outside_git_is_rendered_and_logged_as_such(
    worked_example: Path, transcript: Path, run: Callable[[dict], None], attended: Path,
) -> None:
    run(payload(worked_example, transcript))
    assert (worked_example / PAGE).exists()
    assert [entry["excluded"] for entry in logged(attended, "excluded")] == ["not in a git repository"]


def test_an_agent_directory_the_code_repo_tracks_excludes_its_own_sessions_and_no_other(
    worked_example: Path, transcript: Path, run: Callable[[dict], None],
) -> None:
    """The line is anchored at the agent directory's path in the repo, so a `sessions/` elsewhere in
    the code repo still shows."""
    project = worked_example.parents[2]
    git(project, "init")
    (project / "src" / "sessions").mkdir(parents=True)
    (project / "src" / "sessions" / "a.py").write_text("")
    run(payload(worked_example, transcript))
    assert exclude_file(project).read_text().splitlines()[-1] == "/agent/sessions/"
    assert [line for line in status(project) if "sessions/" in line] == ["?? src/sessions/a.py"]


# Each is the stand-in's script, None for none, and what the log says came of the open.
NO_BROWSER = {
    "a host with no claude-browser": (None, "no claude-browser on PATH"),
    "a claude-browser that hangs and then fails": ("#!/usr/bin/env bash\nsleep 30\nexit 1\n", "started "),
    "a claude-browser that cannot start": ("#!/nowhere/interpreter\n", " did not start: "),
}


@pytest.mark.parametrize("script, said", NO_BROWSER.values(), ids=NO_BROWSER)
def test_a_host_that_cannot_open_the_page_still_renders_it_and_ends_the_turn(
    script: str | None, said: str, worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, attended: Path,
) -> None:
    """The turn ends on the hook's own time, whatever the opener does after it starts, and the log
    says which of these it was."""
    where = tmp_path / "host"
    where.mkdir()
    if script:
        (where / "claude-browser").write_text(script)
        (where / "claude-browser").chmod(0o755)
    rest = [d for d in os.environ["PATH"].split(os.pathsep) if not (Path(d) / "claude-browser").exists()]
    monkeypatch.setenv("PATH", os.pathsep.join([str(where), *rest]))
    started = time.monotonic()
    run(payload(worked_example, transcript))
    assert time.monotonic() - started < 10
    assert shown(capsys)
    assert "Round 3" in (worked_example / PAGE).read_text()
    assert said in logged(attended, "opened")[0]["opened"]


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


@pytest.mark.parametrize("marker, value", LEFT_ALONE.values(), ids=LEFT_ALONE)
def test_a_session_nobody_reads_the_page_of_never_has_it_opened(
    marker: str, value: str, worked_example: Path, transcript: Path,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """Its records would render a first page, and the hook neither writes it nor opens it."""
    monkeypatch.setenv(marker, value)
    run(payload(worked_example, transcript))
    assert not (worked_example / PAGE).exists()
    assert logged(attended, "opened") == []


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
    three lines with no record written this turn goes back, naming the record it belongs in, and the
    page waits for that record."""
    hook = payload(worked_example, unrecorded, reply=FOUR_LINES)
    assert decide(hook, worked_example).verb == "send back"
    (worked_example / PAGE).write_text(stale_page)
    run(hook)
    said = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert str(worked_example / "turns" / "05.md") in said
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
    shown(capsys)
    assert (worked_example / PAGE).read_text() != stale_page


# ---- the line under the turn ------------------------------------------------

ANSWERS_Q7 = "---\ndate: 2026-09-23\nanswered:\n  Q7: a\n---\n\n# Round 4\n\n## Details\n\nThe light review it is.\n"


def test_a_turn_that_wrote_a_record_ends_on_the_hooks_line_naming_what_waits(
    worked_example: Path, transcript: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """stop-hook-prints-the-page-link#P1: the worked example's record 04 leaves Q7 open, and a record
    05 answering it leaves nothing; either way the line ends on the page's link."""
    link = (worked_example / PAGE).as_uri()
    run(payload(worked_example, transcript))
    assert shown(capsys) == f"session page · waiting on you: Q7 · {link}"
    record = worked_example / "turns" / "05.md"
    record.write_text(ANSWERS_Q7)
    with_write(unrecorded, "Write", record)
    run(payload(worked_example, unrecorded))
    assert shown(capsys) == f"session page · nothing waiting on you · {link}"


UNRECORDED = {
    "a one-line answer": ("Yes, the second bank.", False),
    "three lines": (THREE_LINES, False),
    "a long answer sent back once already": (LONG, True),
}


@pytest.mark.parametrize("reply, again", UNRECORDED.values(), ids=UNRECORDED)
def test_a_turn_that_wrote_no_record_gets_no_line(
    reply: str, again: bool, worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None],
) -> None:
    """stop-hook-prints-the-page-link#P2: its answer is in the chat, so the page's link would point
    at nothing new."""
    run(payload(worked_example, unrecorded, reply=reply, stop_hook_active=again))
    assert shown(capsys) == ""
    assert (worked_example / PAGE).is_file()


RECORD_05 = "---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe second bank.\n"


def with_write(transcript: Path, tool: str, record: Path) -> None:
    """Append to the transcript the turn's `tool` call on `record`, a minute after SPOKEN_AFTER."""
    call = {"type": "tool_use", "id": f"toolu_{tool}_{record.stem}", "name": tool, "input": {"file_path": str(record)}}
    entry = {"type": "assistant", "message": {"role": "assistant", "content": [call]}, "timestamp": "2026-09-23T01:36:00.000Z"}
    transcript.write_text(transcript.read_text() + json.dumps(entry) + "\n")


def test_a_record_written_through_the_shell_is_sent_back_once_to_be_written_with_write(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """stop-hook-reads-writes-from-the-transcript-only: a record counts as written this turn only by
    its write call in the transcript, as the page pairs messages. One written through the shell,
    with a long reply beside it, goes back once naming that record, to be written again with Write
    (that ticket's D1), and the turn the Stop hook continued renders; written with Write, it carries
    the user's message."""
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05)
    run(payload(worked_example, unrecorded, reply=LONG))
    said = said_back(capsys)
    assert str(record) in said and "Write" in said and "06.md" not in said
    run(payload(worked_example, unrecorded, reply=LONG, stop_hook_active=True))
    assert capsys.readouterr().out == ""
    assert "Round 4" in (worked_example / PAGE).read_text()
    with_write(unrecorded, "Write", record)
    assert messages_of(render_session(worked_example, unrecorded))["05"] == [SPOKEN_AFTER["message"]["content"]]


def test_a_turn_that_answers_by_editing_an_earlier_record_is_sent_back_to_a_new_one(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """stop-hook-reads-writes-from-the-transcript-only's D2: the page keeps a record's earliest write,
    so an Edit of record 04 after the user spoke writes no record this turn, and the long reply goes
    back to be moved onto 05."""
    record = worked_example / "turns" / "04.md"
    record.write_text(record.read_text() + "\n- Edited this turn to answer the question.\n")
    with_write(unrecorded, "Edit", record)
    run(payload(worked_example, unrecorded, reply=LONG))
    assert str(worked_example / "turns" / "05.md") in said_back(capsys)


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
    assert shown(capsys)
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
        assert "hookSpecificOutput" not in out
        assert (worked_example / PAGE).read_text() != stale_page


def broken(system: str, prompt: str) -> list[dict]:
    raise RuntimeError("claude exited 1: overloaded")


def hung(system: str, prompt: str) -> list[dict]:
    raise subprocess.TimeoutExpired(["run-log"], turn_review.WRAPPER_TIMEOUT_S)


@pytest.mark.parametrize("failing", [broken, hung], ids=["a failing reviewer", "a hung run-log"])
def test_a_reviewer_that_fails_lets_the_page_render_and_logs_why(
    failing: Callable[[str, str], list[dict]], worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """A failed review is the turn's review: the stop another hook continued renders without
    calling the reviewer again."""
    monkeypatch.setattr(turn_review, "review", failing)
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert shown(capsys)
    assert (worked_example / PAGE).read_text() != stale_page
    (entry,) = logged(attended, "decision")
    assert (entry["session_id"], entry["decision"]) == (worked_example.name, "failed")
    monkeypatch.setattr(turn_review, "review", unreachable)
    run(payload(worked_example, transcript, stop_hook_active=True))
    assert shown(capsys)
    assert [entry["decision"] for entry in logged(attended, "decision")] == ["failed", "re-entry"]


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
    with_write(unrecorded, "Write", record)
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    run(payload(worked_example, unrecorded, stop_hook_active=True))
    assert str(record) in said_back(capsys)
    monkeypatch.setattr(turn_review, "review", unreachable)
    record.write_text(record.read_text().replace("a pivotal addition", "the ledger's overflow"))
    run(payload(worked_example, unrecorded, stop_hook_active=True))
    assert shown(capsys)
    assert "overflow" in (worked_example / PAGE).read_text()


# ---- which turn a record and a review belong to -----------------------------

# Prompts Claude Code starts a turn on without the user typing, at SPOKEN_AFTER's time: a
# background task finishing and a subagent handing its report back.
TASK_DONE = {"type": "user", "origin": {"kind": "task-notification"}, "timestamp": SPOKEN_AFTER["timestamp"],
             "message": {"role": "user", "content": "<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n</task-notification>"}}
HANDED_BACK = {"type": "user", "origin": {"kind": "peer", "from": "a1", "handback": True}, "timestamp": SPOKEN_AFTER["timestamp"],
               "message": {"role": "user", "content": 'Another Claude session sent a message:\n<agent-message from="a1">\n'
                                                      "[Subagent hand-back] The figure is built.\n</agent-message>"}}
TURN_STARTS = {"a finished task": TASK_DONE, "a subagent's hand-back": HANDED_BACK}
# A message the user queues while the turn runs, after it wrote its record at 01:36 (with_write).
QUEUED = {"type": "attachment", "timestamp": "2026-09-23T01:37:00.000Z",
          "attachment": {"type": "queued_command", "prompt": "And the third bank?"}}
PIVOTAL_05 = "---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe second bank is a pivotal addition.\n"


def appended(transcript: Path, out: Path, *entries: dict) -> Path:
    out.write_text(transcript.read_text() + "".join(json.dumps(e) + "\n" for e in entries))
    return out


@pytest.mark.parametrize("start", TURN_STARTS.values(), ids=TURN_STARTS)
def test_a_turn_the_user_did_not_start_still_sends_an_answer_in_the_chat_back(
    start: dict, worked_example: Path, transcript: Path, tmp_path: Path,
) -> None:
    """This turn runs from the prompt that started it, whoever sent it: record 04, written in the
    turn before, is no record of a turn a finished task or a hand-back started, so its long reply
    goes back to be moved onto 05."""
    for record in (worked_example / "turns").iterdir():
        os.utime(record, (BEFORE_IT, BEFORE_IT))
    decision = decide(payload(worked_example, appended(transcript, tmp_path / "t.jsonl", start), reply=LONG), worked_example)
    assert (decision.verb, decision.why) == ("send back", "answer in the chat")
    assert str(worked_example / "turns" / "05.md") in decision.reason


@pytest.mark.parametrize("start", [SPOKEN_AFTER, *TURN_STARTS.values()], ids=["the user's prompt", *TURN_STARTS])
def test_a_record_a_later_turn_writes_is_reviewed_though_an_earlier_turns_was(
    start: dict, worked_example: Path, transcript: Path, tmp_path: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The review runs once per turn, not once per session: record 04's review, logged as its own
    turn ended, leaves the record the next turn writes to be reviewed, whoever started that turn."""
    attended.write_text(json.dumps({"ts": "2026-09-23T01:31:00+00:00", "session_id": worked_example.name, "decision": "clean",
                                    "record": str(worked_example / "turns" / "04.md")}) + "\n")
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05)
    later = appended(transcript, tmp_path / "t.jsonl", start)
    with_write(later, "Write", record)
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    run(payload(worked_example, later))
    assert str(record) in said_back(capsys)


def test_a_message_queued_after_the_record_was_written_leaves_it_to_be_reviewed(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A message queued mid-turn joins the turn it arrived in and starts none, so the record the
    turn wrote before it is still this turn's."""
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05)
    with_write(unrecorded, "Write", record)
    appended(unrecorded, unrecorded, QUEUED)
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    run(payload(worked_example, unrecorded))
    assert str(record) in said_back(capsys)


def test_an_old_record_the_transcript_never_writes_is_no_record_of_this_turn(
    worked_example: Path, unrecorded: Path, tmp_path: Path,
) -> None:
    """Record 03, last changed before this turn began and with no Write call in the transcript, as
    from before a /clear, is not taken for one written through the shell this turn: the long reply
    goes back to be moved onto 05."""
    without = tmp_path / "without-03.jsonl"
    without.write_text("".join(line for line in unrecorded.read_text().splitlines(keepends=True) if "/turns/03.md" not in line))
    decision = decide(payload(worked_example, without, reply=LONG), worked_example)
    assert decision.why == "answer in the chat"
    assert str(worked_example / "turns" / "05.md") in decision.reason and "03.md" not in decision.reason


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
    worked_example: Path, transcript: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The reviewer's input carries the earlier turn records and the user's messages, and no tool
    call: the transcript's Write calls and the task notifications that name a tool use carry ids
    starting `toolu_`. The record under review comes last, fenced, and the reviewer runs under
    its own system prompt, bound to the schema."""
    claude = fake_claude(tmp_path, monkeypatch, RESULT | {"structured_output": {"findings": [finding(IN_RECORD[0])]}})
    decision = decide(payload(worked_example, transcript), worked_example)
    assert decision.verb == "send back" and IN_RECORD[0] in decision.reason
    argv = (claude / "argv").read_text().split("\0")[:-1]
    prompt, system = (claude / "stdin").read_text(), argv[argv.index("--system-prompt") + 1]
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

# What claude's stream ends with, as ../run-log/test_run_log.py has it.
RESULT = {"type": "result", "subtype": "success", "is_error": False, "session_id": "sess-1", "num_turns": 1,
          "duration_ms": 4200, "duration_api_ms": 3900, "total_cost_usd": 0.0123,
          "usage": {"input_tokens": 22, "output_tokens": 70, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
          "result": ""}


def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: dict | None, then: str = "exit 0") -> Path:
    """The real reviewer, calling a `claude` first on PATH that records its argv and stdin, streams
    `result` as its last line, and does `then`; the run log is the check's own. Returns the
    directory holding the argv, the stdin and `runs.jsonl`."""
    where = tmp_path / "reviewer"
    where.mkdir()
    (where / "claude").write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\0" "$@" > "{where}/argv"\n'
        f'cat > "{where}/stdin"\n'
        + (f"echo {json.dumps(json.dumps(result))}\n" if result else "echo 'API Error: overloaded'\n")
        + f"{then}\n")
    (where / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{where}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RUN_LOG", str(where / "runs.jsonl"))
    monkeypatch.setattr(turn_review, "review", REVIEW)
    return where


def test_the_review_is_one_line_in_the_run_log_under_its_own_site(
    worked_example: Path, transcript: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    claude = fake_claude(tmp_path, monkeypatch, RESULT | {"structured_output": {"findings": []}})
    assert decide(payload(worked_example, transcript), worked_example).verb == "render"
    (line,) = map(json.loads, (claude / "runs.jsonl").read_text().splitlines())
    assert (line["site"], line["model"], line["effort"], line["cost_usd"], line["end"]) == (
        "turn-review", "claude-opus-5-5", "low", 0.0123, "success")


def test_a_reviewer_run_that_fails_is_still_one_line_in_the_run_log_and_the_page_renders(
    worked_example: Path, transcript: Path, monkeypatch: pytest.MonkeyPatch, attended: Path, tmp_path: Path,
) -> None:
    claude = fake_claude(tmp_path, monkeypatch, None, then="exit 1")
    assert decide(payload(worked_example, transcript), worked_example).verb == "render"
    (line,) = map(json.loads, (claude / "runs.jsonl").read_text().splitlines())
    assert (line["site"], line["exit"], line["end"]) == ("turn-review", 1, "no result")
    (entry,) = logged(attended, "decision")
    assert (entry["decision"], entry["why"]) == ("failed", "claude exited 1: API Error: overloaded")


def test_a_reviewer_past_its_limit_is_ended_with_its_line_written_and_the_page_renders(
    worked_example: Path, transcript: Path, monkeypatch: pytest.MonkeyPatch, attended: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr(turn_review, "REVIEWER_TIMEOUT_S", 1)
    claude = fake_claude(tmp_path, monkeypatch, None, then="exec sleep 30")
    assert decide(payload(worked_example, transcript), worked_example).verb == "render"
    (line,) = map(json.loads, (claude / "runs.jsonl").read_text().splitlines())
    assert (line["site"], line["exit"], line["end"]) == ("turn-review", "timeout", "no result")
    (entry,) = logged(attended, "decision")
    assert entry["decision"] == "failed" and entry["why"].startswith("claude ran past 1s")


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


def through_the_shell(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    hook = in_the_chat(example, transcript, fixtures)
    (example / "turns" / "05.md").write_text(RECORD_05)
    return hook


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
    "a record written through the shell": (through_the_shell, "send back", "record written outside Write", True),
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
    monkeypatch.setattr(turn_review, "LOG", tmp_path / "not-a-directory" / "log.jsonl")
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert shown(capsys)
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
