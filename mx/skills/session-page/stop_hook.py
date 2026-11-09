#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""Stop hook: what the end of a turn does to the session page.

It reads the Stop hook JSON on stdin; `decide` answers with a Verb over the session's own
directory, and `main` applies it. A session's first turn that ends on a reply creates its
directory, holding that reply as a chat turn, so every session someone sits at has a page from then
on. The prose review of the turn's record ran when the agent wrote it (write_hook.py), so it is over
by the time the turn ends. A turn that ends, rather than being sent back, deletes the live file its
calls showed in while it ran (`live_hook.LIVE`).

It leaves alone a session nobody reads the page of: DISPATCH_WORKLOG set (a dispatched worker), or
CLAUDE_CODE_SESSION_ATTENDED set to 0 (a print-mode session).

A render opens no artefact: the page lists what the turn linked among its tasks, and the user opens
each from there. The page itself opens, with `claude-browser` told the session through
MX_ORIGIN_SESSION, only where no container hub answers, and only on the render that writes it
first, since a repeat would be another tab: the hub finds a session's page on disk and reloads it
once it is written anew. The open is a line of the log saying what came of it.

A turn whose answer is on the page ends without a chat message of its own, so a render whose turn
wrote a record shows the user, as a `systemMessage`, what the terminal reads in its place: the
record's headline, a line linking the hub's tab at the session's unit, or the page's file where no
hub answers, and under it a line for each question and to-do waiting on them (`waiting`).

Every decision is one JSON line in `turn_review.LOG`, beside the review's own: the verb, why the
hook took that path, and the session directory it resolved.
"""

import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import turn_review  # noqa: E402
from live_hook import LIVE  # noqa: E402
from session_page import (  # noqa: E402
    PAGE, RecordError, Session, Turn, carry_earlier_records, chat_path, chat_record, inline, left_alone, open_questions,
    open_todos, read_session, write_page, make_session_directory, note_account, session_directory, strip_tags,
    written_this_turn,
)

Verb = Literal["render", "send back", "allow"]


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: Verb
    why: str  # which path the hook took, for the log
    reason: str = ""  # what the agent reads, where it is sent back; empty otherwise
    chat: tuple[Path, str] | None = None  # the chat turn's record a render writes first, as its path and text
    headline: str = ""  # the record's headline, the first line a render's turn that wrote a record shows
    shown: str = ""  # the line under the headline, up to the link `main` adds
    waiting: tuple[str, ...] = ()  # the lines under it, one per open question or to-do


# The container hub's half of the contract, which the dotfiles' `container-hub --help` names: the
# socket it listens on, the variable that moves it, the path it answers while it runs with its
# address, and its tab at a session's unit.
HUB_SOCKET = "~/.local/state/container-hub/hub.sock"
HUB_SOCKET_VARIABLE = "CONTAINER_HUB_SOCKET"
HUB_HEALTH = "/.health"
HUB_UNIT = "/u/{session}"

# How every send-back, the write hook's too, asks the turn to end, as RULES.md has it.
END = (
    "end the turn without a chat message: the Stop hook shows the user the record's headline, the page's link and "
    "what waits on them, so what the user needs goes in the record"
)
UNPARSED = f"Fix the record, then {END}, as you would have without this error. The page renders once every record parses."
OUTSIDE_WRITE = (
    "This turn wrote {record} without the Write tool, so the page pairs the user's message with no turn. "
    f"Write it again with Write, then {END}."
)


def decide(hook: dict, directory: Path | None) -> Decision:
    """What to do with the turn the hook JSON describes, over the session directory. "This turn"
    runs from the prompt that started it (`session_page.turn_start`), whoever sent that prompt.

    A session left alone, or outside a project with an agent repo, lets the turn end, and so does a
    session with no directory whose turn ended on no text. Otherwise:

    - A record that does not parse is sent back with the reason the reader gives, every time, and
      nothing renders. The write hook catches one written with a tool; this catches one written
      through the shell.
    - A record written without the Write tool is sent back, named, to be written again with Write,
      once per turn: a turn a Stop hook already continued renders, so an agent that keeps writing
      it through the shell is not held in a loop.
    - Otherwise the page renders. Where this turn wrote no record and ended on a reply, the reply
      is written first as a chat turn (`session_page.CHAT`), which takes no
      number of the agent's records; `main` creates the session's directory for it where there is
      none yet. Where this turn wrote a record, the render comes with the lines the user sees in place
      of a chat message (`headline`, `shown`, short of its link, and `waiting`), and where that
      record was reviewed, the records as the turn ended are logged beside the review, so the log
      pairs a draft with its revision.
    """
    if unread := left_alone():
        return Decision("allow", unread)
    if directory is None:
        return Decision("allow", "no project with an agent repo")
    reply = (hook.get("last_assistant_message") or "").strip()
    if not directory.is_dir() and not reply:
        return Decision("allow", "no session directory")
    try:
        session = read_session(directory, Path(hook["transcript_path"]))
    except RecordError as e:
        return Decision("send back", "record does not parse", f"{e}\n{UNPARSED}")
    turn = written_this_turn(session)
    outside = written_outside_write(session) if turn is None else None
    if outside and not hook.get("stop_hook_active"):
        return Decision("send back", "record written outside Write", OUTSIDE_WRITE.format(record=outside.path))
    if turn is None and reply and not outside:
        now = datetime.now(UTC)
        return Decision("render", "chat reply recorded", chat=(chat_path(directory / "turns", now), chat_record(hook["last_assistant_message"], now)))
    if turn is None:
        return Decision("render", "no record written this turn")
    asked = waiting(session)
    rendered = {"headline": plain(turn.headline), "shown": shown(asked), "waiting": asked}
    if not turn_review.reviewed_since(session.id, session.began):
        return Decision("render", "record not reviewed this turn", **rendered)
    turn_review.log(session.id, decision="turn end", **turn_review.as_read(session, turn))
    return Decision("render", "record reviewed this turn", **rendered)


def shown(asked: tuple[str, ...]) -> str:
    """The line under the headline of a turn whose answer is on the page, up to its link: whether a
    question waits on the user there, given the lines `waiting` names them in."""
    return f"session page · {'waiting on you' if asked else 'nothing waiting on you'}"


def waiting(session: Session) -> tuple[str, ...]:
    """A line for each open question, oldest first, then each open to-do: its tag, a ticket's
    question qualified by its ticket, `new` where a turn since the user's last message asked it, and
    its headline (`plain`)."""
    return tuple(f"{q.handle}{' new' if asked_since_spoke(session, t) else ''} · {plain(q.headline)}"
                 for t, q in [*open_questions(session), *open_todos(session)])


def plain(markdown: str) -> str:
    """A line of a record as the page's reader reads it, since the terminal renders no markdown: a
    link as its text, emphasis and code without their marks."""
    return strip_tags(inline(markdown, paths=False))


def asked_since_spoke(session: Session, turn: Turn) -> bool:
    """Whether the turn's record was written by the turn that holds the user's last message or a
    later one. A record the transcript never shows written is not."""
    return turn.written is not None and (session.spoke is None or turn.written > session.spoke)


class HubConnection(http.client.HTTPConnection):
    """HTTP to the container hub, over its socket."""

    def __init__(self, path: str):
        super().__init__("localhost", timeout=1)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def hub_unit(session_id: str) -> str:
    """The container hub's tab at the session's unit, where a hub on this host answers its health
    check with its address; empty where none does."""
    hub = HubConnection(os.path.expanduser(os.environ.get(HUB_SOCKET_VARIABLE) or HUB_SOCKET))
    try:
        hub.request("GET", HUB_HEALTH)
        answer = hub.getresponse()
        said = json.loads(answer.read()) if answer.status == 200 else None
    # Refused, absent or timed out (OSError); something on the socket that speaks no HTTP
    # (HTTPException), or answers with a body that is no JSON (ValueError).
    except (OSError, http.client.HTTPException, ValueError):
        return ""
    finally:
        hub.close()
    url = said.get("url") if isinstance(said, dict) else None
    return url + HUB_UNIT.format(session=session_id) if isinstance(url, str) and url else ""


def written_outside_write(session: Session) -> Turn | None:
    """The newest record the transcript never writes whose file changed since this turn began:
    one written through the shell. Its modification time names it in a send-back and decides
    nothing else."""
    if session.began is None:
        return None
    outside = [
        t for t in session.turns
        if t.written is None and datetime.fromtimestamp(t.path.stat().st_mtime, UTC) > session.began
    ]
    return outside[-1] if outside else None


def open_in_browser(target: str, session_id: str) -> str:
    """Open a page, file or URL in the browser as the session's, without waiting on it, and say
    what came of that. A host with no `claude-browser`, or one that fails to start, leaves the turn
    as it was."""
    if not (opener := shutil.which("claude-browser")):
        return "no claude-browser on PATH"
    try:
        subprocess.Popen([opener, target], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env=os.environ | {"MX_ORIGIN_SESSION": session_id})
    except OSError as e:
        return f"{opener} did not start: {e}"
    return f"started {opener}"


def main() -> None:
    hook = json.load(sys.stdin)
    session_id = hook["session_id"]
    if not left_alone():
        carry_earlier_records(Path(hook["cwd"]), session_id)
    directory = session_directory(Path(hook["cwd"]), session_id)
    decision = decide(hook, directory)
    turn_review.log(session_id, verb=decision.verb, why=decision.why, directory=directory and str(directory))
    if decision.verb == "render":
        make_session_directory(Path(hook["cwd"]), session_id)
        first = not (directory / PAGE).exists()
        if decision.chat:
            decision.chat[0].parent.mkdir(parents=True, exist_ok=True)
            decision.chat[0].write_text(decision.chat[1])
        note_account(directory)
        write_page(read_session(directory, Path(hook["transcript_path"])), datetime.now())
        unit = hub_unit(session_id)
        opened = ("not opened: the hub shows it" if unit
                  else open_in_browser(str(directory / PAGE), session_id) if first else "not reopened: no hub answers")
        turn_review.log(session_id, opened=opened, page=str(directory / PAGE))
        if decision.shown:
            line = f"{decision.shown} · {unit or (directory / PAGE).as_uri()}"
            print(json.dumps({"systemMessage": "\n".join((decision.headline, line, *decision.waiting))}))
    elif decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))
    # the turn is over, and the page just rendered holds its calls where it holds the turn
    if decision.verb != "send back" and directory is not None:
        (directory / LIVE).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
