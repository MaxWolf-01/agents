# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for the three context hooks in `checkpoint.py`. Run: uv run test_checkpoint.py

The seam is the script, run as Claude Code runs a command hook: the event's JSON on stdin, the
state directory and the marks in the environment, and what it prints read as the hook's output.
The oracle is the ticket [A long session hears where its context stands](../../../agent/tickets/context-checkpoints.md):
a session crossing a mark is told once per mark, by the mechanism and not by a rule it remembers;
a dispatched worker, a print-mode session and a subagent are told nothing; after /clear a fresh
session in a project whose agent repo holds a continuation the cleared session wrote is handed the
handoff skill's pickup line, and one with no such handoff is handed nothing.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "checkpoint.py"
SKILL = Path(__file__).resolve().parent / "SKILL.md"
HOOKS = Path(__file__).resolve().parents[2] / "hooks" / "hooks.json"


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


def logged(tmp_path: Path) -> list[dict]:
    path = tmp_path / "state" / "mx" / "hooks.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def event(transcript: Path, session: str = "s1", name: str = "PostToolBatch") -> dict:
    return {"session_id": session, "transcript_path": str(transcript), "hook_event_name": name, "cwd": str(transcript.parent)}


def test_a_session_crossing_a_mark_is_told_once_per_mark_and_the_note_names_the_mark(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=150_000))
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == "", "under every mark, nothing is said"

    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=299_996))
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == "", "one token under the mark is under it"
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=299_997) + turn("user"))
    note = context(hook(tmp_path, "checkpoint", event(transcript)))
    assert note.startswith("Context checkpoint: this session's context stands at 300k tokens, past the first of 3 marks (300k; the marks are 300k, 500k, 600k)"), note
    assert "mx handoff skill" in note

    assert context(hook(tmp_path, "checkpoint", event(transcript))) == "", "the same mark is not said twice"
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=480_000))
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == "", "between marks, nothing"
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=610_000))
    note = context(hook(tmp_path, "checkpoint", event(transcript)))
    assert "past the third of 3 marks (600k;" in note, "the highest mark crossed is the one said, once"
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == ""

    out = hook(tmp_path, "checkpoint", event(transcript, session="s2", name="UserPromptSubmit"))
    assert json.loads(out.stdout)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "past the third of 3 marks" in context(out), "another session reading the same size is told on its own account"
    decisions = [(l["session_id"], l["decision"]) for l in logged(tmp_path)]
    assert decisions == [("s1", "quiet"), ("s1", "quiet"), ("s1", "said"), ("s1", "quiet"), ("s1", "quiet"), ("s1", "said"), ("s1", "quiet"), ("s2", "said")]


def test_a_record_no_reading_can_trust_counts_as_never_told(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=350_000))
    (tmp_path / "state" / "mx" / "checkpoints").mkdir(parents=True)
    (tmp_path / "state" / "mx" / "checkpoints" / "s1").write_text("garbage")
    assert "past the first of 3 marks" in context(hook(tmp_path, "checkpoint", event(transcript)))
    assert (tmp_path / "state" / "mx" / "checkpoints" / "s1").read_text() == "300000"


def test_a_context_that_fell_back_under_a_mark_hears_it_again_on_the_way_up(tmp_path: Path) -> None:
    """A compaction keeps the session id and drops the context; the marks above what is left are
    unsaid again."""
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=610_000))
    assert "third of 3 marks" in context(hook(tmp_path, "checkpoint", event(transcript)))
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=30_000))
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == ""
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=310_000))
    assert "past the first of 3 marks" in context(hook(tmp_path, "checkpoint", event(transcript)))
    transcript.write_text(transcript.read_text() + turn("assistant", cache_read_input_tokens=350_000))
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == ""


def test_the_marks_come_from_the_environment_so_a_demo_can_cross_one(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=25_000))
    note = context(hook(tmp_path, "checkpoint", event(transcript), MX_CONTEXT_CHECKPOINTS="20000,40000"))
    assert "past the first of 2 marks (20k; the marks are 20k, 40k)" in note


def test_the_last_assistant_message_is_found_behind_a_line_longer_than_the_read_block(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=350_000)
                          + json.dumps({"type": "user", "message": {"content": "y" * 200_000}}) + "\n"
                          + json.dumps({"type": "system", "content": "z" * 100_000}) + "\n")
    assert "stands at 350k" in context(hook(tmp_path, "checkpoint", event(transcript)))


def test_an_assistant_line_cut_by_a_read_block_boundary_is_read_whole(tmp_path: Path) -> None:
    """The file is read from its end in 64 KiB blocks; the line a block boundary falls inside is
    completed by the next block, not dropped."""
    block = 64 * 1024
    assistant = turn("assistant", cache_read_input_tokens=350_000)
    trailer = json.dumps({"type": "system", "content": "z" * (block - len(assistant) // 2 - 40)}) + "\n"
    trailer = trailer + "\n" * (block - len(assistant) // 2 - len(trailer))  # the boundary lands mid-line
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("user") + assistant + trailer)
    size = transcript.stat().st_size
    assert len(turn("user")) < size - block < len(turn("user")) + len(assistant), "the boundary is inside the assistant line"
    assert "stands at 350k" in context(hook(tmp_path, "checkpoint", event(transcript)))


def test_a_worker_a_print_mode_session_and_a_subagent_hear_nothing(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("assistant", cache_read_input_tokens=650_000))
    assert context(hook(tmp_path, "checkpoint", event(transcript), DISPATCH_WORKLOG=str(tmp_path / "log"))) == ""
    assert context(hook(tmp_path, "checkpoint", event(transcript), CLAUDE_CODE_SESSION_ATTENDED="0")) == ""
    assert context(hook(tmp_path, "checkpoint", {**event(transcript), "agent_id": "a1", "agent_type": "Explore"})) == ""
    assert not (tmp_path / "state" / "mx" / "checkpoints").exists(), "nothing was recorded for a session that was not told"
    assert [l["why"] for l in logged(tmp_path)] == ["dispatched worker", "unattended session", "subagent"]
    assert "past the third" in context(hook(tmp_path, "checkpoint", event(transcript))), "the session's own thread still hears it"


def test_a_transcript_with_no_assistant_message_or_none_at_all_says_nothing(tmp_path: Path) -> None:
    transcript = tmp_path / "s1.jsonl"
    transcript.write_text(turn("user"))
    assert context(hook(tmp_path, "checkpoint", event(transcript))) == ""
    assert context(hook(tmp_path, "checkpoint", event(tmp_path / "missing.jsonl"))) == ""
    assert [l["why"] for l in logged(tmp_path)] == ["no assistant message in the transcript"] * 2


def test_an_event_missing_what_claude_code_always_sends_fails_loudly(tmp_path: Path) -> None:
    out = hook(tmp_path, "checkpoint", {"session_id": "s1"})
    assert out.returncode != 0 and "transcript_path" in out.stderr
    out = hook(tmp_path, "ended", {"session_id": "s1", "reason": "clear"})
    assert out.returncode != 0 and "ended <pid>" in out.stderr


def project(tmp_path: Path) -> Path:
    """A code repo holding its agent repo at agent/, with a handoffs directory."""
    repo = tmp_path / "lamp"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    agent = repo / "agent"
    subprocess.run(["git", "init", "-q", str(agent)], check=True)
    (agent / "tickets").mkdir()
    (agent / "handoffs").mkdir()
    return repo


def handoff(repo: Path, name: str, session: str, purpose: str = "continuation") -> Path:
    path = repo / "agent" / "handoffs" / name
    path.write_text(f"---\nsession: {session}\npurpose: {purpose}\n---\n\n# Where things stand\n")
    return path


def pickup_line(path: Path) -> str:
    """The line the handoff skill has the user type, with the path filled in: what the hook says."""
    line = next(l for l in SKILL.read_text().splitlines() if l.startswith("Continue from <absolute path>."))
    return line.replace("<absolute path>", str(path))


def test_after_clear_the_fresh_session_is_handed_the_continuation_the_cleared_one_wrote(tmp_path: Path) -> None:
    repo = project(tmp_path)
    older = handoff(repo, "2026-09-26-older.md", "old-1")
    mine = handoff(repo, "2026-09-20-effort.md", "old-1")  # the newest written, whatever its name says
    handoff(repo, "2026-09-26-other.md", "someone-else")
    handoff(repo, "2026-09-26-prefix.md", "old-10")
    cites = handoff(repo, "2026-09-26-cites.md", "someone-else")
    cites.write_text(cites.read_text() + "\nContinues from session: old-1, whose handoff this cites.\n")
    fork = handoff(repo, "2026-09-27-flaky-e2e.md", "old-1", purpose="fork")
    now = mine.stat().st_mtime
    os.utime(older, (now - 100, now - 100))
    os.utime(fork, (now + 100, now + 100))
    assert hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4242").stdout == ""
    assert context(hook(tmp_path, "started", {"session_id": "new-0", "source": "clear", "cwd": str(repo)}, "4243")) == "", "another Claude Code process's /clear"
    assert (tmp_path / "state" / "mx" / "clear" / "4242").exists(), "and it consumed nothing of this one's"
    out = hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(repo)}, "4242")
    assert json.loads(out.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert context(out) == pickup_line(mine.resolve()), "the newer fork handoff is another session's; the pickup is the skill's own line"
    assert not (tmp_path / "state" / "mx" / "clear" / "4242").exists(), "the record is consumed by the pickup"
    assert context(hook(tmp_path, "started", {"session_id": "new-2", "source": "clear", "cwd": str(repo)}, "4242")) == ""
    assert [(l["hook"], l["decision"]) for l in logged(tmp_path)] == [("ended", "recorded"), ("started", "quiet"), ("started", "said"), ("started", "quiet")]


def test_the_plugin_registers_the_three_hooks_and_hands_the_pair_one_pid(tmp_path: Path) -> None:
    """What hooks.json says, and what its commands do run from one shell, which is what Claude
    Code is to the two /clear hooks: the pid they pass is the same, so the pair meets."""
    hooks = json.loads(HOOKS.read_text())
    commands = {event: [(group.get("matcher"), h["command"]) for group in hooks["hooks"].get(event, []) for h in group["hooks"]]
                for event in ("PostToolBatch", "UserPromptSubmit", "SessionEnd", "SessionStart")}
    tail = "/skills/handoff/checkpoint.py"
    assert [c for _, c in commands["PostToolBatch"] if tail in c] == ['"${CLAUDE_PLUGIN_ROOT}"' + tail + " checkpoint"]
    assert [c for _, c in commands["UserPromptSubmit"] if tail in c] == ['"${CLAUDE_PLUGIN_ROOT}"' + tail + " checkpoint"]
    assert [(m, c) for m, c in commands["SessionEnd"] if tail in c] == [("clear", '"${CLAUDE_PLUGIN_ROOT}"' + tail + " ended $PPID")]
    assert [(m, c) for m, c in commands["SessionStart"] if tail in c] == [("clear", '"${CLAUDE_PLUGIN_ROOT}"' + tail + " started $PPID")]

    repo = project(tmp_path)
    mine = handoff(repo, "2026-09-26-effort.md", "old-1")
    ended = next(c for _, c in commands["SessionEnd"] if tail in c)
    started = next(c for _, c in commands["SessionStart"] if tail in c)
    script = (f"printf '%s' '{json.dumps({"session_id": "old-1", "reason": "clear"})}' | {ended}\n"
              f"printf '%s' '{json.dumps({"session_id": "new-1", "source": "clear", "cwd": str(repo)})}' | {started}\n")
    done = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(HOOKS.parents[1]), "XDG_STATE_HOME": str(tmp_path / "state")})
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"] == pickup_line(mine.resolve())


def test_a_clear_with_no_handoff_or_no_record_hands_the_fresh_session_nothing(tmp_path: Path) -> None:
    repo = project(tmp_path)
    handoff(repo, "2026-09-26-other.md", "someone-else")
    handoff(repo, "2026-09-27-flaky-e2e.md", "old-1", purpose="fork")
    assert context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(repo)}, "4242")) == "", "no record"
    hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4242")
    assert context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(repo)}, "4242")) == "", "only a fork of that session"
    hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4243")
    outside = tmp_path / "nowhere"
    outside.mkdir()
    out = hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(outside)}, "4243")
    assert context(out) == "" and "no agent repo found" in out.stderr, "no project"
    assert [l["why"] for l in logged(tmp_path) if l["hook"] == "started"] == [
        "no session recorded for this pid", "no continuation of the ended session", "no handoffs directory"]


def test_the_pickup_works_from_a_linked_worktree_of_the_code_repo(tmp_path: Path) -> None:
    """A session usually runs in a worktree that holds no agent/ of its own; the handoff is in the
    main checkout's, which is where the agent repo lives."""
    repo = project(tmp_path)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "one"], check=True)
    worktree = tmp_path / "lamp-warm-preset"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(worktree), "-b", "ticket/warm-preset"], check=True)
    mine = handoff(repo, "2026-09-26-effort.md", "old-1")
    hook(tmp_path, "ended", {"session_id": "old-1", "reason": "clear"}, "4242")
    assert context(hook(tmp_path, "started", {"session_id": "new-1", "source": "clear", "cwd": str(worktree)}, "4242")) == pickup_line(mine.resolve())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
