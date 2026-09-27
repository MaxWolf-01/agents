# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for the three context hooks in `checkpoint.py`. Run: uv run test_checkpoint.py

The seam is the script, run as Claude Code runs a command hook: the event's JSON on stdin, the
state directory and the marks in the environment, and what it prints read as the hook's output.
The oracle is the `context-checkpoints` ticket: a session crossing a mark is told once per mark,
by the mechanism and not by a rule it remembers; a dispatched worker and a print-mode session
are told nothing; after /clear a fresh session in a project whose agent repo holds a handoff the
cleared session wrote is told where it is, and one with no such handoff is told nothing.
"""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "checkpoint.py"


def turn(kind: str, **usage: int) -> str:
    """One transcript line, as Claude Code writes them: the usage is the request's own."""
    if kind == "assistant":
        return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}],
                                                           "usage": {"input_tokens": 3, "output_tokens": 9, **usage}}}) + "\n"
    return json.dumps({"type": kind, "message": {"role": "user", "content": [{"type": "tool_result", "content": "x" * 50}]}}) + "\n"


def hook(tmp_path: Path, mode: str, event: dict, *args: str, **env: str) -> subprocess.CompletedProcess:
    clean = {k: v for k, v in os.environ.items() if k not in ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED", "MX_CONTEXT_CHECKPOINTS")}
    return subprocess.run([str(SCRIPT), mode, *args], input=json.dumps(event), capture_output=True, text=True, timeout=60,
                          env={**clean, "XDG_STATE_HOME": str(tmp_path / "state"), **env})


def context(out: subprocess.CompletedProcess) -> str:
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"] if out.stdout.strip() else ""


def test_a_session_crossing_a_mark_is_told_once_per_mark_and_the_note_names_the_figure(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    event = {"session_id": "s1", "transcript_path": str(transcript), "hook_event_name": "PostToolBatch"}
    transcript.write_text(turn("assistant", cache_read_input_tokens=150_000))
    assert context(hook(tmp_path, "checkpoint", event)) == "", "under every mark, nothing is said"

    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=190_000, cache_creation_input_tokens=20_000) + turn("user"))
    note = context(hook(tmp_path, "checkpoint", event))
    assert note.startswith("Context checkpoint: this session's context stands at 210k tokens, past the 200k mark"), note
    assert "mx handoff skill" in note

    assert context(hook(tmp_path, "checkpoint", event)) == "", "the same mark is not said twice"
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=380_000))
    assert context(hook(tmp_path, "checkpoint", event)) == "", "between marks, nothing"
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=610_000))
    note = context(hook(tmp_path, "checkpoint", event))
    assert "past the 600k mark" in note, "the highest mark crossed is the one said, once"
    assert context(hook(tmp_path, "checkpoint", event)) == ""

    other = {"session_id": "s2", "transcript_path": str(transcript), "hook_event_name": "UserPromptSubmit"}
    out = hook(tmp_path, "checkpoint", other)
    assert json.loads(out.stdout)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "past the 600k mark" in context(out), "another session reading the same size is told on its own account"


def test_the_marks_come_from_the_environment_so_a_demo_can_cross_one(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=25_000))
    event = {"session_id": "s1", "transcript_path": str(transcript), "hook_event_name": "PostToolBatch"}
    note = context(hook(tmp_path, "checkpoint", event, MX_CONTEXT_CHECKPOINTS="20000,40000"))
    assert "past the 20k mark (the marks are 20k, 40k)" in note


def test_the_last_assistant_message_is_found_behind_a_line_longer_than_the_read_block(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=250_000)
                          + json.dumps({"type": "user", "message": {"content": "y" * 200_000}}) + "\n"
                          + json.dumps({"type": "system", "content": "z" * 100_000}) + "\n")
    event = {"session_id": "s1", "transcript_path": str(transcript), "hook_event_name": "PostToolBatch"}
    assert "stands at 250k" in context(hook(tmp_path, "checkpoint", event))


def test_a_worker_and_a_print_mode_session_hear_nothing(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=650_000))
    event = {"session_id": "s1", "transcript_path": str(transcript), "hook_event_name": "PostToolBatch"}
    assert context(hook(tmp_path, "checkpoint", event, DISPATCH_WORKLOG=str(tmp_path / "log"))) == ""
    assert context(hook(tmp_path, "checkpoint", event, CLAUDE_CODE_SESSION_ATTENDED="0")) == ""
    assert not (tmp_path / "state").exists(), "nothing was recorded for a session that was not told"


def test_a_transcript_with_no_assistant_message_or_none_at_all_says_nothing(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("user"))
    event = {"session_id": "s1", "transcript_path": str(transcript), "hook_event_name": "PostToolBatch"}
    assert context(hook(tmp_path, "checkpoint", event)) == ""
    event["transcript_path"] = str(tmp_path / "missing.jsonl")
    assert context(hook(tmp_path, "checkpoint", event)) == ""


def project(tmp_path: Path) -> Path:
    """A code repo holding its agent repo at agent/, with a handoffs directory."""
    repo = tmp_path / "lamp"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    agent = repo / "agent"
    subprocess.run(["git", "init", "-q", str(agent)], check=True)
    (agent / "tickets").mkdir()
    (agent / "handoffs").mkdir()
    return repo


def handoff(repo: Path, name: str, session: str) -> Path:
    path = repo / "agent" / "handoffs" / name
    path.write_text(f"---\nsession: {session}\npurpose: continuation\n---\n\n# Where things stand\n")
    return path


def test_after_clear_the_fresh_session_is_handed_the_handoff_the_cleared_one_wrote(tmp_path: Path) -> None:
    repo = project(tmp_path)
    handoff(repo, "2026-09-20-older.md", "old-1")
    mine = handoff(repo, "2026-09-26-effort.md", "old-1")
    handoff(repo, "2026-09-26-other.md", "someone-else")
    assert hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4242").stdout == ""
    out = hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(repo)}, "4242")
    note = context(out)
    assert json.loads(out.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert note.startswith(f"The session before /clear wrote a handoff for this one: {mine.resolve()}."), note
    assert "reads it in full first" in note and "git rm" in note
    assert not (tmp_path / "state" / "mx" / "clear" / "4242").exists(), "the record is consumed by the pickup"
    assert context(hook(tmp_path, "started", {"session_id": "new-2", "source": "clear", "cwd": str(repo)}, "4242")) == ""


def test_a_clear_with_no_handoff_or_no_record_hands_the_fresh_session_nothing(tmp_path: Path) -> None:
    repo = project(tmp_path)
    handoff(repo, "2026-09-26-other.md", "someone-else")
    assert context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(repo)}, "4242")) == "", "no record"
    hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4242")
    assert context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(repo)}, "4242")) == "", "no handoff of that session"
    hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4243")
    outside = tmp_path / "nowhere"
    outside.mkdir()
    assert context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(outside)}, "4243")) == "", "no project"


def test_the_pickup_works_from_a_linked_worktree_of_the_code_repo(tmp_path: Path) -> None:
    """A session usually runs in a worktree that holds no agent/ of its own; the handoff is in the
    main checkout's, which is where the agent repo lives."""
    repo = project(tmp_path)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "one"], check=True)
    worktree = tmp_path / "lamp-warm-preset"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(worktree), "-b", "ticket/warm-preset"], check=True)
    mine = handoff(repo, "2026-09-26-effort.md", "old-1")
    hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4242")
    note = context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(worktree)}, "4242"))
    assert str(mine.resolve()) in note
