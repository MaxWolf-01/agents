#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Stop hook: what the end of a turn does to the session page.

It reads the Stop hook JSON on stdin; `decide` answers with a Verb over the session's own
directory, and `main` applies it. A session's first turn that ends on a reply creates its
directory, holding that reply as a chat turn, so every session someone sits at has a page from then
on. The prose review of the turn's record ran when the agent wrote it (write_hook.py), so it is over
by the time the turn ends.

It leaves alone a session nobody reads the page of: DISPATCH_WORKLOG set (a dispatched worker), or
CLAUDE_CODE_SESSION_ATTENDED set to 0 (a print-mode session).

A render opens each artefact that this turn's record links with `claude-browser`, where the host
has one, and tells it the session through MX_ORIGIN_SESSION. A ticket file is not an artefact, so
it never opens. Where the container hub answers, every render opens the page too: the hub lands
each page in the session's unit and turns a repeat into a reload. Where none does, only the render
that writes the page first opens it, since a repeat would be another tab. The first render also
keeps `sessions/` out of the agent repo's `git status`, through that clone's `.git/info/exclude`,
where nothing ignores it yet. Each open, and the exclude, is a line of the log saying what came of
it.

The agent ends a turn whose answer is on the page on its recap, which carries no link, so a render
whose turn wrote a record shows the user one line of the hook's own under it, as a `systemMessage`:
the questions waiting on them and a link to the hub's tab at the session's unit, or to the page's
file where no hub answers.

Every decision is one JSON line in `turn_review.LOG`, beside the review's own: the verb, why the
hook took that path, and the session directory it resolved.
"""

import json
import os
import shutil
import subprocess
import sys
import http.client
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import turn_review  # noqa: E402
from session_page import (  # noqa: E402
    PAGE, RecordError, Session, Turn, chat_path, chat_record, left_alone, open_questions, page, read_session,
    resolved, session_directory, written_this_turn,
)

Verb = Literal["render", "send back", "allow"]


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: Verb
    why: str  # which path the hook took, for the log
    reason: str = ""  # what the agent reads, where it is sent back; empty otherwise
    chat: tuple[Path, str] | None = None  # the chat turn's record a render writes first, as its path and text
    shown: str = ""  # what waits on the user, where a render's turn wrote a record; `main` adds the link
    artefacts: tuple[str, ...] = ()  # the file or URL of each artefact the record this turn wrote links


# The container hub's half of the contract, which the dotfiles' `container-hub --help` names: the
# port it serves on, the variable that moves it, the path it answers while it runs, and its tab at a
# session's unit.
HUB_PORT = 8377
HUB_PORT_VARIABLE = "CONTAINER_HUB_PORT"
HUB_HEALTH = "/.health"
HUB_UNIT = "/u/{session}"

# How every send-back, the write hook's too, asks the turn to end: RULES.md's chat recap. The
# hook shows the link to the page under it.
RECAP = (
    "end the turn on its chat recap: what waits on the user, as action items, one plain line each that reads "
    "on its own, each open question named by what it decides, or one line saying nothing does; "
    "no line points at the page"
)
UNPARSED = f"Fix the record, then {RECAP}, as you would have without this error. The page renders once every record parses."
OUTSIDE_WRITE = (
    "This turn wrote {record} without the Write tool, so the page pairs the user's message with no turn. "
    f"Write it again with Write, then {RECAP}."
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
      none yet. Where this turn wrote a record, the render comes with the line the user sees under
      the agent's recap (`shown`, short of its link) and the record's artefacts, and where that
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
    rendered = {"shown": shown(session), "artefacts": linked(session, turn)}
    if not turn_review.reviewed_since(session.id, session.began):
        return Decision("render", "record not reviewed this turn", **rendered)
    turn_review.log(session.id, decision="turn end", **turn_review.as_read(session, turn))
    return Decision("render", "record reviewed this turn", **rendered)


def shown(session: Session) -> str:
    """The line under a turn whose answer is on the page, up to its link: what waits on the user there."""
    waiting = [q.tag for _, q in open_questions(session)]
    ask = f"waiting on you: {' '.join(waiting)}" if waiting else "nothing waiting on you"
    return f"session page · {ask}"


def hub_unit(session_id: str) -> str:
    """The container hub's tab at the session's unit, where a hub answers its health check on this
    host; empty where none does."""
    hub = f"http://127.0.0.1:{os.environ.get(HUB_PORT_VARIABLE) or HUB_PORT}"
    try:
        with urllib.request.urlopen(hub + HUB_HEALTH, timeout=1):
            return hub + HUB_UNIT.format(session=session_id)
    # Refused, timed out or an error status (OSError); a port that is no number (InvalidURL), or
    # something on the port that speaks no HTTP (BadStatusLine), both HTTPException.
    except (OSError, http.client.HTTPException):
        return ""


def linked(session: Session, turn: Turn) -> tuple[str, ...]:
    """What the turn's artefacts open, each file or URL once, resolved as the page's artefact column
    resolves a link: two links into sections of one page open it once."""
    return tuple(dict.fromkeys(resolved(link.path, session.root) for link in turn.artefacts))


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


def exclude_sessions(sessions: Path) -> str:
    """Add `sessions` to the exclude file of the repo it sits in, unless git already ignores it or
    the repo tracks files under it, and say what came of that. A repo that tracks session records
    means to, and an exclude line would leave every later session's out of a broad `git add`. The
    line is anchored at its path from the repo root, so it matches that directory and no other of
    the same name. Outside git, or where git fails, nothing is written."""

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(sessions.parent), *args], capture_output=True, text=True)

    found = git("rev-parse", "--path-format=absolute", "--git-path", "info/exclude", "--show-prefix")
    if found.returncode != 0:
        if "not a git repository" in found.stderr:
            return "not in a git repository"
        return f"git rev-parse failed: {found.stderr.strip()}"
    if git("ls-files", "--", f"{sessions.name}/").stdout:
        return "tracked, so not excluded"
    checked = git("check-ignore", "-q", f"{sessions.name}/")
    if checked.returncode == 0:
        return "already ignored"
    if checked.returncode != 1:
        return f"git check-ignore failed: {checked.stderr.strip()}"
    exclude, prefix = (found.stdout.splitlines() + [""])[:2]
    line = f"/{prefix}{sessions.name}/"
    try:
        Path(exclude).parent.mkdir(parents=True, exist_ok=True)
        with Path(exclude).open("a+") as f:
            f.seek(0)
            before = f.read()
            f.write(("\n" if before and not before.endswith("\n") else "") + line + "\n")
    except OSError as e:
        return f"{exclude} not written: {e}"
    return f"added {line} to {exclude}"


def main() -> None:
    hook = json.load(sys.stdin)
    session_id = hook["session_id"]
    directory = session_directory(Path(hook["cwd"]), session_id)
    decision = decide(hook, directory)
    turn_review.log(session_id, verb=decision.verb, why=decision.why, directory=directory and str(directory))
    if decision.verb == "render":
        first = not (directory / PAGE).exists()
        if decision.chat:
            decision.chat[0].parent.mkdir(parents=True, exist_ok=True)
            decision.chat[0].write_text(decision.chat[1])
        (directory / PAGE).write_text(page(read_session(directory, Path(hook["transcript_path"])), datetime.now()))
        unit = hub_unit(session_id)
        opened = open_in_browser(str(directory / PAGE), session_id) if unit or first else "not reopened: no hub answers"
        turn_review.log(session_id, opened=opened, page=str(directory / PAGE))
        for artefact in decision.artefacts:
            turn_review.log(session_id, opened=open_in_browser(artefact, session_id), artefact=artefact)
        if first:
            turn_review.log(session_id, excluded=exclude_sessions(directory.parent))
        if decision.shown:
            print(json.dumps({"systemMessage": f"{decision.shown} · {unit or (directory / PAGE).as_uri()}"}))
    elif decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
