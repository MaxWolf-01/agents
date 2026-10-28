# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision out,
with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md, its Properties and its Decisions on what the hook does with a turn,
and turns-end-on-their-recap's P3, every-session-gets-a-page's and pages-link-across-handoffs'
Properties, over the worked example in `fixtures/`, whose records a check corrupts one at a time.
The prose reviewer, which the hook never calls, is stubbed by conftest.py.
The browser is a stand-in `claude-browser` first on PATH that records what it was asked to open, and
for which session; the hub is absent unless a check starts a stand-in of it on a socket of its own.
"""

import io
import json
import os
import re
import select
import socket
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

import session_page
import stop_hook
import turn_review
from live_hook import LIVE
from session_checks import (
    BEFORE_IT, DRAWN, LEFT_ALONE, LISTS_A_QUESTION, LONG, SPOKEN_AFTER, TASK_DONE, TURN_ANCHOR, TURN_ENDED, TURN_STARTS,
    UNPARSEABLE, appended, asked_in_order, elements, logged, messages_of, payload, project_of, sessions, turns_on, unreachable,
    view_of, with_write, write_tickets,
)
from session_checks import record as drawn_record
from session_page import AGENT_REPO, LOG, PAGE, PREVIOUS, SESSIONS, pages_directory
from stop_hook import decide


@pytest.fixture
def sockets() -> Iterator[Path]:
    """A directory of its own whose path is short enough for a unix socket in it, which a test's
    tmp_path may not be."""
    where = Path(tempfile.mkdtemp(prefix="hub."))
    yield where
    shutil.rmtree(where, ignore_errors=True)


@pytest.fixture(autouse=True)
def browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sockets: Path) -> Iterator[Path]:
    """A `claude-browser` first on PATH that appends each open it is asked for to the file handed
    back, as the session it was told and the path, so no check starts a browser, then says so down
    the pipe beside it. No hub answers on the socket the hook asks, so no check reaches one running
    on the host."""
    where = tmp_path / "browser"
    where.mkdir()
    os.mkfifo(where / "landed")
    (where / "claude-browser").write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        f"with open({str(where / 'opened')!r}, 'a') as record:\n"
        "    record.write(os.environ['MX_ORIGIN_SESSION'] + '\\t' + ' '.join(sys.argv[1:]) + '\\n')\n"
        "try:\n"
        f"    os.write(os.open({str(where / 'landed')!r}, os.O_WRONLY | os.O_NONBLOCK), b'.')\n"
        "except OSError:\n"
        "    pass  # the check that would read it is over\n")
    (where / "claude-browser").chmod(0o755)
    monkeypatch.setenv("PATH", f"{where}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CONTAINER_HUB_SOCKET", str(sockets / "hub.sock"))
    # Held for the check's length: a read end, so the stand-in's write lands, and a write end, so
    # the pipe reads as empty between opens rather than as closed.
    ends = os.open(where / "landed", os.O_RDONLY | os.O_NONBLOCK), os.open(where / "landed", os.O_WRONLY)
    yield where / "opened"
    for end in ends:
        os.close(end)


def opened(record: Path, count: int) -> list[tuple[str, str]]:
    """What the stand-in browser was asked to open, as (session, path) in the order the opens
    landed, once `count` have landed: the hook starts each open and waits on none. An open beyond
    the count may land later, so what proves none was asked for is the log, which `main` writes
    before it returns."""

    def landed() -> list[tuple[str, str]]:
        return [tuple(line.split("\t", 1)) for line in record.read_text().splitlines()] if record.exists() else []

    pipe = os.open(record.parent / "landed", os.O_RDONLY | os.O_NONBLOCK)
    try:
        while len(landed()) < count and select.select([pipe], [], [], 60)[0]:
            os.read(pipe, 4096)
    finally:
        os.close(pipe)
    return landed()


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict], None]:
    """Call the hook the way Claude Code does, on the payload given."""

    def call(payload: dict) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        stop_hook.main()

    return call


def shown(capsys: pytest.CaptureFixture) -> str:
    """The line the hook showed the user as the turn ended, empty where it showed none. A turn the
    hook sent back fails the check."""
    out = capsys.readouterr().out
    if not out:
        return ""
    said = json.loads(out)
    assert "hookSpecificOutput" not in said, f"the turn was sent back: {said}"
    return said["systemMessage"]


def first_line(message: str) -> str:
    """The line of the hook's message that links the page; the open questions follow it."""
    return message.splitlines()[0]


def said_back(capsys: pytest.CaptureFixture) -> str:
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


def git(where: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def test_a_session_keeps_its_page_in_one_directory_whichever_worktree_it_ran_in(
    worked_example: Path, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, transcript: Path,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Where the Decisions put a session's records, pinned as literals: `session-pages/<id>` under
    the account's directory, outside every checkout, tied to the agent repo in the main checkout,
    from the code repo's main checkout, from a linked worktree of it, which holds no `agent/`, and
    from inside the agent repo. The command the show skill has the agent run prints that directory
    from each, and the hook renders the page there. A session with no directory yet in no project
    with an agent repo gets none, and the command says so."""
    main, worktree = tmp_path / "ledger", tmp_path / "ledger-map-columns"
    (main / "agent" / "tickets").mkdir(parents=True)
    git(main, "init", "-q")
    git(main, "commit", "-q", "--allow-empty", "-m", "start")
    git(main, "worktree", "add", "-q", str(worktree))
    git(main / "agent", "init", "-q")
    directory = tmp_path / "claude-config/session-pages" / worked_example.name
    assert directory == worked_example
    (directory / AGENT_REPO).unlink()  # its records, not yet tied to the agent repo
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", worked_example.name)
    monkeypatch.setattr(sys, "argv", ["session-page"])
    for cwd in (main, worktree, main / "agent" / "tickets"):
        monkeypatch.chdir(cwd)
        session_page.main()
        assert capsys.readouterr().out.splitlines()[0] == str(directory), cwd
        assert (directory / AGENT_REPO).read_text() == f"{main / 'agent'}\n", cwd
        (directory / PAGE).unlink(missing_ok=True)
        run(payload(directory, transcript) | {"cwd": str(cwd)})
        assert (directory / PAGE).is_file(), cwd
        assert first_line(shown(capsys)).endswith((directory / PAGE).as_uri()), cwd
    assert not (worktree / "agent").exists()
    assert not (main / "agent" / "sessions").exists()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "8e0f1c22-0000-0000-0000-000000000000")
    monkeypatch.chdir(tmp_path_factory.mktemp("loose"))
    with pytest.raises(SystemExit, match="in no project with an agent repo"):
        session_page.main()
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    with pytest.raises(SystemExit, match="no session id"):
        session_page.main()


# ---- properties -------------------------------------------------------------

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
    return pages_directory(session_page.account(), FRESH), said


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
    assert sorted(p.name for p in directory.iterdir()) == [AGENT_REPO, PAGE, LOG, "turns"]
    page = (directory / PAGE).read_text()
    assert rows(page) == [chat.stem]
    assert "<title>Helferline handoff continued · session page</title>" in page
    assert opened(browser, 1) == [(FRESH, str(directory / PAGE))]


SAID_NOTHING = {"no text": "", "only blank lines": "\n  \n"}


@pytest.mark.parametrize("reply", SAID_NOTHING.values(), ids=SAID_NOTHING)
def test_a_first_turn_that_ends_on_no_text_creates_nothing(
    reply: str, first_turn: tuple[Path, Path], capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    directory, said = first_turn
    run(payload(directory, said, reply=reply))
    assert not directory.parent.exists()
    assert capsys.readouterr().out == ""


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


def test_a_turn_that_ends_drops_its_live_calls_and_one_sent_back_keeps_them(
    worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """The live file shows a turn while it runs: a turn sent back runs on, and one that ends is on
    the page the hook just rendered."""
    live = worked_example / LIVE
    live.write_text('window.liveCalls = {"prompt": "", "steps": []}\n')
    newest = worked_example / "turns" / "04.md"
    record = newest.read_text()
    newest.write_text(UNPARSEABLE["no headline"][1])
    run(payload(worked_example, transcript))
    assert "hookSpecificOutput" in json.loads(capsys.readouterr().out) and live.exists()
    newest.write_text(record)
    run(payload(worked_example, transcript))
    shown(capsys)
    assert not live.exists()


def test_a_session_that_needed_a_page_has_one_beside_its_records(
    worked_example: Path, transcript: Path, stale_page: str, run: Callable[[dict], None]
) -> None:
    """The other side of session-page#P3: the turn that wrote a record is what renders the page,
    and the page is that directory's index.html."""
    hook = payload(worked_example, transcript)
    (worked_example / PAGE).write_text(stale_page)
    run(hook)
    assert sorted(path.name for path in worked_example.iterdir()) == ["agent-repo", "index.html", "session.md", "tool-calls.js", "turns"]
    assert (worked_example / "index.html").read_text() != stale_page


def test_the_page_the_hook_writes_resolves_a_records_paths_from_the_repo_root(
    worked_example: Path, transcript: Path, run: Callable[[dict], None], tmp_path: Path
) -> None:
    """The page the hook writes is the renderer's, links included: an artefact carries the path the
    hub finds it by, and a path a record writes as code opens the file, both resolved from the repo
    root the records sit under."""
    root = tmp_path  # the worked example's project, which its `agent-repo` names
    (root / "mx").mkdir()
    (root / "mx" / "tool.py").write_text("")
    newest = worked_example / "turns" / "04.md"
    newest.write_text(newest.read_text().replace("\n## Details\n\n", "\n## Details\n\nThe code is `mx/tool.py`.\n\n", 1))
    run(payload(worked_example, transcript))
    written = (worked_example / PAGE).read_text()
    assert f'{session_page.ARTEFACT}="{root}/agent/show/session-page/round-3/spec.html"' in written
    assert f'<a class="path" href="{(root / "mx" / "tool.py").as_uri()}"' in written


# ---- what a turn's end opens ------------------------------------------------


# Each is whether a hub answers, how many of three renders open the page, and what the log says of
# each render that does not.
PAGE_OPENS = {"a hub that answers": (True, 0, "not opened: the hub shows it"), "no hub": (False, 1, "not reopened: no hub answers")}


@pytest.mark.parametrize("answers, opens, why", PAGE_OPENS.values(), ids=PAGE_OPENS)
def test_the_page_opens_on_the_first_render_where_no_hub_answers_and_never_where_one_does(
    answers: bool, opens: int, why: str, worked_example: Path, unrecorded: Path, browser: Path, run: Callable[[dict], None],
    attended: Path, hub: Callable[..., None],
) -> None:
    """A render hands the page to `claude-browser`, told the session it belongs to, only the first
    time and only where no hub answers, since a repeat would be another tab. A hub finds the page on
    disk and reloads it once it is written anew, so nothing hands it over. The turns wrote no record,
    so the links record 04 carries, from a turn before, open nothing."""
    if answers:
        hub(200)
    for _ in range(3):
        run(payload(worked_example, unrecorded))
    page = str(worked_example / PAGE)
    assert opened(browser, opens) == [(worked_example.name, page)] * opens
    said = [(entry["page"], entry["opened"]) for entry in logged(attended, "opened")]
    assert [(where, what.startswith("started ")) for where, what in said[:opens]] == [(page, True)] * opens
    assert said[opens:] == [(page, why)] * (3 - opens)


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
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], attended: Path, tmp_path: Path,
) -> None:
    """session-pages-feed-the-hub#P1, at the Stop hook's input: the record this turn wrote, its
    links in, and the `claude-browser` calls out, each told the session, beside the page's own on
    its first render. The log says what came of each."""
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05 + ("\n## Links\n\n" + "\n".join(links) + "\n" if links else ""))
    with_write(unrecorded, "Write", record)
    run(payload(worked_example, unrecorded))
    assert shown(capsys)
    root = tmp_path  # the worked example's project
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
    first = len(opened(browser, sum(entry["opened"].startswith("started ") for entry in logged(attended, "opened"))))
    record = worked_example / "turns" / "05.md"
    record.write_text(RECORD_05 + "\n## Links\n\n- [The figure](/srv/figures/fig.svg)\n")
    with_write(unrecorded, "Write", record)
    run(payload(worked_example, unrecorded))
    assert opened(browser, first + 1)[first:] == [(worked_example.name, "/srv/figures/fig.svg")]
    assert [entry["opened"] for entry in logged(attended, "page")][-1] == "not reopened: no hub answers"


def test_a_page_already_there_is_rendered_and_not_reopened_where_no_hub_answers(
    worked_example: Path, transcript: Path, stale_page: str, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], attended: Path, tmp_path: Path,
) -> None:
    """A page on disk that this hook did not write, a render of an older version say, is rendered
    over and, with no hub, not opened again; the turn's artefacts still open, and the line still
    shows under the recap."""
    (worked_example / PAGE).write_text(stale_page)
    run(payload(worked_example, transcript))
    assert (worked_example / PAGE).read_text() != stale_page
    assert [entry["opened"] for entry in logged(attended, "page")] == ["not reopened: no hub answers"]
    assert [entry["artefact"] for entry in logged(attended, "artefact")] == [
        str(tmp_path / "agent/show/session-page/round-3" / page)
        for page in ("pages.html", "spec.html")]
    assert first_line(shown(capsys)) == f"session page · waiting on you · {(worked_example / PAGE).as_uri()}"


# ---- the hub ----------------------------------------------------------------


class SocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


HUB_URL = "https://pc.example.ts.net:8377"
"""The address the stand-in hub says it is at: no loopback port, as pc's hub has none."""


@pytest.fixture
def hub(sockets: Path) -> Iterator[Callable[..., None]]:
    """Start a stand-in of the container hub on the socket the hook asks, which answers its health
    check with the status given and, where one is given, its address."""
    servers: list[SocketServer] = []

    def start(status: int, url: str | None = HUB_URL) -> None:
        class Answer(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = json.dumps({"saves": True, **({"url": url} if url else {})}).encode()
                self.send_response(status if self.path == "/.health" else 404)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        server = SocketServer(str(sockets / "hub.sock"), Answer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


# Each is what answers the hub's health check, None for nothing on the socket, the address it names,
# and whether the line links the unit.
HUBS = {
    "a hub that answers": (200, HUB_URL, True),
    "a hub that names no address": (200, None, False),
    "something else on the socket": (404, HUB_URL, False),
    "no hub": (None, None, False),
}


@pytest.mark.parametrize("status, url, unit", HUBS.values(), ids=HUBS)
def test_the_hooks_line_links_the_sessions_unit_where_a_hub_answers_and_the_page_where_none_does(
    status: int | None, url: str | None, unit: bool, worked_example: Path, transcript: Path,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], hub: Callable[..., None],
) -> None:
    """stop-hook-opens-the-turns-artefacts and hub-backend-on-a-socket: the hub answers `GET /.health`
    on its socket when it runs, naming the address its tab is at, and the line links that tab at the
    session's unit, `<address>/u/<session id>`; where nothing does, the line keeps the page's
    `file://` link."""
    if status:
        hub(status, url)
    link = f"{HUB_URL}/u/{worked_example.name}" if unit else (worked_example / PAGE).as_uri()
    run(payload(worked_example, transcript))
    assert first_line(shown(capsys)) == f"session page · waiting on you · {link}"


@pytest.fixture
def speaks_no_http(sockets: Path) -> Iterator[Path]:
    """Something on a socket of its own that answers a request with a line that is no HTTP. Hands
    back the socket."""
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sockets / "other.sock"))
    server.listen()

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
    yield sockets / "other.sock"
    server.close()


def plain_file(where: Path) -> Path:
    (where / "plain").write_text("")
    return where / "plain"


# Each hands back a hub socket the health check cannot ask.
UNASKABLE = {
    "a file that is no socket": lambda request: plain_file(request.getfixturevalue("sockets")),
    "something on the socket that speaks no HTTP": lambda request: request.getfixturevalue("speaks_no_http"),
}


@pytest.mark.parametrize("hub_socket", UNASKABLE.values(), ids=UNASKABLE)
def test_a_hub_socket_that_cannot_be_asked_is_no_hub(
    hub_socket: Callable[[pytest.FixtureRequest], Path], worked_example: Path, transcript: Path,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest, attended: Path,
) -> None:
    """The first render still opens the page and links the page's file, as it does where nothing
    listens."""
    monkeypatch.setenv("CONTAINER_HUB_SOCKET", str(hub_socket(request)))
    run(payload(worked_example, transcript))
    assert [entry["opened"].startswith("started ") for entry in logged(attended, "page")] == [True]
    assert first_line(shown(capsys)) == f"session page · waiting on you · {(worked_example / PAGE).as_uri()}"


# ---- the records kept out of every checkout ----------------------------------


def test_a_session_whose_records_sit_in_the_agent_repo_keeps_its_turns_on_its_next_page(
    worked_example: Path, transcript: Path, run: Callable[[dict], None], capsys: pytest.CaptureFixture, browser: Path,
) -> None:
    """A session running since before mx kept the records outside the checkout has them in the agent
    repo's `sessions/<id>/`, its page beside them: its next turn's end starts its directory from
    them, so the page still shows every turn, opens that page as a first render does, and leaves
    the agent repo's copy where it was."""
    earlier = project_of(worked_example) / "agent" / "sessions" / worked_example.name
    shutil.move(worked_example, earlier)
    (earlier / AGENT_REPO).unlink()
    (earlier / PAGE).write_text("<html>the page the old mx rendered</html>")
    run(payload(worked_example, transcript, reply="Still on the ledger.") | {"cwd": str(earlier.parents[2])})
    capsys.readouterr()
    assert (worked_example / AGENT_REPO).read_text() == f"{earlier.parents[1]}\n"
    assert {"t01", "t02", "t03", "t04"} <= set(rows((worked_example / PAGE).read_text()))
    assert sorted(p.name for p in (earlier / "turns").iterdir()) == ["01.md", "02.md", "03.md", "04.md"]
    assert (worked_example.name, str(worked_example / PAGE)) in opened(browser, 3), "its first render under the account opens it"


def test_a_session_with_a_directory_keeps_it_tied_to_its_project_wherever_it_works_next(
    worked_example: Path, transcript: Path, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory,
    run: Callable[[dict], None], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """Once a session has its directory, the directory is found from wherever it works next, a
    second project with an agent repo of its own or a directory in no project: the command prints
    it, the hook renders the page there, and it stays tied to the first project's agent repo."""
    second = tmp_path_factory.mktemp("budget")
    (second / "agent" / "tickets").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", worked_example.name)
    monkeypatch.setattr(sys, "argv", ["session-page"])
    for cwd in (second, tmp_path_factory.mktemp("loose")):
        monkeypatch.chdir(cwd)
        session_page.main()
        assert capsys.readouterr().out.splitlines()[0] == str(worked_example), cwd
        (worked_example / PAGE).unlink(missing_ok=True)
        run(payload(worked_example, transcript) | {"cwd": str(cwd)})
        capsys.readouterr()
        assert (worked_example / PAGE).is_file(), cwd
        assert (worked_example / AGENT_REPO).read_text() == f"{tmp_path / 'agent'}\n", cwd



def status(where: Path) -> list[str]:
    return subprocess.run(["git", "-C", str(where), "status", "--porcelain", "--untracked-files=all"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def test_a_running_sessions_records_and_page_stay_out_of_every_checkout(
    first_turn: tuple[Path, Path], run: Callable[[dict], None],
) -> None:
    """session-records-outside-the-checkout, "a running session's records sit outside every
    checkout": a session's first reply makes its directory and its page, and neither the code repo's checkout nor the agent repo's, which ignores
    nothing, holds anything new, so a copy of the records arriving there from another host has
    nothing to collide with."""
    directory, said = first_turn
    project = project_of(directory) / "ledger"
    (project / "agent" / "tickets").mkdir(parents=True)
    for repo in (project, project / "agent"):
        git(repo, "init")
        (repo / ".gitignore").write_text("agent/\n" if repo == project else "")
        git(repo, "add", ".gitignore")
        git(repo, "commit", "-m", "start")
    run(payload(directory, said, reply="On it.") | {"cwd": str(project)})
    assert (directory / PAGE).is_file()
    assert (directory / AGENT_REPO).read_text() == f"{project / 'agent'}\n"
    assert status(project) == status(project / "agent") == []


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
ASKS_NOTHING = "---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe ledger has one bank.\n"
Q7 = "What reviews a turn's own prose?"  # the headline record 04 asks Q7 by


def test_a_turn_that_wrote_a_record_ends_on_the_hooks_line_naming_what_waits(
    worked_example: Path, transcript: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """stop-hook-prints-the-page-link#P1 and turn-end-line-names-the-open-questions: the worked
    example's record 04 asks Q7 after the user's last message, so the line under it names Q7 by its
    headline, new; a record 05 answering it, after the user spoke again, leaves nothing. Either way
    the first line ends on the page's link."""
    link = (worked_example / PAGE).as_uri()
    run(payload(worked_example, transcript))
    assert shown(capsys) == f"session page · waiting on you · {link}\nQ7 new · {Q7}"
    fifth = worked_example / "turns" / "05.md"
    fifth.write_text(ANSWERS_Q7)
    with_write(unrecorded, "Write", fifth)
    run(payload(worked_example, unrecorded))
    assert shown(capsys) == f"session page · nothing waiting on you · {link}"


def test_a_question_asked_before_the_users_last_message_is_not_new(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """turn-end-line-names-the-open-questions#P2: the user spoke after record 04 asked Q7, and the
    turn that answered wrote a record leaving Q7 open, so Q7 is still named and no longer new."""
    fifth = worked_example / "turns" / "05.md"
    fifth.write_text(ASKS_NOTHING)
    with_write(unrecorded, "Write", fifth)
    run(payload(worked_example, unrecorded))
    assert shown(capsys).splitlines()[1:] == [f"Q7 · {Q7}"]


# A question whose headline links another, as session 168b5d8b's turn 3 asked one with `[Q6](#q6)`
# in it, and carries emphasis and code besides.
ASKS_WITH_MARKDOWN = (
    "---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Questions\n\n"
    "- [Q8] **Fold [Q7](#q7) into the _light_ review in `turn_review.py`?** What it would replace.\n"
    "  - (a) Fold it. *my pick*\n  - (b) Keep both.\n"
)


def test_a_headline_reaches_the_line_as_plain_text(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """turn-end-line-names-the-open-questions, story 1: the terminal renders no markdown, so a link
    in a headline reaches the line as its text, and emphasis and code without their marks."""
    fifth = worked_example / "turns" / "05.md"
    fifth.write_text(ASKS_WITH_MARKDOWN)
    with_write(unrecorded, "Write", fifth)
    run(payload(worked_example, unrecorded))
    assert shown(capsys).splitlines()[1:] == [f"Q7 · {Q7}", "Q8 new · Fold Q7 into the light review in turn_review.py?"]


# What starts a drawn turn: the user's own prompt; a finished task, with the user saying nothing;
# or a finished task, with the user queuing a message once the turn has written its record.
STARTS = ("typed", "task", "queued")


@st.composite
def started_sessions(draw: st.DrawFn) -> tuple[list[dict], set[str], list[str]]:
    """A drawn session (`sessions`) with what started each of its turns."""
    turns, open_tags = draw(sessions())
    return turns, open_tags, draw(st.lists(st.sampled_from(STARTS), min_size=len(turns), max_size=len(turns)))


def started_transcript(path: Path, directory: Path, starts: list[str]) -> Path:
    """A transcript in which turn n starts at hour n as `starts` says, writes its record at half
    past, and, but for the turn ending now, ends at ten to the next hour, as Claude Code marks a
    turn's end once its Stop hooks let it."""
    lines = []
    for number, start in enumerate(starts, start=1):
        hour = f"2026-09-23T{number:02d}"
        prompt = {"type": "user", "message": {"role": "user", "content": f"What I asked in turn {number}."}}
        lines.append((prompt if start == "typed" else TASK_DONE) | {"timestamp": f"{hour}:00:00.000Z", "uuid": f"u{number}"})
        call = {"type": "tool_use", "name": "Write", "input": {"file_path": str(directory / "turns" / f"{number:02d}.md")}}
        lines.append({"type": "assistant", "message": {"role": "assistant", "content": [call]}, "timestamp": f"{hour}:30:00.000Z"})
        if start == "queued":
            lines.append({"type": "attachment", "timestamp": f"{hour}:40:00.000Z",
                          "attachment": {"type": "queued_command", "prompt": f"Also, about turn {number}."}})
        if number < len(starts):
            lines.append(TURN_ENDED | {"timestamp": f"{hour}:50:00.000Z"})
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(drawn=started_sessions())
def test_the_line_names_each_open_question_once_oldest_first_and_marks_the_new_ones(
    drawn: tuple[list[dict], set[str], list[str]], tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """turn-end-line-names-the-open-questions#P1 and P2, over sessions whose questions meet every
    fate and whose turns the user, a task or both started: the lines under the link are the open
    questions the draw left, each once, oldest first, each by its headline; one is new exactly where
    the turn that asked it is the one holding the user's last message, or a later one. A ticket's
    question is named qualified by its ticket, while its ticket holds it open."""
    turns, open_tags, starts = drawn
    project = tmp_path_factory.mktemp("project")
    directory = project / SESSIONS / DRAWN
    (directory / "turns").mkdir(parents=True)
    write_tickets(project, turns)
    for number, turn in enumerate(turns, start=1):
        (directory / "turns" / f"{number:02d}.md").write_text(drawn_record(number, turn))
    transcript = started_transcript(directory.parent / "transcript.jsonl", directory, starts)
    asked_in = {handle: number for number, turn in enumerate(turns, start=1) for handle in asked_in_order([turn])}
    spoke = max((number for number, start in enumerate(starts, start=1) if start != "task"), default=0)
    decision = decide(payload(directory, transcript), directory)
    lines = [line.split(" · ") for line in decision.waiting]
    handles = [head.removesuffix(" new") for head, _ in lines]
    assert handles == [handle for handle in asked_in_order(turns) if handle in open_tags]
    for (head, headline), handle in zip(lines, handles):
        assert headline == f"What about {handle}?"
        assert head == (f"{handle} new" if asked_in[handle] >= spoke else handle)
    assert decision.shown == f"session page · {'waiting on you' if open_tags else 'nothing waiting on you'}"


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


def chats(directory: Path) -> list[Path]:
    """The chat turns' records in the session directory."""
    return sorted((directory / "turns").glob("chat-*.md"))


def rows(page: str) -> list[str]:
    """The ids of the page's turns, top to bottom."""
    return re.findall(rf'\bid="({TURN_ANCHOR})"', page)


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
    said = turns_on(page)[chat.stem]
    assert said.startswith(f"you {SPOKEN_AFTER['message']['content']}"), "a chat turn shows no number"
    assert [anchor for anchor, turn in elements(page, r"t\d+").items() if re.match(r"<details\b[^>]*\bopen\b", turn)] == ["t04"]


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
    assert "And the third?" in turns_on(page)["t05"]
    assert messages_of(view_of(worked_example, next_turn))["05"] == ["And the third?"]
    assert "Yes, the second bank." in chat.read_text()


RECORD_05 = "---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe second bank.\n"


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
    assert messages_of(view_of(worked_example, unrecorded))["05"] == [SPOKEN_AFTER["message"]["content"]]


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

# A message the user queues while the turn runs, after it wrote its record at 01:36 (with_write).
QUEUED = {"type": "attachment", "timestamp": "2026-09-23T01:37:00.000Z",
          "attachment": {"type": "queued_command", "prompt": "And the third bank?"}}


@pytest.mark.parametrize("start", TURN_STARTS.values(), ids=TURN_STARTS)
def test_a_turn_the_user_did_not_start_still_records_its_reply_as_a_chat_turn(
    start: tuple[dict, ...], worked_example: Path, transcript: Path, tmp_path: Path,
) -> None:
    """This turn runs from the prompt that started it, whoever sent it: record 04, written in the
    turn before, is no record of a turn a finished task, a hand-back, another session's message
    or a scheduled prompt started, so its reply is this turn's chat turn."""
    for record in (worked_example / "turns").iterdir():
        os.utime(record, (BEFORE_IT, BEFORE_IT))
    decision = decide(payload(worked_example, appended(transcript, tmp_path / "t.jsonl", *start), reply=LONG), worked_example)
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
    return payload(example.parent / FRESH, transcript) | {"cwd": str(loose)}


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
    directory = str(pages_directory(session_page.account(), hook["session_id"])) if resolved else None
    assert entries == [{"ts": entries[0]["ts"], "session_id": hook["session_id"], "verb": verb, "why": why, "directory": directory}]


SENT_BACK_AT_THE_END = {"a record that does not parse": unparsed, "a record written through the shell": through_the_shell}


@pytest.mark.parametrize("arrange", SENT_BACK_AT_THE_END.values(), ids=SENT_BACK_AT_THE_END)
def test_what_the_turns_end_still_sends_back_asks_for_the_recap(
    arrange: Callable, worked_example: Path, transcript: Path, capsys: pytest.CaptureFixture,
    run: Callable[[dict], None], request: pytest.FixtureRequest,
) -> None:
    """turns-end-on-their-recap#P3 and P4: the records the write hook never saw are still checked
    at the turn's end, and the send-back asks the turn to end on its recap, which
    (turn-end-line-names-the-open-questions#P3) lists no question: the hook's message names them."""
    run(arrange(worked_example, transcript, request))
    said = said_back(capsys)
    assert stop_hook.RECAP in said and "without a reply" not in said
    assert not LISTS_A_QUESTION.search(said.splitlines()[-1])


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
# The link is written by the handoff skill's pickup command, run here as the agent runs it; the
# Stop hook renders the fresh session's page from it.

PICKUP = Path(__file__).resolve().parents[1] / "handoff" / "pickup.py"
BEFORE = "46944b2a-c996-4889-b308-48c1d884a675"  # the session that wrote the handoff
CONTINUATION = f"session: {BEFORE}\npurpose: continuation"


def pick_up(project: Path, front: str, session: str = FRESH, name: str = "2026-10-05-ledger.md") -> subprocess.CompletedProcess:
    """A handoff of frontmatter `front` committed in the project's agent repo, and picked up there
    by `session` through the command."""
    agent = project / "agent"
    if not (agent / ".git").exists():
        git(agent, "init", "-q")
    (agent / "handoffs").mkdir(exist_ok=True)
    (agent / "handoffs" / name).write_text(f"---\n{front}\n---\n\n# Carry the ledger work on\n")
    git(agent, "add", "handoffs")
    git(agent, "commit", "-q", "-m", "hand off")
    identity = {f"GIT_{who}_{what}": value for who in ("AUTHOR", "COMMITTER") for what, value in (("NAME", "t"), ("EMAIL", "t@t"))}
    done = subprocess.run([str(PICKUP), str(agent / "handoffs" / name)], cwd=project, capture_output=True, text=True,
                          timeout=120, env={**os.environ, **identity, "CLAUDE_CODE_SESSION_ID": session})
    assert done.returncode == 0, done.stderr
    return done


def transcript_of(session: str) -> Path:
    """Where Claude Code keeps the session's transcript, under the check's own config directory."""
    return Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "-srv-helferline" / f"{session}.jsonl"


@pytest.fixture
def handed_over(first_turn: tuple[Path, Path], run: Callable[[dict], None], capsys: pytest.CaptureFixture) -> Callable[..., Path]:
    """The session `BEFORE`, which has a page and its transcript where Claude Code keeps it, and a
    way to have the fresh session pick up a handoff of the frontmatter given and end its first turn
    on a reply. Hands back the directory of `BEFORE`; the last pickup's output is `handed_over.done`."""
    directory, said = first_turn
    before = directory.parent / BEFORE
    theirs = transcript_of(BEFORE)
    theirs.parent.mkdir(parents=True, exist_ok=True)
    theirs.write_text(json.dumps(FIRST_PROMPT | {"sessionId": BEFORE}) + "\n")
    run(payload(before, theirs, reply="Writing the handoff."))
    capsys.readouterr()

    def read(front: str, **pickup: str) -> Path:
        read.done = pick_up(project_of(directory), front, **pickup)
        run(payload(directory, said, reply="On it."))
        capsys.readouterr()
        return before

    return read


def links_to(page: Path) -> list[str]:
    """The sessions a page links to, each once: the line under its title and an end of its timeline both link it."""
    return list(dict.fromkeys(re.findall(r'href="file://[^"]*/([^"/]+)/index\.html"', page.read_text())))


def test_a_session_that_picked_up_a_continuation_handoff_links_to_the_page_before_and_back(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path],
) -> None:
    """pages-link-across-handoffs#P1, read through the pickup command: the session that picked up a
    continuation handoff gets `previous`, naming the session that wrote the handoff; its page links
    to that one's, and that one's, rendered again, links forward; each link resolves on disk."""
    directory, _ = first_turn
    before = handed_over(CONTINUATION)
    assert (directory / PREVIOUS).read_text().strip() == BEFORE
    assert links_to(directory / PAGE) == [BEFORE]
    assert links_to(before / PAGE) == [FRESH]
    assert f'href="{(before / PAGE).as_uri()}"' in (directory / PAGE).read_text()
    assert f'href="{(directory / PAGE).as_uri()}"' in (before / PAGE).read_text()


# Where the session before may keep its page, from the check's project: in its agent repo, as a
# session that ended before mx kept the records outside the checkout left it, or under an account
# beside the check's own.
KEPT_BEFORE = {"in the agent repo": "agent/sessions", "under another account": ".claude-other/session-pages"}


@pytest.mark.parametrize("where", KEPT_BEFORE.values(), ids=KEPT_BEFORE)
def test_a_continuation_links_to_the_page_before_wherever_that_session_keeps_it(
    where: str, handed_over: Callable[..., Path], first_turn: tuple[Path, Path],
) -> None:
    """pages-link-across-handoffs#P1 across the places a page can be: a handoff picked up from a
    session whose page sits elsewhere than this session's still links the two pages both ways."""
    directory, _ = first_turn
    kept = project_of(directory) / where / BEFORE
    kept.parent.mkdir(parents=True)
    shutil.move(directory.parent / BEFORE, kept)
    if where == "agent/sessions":
        (kept / AGENT_REPO).unlink()
    else:  # that account keeps the session's transcript too
        theirs = kept.parents[1] / transcript_of(BEFORE).relative_to(session_page.account())
        theirs.parent.mkdir(parents=True)
        shutil.move(transcript_of(BEFORE), theirs)
    handed_over(CONTINUATION)
    assert f'href="{(kept / PAGE).as_uri()}"' in (directory / PAGE).read_text()
    assert links_to(kept / PAGE) == [FRESH]


NO_LINK = {
    "a fork's handoff": f"session: {BEFORE}\npurpose: fork",
    "a handoff the session wrote itself": f"session: {FRESH}\npurpose: continuation",
    "a session id that is no id": "session: ../../etc\npurpose: continuation",
    "frontmatter that is not YAML": f"session: [{BEFORE}\npurpose: continuation",
}


@pytest.mark.parametrize("front", NO_LINK.values(), ids=NO_LINK)
def test_a_handoff_that_continues_no_other_session_links_nothing(
    front: str, handed_over: Callable[..., Path], first_turn: tuple[Path, Path],
) -> None:
    """pages-link-across-handoffs#P2, and the handoffs that name no other session by a safe id."""
    directory, _ = first_turn
    before = handed_over(front)
    assert not (directory / PREVIOUS).exists()
    assert links_to(directory / PAGE) == links_to(before / PAGE) == []


def handoff_read(path: str, front: str) -> dict:
    """The transcript entry Claude Code writes for a Read of `path`, the file returned as read; a
    handoff's frontmatter is `front`."""
    content = f"---\n{front}\n---\n\n# Carry the ledger work on\n"
    return {"type": "user", "timestamp": "2026-10-05T09:00:05.000Z",
            "message": {"role": "user", "content": [{"tool_use_id": "toolu_1", "type": "tool_result", "content": content}]},
            "toolUseResult": {"type": "text", "file": {"filePath": path, "content": content, "startLine": 1}}}


def bash(command: str) -> list[dict]:
    """The transcript entries Claude Code writes for a Bash call of `command` and its result."""
    return [{"type": "assistant", "timestamp": "2026-10-05T09:00:06.000Z",
             "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_2", "name": "Bash", "input": {"command": command}}]}},
            {"type": "user", "timestamp": "2026-10-05T09:00:07.000Z",
             "message": {"role": "user", "content": [{"tool_use_id": "toolu_2", "type": "tool_result", "content": ""}]}}]


def test_a_handoff_picked_up_without_the_command_links_nothing(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path], run: Callable[[dict], None],
) -> None:
    """handoff-pickup-command's Decisions: the Stop hook reads no pickup out of the transcript, so a
    continuation handoff read and `git rm`'d by hand writes no `previous`."""
    directory, said = first_turn
    before = handed_over(f"session: {BEFORE}\npurpose: fork")
    handoff = project_of(directory) / "agent" / "handoffs" / "2026-10-06-ledger.md"
    with said.open("a") as f:
        for e in [handoff_read(str(handoff), CONTINUATION), *bash(f"git rm {handoff} && git commit -m 'pick up'")]:
            f.write(json.dumps(e) + "\n")
    run(payload(directory, said, reply="Carrying on."))
    assert not (directory / PREVIOUS).exists()
    assert links_to(directory / PAGE) == links_to(before / PAGE) == []


def test_previous_is_written_once(handed_over: Callable[..., Path], first_turn: tuple[Path, Path]) -> None:
    """A `previous` already there stays, whatever handoff the session picks up after it was written."""
    directory, _ = first_turn
    handed_over(f"session: {BEFORE}\npurpose: fork")
    earlier = "0d1e2f3a-0000-0000-0000-000000000000"
    (directory / PREVIOUS).write_text(earlier + "\n")
    handed_over(CONTINUATION, name="2026-10-06-ledger.md")
    assert (directory / PREVIOUS).read_text().strip() == earlier
    assert f"already names {earlier}" in handed_over.done.stderr


def test_a_predecessor_with_no_page_is_recorded_and_not_linked(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path],
) -> None:
    """A handoff written by a session that has no page here, one from before every session had one
    or from another machine: `previous` names it, the page links nowhere, and the pickup says why."""
    directory, _ = first_turn
    gone = "0d1e2f3a-0000-0000-0000-000000000000"
    handed_over(f"session: {gone}\npurpose: continuation")
    assert (directory / PREVIOUS).read_text().strip() == gone
    assert links_to(directory / PAGE) == []
    assert "no session directory" in handed_over.done.stderr


def test_a_handoff_two_sessions_picked_up_links_forward_to_both(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path], run: Callable[[dict], None], capsys: pytest.CaptureFixture,
) -> None:
    """One handoff split into several: the page before links forward to every session that picked
    up one of them."""
    directory, _ = first_turn
    before = handed_over(CONTINUATION)
    second = "0a0b0c0d-0000-0000-0000-000000000000"
    theirs = transcript_of(second)
    theirs.write_text(json.dumps(FIRST_PROMPT | {"sessionId": second}) + "\n")
    pick_up(project_of(directory), CONTINUATION, session=second, name="2026-10-05-ledger-bank.md")
    run(payload(directory.parent / second, theirs, reply="On it."))
    capsys.readouterr()
    assert links_to(before / PAGE) == sorted([FRESH, second])


def test_a_predecessor_with_no_transcript_is_said_and_links_forward_at_its_next_render(
    handed_over: Callable[..., Path], first_turn: tuple[Path, Path], run: Callable[[dict], None],
    capsys: pytest.CaptureFixture,
) -> None:
    """pages-link-across-handoffs' Decisions: with no transcript to render it from, the pickup says
    so and the forward link waits for the predecessor's next render."""
    directory, _ = first_turn
    theirs = transcript_of(BEFORE)
    kept = theirs.read_text()
    theirs.unlink()
    before = handed_over(CONTINUATION)
    assert links_to(directory / PAGE) == [BEFORE]
    assert links_to(before / PAGE) == []
    assert "no transcript under" in handed_over.done.stderr
    theirs.write_text(kept)
    run(payload(before, theirs, reply="Still here."))
    capsys.readouterr()
    assert links_to(before / PAGE) == [FRESH]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
