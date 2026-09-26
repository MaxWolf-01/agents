#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "markdown"]
# ///
"""Stop hook: what the end of a turn does to the session page.

It reads the Stop hook JSON on stdin and answers with a Verb over the session's own directory,
which `main` then applies. A session with no directory never gets one from here: the agent creates
it by writing the first record.

The rule is stubbed. test_stop_hook.py holds the properties it has to satisfy, and
agent/tickets/session-stop-hook.md fills it in against the Decisions of its parent,
agent/tickets/session-page.md.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from session_page import PAGE, SESSIONS, Session, render_session  # noqa: E402

Verb = Literal["render", "send back", "allow"]


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: Verb
    reason: str = ""  # what the agent reads, where it is sent back; empty otherwise


def session_directory(hook: dict) -> Path:
    """The directory this session's page and records live in, whether or not it exists."""
    return Path(hook["cwd"]) / SESSIONS / hook["session_id"]


def review(session: Session) -> list[str]:
    """At most three findings on the prose of the record the last turn wrote, from Opus 5.5 at low
    effort reading it against the chat rules of mx/skills/writing-for-humans/CATALOGUE.md with what
    the reader of the page has seen: the session's earlier records and the user's messages, no tool
    calls. The agent revises the record, and the page renders on the turn after. Lifted by
    turn-record-review.
    """
    raise NotImplementedError


def decide(hook: dict, directory: Path) -> Decision:
    """What to do with the turn the hook JSON describes, over the session directory.

    A record that does not parse is sent back with the reason the reader gives, and nothing
    renders; a session whose directory holds a record, answered in the chat without writing one
    this turn, is sent back to move the answer onto the page; a session whose directory holds the
    records of this turn renders them; anything else lets the turn end. Lifted by
    session-stop-hook; turn-record-review adds the send-back for what `review` finds in a record.
    """
    raise NotImplementedError


def main() -> None:
    hook = json.load(sys.stdin)
    directory = session_directory(hook)
    decision = decide(hook, directory)
    if decision.verb == "render":
        (directory / PAGE).write_text(render_session(directory, Path(hook["transcript_path"])))
    elif decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
