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
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from session_page import PAGE, SESSIONS, RecordError, Session, page, read_session, session_directory  # noqa: E402

Verb = Literal["render", "send back", "allow"]


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: Verb
    reason: str = ""  # what the agent reads, where it is sent back; empty otherwise
    page: str = ""  # the session page, where the verb is render


# The longest chat reply a session that has a page ends a turn with and writes no record.
CHAT_LINES = 3

UNPARSED = "Fix the record; the session page renders once every record parses."
IN_THE_CHAT = (
    "This session has a page, and this turn wrote no record for it: the answer went to the chat. "
    "Move it onto the page as {record}, then reply with one line and the page's link: {page}"
)


def review(session: Session) -> list[str]:
    """At most three findings on the prose of the record the last turn wrote, from Opus 5.5 at low
    effort reading it against the chat rules of mx/skills/writing-for-humans/CATALOGUE.md with what
    the reader of the page has seen: the session's earlier records and the user's messages, no tool
    calls. The agent revises the record, and the page renders on the turn after. Lifted by
    turn-record-review.
    """
    raise NotImplementedError


def decide(hook: dict, directory: Path | None) -> Decision:
    """What to do with the turn the hook JSON describes, over the session directory.

    In a session that has a directory, a record that does not parse is sent back with the reason
    the reader gives, and nothing renders; a reply longer than CHAT_LINES with no record written
    since the user last spoke is sent back to move the answer onto the page; otherwise the page
    renders. A session with no directory, or one left alone, lets the turn end. turn-record-review
    adds the send-back for what `review` finds in a record.

    The answer in the chat is sent back once per turn: a turn a Stop hook already continued
    renders, so an agent that keeps its answer in the chat is not held in a loop. A record that
    does not parse is sent back every time, since the page never renders one.
    """
    if os.environ.get("DISPATCH_WORKLOG") or os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return Decision("allow")
    if directory is None or not directory.is_dir():
        return Decision("allow")
    try:
        session = read_session(directory, Path(hook["transcript_path"]))
    except RecordError as e:
        return Decision("send back", f"{e}\n{UNPARSED}")
    reply = [line for line in (hook.get("last_assistant_message") or "").splitlines() if line.strip()]
    if len(reply) > CHAT_LINES and not recorded_since_spoken(session) and not hook.get("stop_hook_active"):
        return Decision("send back", IN_THE_CHAT.format(record=directory / "turns" / f"{session.turns[-1].number + 1:02d}.md", page=(directory / PAGE).as_uri()))
    return Decision("render", page=page(session, datetime.now()))


def recorded_since_spoken(session: Session) -> bool:
    """Whether a record was written after the user last spoke: by the transcript's write call on
    it, or, for one written some other way, by the file's modification time."""
    if session.last_said is None:
        return True
    return any(
        (turn.written and turn.written > session.last_said)
        or datetime.fromtimestamp(turn.path.stat().st_mtime, UTC) > session.last_said
        for turn in session.turns
    )


def main() -> None:
    hook = json.load(sys.stdin)
    directory = session_directory(Path(hook["cwd"]), hook["session_id"])
    decision = decide(hook, directory)
    if decision.verb == "render":
        (directory / PAGE).write_text(decision.page)
    elif decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
