#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Stop hook: what the end of a turn does to the session page.

It reads the Stop hook JSON on stdin and answers with a Verb over the session's own directory,
which `main` then applies. A session with no directory never gets one from here: the agent creates
it by writing the first record.

It leaves alone a session nobody reads the page of: DISPATCH_WORKLOG set (a dispatched worker), or
CLAUDE_CODE_SESSION_ATTENDED set to 0 (a print-mode session).

Every decision is one JSON line in `session_page.LOG`, beside the review's own: the verb, why the
hook took that path, and the session directory it resolved.
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import turn_review  # noqa: E402
from session_page import PAGE, SESSIONS, RecordError, Session, Turn, page, read_session, session_directory  # noqa: E402

Verb = Literal["render", "send back", "allow"]


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: Verb
    why: str  # which path the hook took, for the log
    reason: str = ""  # what the agent reads, where it is sent back; empty otherwise
    page: str = ""  # the session page, where the verb is render


# The longest chat reply a session that has a page ends a turn with and writes no record.
CHAT_LINES = 3

UNPARSED = "Fix the record; the session page renders once every record parses."
IN_THE_CHAT = (
    "This session has a page, and this turn wrote no record for it: the answer went to the chat. "
    "Move it onto the page as {record}, then reply with one line and the page's link: {page}"
)


def decide(hook: dict, directory: Path | None) -> Decision:
    """What to do with the turn the hook JSON describes, over the session directory.

    In a session that has a directory, a record that does not parse is sent back with the reason
    the reader gives, and nothing renders; a reply longer than CHAT_LINES with no record written
    since the user last spoke is sent back to move the answer onto the page; a record written this
    turn that `turn_review` finds fault with is sent back with its findings; otherwise the page
    renders. A session with no directory, or one left alone, lets the turn end.

    The answer in the chat and the review each send the agent back once per turn: a turn a Stop hook
    already continued renders a long reply, and a record reviewed since the user last spoke renders
    unreviewed, so the revised record reaches the page and an agent that keeps its answer in the
    chat is not held in a loop. A record that does not parse is sent back every time,
    since the page never renders one.
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
        return Decision("send back", "answer in the chat", IN_THE_CHAT.format(record=directory / "turns" / f"{session.turns[-1].number + 1:02d}.md", page=(directory / PAGE).as_uri()))
    if turn is None:
        return Decision("render", "no record written this turn", page=page(session, datetime.now()))
    if turn_review.reviewed_since(session.id, session.last_said):
        turn_review.log(session.id, decision="re-entry", record=str(turn.path), text=turn.path.read_text())
        return Decision("render", "record reviewed this turn", page=page(session, datetime.now()))
    if said := turn_review.feedback_on(session, turn):
        return Decision("send back", "review findings", said)
    return Decision("render", "review found nothing", page=page(session, datetime.now()))


def written_this_turn(session: Session) -> Turn | None:
    """The newest record written after the user last spoke: by the transcript's write call on it,
    or, for one written some other way, by the file's modification time. With nothing said yet,
    the newest record."""
    if session.last_said is None:
        return session.turns[-1] if session.turns else None
    written = [
        turn for turn in session.turns
        if (turn.written and turn.written > session.last_said)
        or datetime.fromtimestamp(turn.path.stat().st_mtime, UTC) > session.last_said
    ]
    return written[-1] if written else None


def main() -> None:
    hook = json.load(sys.stdin)
    directory = session_directory(Path(hook["cwd"]), hook["session_id"])
    decision = decide(hook, directory)
    turn_review.log(hook["session_id"], verb=decision.verb, why=decision.why, directory=directory and str(directory))
    if decision.verb == "render":
        (directory / PAGE).write_text(decision.page)
    elif decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
