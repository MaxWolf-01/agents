#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""SessionStart and UserPromptSubmit hook: tell the agent when the mx it runs from has changed.

A session loads mx's skills and hooks from one installed version, and moves to another only on
`/reload-plugins` (which the container hub types into an idle session once a newer one is
installed) or on a resume. Skill text the agent read before the move stays in its context as it
was, so it has to hear that it moved, and what changed.

Per session, this keeps the version it last ran from in `$CLAUDE_PLUGIN_DATA/sessions/<session
id>`, one line, which the container hub also reads as the version the session has loaded. Where
the version it runs from now differs, it tells the agent (`additionalContext`) which versions it
moved across and the CHANGELOG.md entries of those versions, and the user (`systemMessage`) the
move in one line. A session's start records its version and says nothing. A prompt with no
record yet comes from a session that started before this hook existed and has since been moved
onto it; the agent hears that much, without entries, since the version it came from is unknown.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
SHOWN = 20  # changelog lines the agent reads at most; the rest stay in CHANGELOG.md
KEPT = 60 * 86400  # a record of a session that has not run this long is deleted when another session starts


def version_of(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text))


def entries(old: str, new: str) -> list[str]:
    """The CHANGELOG.md sections of the versions after `old`, up to and including `new`, newest first, each under
    its heading. Every installed mx carries the file (`make release-*` writes it), so a missing one is an error."""
    lines, taking = [], False
    for line in CHANGELOG.read_text().splitlines():
        if heading := re.match(r"##\s+(\S+)", line):
            taking = version_of(old) < version_of(heading[1]) <= version_of(new)
        if taking and line.strip():
            lines.append(line)
    return lines


def told(old: str | None, new: str) -> tuple[str, str]:
    """What the agent and the user read of a move from `old` to `new`."""
    if old is None:
        return (f"mx, the plugin your skills and hooks come from, was updated in this session to {new}. Skills and "
                "rules you read before this point may be out of date: read a skill again before you rely on it.",
                f"mx updated to {new}")
    lines = entries(old, new)
    more = f"\n... and {len(lines) - SHOWN} more lines in {CHANGELOG}" if len(lines) > SHOWN else ""
    changes = " What changed:\n" + "\n".join(lines[:SHOWN]) + more if lines else ""
    return (f"mx, the plugin your skills and hooks come from, moved from {old} to {new} in this session. Skills and "
            f"rules you read before this point are {old}'s: read a skill again before you rely on it.{changes}",
            f"mx updated from {old} to {new}")


def main() -> None:
    hook = json.load(sys.stdin)
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data:
        return
    sessions = Path(data) / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    record = sessions / hook["session_id"]
    now = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
    try:
        before = record.read_text().strip()
    except FileNotFoundError:
        before = None
    started = hook["hook_event_name"] == "SessionStart"
    if started:
        for old in sessions.iterdir():
            if old != record and time.time() - old.stat().st_mtime > KEPT:
                old.unlink(missing_ok=True)
    if before != now:
        tmp = record.with_name(f".{record.name}.tmp")
        tmp.write_text(now + "\n")
        tmp.replace(record)
    else:
        record.touch()  # a record's age is how long its session has not run, which pruning goes by
    if before == now or (before is None and started):
        return
    agent, user = told(before, now)
    print(json.dumps({"systemMessage": user,
                      "hookSpecificOutput": {"hookEventName": hook["hook_event_name"], "additionalContext": agent}}))


if __name__ == "__main__":
    main()
