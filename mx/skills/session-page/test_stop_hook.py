# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision out,
with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md, its Properties and its Decisions on what the hook does with a turn,
and turns-end-on-their-recap's P3, every-session-gets-a-page's and pages-link-across-handoffs'
Properties, over the worked example in `fixtures/`, whose records a check corrupts one at a time.
The prose reviewer, which the hook never calls, is stubbed by conftest.py.
The browser is a stand-in `claude-browser` first on PATH that records what it was asked to open, and
for which session; the hub is absent unless a check starts a stand-in of it on a port of its own.
"""

import io
import json
import html
import os
import re
import socket
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

import session_page
import stop_hook
import turn_review
from conftest import BEFORE_IT, SPOKEN_AFTER, unreachable
from session_page import PAGE, PREVIOUS, SESSIONS, continued_from, render_session
from stop_hook import decide
from test_reading import messages_of

@pytest.fixture(autouse=True)
def browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A `claude-browser` first on PATH that appends each open it is asked for to the file handed
    back, as the session it was told and the path, so no check starts a browser. No hub answers on
    the port the hook asks, so no check reaches one running on the host."""
    where = tmp_path / "browser"
    where.mkdir()
    (where / "claude-browser").write_text(
        f'#!/usr/bin/env bash\nprintf \'%s\\t%s\\n\' "$MX_ORIGIN_SESSION" "$*" >> "{where}/opened"\n')
    (where / "claude-browser").chmod(0o755)
    monkeypatch.setenv("PATH", f"{where}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CONTAINER_HUB_PORT", str(closed_port()))
    return where / "opened"


def closed_port() -> int:
    """A port nothing listens on: one the system just handed out and took back."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def opened(record: Path, count: int) -> list[tuple[str, str]]:
    """What the stand-in browser was asked to open, as (session, path) in the order the opens
    landed, once `count` have landed or five seconds have passed: the hook starts each open and
    waits on none. An open beyond the count may land later, so what proves none was asked for is
    the log, which `main` writes before it returns."""
    deadline = time.monotonic() + 5
    while (len(record.read_text().splitlines()) if record.exists() else 0) < count and time.monotonic() < deadline:
        time.sleep(0.05)
    return [tuple(line.split("\t", 1)) for line in record.read_text().splitlines()] if record.exists() else []


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

# A reply of several lines, an answer that would fill a turn record.
LONG = "\n".join(f"Line {n} of an answer that belongs on the page." for n in range(1, 6))
TWENTY_LINES = "\n".join(f"Line {n} of where the work stands." for n in range(1, 21))

FRESH = "8e0f1c22-0000-0000-0000-000000000000"  # a session that has no directory yet
FIRST_PROMPT = {"type": "user", "message": {"role": "user", "content": "Carry on from the handoff."},
                "timestamp": "2026-10-05T09:00:00.000Z", "cwd": "/srv/helferline", "sessionId": FRESH}


@pytest.fixture
def first_turn(tmp_path: Path) -> tuple[Path, Path]:
    """A fresh session's directory, not yet there, in a project with an agent repo that has never had
    one, and the transcript of its first turn, which Claude Code has given a title of its own."""
    (tmp_path / "agent" / "tickets").mkdir(parents=True)
    said = tmp_path / "first.jsonl"
    titled = {"type": "ai-title", "aiTitle": "Helferline handoff continued", "sessionId": FRESH}
    said.write_text(json.dumps(FIRST_PROMPT) + "\n" + json.dumps(titled) + "\n")
    return tmp_path / SESSIONS / FRESH, said


FIRST_REPLIES = {"a one-line reply": "On it: reading the handoff.", "twenty lines": TWENTY_LINES}


@pytest.mark.parametrize("reply", FIRST_REPLIES.values(), ids=FIRST_REPLIES)
def test_a_sessions_first_turn_that_ends_on_a_reply_starts_its_page_with_that_reply(
    reply: str, first_turn: tuple[Path, Path], browser: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], attended: Path,
) -> None:
    """every-session-gets-a-page#P1 and P2: the hook creates the session's directory, writes the
    reply as its first chat turn, renders the page titled as Claude Code titles the session, and
    opens it as a first render does. Nothing is sent back, whatever the reply's length (P3)."""
    directory, said = first_turn
    run(payload(directory, said, reply=reply))
    assert capsys.readouterr().out == ""
    [chat] = chats(directory)
    assert chat.read_text().split("---\n", 2)[2].strip() == reply
    assert sorted(p.name for p in directory.iterdir()) == [PAGE, "turns"]
    page = (directory / PAGE).read_text()
    assert rows(page) == [chat.stem]
    assert "<title>Helferline handoff continued · session page</title>" in page
    assert opened(browser, 1) == [(FRESH, str(directory / PAGE))]
    assert [e["excluded"] for e in logged(attended, "excluded")] == ["not in a git repository"]


SAID_NOTHING = {"no text": "", "only blank lines": "\n  \n"}


@pytest.mark.parametrize("reply", SAID_NOTHING.values(), ids=SAID_NOTHING)
def test_a_first_turn_that_ends_on_no_text_creates_nothing(
    reply: str, first_turn: tuple[Path, Path], capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    directory, said = first_turn
    run(payload(directory, said, reply=reply))
    assert not directory.parent.exists()
    assert capsys.readouterr().out == ""


LEFT_ALONE = {"a dispatched worker": ("DISPATCH_WORKLOG", "/w/log"), "a print-mode session": ("CLAUDE_CODE_SESSION_ATTENDED", "0")}


@pytest.mark.parametrize("marker, value", LEFT_ALONE.values(), ids=LEFT_ALONE)
def test_a_session_nobody_reads_the_page_of_never_gets_a_directory(
    marker: str, value: str, first_turn: tuple[Path, Path], capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """every-session-gets-a-page#P4: its first reply, long or short, leaves no trace under `sessions/`."""
    monkeypatch.setenv(marker, value)
    directory, said = first_turn
    for reply in FIRST_REPLIES.values():
        run(payload(directory, said, reply=reply))
    assert not directory.parent.exists()
    assert capsys.readouterr().out == ""


@settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(lines=st.lists(st.text(st.characters(categories=["L", "N", "P", "Zs"]), min_size=1).filter(str.strip), min_size=1, max_size=60))
def test_a_reply_of_any_length_with_no_record_is_recorded_and_never_sent_back(
    lines: list[str], worked_example: Path, unrecorded: Path,
) -> None:
    """every-session-gets-a-page#P2 and P3, over generated replies in a session that has a page and
    a turn that wrote no record: the hook renders, and the chat turn it writes holds the reply."""
    reply = "\n".join(lines)
    decision = decide(payload(worked_example, unrecorded, reply=reply), worked_example)
    assert (decision.verb, decision.why) == ("render", "chat reply recorded")
    assert decision.chat[1].split("---\n", 2)[2].strip() == reply.strip()


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


def test_the_page_the_hook_writes_resolves_a_records_paths_from_the_repo_root(
    worked_example: Path, transcript: Path, run: Callable[[dict], None]
) -> None:
    """The page the hook writes is the renderer's, links included: an artefact carries the path the
    hub finds it by, and a path a record writes as code opens the file, both resolved from the repo
    root the records sit under."""
    root = worked_example.parents[len(SESSIONS.parts)]
    (root / "mx").mkdir()
    (root / "mx" / "tool.py").write_text("")
    newest = worked_example / "turns" / "04.md"
    newest.write_text(newest.read_text().replace("\n## Details\n\n", "\n## Details\n\nThe code is `mx/tool.py`.\n\n", 1))
    run(payload(worked_example, transcript))
    written = (worked_example / PAGE).read_text()
    assert f'{session_page.ARTEFACT}="{root}/agent/show/session-page/round-3/spec.html"' in written
    assert '<a class="path" href="../../../mx/tool.py"' in written


# ---- what a turn's end opens ------------------------------------------------


# Each is whether a hub answers, and how many of three renders open the page.
PAGE_OPENS = {"a hub that answers": (True, 3), "no hub": (False, 1)}


@pytest.mark.parametrize("answers, opens", PAGE_OPENS.values(), ids=PAGE_OPENS)
def test_the_page_opens_on_every_render_where_a_hub_answers_and_on_the_first_where_none_does(
    answers: bool, opens: int, worked_example: Path, unrecorded: Path, browser: Path, run: Callable[[dict], None],
    attended: Path, hub: Callable[[int], int],
) -> None:
    """stop-hook-opens-the-turns-artefacts and its D4: a render hands the page to `claude-browser`,
    told the session it belongs to, every time where the hub turns a repeat into a reload, and only
    the first time where no hub would, since a repeat would be another tab. The turns wrote no
    record, so the links record 04 carries, from a turn before, open nothing."""
    if answers:
        hub(200)
    for _ in range(3):
        run(payload(worked_example, unrecorded))
    page = str(worked_example / PAGE)
    assert opened(browser, opens) == [(worked_example.name, page)] * opens
    said = [(entry["page"], entry["opened"]) for entry in logged(attended, "opened")]
    assert [(where, what.startswith("started ")) for where, what in said[:opens]] == [(page, True)] * opens
    assert said[opens:] == [(page, "not reopened: no hub answers")] * (3 - opens)


# Each is the `## Links` a record written this turn carries, and the paths `claude-browser` is handed
# for them, from the repo root the session's directory sits under: a path from the root joined to
# it, an absolute or `~` path as it is, a URL as it is, and a fragment dropped, as the hub finds a
# page by its file, so a page opens once however many of its sections are linked. A ticket file
# is no artefact (session-pages-feed-the-hub#P2) and is handed none.
RECORD_LINKS = {
    "a page from the repo root": (["- [The spec](agent/show/x/spec.html): this round's"], ["{root}/agent/show/x/spec.html"]),
    "a section of a page": (["- [P1](agent/show/x/spec.html#p1)"], ["{root}/agent/show/x/spec.html"]),
    "two sections of one page": (["- [P1](agent/show/x/spec.html#p1)", "- [P2](agent/show/x/spec.html#p2)"],
                                 ["{root}/agent/show/x/spec.html"]),
    "a file outside the repo": (["- [The figure](/srv/figures/fig.svg)"], ["/srv/figures/fig.svg"]),
    "a file under home": (["- [Notes](~/notes/fig.html)"], ["{home}/notes/fig.html"]),
    "a URL": (["- [The run](http://127.0.0.1:8000/run?step=3)"], ["http://127.0.0.1:8000/run?step=3"]),
    "a ticket file": (["- [The ticket](agent/tickets/session-page.md)"], []),
    "a ticket file in another repo": (["- [The ticket](/srv/other/agent/tickets/one-hub-tab.md#d2)"], []),
    "several at once": (
        ["- [Pages](agent/show/x/pages.html): which page carries what", "- [The diff](agent/show/x/diff.html)",
         "- [The ticket](agent/tickets/session-page.md)"],
        ["{root}/agent/show/x/pages.html", "{root}/agent/show/x/diff.html"]),
    "no links": ([], []),
}


@pytest.mark.parametrize("links, handed", RECORD_LINKS.values(), ids=RECORD_LINKS)
def test_every_artefact_the_turns_record_links_is_handed_to_the_browser_as_the_sessions(
    links: list[str], handed: list[str], worked_example: Path, unrecorded: Path, browser: Path,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], attended: Path,
) -> None:
    """session-pages-feed-the-hub#P1, at the Stop hook's input: the record this turn wrote, its
    links in, and the `claude-browser` calls out, each told the session, beside the page's own on
    its first render. The log says what came of each."""
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05 + ("\n## Links\n\n" + "\n".join(links) + "\n" if links else ""))
    with_write(unrecorded, "Write", record)
    run(payload(worked_example, unrecorded))
    assert shown(capsys)
    root = worked_example.parents[len(SESSIONS.parts)]
    expected = [path.format(root=root, home=Path.home()) for path in handed]
    calls = opened(browser, len(expected) + 1)
    assert sorted(calls) == sorted([(worked_example.name, str(worked_example / PAGE))] + [(worked_example.name, path) for path in expected])
    assert [(entry["artefact"], entry["opened"].startswith("started ")) for entry in logged(attended, "artefact")] == [
        (path, True) for path in expected]


def test_a_later_turns_artefacts_open_where_no_hub_answers_and_the_page_does_not_reopen(
    worked_example: Path, unrecorded: Path, transcript: Path, browser: Path, run: Callable[[dict], None],
    attended: Path,
) -> None:
    """stop-hook-opens-the-turns-artefacts' D4 leaves a turn's artefacts out of it: with no hub, a
    render after the first hands `claude-browser` the artefact its turn linked and not the page."""
    run(payload(worked_example, transcript))
    first = len(opened(browser, 3))
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05 + "\n## Links\n\n- [The figure](/srv/figures/fig.svg)\n")
    with_write(unrecorded, "Write", record)
    run(payload(worked_example, unrecorded))
    assert opened(browser, first + 1)[first:] == [(worked_example.name, "/srv/figures/fig.svg")]
    assert [entry["opened"] for entry in logged(attended, "page")][-1] == "not reopened: no hub answers"


def test_a_page_already_there_is_rendered_and_not_reopened_where_no_hub_answers(
    worked_example: Path, transcript: Path, stale_page: str, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], attended: Path,
) -> None:
    """A page on disk that this hook did not write, a render of an older version say, is rendered
    over and, with no hub, not opened again; the turn's artefacts still open, and the line still
    shows under the recap."""
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert (worked_example / PAGE).read_text() != stale_page
    assert [entry["opened"] for entry in logged(attended, "page")] == ["not reopened: no hub answers"]
    assert [entry["artefact"] for entry in logged(attended, "artefact")] == [
        str(worked_example.parents[len(SESSIONS.parts)] / "agent/show/session-page/round-3" / page)
        for page in ("pages.html", "spec.html")]
    assert shown(capsys) == f"session page · waiting on you: Q7 · {(worked_example / PAGE).as_uri()}"


# ---- the hub ----------------------------------------------------------------


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[int], int]]:
    """Start a stand-in of the container hub on a port of its own, which answers every GET with the
    status given, and point the hook at that port. Hands back the port."""
    servers: list[ThreadingHTTPServer] = []

    def start(status: int) -> int:
        class Answer(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(status if self.path == "/.health" else 404)
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Answer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        monkeypatch.setenv("CONTAINER_HUB_PORT", str(server.server_port))
        return server.server_port

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


# Each is what answers the hub's health check, None for nothing on the port, and whether the line
# links the unit.
HUBS = {"a hub that answers": (200, True), "something else on the port": (404, False), "no hub": (None, False)}


@pytest.mark.parametrize("status, unit", HUBS.values(), ids=HUBS)
def test_the_hooks_line_links_the_sessions_unit_where_a_hub_answers_and_the_page_where_none_does(
    status: int | None, unit: bool, worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], hub: Callable[[int], int],
) -> None:
    """stop-hook-opens-the-turns-artefacts: the hub tab at the session's unit is
    `http://127.0.0.1:<port>/u/<session id>`, and the hub answers `GET /.health` when it runs;
    where nothing does, the line keeps the page's `file://` link."""
    port = hub(status) if status else None
    link = f"http://127.0.0.1:{port}/u/{worked_example.name}" if unit else (worked_example / PAGE).as_uri()
    run(payload(worked_example, transcript))
    assert shown(capsys) == f"session page · waiting on you: Q7 · {link}"


@pytest.fixture
def speaks_no_http() -> Iterator[int]:
    """Something on a port of its own that answers a request with a line that is no HTTP. Hands back
    the port."""
    server = socket.create_server(("127.0.0.1", 0))

    def answer() -> None:
        while True:
            try:
                connection, _ = server.accept()
            except OSError:
                return
            with connection:
                connection.recv(1024)
                connection.sendall(b"hello, this is no hub\r\n")

    threading.Thread(target=answer, daemon=True).start()
    yield server.getsockname()[1]
    server.close()


# Each hands back a hub port the health check cannot ask.
UNASKABLE = {
    "a port that is no number": lambda request: "abc",
    "something on the port that speaks no HTTP": lambda request: str(request.getfixturevalue("speaks_no_http")),
}


@pytest.mark.parametrize("port", UNASKABLE.values(), ids=UNASKABLE)
def test_a_hub_port_that_cannot_be_asked_is_no_hub(
    port: Callable[[pytest.FixtureRequest], str], worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, attended: Path,
) -> None:
    """The first render still opens the page, keeps `sessions/` out of the agent repo's status and
    links the page's file, as it does where nothing listens."""
    monkeypatch.setenv("CONTAINER_HUB_PORT", port(request))
    run(payload(worked_example, transcript))
    assert [entry["opened"].startswith("started ") for entry in logged(attended, "page")] == [True]
    assert logged(attended, "excluded")
    assert shown(capsys) == f"session page · waiting on you: Q7 · {(worked_example / PAGE).as_uri()}"


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


# ---- the sessions it leaves alone, and the reply in the chat ----------------


@pytest.mark.parametrize("marker, value", LEFT_ALONE.values(), ids=LEFT_ALONE)
def test_a_session_nobody_reads_the_page_of_is_left_alone(
    marker: str, value: str, worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither a broken record nor a long reply sends the agent back, and the page stays as it was."""
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


THREE_LINES = "\n\n".join(LONG.splitlines()[:3])


RENDERED = {
    "a long answer and a record": (False, LONG, False),
    "three lines and no record": (True, THREE_LINES, False),
    "a long answer and no record": (True, LONG, False),
    "a long answer sent back once already": (True, LONG, True),
}


@pytest.mark.parametrize("answered_in_chat, reply, again", RENDERED.values(), ids=RENDERED)
def test_every_other_turn_of_a_session_with_a_page_renders_it(
    answered_in_chat: bool, reply: str, again: bool, worked_example: Path, transcript: Path, request: pytest.FixtureRequest,
    stale_page: str, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """every-session-gets-a-page#P3: no turn is sent back for the length of its reply."""
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
    "a long answer": (LONG, False),
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


# ---- a chat turn ------------------------------------------------------------

ANSWERED_IN_THE_CHAT = {
    "a one-line answer": ("Yes, the second bank.", False),
    "three lines": (THREE_LINES, False),
    "twenty lines": (TWENTY_LINES, False),
    "a long answer sent back once already": (LONG, True),
    "a reply with a heading of its own": ("# Yes\n\nThe second bank, `ledger.py:12`.", False),
}
NUMBERED = ["01.md", "02.md", "03.md", "04.md"]  # the worked example's records
TURN_ID = re.compile(r'<(?:details|article) class="turn[^"]*" id="([^"]+)"')


def chats(directory: Path) -> list[Path]:
    """The chat turns' records in the session directory."""
    return sorted((directory / "turns").glob("chat-*.md"))


def rows(page: str) -> list[str]:
    """The ids of the page's turns, top to bottom."""
    return [i for _, i in sorted((m.start(), m.group(1)) for m in TURN_ID.finditer(page))]



@pytest.mark.parametrize("reply, again", ANSWERED_IN_THE_CHAT.values(), ids=ANSWERED_IN_THE_CHAT)
def test_a_turn_that_ends_on_a_chat_reply_and_wrote_no_record_gets_the_reply_as_a_chat_turn(
    reply: str, again: bool, worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None],
) -> None:
    """chat-replies-reach-the-page, as its D1 rules: the hook writes the reply as `turns/chat-<time>.md`,
    taking no number of the agent's records, its body the reply as it stood; the page shows it with
    no number, newest, with the user's message the transcript pairs with it, and the agent's newest
    record stays the turn open."""
    before = datetime.now(UTC).replace(microsecond=0)
    run(payload(worked_example, unrecorded, reply=reply, stop_hook_active=again))
    assert shown(capsys) == ""
    assert sorted(p.name for p in (worked_example / "turns").glob("[0-9]*.md")) == NUMBERED
    [chat] = chats(worked_example)
    assert before <= datetime.strptime(chat.name, "chat-%Y%m%dT%H%M%SZ.md").replace(tzinfo=UTC) <= datetime.now(UTC)
    front, body = chat.read_text().split("---\n", 2)[1:]
    assert [line.split(": ")[0] for line in front.splitlines()] == ["date", "chat"]
    assert body.strip() == reply.strip()
    page = (worked_example / PAGE).read_text()
    assert rows(page) == [chat.stem, "t04", "t03", "t02", "t01"]
    row = page[page.index(f'id="{chat.stem}"'):]
    row = row[:row.index("</article>")]
    assert '<span class="rail"></span>' in row
    assert html.unescape(re.findall(r'<div class="msg"><p>(.*?)</p>', row)[0]) == SPOKEN_AFTER["message"]["content"]
    assert '<details class="turn blk" id="t04" data-block open>' in page


@pytest.mark.parametrize("reply", SAID_NOTHING.values(), ids=SAID_NOTHING)
def test_a_turn_that_ends_on_no_text_writes_no_record_and_still_renders(
    reply: str, worked_example: Path, unrecorded: Path, stale_page: str, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None],
) -> None:
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, unrecorded, reply=reply))
    assert shown(capsys) == ""
    assert sorted(p.name for p in (worked_example / "turns").glob("*.md")) == NUMBERED
    assert (worked_example / PAGE).read_text() != stale_page


def test_a_record_written_through_the_shell_is_the_turns_and_no_chat_turn_is_added(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """A turn that wrote a record, if not with Write, wrote one: its short reply is no record of its own."""
    (worked_example / "turns" / "05.md").write_text(RECORD_05)
    run(payload(worked_example, unrecorded, reply="Round 4 is on the page."))
    capsys.readouterr()
    assert chats(worked_example) == []


def test_the_turn_after_a_chat_turn_numbers_on_from_the_agents_own_last_record(
    worked_example: Path, unrecorded: Path, tmp_path: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """D1's point: no record the agent writes can land on a chat turn. After one, the agent's next
    record is 05, the number after its own 04, written with Write; it is that turn's, shown under
    its recap above the chat turn, which keeps its reply."""
    run(payload(worked_example, unrecorded, reply="Yes, the second bank."))
    capsys.readouterr()
    [chat] = chats(worked_example)
    later = {"type": "user", "message": {"role": "user", "content": "And the third?"},
             "timestamp": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()}
    next_turn = appended(unrecorded, tmp_path / "next.jsonl", later)
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05)
    call = {"type": "tool_use", "id": "toolu_05", "name": "Write", "input": {"file_path": str(record)}}
    appended(next_turn, next_turn, {"type": "assistant", "message": {"role": "assistant", "content": [call]},
                                    "timestamp": (datetime.now(UTC) + timedelta(minutes=2)).isoformat()})
    run(payload(worked_example, next_turn, reply="Round 4 is on the page."))
    assert shown(capsys).startswith("session page · ")
    page = (worked_example / PAGE).read_text()
    assert rows(page) == ["t05", chat.stem, "t04", "t03", "t02", "t01"]
    assert messages_of(page)["05"] == ["And the third?"]
    assert "Yes, the second bank." in chat.read_text()


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
    its write call in the transcript, as the page pairs messages. One written through the shell goes
    back once naming that record, to be written again with Write (that ticket's D1), whatever the
    reply beside it, and the turn the Stop hook continued renders; written with Write, it carries
    the user's message."""
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05)
    for reply in ("Round 4 is on the page.", LONG):
        run(payload(worked_example, unrecorded, reply=reply))
        said = said_back(capsys)
        assert str(record) in said and "Write" in said and "06.md" not in said
    run(payload(worked_example, unrecorded, reply=LONG, stop_hook_active=True))
    assert capsys.readouterr().out == ""
    assert "Round 4" in (worked_example / PAGE).read_text()
    with_write(unrecorded, "Write", record)
    assert messages_of(render_session(worked_example, unrecorded))["05"] == [SPOKEN_AFTER["message"]["content"]]


def test_a_turn_that_answers_by_editing_an_earlier_record_gets_its_reply_as_a_chat_turn(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """stop-hook-reads-writes-from-the-transcript-only's D2: the page keeps a record's earliest write,
    so an Edit of record 04 after the user spoke writes no record this turn, and the reply is
    recorded as a chat turn."""
    record = worked_example / "turns" / "04.md"
    record.write_text(record.read_text() + "\n- Edited this turn to answer the question.\n")
    with_write(unrecorded, "Edit", record)
    run(payload(worked_example, unrecorded, reply=LONG))
    assert shown(capsys) == ""
    assert len(chats(worked_example)) == 1


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
def test_a_turn_the_user_did_not_start_still_records_its_reply_as_a_chat_turn(
    start: dict, worked_example: Path, transcript: Path, tmp_path: Path,
) -> None:
    """This turn runs from the prompt that started it, whoever sent it: record 04, written in the
    turn before, is no record of a turn a finished task or a hand-back started, so its reply is
    this turn's chat turn."""
    for record in (worked_example / "turns").iterdir():
        os.utime(record, (BEFORE_IT, BEFORE_IT))
    decision = decide(payload(worked_example, appended(transcript, tmp_path / "t.jsonl", start), reply=LONG), worked_example)
    assert (decision.verb, decision.why) == ("render", "chat reply recorded")


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
    from before a /clear, is not taken for one written through the shell this turn: the reply is
    recorded as a chat turn."""
    without = tmp_path / "without-03.jsonl"
    without.write_text("".join(line for line in unrecorded.read_text().splitlines(keepends=True) if "/turns/03.md" not in line))
    decision = decide(payload(worked_example, without, reply=LONG), worked_example)
    assert decision.why == "chat reply recorded"


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
    return payload(example.parent / FRESH, transcript)


def first_reply(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example.parent / FRESH, transcript, reply="On it.")


def unparsed(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    (example / "turns" / "04.md").write_text("no frontmatter\n")
    return payload(example, transcript)


def through_the_shell(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    hook = payload(example, fixtures.getfixturevalue("unrecorded"), reply=LONG)
    (example / "turns" / "05.md").write_text(RECORD_05)
    return hook


def no_record(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, fixtures.getfixturevalue("unrecorded"))


def chat_reply(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, fixtures.getfixturevalue("unrecorded"), reply="Yes, the second bank.")


def reviewed(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    """The record's Write had it reviewed, as the write hook logs it."""
    fixtures.getfixturevalue("attended").write_text(json.dumps(REVIEWED_04 | {"session_id": example.name}) + "\n")
    return payload(example, transcript)


def not_reviewed(example: Path, transcript: Path, fixtures: pytest.FixtureRequest) -> dict:
    return payload(example, transcript)


# Each path the hook takes, and the line it logs for it: the verb, why, and whether it resolved a
# session directory. The four that allow are the ones that look the same from outside.
PATHS = {
    "a dispatched worker": (worker, "allow", "dispatched worker", True),
    "a print-mode session": (print_mode, "allow", "print-mode session", True),
    "a directory in no project": (in_no_project, "allow", "no project with an agent repo", False),
    "a session with no directory that said nothing": (with_no_directory, "allow", "no session directory", True),
    "a session's first reply": (first_reply, "render", "chat reply recorded", True),
    "a record that does not parse": (unparsed, "send back", "record does not parse", True),
    "a record written through the shell": (through_the_shell, "send back", "record written outside Write", True),
    "a turn that wrote no record": (no_record, "render", "no record written this turn", True),
    "a chat reply and no record": (chat_reply, "render", "chat reply recorded", True),
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


SENT_BACK_AT_THE_END = {"a record that does not parse": unparsed, "a record written through the shell": through_the_shell}


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
    """turns-end-on-their-recap#P4 as recap-states-action-items amends it: what waits on the user,
    as action items, one plain line each, each open question named by what it decides, and no
    pointer to the page. A phrase pin: each part is RECAP's own wording of the ticket's."""
    for part in ("what waits on the user", "action items", "one plain line each", "named by what it decides",
                 "no line points at the page"):
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


# ---- pages across handoffs ----------------------------------------------------

BEFORE = "46944b2a-c996-4889-b308-48c1d884a675"  # the session that wrote the handoff


def handoff_read(path: str, front: str, start: int = 1) -> dict:
    """The transcript entry Claude Code writes for a Read of `path`, the file returned as read; a
    handoff's frontmatter is `front`."""
    content = f"---\n{front}\n---\n\n# Carry the ledger work on\n"
    return {"type": "user", "timestamp": "2026-10-05T09:00:05.000Z",
            "message": {"role": "user", "content": [{"tool_use_id": "toolu_1", "type": "tool_result", "content": content}]},
            "toolUseResult": {"type": "text", "file": {"filePath": path, "content": content, "startLine": start}}}


HANDOFF = "/srv/helferline/agent/handoffs/2026-10-05-ledger.md"
PICKUP = "git -C /srv/helferline/agent rm handoffs/2026-10-05-ledger.md && git -C /srv/helferline/agent commit -m 'pick up the ledger handoff'"


def bash(command: str, error: bool = False, call: str = "toolu_2") -> list[dict]:
    """The transcript entries Claude Code writes for a Bash call of `command` and its result."""
    return [{"type": "assistant", "timestamp": "2026-10-05T09:00:06.000Z",
             "message": {"role": "assistant", "content": [{"type": "tool_use", "id": call, "name": "Bash", "input": {"command": command}}]}},
            {"type": "user", "timestamp": "2026-10-05T09:00:07.000Z",
             "message": {"role": "user", "content": [{"tool_use_id": call, "type": "tool_result", "content": "", "is_error": error}]}}]


@pytest.fixture
def handed_over(first_turn: tuple[Path, Path], run: Callable[[dict], None], capsys: pytest.CaptureFixture) -> Callable[..., Path]:
    """The session `BEFORE`, which has a page and its transcript beside the fresh session's, and a
    way to have the fresh session's first turn read a handoff, as a frontmatter, and end on a reply.
    Hands back the directory of `BEFORE`."""
    directory, said = first_turn
    before = directory.parent / BEFORE
    theirs = said.parent / f"{BEFORE}.jsonl"
    theirs.write_text(json.dumps(FIRST_PROMPT | {"sessionId": BEFORE}) + "\n")
    run(payload(before, theirs, reply="Writing the handoff."))
    capsys.readouterr()

    def read(front: str, path: str = HANDOFF, then: list[dict] | None = None, **entry: object) -> Path:
        """The handoff at `path` read, and `then` after it: by default the `git rm` that picks it up."""
        with said.open("a") as f:
            for e in [handoff_read(path, front, **entry), *(bash(PICKUP) if then is None else then)]:
                f.write(json.dumps(e) + "\n")
        run(payload(directory, said, reply="On it."))
        capsys.readouterr()
        return before

    return read


def links_to(page: Path) -> list[str]:
    return re.findall(r'href="\.\./([^"/]+)/index\.html"', page.read_text())


def test_a_session_that_picked_up_a_continuation_handoff_links_to_the_page_before_and_back(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path],
) -> None:
    """pages-link-across-handoffs#P1: a session that read a continuation handoff and then `git rm`'d
    it gets `previous`, naming the session that wrote the handoff; its page links to that one's,
    and that one's, rendered again, links forward; each link resolves on disk."""
    directory, _ = first_turn
    before = handed_over(f"session: {BEFORE}\npurpose: continuation")
    assert (directory / PREVIOUS).read_text().strip() == BEFORE
    assert links_to(directory / PAGE) == [BEFORE]
    assert links_to(before / PAGE) == [FRESH]
    assert (directory / PAGE).parent.joinpath(f"../{BEFORE}/{PAGE}").resolve() == (before / PAGE).resolve()


NO_LINK = {
    "a fork's handoff": (f"session: {BEFORE}\npurpose: fork", {}),
    "a handoff the session wrote itself": (f"session: {FRESH}\npurpose: continuation", {}),
    "a file outside agent/handoffs": (f"session: {BEFORE}\npurpose: continuation", {"path": "/srv/helferline/agent/tickets/ledger.md"}),
    "a read that starts past the frontmatter": (f"session: {BEFORE}\npurpose: continuation", {"start": 40}),
    "a session id that is no id": ("session: ../../etc\npurpose: continuation", {}),
    "frontmatter that is not YAML": (f"session: [{BEFORE}\npurpose: continuation", {}),
    "a handoff only read": (f"session: {BEFORE}\npurpose: continuation", {"then": []}),
    "a git rm of another handoff": (f"session: {BEFORE}\npurpose: continuation", {"then": bash("git rm agent/handoffs/2026-10-04-ledger.md")}),
    "a plain rm": (f"session: {BEFORE}\npurpose: continuation", {"then": bash("rm agent/handoffs/2026-10-05-ledger.md")}),
}


@pytest.mark.parametrize("front, entry", NO_LINK.values(), ids=NO_LINK)
def test_a_handoff_that_continues_no_other_session_links_nothing(
    front: str, entry: dict, handed_over: Callable[..., Path], first_turn: tuple[Path, Path],
) -> None:
    """pages-link-across-handoffs#P2, and the reads that are no pickup of another session's handoff."""
    directory, _ = first_turn
    before = handed_over(front, **entry)
    assert not (directory / PREVIOUS).exists()
    assert links_to(directory / PAGE) == links_to(before / PAGE) == []


def test_previous_is_written_once(handed_over: Callable[..., Path], first_turn: tuple[Path, Path]) -> None:
    """A `previous` already there stays, whatever handoff the session reads after it was written."""
    directory, _ = first_turn
    handed_over(f"session: {BEFORE}\npurpose: fork")
    earlier = "0d1e2f3a-0000-0000-0000-000000000000"
    (directory / PREVIOUS).write_text(earlier + "\n")
    handed_over(f"session: {BEFORE}\npurpose: continuation")
    assert (directory / PREVIOUS).read_text().strip() == earlier


CONTINUATION = f"session: {BEFORE}\npurpose: continuation"

PATH_FORMS = {
    "the absolute path": f"git rm {HANDOFF}",
    "relative to the agent repo, through -C": PICKUP,
    "relative to the project": "git rm -q agent/handoffs/2026-10-05-ledger.md",
    "from inside the handoffs directory": "cd agent/handoffs && git rm 2026-10-05-ledger.md",
    "quoted, from a sibling directory": "git rm '../agent/handoffs/2026-10-05-ledger.md'",
    "one of several, in a script": "git status\ngit rm --cached agent/handoffs/old.md agent/handoffs/2026-10-05-ledger.md; git commit -m 'rm handoffs'",
}


@pytest.mark.parametrize("command", PATH_FORMS.values(), ids=PATH_FORMS)
def test_a_git_rm_names_the_handoff_in_any_path_form(command: str) -> None:
    assert continued_from([handoff_read(HANDOFF, CONTINUATION), *bash(command)], FRESH) == BEFORE


def test_an_absolute_path_with_shell_word_breaks_in_it_names_the_handoff() -> None:
    handoff = "/home/u/work@2+x:y/agent/handoffs/2026-10-05-ledger.md"
    assert continued_from([handoff_read(handoff, CONTINUATION), *bash(f"git rm {handoff}")], FRESH) == BEFORE


def test_a_git_rm_whose_chained_commit_failed_is_a_pickup() -> None:
    """The rm took before the commit failed, and the retry commits without naming the handoff."""
    assert continued_from([handoff_read(HANDOFF, CONTINUATION), *bash(PICKUP, error=True)], FRESH) == BEFORE


def test_a_git_rm_before_the_read_is_no_pickup() -> None:
    assert continued_from([*bash(PICKUP), handoff_read(HANDOFF, CONTINUATION)], FRESH) == ""


def test_of_two_continuation_handoffs_picked_up_the_first_read_is_the_predecessor() -> None:
    other = "0d1e2f3a-0000-0000-0000-000000000000"
    reads = [handoff_read(f"/p/agent/handoffs/{n}.md", f"session: {s}\npurpose: continuation") for n, s in ((1, BEFORE), (2, other))]
    both = bash("git rm /p/agent/handoffs/1.md /p/agent/handoffs/2.md")
    assert continued_from([*reads, *both], FRESH) == BEFORE
    assert continued_from([*reads[::-1], *both], FRESH) == other


def test_a_handoff_only_read_gives_way_to_one_picked_up_after_it() -> None:
    """A session that reads a handoff to look at it and then picks up another continues the other."""
    other = "0d1e2f3a-0000-0000-0000-000000000000"
    entries = [handoff_read("/p/agent/handoffs/1.md", CONTINUATION),
               handoff_read("/p/agent/handoffs/2.md", f"session: {other}\npurpose: continuation"), *bash("git rm agent/handoffs/2.md")]
    assert continued_from(entries, FRESH) == other


def test_a_predecessor_with_no_page_is_recorded_and_not_linked(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path], attended: Path,
) -> None:
    """A handoff written by a session that has no page here, one from before every session had one
    or from another machine: `previous` names it, the page links nowhere, and the log says why."""
    directory, _ = first_turn
    gone = "0d1e2f3a-0000-0000-0000-000000000000"
    handed_over(f"session: {gone}\npurpose: continuation")
    assert (directory / PREVIOUS).read_text().strip() == gone
    assert links_to(directory / PAGE) == []
    assert [(e["previous"], e["rendered"]) for e in logged(attended, "previous")] == [(gone, "no session directory")]


def test_a_handoff_two_sessions_picked_up_links_forward_to_both(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path], run: Callable[[dict], None], capsys: pytest.CaptureFixture,
) -> None:
    """One handoff split into several: the page before links forward to every session that picked
    it up."""
    directory, said = first_turn
    front = f"session: {BEFORE}\npurpose: continuation"
    before = handed_over(front)
    second = "0a0b0c0d-0000-0000-0000-000000000000"
    theirs = said.parent / f"{second}.jsonl"
    theirs.write_text("".join(json.dumps(e) + "\n" for e in [FIRST_PROMPT | {"sessionId": second}, handoff_read(HANDOFF, front), *bash(PICKUP)]))
    run(payload(directory.parent / second, theirs, reply="On it."))
    capsys.readouterr()
    assert links_to(before / PAGE) == sorted([FRESH, second])


def test_a_predecessor_with_no_transcript_beside_it_is_logged_and_links_forward_at_its_next_render(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path], run: Callable[[dict], None],
    capsys: pytest.CaptureFixture, attended: Path,
) -> None:
    """pages-link-across-handoffs' Decisions: with no transcript there, the hook logs that and the
    forward link waits for the predecessor's next render."""
    directory, said = first_turn
    theirs = said.parent / f"{BEFORE}.jsonl"
    kept = theirs.read_text()
    theirs.unlink()
    before = handed_over(f"session: {BEFORE}\npurpose: continuation")
    assert links_to(directory / PAGE) == [BEFORE]
    assert links_to(before / PAGE) == []
    [entry] = logged(attended, "previous")
    assert entry["previous"] == BEFORE and entry["rendered"].startswith(f"no transcript at {theirs}")
    theirs.write_text(kept)
    run(payload(before, theirs, reply="Still here."))
    capsys.readouterr()
    assert links_to(before / PAGE) == [FRESH]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
