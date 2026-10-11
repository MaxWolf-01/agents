# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The SessionEnd hook's properties. Run: uv run test_end_hook.py

The seam is the hook at its input: the SessionEnd JSON in, run the way Claude Code runs it, over
the worked example's session directory in a throwaway agent repo that ignores `sessions/` as the
real one does. The oracle is agent/tickets/session-records-tracked.md, its P1 and P2 and its
Decisions, read off git's own record of the commit and of `git status`.
"""

import io
import json
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import end_hook
from session_page import PAGE

RECORDS = ["session.md", "turns/01.md", "turns/02.md", "turns/03.md", "turns/04.md"]  # the worked example's


def git(where: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          check=True, capture_output=True, text=True).stdout


@pytest.fixture
def agent(worked_example: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The worked example's agent repo, ignoring `sessions/`, with a commit, a ticket file staged by
    another session, and the session's rendered page beside its records."""
    repo = worked_example.parents[1]
    git(repo, "init", "-q")
    (repo / ".gitignore").write_text("sessions/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "start")
    (repo / "tickets" / "other.md").write_text("# another session's ticket\n")
    git(repo, "add", "tickets/other.md")
    (worked_example / PAGE).write_text("<html></html>")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@t")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@t")
    return repo


@pytest.fixture
def end(worked_example: Path, monkeypatch: pytest.MonkeyPatch, attended: Path) -> Callable[[], list[dict]]:
    """End the session the way Claude Code does, and hand back the log's lines once the detached
    commit has said what came of it. A session the hook starts no commit for has nothing to wait on.
    A commit that never says fails the check."""

    def call() -> list[dict]:
        hook = {"session_id": worked_example.name, "cwd": str(worked_example.parents[2]), "reason": "prompt_input_exit",
                "transcript_path": "", "hook_event_name": "SessionEnd"}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook)))
        end_hook.main()
        deadline = time.monotonic() + 10
        while True:
            lines = [json.loads(line) for line in attended.read_text().splitlines()]
            if not any(entry.get("why") == "commit started" for entry in lines) or any("committed" in entry for entry in lines):
                return lines
            if time.monotonic() > deadline:
                pytest.fail(f"the detached commit logged nothing in ten seconds: {lines}")
            time.sleep(0.05)

    return call


def committed(repo: Path) -> list[str]:
    """The paths HEAD's commit changed, as git records them."""
    return git(repo, "show", "--name-only", "--format=", "HEAD").split()


def in_status(repo: Path) -> list[str]:
    return [line for line in git(repo, "status", "--porcelain", "--untracked-files=all").splitlines() if "sessions/" in line]


def test_a_session_that_ends_commits_its_records_and_nothing_else(
    agent: Path, worked_example: Path, end: Callable[[], list[dict]],
) -> None:
    """P1, through the hook as Claude Code runs it: the commit holds the session's `session.md` and
    `turns/`, not its derived page and not what another session staged, which stays staged; it
    names the session in a `Session:` trailer."""
    end()
    assert committed(agent) == [f"sessions/{worked_example.name}/{path}" for path in RECORDS]
    assert git(agent, "log", "-1", "--format=%(trailers:key=Session,valueonly)").strip() == worked_example.name
    assert git(agent, "status", "--porcelain").splitlines() == ["A  tickets/other.md"]


def test_records_in_flight_stay_out_of_status_and_edits_to_committed_ones_show(
    agent: Path, worked_example: Path,
) -> None:
    """P2, and the Decision that the commit force-adds: before the commit and after it, no session's
    records show, another session's still in flight included; a later edit to a committed record
    does."""
    later = worked_example.parent / "a-later-session"
    (later / "turns").mkdir(parents=True)
    (later / "turns" / "01.md").write_text("in flight\n")
    assert in_status(agent) == []
    end_hook.commit_records(worked_example)
    assert in_status(agent) == []
    (worked_example / "turns" / "04.md").write_text("revised\n")
    assert in_status(agent) == [f" M sessions/{worked_example.name}/turns/04.md"]


def test_a_resumed_session_commits_what_changed_when_it_ends_again(agent: Path, worked_example: Path) -> None:
    end_hook.commit_records(worked_example)
    first = git(agent, "rev-parse", "HEAD")
    assert end_hook.commit_records(worked_example) == "nothing changed since the last commit"
    assert git(agent, "rev-parse", "HEAD") == first
    (worked_example / "turns" / "05.md").write_text("the resumed session's turn\n")
    end_hook.commit_records(worked_example)
    assert committed(agent) == [f"sessions/{worked_example.name}/turns/05.md"]


def test_a_commit_waits_out_another_sessions_index_lock(agent: Path, worked_example: Path) -> None:
    """Several sessions share the agent repo's main checkout, so another's commit may hold the index."""
    lock = agent / ".git" / "index.lock"
    lock.write_text("")
    threading.Timer(0.5, lock.unlink).start()
    end_hook.commit_records(worked_example)
    assert committed(agent) == [f"sessions/{worked_example.name}/{path}" for path in RECORDS]


def test_a_commit_that_fails_leaves_nothing_staged_for_another_sessions_commit(agent: Path, worked_example: Path) -> None:
    """P1 holds for the next commit too: the index is shared, so records left staged would land in it."""
    hook = agent / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    assert end_hook.commit_records(worked_example).endswith("; unstaged")
    assert git(agent, "status", "--porcelain").splitlines() == ["A  tickets/other.md"]


def test_an_agent_directory_inside_the_code_repo_gets_no_commit(worked_example: Path) -> None:
    """The records are the agent repo's history; where the agent directory is no repo of its own, a
    commit would land on the code repo's checked-out branch and reach its remote."""
    project = worked_example.parents[2]
    git(project, "init", "-q")
    git(project, "commit", "-q", "--allow-empty", "-m", "start")
    assert end_hook.commit_records(worked_example) == "the agent directory is not a repo of its own"
    assert git(project, "rev-list", "--count", "HEAD").strip() == "1"
    assert git(project, "diff", "--cached", "--name-only") == ""


UNREAD = {"a dispatched worker": ("DISPATCH_WORKLOG", "/tmp/worklog", "dispatched worker"),
          "a print-mode session": ("CLAUDE_CODE_SESSION_ATTENDED", "0", "print-mode session")}


@pytest.mark.parametrize("variable, value, why", UNREAD.values(), ids=UNREAD)
def test_a_session_left_alone_commits_nothing(
    variable: str, value: str, why: str, agent: Path, end: Callable[[], list[dict]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(variable, value)
    head = git(agent, "rev-parse", "HEAD")
    assert [entry["why"] for entry in end()] == [why]
    assert git(agent, "rev-parse", "HEAD") == head


def test_a_session_with_no_records_commits_nothing(
    agent: Path, worked_example: Path, end: Callable[[], list[dict]],
) -> None:
    """A session that never wrote a record: its directory holds at most the page."""
    (worked_example / "session.md").unlink()
    shutil.rmtree(worked_example / "turns")
    head = git(agent, "rev-parse", "HEAD")
    assert [entry["why"] for entry in end()] == ["no records"]
    assert git(agent, "rev-parse", "HEAD") == head


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
