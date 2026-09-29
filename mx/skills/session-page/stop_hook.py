#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Stop hook: what the end of a turn does to the session page.

It reads the Stop hook JSON on stdin; `decide` answers with a Verb over the session's own
directory, running the turn review and logging a re-entry on the way, and `main` applies it. A
session with no directory never gets one from here: the agent creates it by writing the first
record.

It leaves alone a session nobody reads the page of: DISPATCH_WORKLOG set (a dispatched worker), or
CLAUDE_CODE_SESSION_ATTENDED set to 0 (a print-mode session).

The render that writes a session's page for the first time opens it with `claude-browser`, where
the host has one; later renders rewrite the same file, and the open tab is reloaded by hand. That
open is a line of the log too, saying what came of it.

The agent ends a turn whose answer is on the page without a reply, so a render whose turn wrote a
record shows the user one line of the hook's own under it, as a `systemMessage`: the questions
waiting on them and the page's link.

Every decision is one JSON line in `turn_review.LOG`, beside the review's own: the verb, why the
hook took that path, and the session directory it resolved.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import turn_review  # noqa: E402
from session_page import PAGE, RecordError, Session, Turn, open_questions, page, read_session, session_directory  # noqa: E402

Verb = Literal["render", "send back", "allow"]


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: Verb
    why: str  # which path the hook took, for the log
    reason: str = ""  # what the agent reads, where it is sent back; empty otherwise
    page: str = ""  # the session page, where the verb is render
    shown: str = ""  # the line the user sees under the turn, where a render's turn wrote a record


# The longest chat reply a session that has a page ends a turn with and writes no record.
CHAT_LINES = 3

UNPARSED = "Fix the record; the session page renders once every record parses."
IN_THE_CHAT = (
    "This session has a page, and this turn wrote no record for it, so the answer went to the chat. "
    "Move it onto the page as {record}, then end the turn without a reply: the hook shows the user the page's link."
)
OUTSIDE_WRITE = (
    "This turn wrote {record} without the Write tool, so the page pairs the user's message with no turn. "
    "Write it again with Write, then end the turn without a reply: the hook shows the user the page's link."
)


def decide(hook: dict, directory: Path | None) -> Decision:
    """What to do with the turn the hook JSON describes, over the session directory. "This turn"
    runs from the prompt that started it (`session_page.turn_start`), whoever sent that prompt.

    A session with no directory, or one left alone, lets the turn end. In a session that has a
    directory:

    - A record that does not parse is sent back with the reason the reader gives, every time, and
      nothing renders.
    - A reply longer than CHAT_LINES with no record written this turn is sent back to move the
      answer onto the page. Where the turn wrote a record without the Write tool, the send-back
      names that record, to be written again with Write.
    - A record written this turn that `turn_review` finds fault with is sent back with its findings.
    - Otherwise the page renders. Where this turn wrote a record, the render comes with the line
      the user sees under the turn (`shown`), since the agent ends such a turn without a reply.

    The answer in the chat and the review each send the agent back once per turn. A turn a Stop hook
    already continued renders a long reply, so an agent that keeps its answer in the chat is not
    held in a loop. A record reviewed this turn renders unreviewed, so the revised record reaches
    the page.
    """
    if os.environ.get("DISPATCH_WORKLOG") or os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return Decision("allow", "dispatched worker" if os.environ.get("DISPATCH_WORKLOG") else "print-mode session")
    if directory is None:
        return Decision("allow", "no project with an agent repo")
    if not directory.is_dir():
        return Decision("allow", "no session directory")
    try:
        session = read_session(directory, Path(hook["transcript_path"]))
    except RecordError as e:
        return Decision("send back", "record does not parse", f"{e}\n{UNPARSED}")
    reply = [line for line in (hook.get("last_assistant_message") or "").splitlines() if line.strip()]
    turn = written_this_turn(session)
    again = hook.get("stop_hook_active")
    if len(reply) > CHAT_LINES and turn is None and not again:
        if outside := written_outside_write(session):
            return Decision("send back", "record written outside Write", OUTSIDE_WRITE.format(record=outside.path, page=(directory / PAGE).as_uri()))
        return Decision("send back", "answer in the chat", IN_THE_CHAT.format(record=directory / "turns" / f"{session.turns[-1].number + 1:02d}.md", page=(directory / PAGE).as_uri()))
    if turn is None:
        return Decision("render", "no record written this turn", page=page(session, datetime.now()))
    if turn_review.reviewed_since(session.id, session.began):
        turn_review.log(session.id, decision="re-entry", record=str(turn.path), text=turn.path.read_text())
        return Decision("render", "record reviewed this turn", page=page(session, datetime.now()), shown=shown(session, directory))
    if said := turn_review.feedback_on(session, turn):
        return Decision("send back", "review findings", said)
    return Decision("render", "review found nothing", page=page(session, datetime.now()), shown=shown(session, directory))


def shown(session: Session, directory: Path) -> str:
    """The line under a turn whose answer is on the page: what waits on the user there, and the link."""
    waiting = [q.tag for _, q in open_questions(session)]
    ask = f"waiting on you: {' '.join(waiting)}" if waiting else "nothing waiting on you"
    return f"session page · {ask} · {(directory / PAGE).as_uri()}"


def written_this_turn(session: Session) -> Turn | None:
    """The newest record the transcript writes after this turn began, by the write time the page
    pairs messages by. With no turn begun yet, the newest record the transcript writes."""
    written = [t for t in session.turns if t.written and (session.began is None or t.written > session.began)]
    return written[-1] if written else None


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


def open_in_browser(page: Path) -> str:
    """Open the page in the browser without waiting on it, and say what came of that. A host with no
    `claude-browser`, or one that fails to start, leaves the page on disk and the turn as it was."""
    if not (opener := shutil.which("claude-browser")):
        return "no claude-browser on PATH"
    try:
        subprocess.Popen([opener, str(page)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        return f"{opener} did not start: {e}"
    return f"started {opener}"


def main() -> None:
    hook = json.load(sys.stdin)
    directory = session_directory(Path(hook["cwd"]), hook["session_id"])
    decision = decide(hook, directory)
    turn_review.log(hook["session_id"], verb=decision.verb, why=decision.why, directory=directory and str(directory))
    if decision.verb == "render":
        first = not (directory / PAGE).exists()
        (directory / PAGE).write_text(decision.page)
        if first:
            turn_review.log(hook["session_id"], opened=open_in_browser(directory / PAGE), page=str(directory / PAGE))
        if decision.shown:
            print(json.dumps({"systemMessage": decision.shown}))
    elif decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
