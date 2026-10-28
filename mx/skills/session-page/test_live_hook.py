"""The live hook: the turn under way's tool calls, as the page's log polls them. The seam is the
hook as Claude Code calls it, a payload on stdin, and the oracle the file it leaves beside the page,
read as the page reads it. Run: pytest test_live_hook.py"""

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import live_hook
from live_hook import LIVE, PREFIX
from session_page import pages_directory

SESSION = "5e55i0n0-0000-4000-8000-000000000000"


@pytest.fixture
def directory(registry: Path) -> Path:
    """The session's directory, which a session gets with its first record."""
    made = pages_directory(registry.parent, SESSION)
    made.mkdir(parents=True)
    return made


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Call the hook the way Claude Code does, on an event of the session's."""

    def call(event: str, **fields: object) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": SESSION, "hook_event_name": event, **fields})))
        live_hook.main()

    return call


def live(directory: Path) -> dict | None:
    """The file as the page reads it: the value it sets `window.liveCalls` to; None where it is absent."""
    path = directory / LIVE
    if not path.exists():
        return None
    text = path.read_text()
    assert text.startswith(PREFIX)
    return json.loads(text.removeprefix(PREFIX))


def lines(directory: Path) -> list[tuple]:
    return [(s["verb"], s["subject"], s["output"], s["failed"], s["done"] is not None) for s in live(directory)["steps"]]


BASH = {"command": "make test", "description": "Run the suite"}
READ = {"file_path": "/repo/page.js"}


def test_a_turns_calls_show_as_they_start_and_as_they_come_back(directory: Path, run: Callable[..., None]) -> None:
    run("UserPromptSubmit", prompt="\nfix the log\nplease")
    assert live(directory) == {"prompt": "fix the log", "steps": []}
    run("PreToolUse", tool_name="Bash", tool_input=BASH, tool_use_id="a")
    run("PreToolUse", tool_name="Read", tool_input=READ, tool_use_id="b")
    assert lines(directory) == [("ran", "Run the suite", "", False, False), ("read", "/repo/page.js", "", False, False)]
    run("PostToolUseFailure", tool_name="Bash", tool_input=BASH, tool_use_id="a", error="Exit code 2")
    run("PostToolBatch", tool_calls=[
        {"tool_name": "Bash", "tool_input": BASH, "tool_use_id": "a", "tool_response": "Exit code 2\n3 failed"},
        {"tool_name": "Read", "tool_input": READ, "tool_use_id": "b", "tool_response": [{"type": "text", "text": "1→const a"}]},
    ])
    assert lines(directory) == [("ran", "Run the suite", "Exit code 2\n3 failed", True, True), ("read", "/repo/page.js", "1→const a", False, True)]
    run("UserPromptSubmit", prompt="next")
    assert live(directory) == {"prompt": "next", "steps": []}, "a new prompt starts the turn under way anew"


def test_a_result_before_its_calls_own_event_adds_the_call(directory: Path, run: Callable[..., None]) -> None:
    run("UserPromptSubmit", prompt="go")
    run("PostToolBatch", tool_calls=[{"tool_name": "Read", "tool_input": READ, "tool_use_id": "b", "tool_response": "x"}])
    run("PreToolUse", tool_name="Read", tool_input=READ, tool_use_id="b")
    assert lines(directory) == [("read", "/repo/page.js", "x", False, True)]


def test_only_a_prompt_starts_the_file(directory: Path, run: Callable[..., None]) -> None:
    """After the Stop hook took the file away, a late result leaves it away."""
    run("PostToolBatch", tool_calls=[{"tool_name": "Read", "tool_input": READ, "tool_use_id": "b", "tool_response": "x"}])
    run("PreToolUse", tool_name="Read", tool_input=READ, tool_use_id="b")
    assert live(directory) is None


@pytest.mark.parametrize("why", ["subagent", "worker", "no directory"])
def test_calls_nobody_reads_live_are_left_alone(why: str, registry: Path, run: Callable[..., None], monkeypatch: pytest.MonkeyPatch) -> None:
    directory = pages_directory(registry.parent, SESSION)
    if why != "no directory":
        directory.mkdir(parents=True)
    if why == "worker":
        monkeypatch.setenv("DISPATCH_WORKLOG", "/tmp/log")
    run("UserPromptSubmit", prompt="go", **({"agent_id": "agent-1"} if why == "subagent" else {}))
    assert live(directory) is None
    assert why != "no directory" or not directory.exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
