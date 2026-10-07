#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""Three hooks: a session hears where its context stands, and a /clear finds the handoff it wrote.

`checkpoint` runs on PostToolBatch and UserPromptSubmit: it reads the session's context size off
the last assistant message in the transcript (the tokens the last request sent as its prompt) and,
the first time it stands past a mark, says so to the model, once per mark, naming the mark by its
place (the first, second, third of them) and its figure. The marks are MX_CONTEXT_CHECKPOINTS,
comma-separated token counts, three of them unless set (MARKS below). A context that has fallen
back under a mark said (a compaction) hears that mark again on its way back up. A dispatched
worker (DISPATCH_WORKLOG set), a print-mode session (CLAUDE_CODE_SESSION_ATTENDED=0) and a
subagent's tool batches (agent_id in the event) hear nothing: only the session's own thread has a
user to tell.

`ended <pid>` runs on SessionEnd with reason clear and `started <pid>` on SessionStart with source
clear, in the same Claude Code process: the first records the session id that just ended under
that process's pid, the second reads it back and looks for a continuation handoff that session
wrote in the agent repo of the working directory (`tracker root` finds it). With one there, the
fresh session is handed the handoff skill's pickup line, which names `pickup.py` by its absolute
path; with none, or nothing recorded, nothing.
<pid> is the hook shell's $PPID, which is the Claude Code process.

State is under $XDG_STATE_HOME/mx (~/.local/state/mx): checkpoints/<session id> holds the highest
mark said, clear/<pid> the id of the session that /clear ended, and hooks.jsonl one line per run
of any of the three, with what it decided and why, so a hook that never ran reads differently
from one that ran and stayed silent.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "mx"
MARKS = [int(m) for m in os.environ.get("MX_CONTEXT_CHECKPOINTS", "300000,500000,600000").split(",") if m.strip()]
TRACKER = Path(__file__).resolve().parents[1] / "tracker" / "tracker.py"
PICKUP = Path(__file__).resolve().parent / "pickup.py"
BLOCK = 64 * 1024
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth")


def log(mode: str, session: str | None, **entry: object) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "hooks.jsonl").open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "hook": mode, "session_id": session, **entry}) + "\n")


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


def figure(tokens: int) -> str:
    return f"{tokens // 1000}k"


def checkpoint(hook: dict) -> None:
    session = hook["session_id"]
    if os.environ.get("DISPATCH_WORKLOG"):
        return log("checkpoint", session, decision="skip", why="dispatched worker")
    if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return log("checkpoint", session, decision="skip", why="unattended session")
    if hook.get("agent_id"):
        return log("checkpoint", session, decision="skip", why="subagent", agent_id=hook["agent_id"])
    tokens = context_tokens(Path(hook["transcript_path"]))
    if tokens is None:
        return log("checkpoint", session, decision="quiet", why="no assistant message in the transcript")
    seen = STATE / "checkpoints" / session
    try:
        told = int(seen.read_text())
    except (OSError, ValueError):
        told = 0  # never told, or a record no reading can trust: the marks are unsaid again
    if tokens < told:
        # the context fell back under a mark already said (a compaction): the marks above it are
        # unsaid again, so the session hears them as it grows back
        told = max([m for m in MARKS if m <= tokens], default=0)
        seen.write_text(str(told))
    passed = [m for m in MARKS if told < m <= tokens]
    if not passed:
        return log("checkpoint", session, decision="quiet", tokens=tokens, told=told)
    mark = max(passed)
    seen.parent.mkdir(parents=True, exist_ok=True)
    seen.write_text(str(mark))
    place = ORDINALS[MARKS.index(mark)] if MARKS.index(mark) < len(ORDINALS) else f"{MARKS.index(mark) + 1}th"
    marks = ", ".join(figure(m) for m in MARKS)
    said(f"Context checkpoint: this session's context stands at {figure(tokens)} tokens, past the "
         f"{place} of {len(MARKS)} marks ({figure(mark)}; the marks are {marks}). What a session does at "
         f"each mark is in the mx handoff skill, under Continuation.", hook["hook_event_name"])
    log("checkpoint", session, decision="said", tokens=tokens, mark=mark)


def ended(hook: dict, pid: str) -> None:
    record = STATE / "clear" / pid
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(hook["session_id"])
    log("ended", hook["session_id"], decision="recorded", pid=pid)


def handoffs_of(cwd: Path) -> Path | None:
    """The agent repo's handoffs directory for the project at cwd, through the one command that
    finds the agent repo; None outside any project, with the command's own words on stderr."""
    done = subprocess.run([str(TRACKER), "root"], cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0 or not done.stdout.strip():
        print(f"checkpoint.py: no agent repo found from {cwd}: {done.stderr.strip()}", file=sys.stderr)
        return None
    return Path(done.stdout.strip()).parent / "handoffs"


def continuation_of(handoff: Path, session: str) -> bool:
    """Whether the handoff's frontmatter names `session` and the continuation purpose: a fork's
    handoff carries the same session id and is another session's to pick up."""
    text = handoff.read_text(errors="replace")
    if not text.startswith("---") or text.count("---") < 2:
        return False
    lines = {line.strip() for line in text.split("---", 2)[1].splitlines()}
    return f"session: {session}" in lines and "purpose: continuation" in lines


def started(hook: dict, pid: str) -> None:
    record = STATE / "clear" / pid
    if not record.exists():
        return log("started", hook["session_id"], decision="quiet", why="no session recorded for this pid", pid=pid)
    session = record.read_text().strip()
    record.unlink()
    cwd = Path(hook["cwd"])
    handoffs = handoffs_of(cwd)
    if handoffs is None or not handoffs.is_dir():
        return log("started", hook["session_id"], decision="quiet", why="no handoffs directory", cwd=str(cwd), ended=session)
    written = [p for p in handoffs.glob("*.md") if continuation_of(p, session)]
    if not written:
        return log("started", hook["session_id"], decision="quiet", why="no continuation of the ended session", ended=session)
    latest = max(written, key=lambda p: p.stat().st_mtime).resolve()
    # the pickup line, as /mx:handoff gives it to the user to type
    said(f"Continue from {latest}: first run `{PICKUP} {latest}`, which prints the handoff in full, retires it "
         f"and links the session pages.", "SessionStart")
    log("started", hook["session_id"], decision="said", handoff=str(latest), ended=session)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    pid = sys.argv[2] if len(sys.argv) > 2 else ""
    hook = json.load(sys.stdin)
    if mode == "checkpoint":
        checkpoint(hook)
    elif mode in ("ended", "started") and pid:
        (ended if mode == "ended" else started)(hook, pid)
    else:
        sys.exit(f"checkpoint.py: takes checkpoint, ended <pid> or started <pid>, not {sys.argv[1:]!r}")


if __name__ == "__main__":
    main()
