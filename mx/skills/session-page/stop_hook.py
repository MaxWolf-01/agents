#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stop hook: what the end of a turn does to the session page.

It reads the Stop hook JSON on stdin and answers with one of three verbs over the session's own
directory: render the page, send the agent back with a reason, or let the turn end. A session
with no directory never gets one from here: the agent creates it by writing the first record.

The rule is stubbed. test_stop_hook.py holds the properties it has to satisfy, and the
`session-stop-hook` slice of agent/tickets/session-page.md fills it in against its Decisions.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from session_page import PAGE, render_session  # noqa: E402

SESSIONS = Path("agent/sessions")  # where a session's directory sits, from the repo root

RENDER = "render"
SEND_BACK = "send back"
ALLOW = "allow"


@dataclass(frozen=True)
class Decision:
    """What the turn's end comes to, and what the agent is sent back with."""

    verb: str  # RENDER, SEND_BACK or ALLOW
    reason: str = ""  # what the agent reads, on SEND_BACK; empty otherwise


def session_directory(hook: dict) -> Path:
    """The directory this session's page and records live in, whether or not it exists."""
    return Path(hook["cwd"]) / SESSIONS / hook["session_id"]


def decide(hook: dict, directory: Path) -> Decision:
    """What to do with the turn the hook JSON describes, over the session directory.

    A record that does not parse is sent back with its `path:line: reason` and nothing renders; a
    session that has a page and answered in the chat without writing a record this turn is sent
    back to move the answer onto the page; a session with a page and a record renders it; anything
    else lets the turn end. Lifted by session-stop-hook.
    """
    raise NotImplementedError


def main() -> None:
    hook = json.load(sys.stdin)
    directory = session_directory(hook)
    decision = decide(hook, directory)
    if decision.verb == RENDER:
        (directory / PAGE).write_text(render_session(directory, Path(hook["transcript_path"])))
    elif decision.verb == SEND_BACK:
        # additionalContext continues the turn and shows in the transcript as "Stop hook feedback"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
