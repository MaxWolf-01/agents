#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""PostToolUse hook: what writing a session record does while the turn still runs.

It reads the PostToolUse JSON of a Write, Edit or MultiEdit on stdin; `decide` answers with a
Decision over the session's own directory, and `main` hands its reason to the agent as added
context. The agent fixes the record before it writes its recap, so the turn ends on the recap and
not on the fix.

- A write that leaves a record of the session unparseable is sent back with the reader's error,
  every time. A session whose first turn record is still to come is not unparseable for that.
- The turn record a turn first writes with Write gets the turn's prose review (`turn_review`), and
  its findings are sent back. The review runs once per turn: an edit after the findings, or a
  record written later in the turn, is parsed and not reviewed again.

Claude Code writes a tool call to the transcript only after its PostToolUse hooks have run, so the
hook reads the transcript as though it ended on the call it was given; the page pairs a record with
the user's messages by that call.

It leaves alone the sessions the Stop hook does, and every write outside this session's directory,
which it tells from the path alone: it runs on every file edit of every session. Each decision on a
record is one JSON line in `turn_review.LOG`.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The modules beside this one cost a third of a second to import, so they are imported where they
# are used, past the check in `main` that a write outside the session's directory stops at.
if TYPE_CHECKING:
    from stop_hook import Decision


def decide(hook: dict, directory: Path | None) -> "Decision":
    """What to tell the agent after the write the hook JSON describes, over the session directory.
    The verb is "send back" with a reason for the agent, or "allow" with none."""
    import turn_review
    from session_page import NoTurnRecords, RecordError, read_session
    from stop_hook import RECAP, UNPARSED, Decision, left_alone, written_this_turn

    if unread := left_alone():
        return Decision("allow", unread)
    if directory is None:
        return Decision("allow", "no project with an agent repo")
    written = Path(hook["cwd"], hook["tool_input"]["file_path"]).resolve()
    if written.parent not in (directory.resolve(), directory.resolve() / "turns"):
        return Decision("allow", "no record of this session")
    call = {"type": "assistant", "timestamp": datetime.now(UTC).isoformat(),
            "message": {"content": [{"type": "tool_use", "name": hook["tool_name"], "input": hook["tool_input"]}]}}
    try:
        session = read_session(directory, Path(hook["transcript_path"]), pending=(call,))
    except NoTurnRecords:
        return Decision("allow", "no turn record yet")
    except RecordError as e:
        return Decision("send back", "record does not parse", f"{e}\n{UNPARSED}")
    turn = written_this_turn(session)
    if hook["tool_name"] != "Write" or turn is None or turn.path.resolve() != written:
        return Decision("allow", "records parse")
    if turn_review.reviewed_since(session.id, session.began):
        return Decision("allow", "record reviewed this turn")
    if said := turn_review.feedback_on(session, turn):
        return Decision("send back", "review findings", f"{said}\nThis review is yours alone: once the record is revised, {RECAP}, as you would have without it.")
    return Decision("allow", "review found nothing")


def main() -> None:
    hook = json.load(sys.stdin)
    if hook["session_id"] not in Path(str(hook.get("tool_input", {}).get("file_path", ""))).parts:
        return
    import turn_review
    from session_page import session_directory

    directory = session_directory(Path(hook["cwd"]), hook["session_id"])
    decision = decide(hook, directory)
    turn_review.log(hook["session_id"], verb=decision.verb, why=decision.why, tool=hook["tool_name"], path=hook["tool_input"]["file_path"])
    if decision.verb == "send back":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": decision.reason}}))


if __name__ == "__main__":
    main()
