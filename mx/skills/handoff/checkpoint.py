#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""Three hooks that tell a session where its context stands and hand a fresh one its handoff.

`checkpoint` runs on PostToolBatch and UserPromptSubmit: it reads the session's context size off
the last assistant message in the transcript (the tokens the last request sent as its prompt) and,
the first time it stands past a mark, says so to the model, once per mark. The marks are
MX_CONTEXT_CHECKPOINTS, comma-separated token counts, 200000,400000,600000 unless set. A dispatched
worker (DISPATCH_WORKLOG set) and a print-mode session (CLAUDE_CODE_SESSION_ATTENDED=0) hear
nothing: neither has a user to type /clear.

`ended <pid>` runs on SessionEnd with reason clear and `started <pid>` on SessionStart with source
clear, in the same Claude Code process: the first records the session id that just ended under
that process's pid, the second reads it back and looks for a handoff that session wrote in the agent
repo of the working directory (`tracker root` finds it). With one there, the fresh session is told
where to continue from; with none, or nothing recorded, it is told nothing. <pid> is the hook
shell's $PPID, which is the Claude Code process.

State is under $XDG_STATE_HOME/mx (~/.local/state/mx): checkpoints/<session id> holds the highest
mark said, clear/<pid> the id of the session that /clear ended.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "mx"
MARKS = [int(m) for m in os.environ.get("MX_CONTEXT_CHECKPOINTS", "200000,400000,600000").split(",") if m.strip()]
PLUGIN = Path(__file__).resolve().parents[2]
BLOCK = 64 * 1024


def context_tokens(transcript: Path) -> int | None:
    """What the last request sent as its prompt: the last assistant message's input, cache-read and
    cache-write tokens together. Read from the end of the file, since a transcript grows to
    megabytes and the answer is in its last lines."""
    try:
        size = transcript.stat().st_size
    except OSError:
        return None
    with transcript.open("rb") as f:
        tail = b""
        end = size
        while end > 0:
            start = max(0, end - BLOCK)
            f.seek(start)
            tail = f.read(end - start) + tail
            end = start
            for line in reversed(tail.split(b"\n")):
                if b'"assistant"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                usage = entry.get("message", {}).get("usage") if entry.get("type") == "assistant" else None
                if usage:
                    return sum(usage.get(k) or 0 for k in
                               ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            # the first line of the block may be cut; the next block completes it
            tail = tail.split(b"\n", 1)[0] if start > 0 else b""
    return None


def said(text: str, event: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def checkpoint(hook: dict) -> None:
    if os.environ.get("DISPATCH_WORKLOG") or os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return
    session, transcript = hook.get("session_id"), hook.get("transcript_path")
    if not session or not transcript:
        return
    tokens = context_tokens(Path(transcript))
    if tokens is None:
        return
    seen = STATE / "checkpoints" / session
    told = int(seen.read_text()) if seen.exists() else 0
    passed = [m for m in MARKS if told < m <= tokens]
    if not passed:
        return
    mark = max(passed)
    seen.parent.mkdir(parents=True, exist_ok=True)
    seen.write_text(str(mark))
    marks = ", ".join(f"{m // 1000}k" for m in MARKS)
    said(f"Context checkpoint: this session's context stands at {tokens // 1000}k tokens, past the "
         f"{mark // 1000}k mark (the marks are {marks}). What a session does at a checkpoint is in the "
         f"mx handoff skill, under Continuation.", hook.get("hook_event_name", "PostToolBatch"))


def ended(hook: dict, pid: str) -> None:
    session = hook.get("session_id")
    if not session or not pid:
        return
    record = STATE / "clear" / pid
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(session)


def handoffs_of(cwd: Path) -> Path | None:
    """The agent repo's handoffs directory for the project at cwd, through the one command that
    finds the agent repo; None outside any project."""
    done = subprocess.run(["uv", "run", "--quiet", str(PLUGIN / "skills" / "tracker" / "tracker.py"), "root"],
                          cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0 or not done.stdout.strip():
        return None
    return Path(done.stdout.strip()).parent / "handoffs"


def names_session(handoff: Path, session: str) -> bool:
    """Whether the handoff's frontmatter carries `session: <session>`."""
    text = handoff.read_text(errors="replace")
    if not text.startswith("---"):
        return False
    front = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    return any(line.strip() == f"session: {session}" for line in front.splitlines())


def started(hook: dict, pid: str) -> None:
    record = STATE / "clear" / pid
    if not pid or not record.exists():
        return
    session = record.read_text().strip()
    record.unlink()
    handoffs = handoffs_of(Path(hook.get("cwd") or os.getcwd()))
    if handoffs is None or not handoffs.is_dir():
        return
    written = [p for p in handoffs.glob("*.md") if names_session(p, session)]
    if not written:
        return
    latest = max(written, key=lambda p: p.stat().st_mtime)
    said(f"The session before /clear wrote a handoff for this one: {latest.resolve()}. "
         f"The mx handoff skill says a continuation reads it in full first, then git rm's it in the "
         f"agent repo and commits, since a handoff is retired once a session has picked it up.",
         "SessionStart")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    pid = sys.argv[2] if len(sys.argv) > 2 else ""
    hook = json.load(sys.stdin)
    if mode == "checkpoint":
        checkpoint(hook)
    elif mode == "ended":
        ended(hook, pid)
    elif mode == "started":
        started(hook, pid)
    else:
        sys.exit(f"checkpoint.py: takes checkpoint, ended <pid> or started <pid>, not {mode!r}")


if __name__ == "__main__":
    main()
