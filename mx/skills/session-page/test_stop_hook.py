# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision out,
with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md, its Properties and its Decisions on what the hook does with a turn,
and turns-end-on-their-recap's P3, over the worked example in `fixtures/`, whose records a check
corrupts one at a time. The prose reviewer, which the hook never calls, is stubbed by conftest.py.
The browser is a stand-in `claude-browser` first on PATH that records what it was asked to open.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import session_page
import stop_hook
import turn_review
from conftest import BEFORE_IT, SPOKEN_AFTER, unreachable
from session_page import PAGE, SESSIONS, render_session
from stop_hook import decide
from test_reading import messages_of

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


def said_back(capsys: pytest.CaptureFixture) -> str:
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


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
    "by its .gitignore": (".gitignore", "sessions/"),
    "by its exclude file": (".git/info/exclude", "sessions/"),
    "by a pattern over what it holds": (".gitignore", "sessions/*"),
}


@pytest.mark.parametrize("where, pattern", ALREADY_IGNORED.values(), ids=ALREADY_IGNORED)
def test_an_agent_repo_that_already_ignores_sessions_gets_no_line_added(
    where: str, pattern: str, worked_example: Path, transcript: Path, run: Callable[[dict], None], attended: Path,
) -> None:
    agent = worked_example.parents[1]
    git(agent, "init")
    (agent / where).parent.mkdir(parents=True, exist_ok=True)
    (agent / where).write_text(f"reviews/\n{pattern}\n")
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


FOUR_LINES = "\n".join(LONG.splitlines()[:4])
THREE_LINES = "\n\n".join(LONG.splitlines()[:3])


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


# ---- no review at the turn's end --------------------------------------------


REVIEWED_04 = {"ts": "2026-09-23T01:31:00+00:00", "decision": "feedback", "findings": [], "record": "04.md"}
TURNS_WITH_A_RECORD = {"a record the write hook reviewed": True, "a record not reviewed this turn": False}


@pytest.mark.parametrize("reviewed", TURNS_WITH_A_RECORD.values(), ids=TURNS_WITH_A_RECORD)
def test_the_turns_end_runs_no_review(
    reviewed: bool, worked_example: Path, transcript: Path, stale_page: str, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """turns-end-on-their-recap#P3: the review ran when the record was written, or not at all, and a
    turn that wrote a record renders with the hook's line under the recap either way. The log says
    which of the two it was."""
    if reviewed:
        attended.write_text(json.dumps(REVIEWED_04 | {"session_id": worked_example.name}) + "\n")
    monkeypatch.setattr(turn_review, "review", unreachable)
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript, reply="Round 3 is on the page.\nQ7, what reviews a turn's prose, waits on you."))
    assert shown(capsys)
    assert (worked_example / PAGE).read_text() != stale_page
    assert logged(attended, "verb")[-1]["why"] == ("record reviewed this turn" if reviewed else "record not reviewed this turn")


def test_the_records_as_the_turn_ended_are_logged_beside_their_review(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None], attended: Path,
) -> None:
    """The review's line, from the record's Write, and the turn's end line after the agent revised
    the record and the session record, paired by session id, show which flagged passages the agent
    kept."""
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05)
    with_write(unrecorded, "Write", record)
    call = {"type": "tool_use", "id": "toolu_Edit_session", "name": "Edit", "input": {"file_path": str(worked_example / "session.md")}}
    appended(unrecorded, unrecorded, {"type": "assistant", "message": {"role": "assistant", "content": [call]}, "timestamp": "2026-09-23T01:35:30.000Z"})
    attended.write_text(json.dumps({"ts": "2026-09-23T01:36:01+00:00", "session_id": worked_example.name, "decision": "feedback",
                                    "record": str(record), "text": RECORD_05}) + "\n")
    revised = RECORD_05.replace("The second bank.", "The second bank, revised.")
    record.write_text(revised)
    run(payload(worked_example, unrecorded))
    assert shown(capsys)
    assert logged(attended, "decision")[-1] | {"ts": ""} == {
        "ts": "", "session_id": worked_example.name, "decision": "turn end", "record": str(record), "text": revised,
        "session_record": (worked_example / "session.md").read_text()}


# ---- which turn a record belongs to ------------------------------------------

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


def test_a_message_queued_after_the_record_was_written_leaves_it_this_turns(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """A message queued mid-turn joins the turn it arrived in and starts none, so the record the
    turn wrote before it is still this turn's: the long reply beside it is not sent back, and the
    turn ends on the hook's line."""
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05)
    with_write(unrecorded, "Write", record)
    appended(unrecorded, unrecorded, QUEUED)
    run(payload(worked_example, unrecorded, reply=LONG))
    assert shown(capsys)


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


def no_record(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, fixtures.getfixturevalue("unrecorded"))


def reviewed(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    """The record's Write had it reviewed, as the write hook logs it."""
    fixtures.getfixturevalue("attended").write_text(json.dumps(REVIEWED_04 | {"session_id": example.name}) + "\n")
    return payload(example, transcript)


def not_reviewed(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
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
    "a turn that wrote no record": (no_record, "render", "no record written this turn", True),
    "a record reviewed when it was written": (reviewed, "render", "record reviewed this turn", True),
    "a record not reviewed this turn": (not_reviewed, "render", "record not reviewed this turn", True),
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


SENT_BACK_AT_THE_END = {"a record that does not parse": unparsed, "an answer in the chat": in_the_chat,
                        "a record written through the shell": through_the_shell}


@pytest.mark.parametrize("arrange", SENT_BACK_AT_THE_END.values(), ids=SENT_BACK_AT_THE_END)
def test_what_the_turns_end_still_sends_back_asks_for_the_recap(
    arrange: Callable, worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], request: pytest.FixtureRequest,
) -> None:
    """turns-end-on-their-recap#P3 and P4: the records the write hook never saw are still checked
    at the turn's end, and the send-back asks the turn to end on its recap."""
    run(arrange(worked_example, transcript, request))
    said = said_back(capsys)
    assert stop_hook.RECAP in said and "without a reply" not in said


def test_the_recap_every_send_back_asks_for_is_the_one_the_ticket_states() -> None:
    """turns-end-on-their-recap#P4, in its own words: at most three lines, what the page holds now,
    what comes next and what waits on the user, each open question named by what it decides."""
    for part in ("3 short lines at most", "what the page holds now", "what comes next", "what waits on the user",
                 "named by what it decides"):
        assert part in stop_hook.RECAP


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
