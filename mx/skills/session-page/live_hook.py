#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Async hook: the tool calls of the turn under way, written beside the session's page as they
happen (`LIVE`), which the page's log polls while it is open. The page itself is rendered only as a
turn ends, and its log (`session_page.LOG`) holds only turns that ended.

It runs on four events, each handing it its JSON on stdin:

- UserPromptSubmit starts the file anew, holding the prompt and no calls. A turn the user
  interrupted fires no Stop, so its calls are dropped here, as the next one starts.
- PreToolUse adds the call, with no result yet.
- PostToolBatch gives each call of the batch its result, the text the model reads.
- PostToolUseFailure marks the call failed.

The Stop hook deletes the file once the page holds the turn. Events after it find no file and leave
it absent: only a prompt or a call starts one. Two calls of one batch run their hooks at once, so
each rewrite holds a lock on the session's directory, and a result that comes before its call's
own event adds the call itself.

It leaves alone a subagent's calls, and a session with no directory: one whose first turn has not
ended yet, or one nobody reads the page of (`session_page.left_alone`), which never gets one.
"""

import fcntl
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from steps import Step, result_text, shown  # noqa: E402

# Beside the page, as a script setting `window.liveCalls` to {"prompt", "steps"}; `steps` is a list
# of `steps.shown`, each with its call's id.
LIVE = "live-calls.js"
PREFIX = "window.liveCalls = "
PAGES = "session-pages"  # session_page.PAGES, which this does not import: it costs a third of a second


def main() -> None:
    hook = json.load(sys.stdin)
    if hook.get("agent_id"):
        return
    account = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    directory = account / PAGES / hook["session_id"]
    if not directory.is_dir():
        return
    lock = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        update(directory / LIVE, hook, datetime.now(UTC))
    finally:
        os.close(lock)


def update(path: Path, hook: dict, now: datetime) -> None:
    """Apply the event `hook` describes to the live file at `path`, as of `now`."""
    event = hook["hook_event_name"]
    if event == "UserPromptSubmit":
        return write(path, {"prompt": first_line(hook.get("prompt", "")), "steps": []})
    if (live := read(path)) is None:
        return
    calls = {s["id"]: s for s in live["steps"]}

    def call(hook_call: dict) -> dict:
        """The step of the call the event names, added where its own event has not come yet."""
        key = hook_call["tool_use_id"]
        if key not in calls:
            step = shown(Step(now, hook_call["tool_name"], hook_call.get("tool_input") or {})) | {"id": key}
            calls[key] = step
            live["steps"].append(step)
        return calls[key]

    if event == "PreToolUse":
        call(hook)
    elif event == "PostToolBatch":
        for c in hook.get("tool_calls", []):
            call(c).update(output=result_text(c.get("tool_response")), done=now.isoformat())
    elif event == "PostToolUseFailure":
        step = call(hook)
        step.update(failed=True, done=step["done"] or now.isoformat(), output=step["output"] or str(hook.get("error", "")))
    else:
        return
    write(path, live)


def first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text().removeprefix(PREFIX))
    except (FileNotFoundError, ValueError):
        return None


def write(path: Path, live: dict) -> None:
    """Replace the file whole, so the page never loads one half written."""
    part = path.with_suffix(".part")
    part.write_text(f"{PREFIX}{json.dumps(live, ensure_ascii=False)}\n")
    part.replace(path)


if __name__ == "__main__":
    main()
