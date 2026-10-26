# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""The SessionEnd hook's properties. Run: uv run test_end_hook.py

The seam is the hook at its input: the SessionEnd JSON in, run the way Claude Code runs it, over
the worked example's session directory, which names a throwaway agent repo that ignores
`sessions/` as the real one does. The oracle is agent/tickets/session-records-tracked.md, its P1
and P2 and its Decisions, agent/tickets/session-records-outside-the-checkout.md, and
agent/tickets/loose-work-retired.md, whose session work's artefacts sit in the session's directory
and are committed as it ends, read off git's own record of the commit and of `git status`.
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
from session_checks import project_of
from session_page import PAGE, agent_repo_of

RECORDS = ["session.md", "turns/01.md", "turns/02.md", "turns/03.md", "turns/04.md"]  # the worked example's


def git(where: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          check=True, capture_output=True, text=True).stdout


@pytest.fixture
def agent(worked_example: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The worked example's agent repo, ignoring `sessions/`, with a commit, a ticket file staged by
    another session, and the session's rendered page beside its records."""
    repo = agent_repo_of(worked_example)
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
        hook = {"session_id": worked_example.name, "cwd": str(project_of(worked_example)), "reason": "prompt_input_exit",
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
    return git(repo, "show", "--name-only", "--no-renames", "--format=", "HEAD").split()


def in_status(repo: Path) -> list[str]:
    return [line for line in git(repo, "status", "--porcelain", "--untracked-files=all").splitlines() if "sessions/" in line]


def test_a_session_that_ends_commits_its_records_and_nothing_else(
    agent: Path, worked_example: Path, end: Callable[[], list[dict]],
) -> None:
    """P1, through the hook as Claude Code runs it: the commit holds the session's `session.md` and
    `turns/`, copied into the agent repo as they were, not its derived page, not a stray file
    lying in the agent repo's copy of its turns and not what another session staged, which stays
    staged; it names the session in a `Session:` trailer."""
    stray = agent / "sessions" / worked_example.name / "turns" / "draft.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("a draft written where the records went before\n")
    end()
    assert committed(agent) == [f"sessions/{worked_example.name}/{path}" for path in RECORDS]
    kept = agent / "sessions" / worked_example.name
    assert all((kept / path).read_text() == (worked_example / path).read_text() for path in RECORDS)
    assert not (kept / PAGE).exists()
    assert git(agent, "log", "-1", "--format=%(trailers:key=Session,valueonly)").strip() == worked_example.name
    assert git(agent, "status", "--porcelain").splitlines() == ["A  tickets/other.md"]


def test_a_session_commits_its_artefacts_with_its_records_less_what_a_show_directory_ignores(
    agent: Path, worked_example: Path, end: Callable[[], list[dict]],
) -> None:
    """A session's own work's artefacts sit under `show/` in its directory and reach history with its
    records; what the agent repo ignores under its own `show/` (a runnable artefact's `out/`, a
    rendered PNG, whatever its name is spelt in) stays out of the commit, though the commit
    force-adds."""
    (agent / ".gitignore").write_text("sessions/\nshow/**/out/\nshow/**/*.png\n")
    show = worked_example / "show"
    for path, text in {"figure.html": "<svg/>", "abläufe.png": "png", "demo/run": "#!/bin/sh\n",
                       "demo/out/result.txt": "1"}.items():
        (show / path).parent.mkdir(parents=True, exist_ok=True)
        (show / path).write_text(text)
    end()
    assert sorted(committed(agent)) == sorted(f"sessions/{worked_example.name}/{path}"
                                              for path in [*RECORDS, "show/demo/run", "show/figure.html"])


def test_an_artefact_the_resumed_session_deleted_leaves_history_when_it_ends_again(
    agent: Path, worked_example: Path,
) -> None:
    """P2 for artefacts: once committed, one deleted is committed as gone rather than left in status."""
    (worked_example / "show").mkdir()
    (worked_example / "show" / "figure.html").write_text("<svg/>")
    end_hook.commit_records(worked_example)
    (worked_example / "show" / "figure.html").unlink()
    end_hook.commit_records(worked_example)
    assert committed(agent) == [f"sessions/{worked_example.name}/show/figure.html"]
    assert in_status(agent) == []


def test_records_in_flight_never_reach_the_checkout_and_reach_its_history_as_the_session_ends(
    agent: Path, worked_example: Path,
) -> None:
    """P2, and session-records-outside-the-checkout, "a running session's records sit outside every
    checkout ... and they are committed into the agent repo as the session ends": a running
    session's records, another session's still in flight included, sit outside the agent repo, so nothing of them is in its tree; once the commit
    has landed, what it copied in is all there is, and committed."""
    later = worked_example.parent / "a-later-session"
    (later / "turns").mkdir(parents=True)
    (later / "turns" / "01.md").write_text("in flight\n")
    assert not (agent / "sessions").exists()
    end_hook.commit_records(worked_example)
    assert sorted(p.name for p in (agent / "sessions").iterdir()) == [worked_example.name]
    assert in_status(agent) == []


def test_a_resumed_session_commits_what_changed_when_it_ends_again(agent: Path, worked_example: Path) -> None:
    end_hook.commit_records(worked_example)
    first = git(agent, "rev-parse", "HEAD")
    assert end_hook.commit_records(worked_example) == "nothing changed since the last commit"
    assert git(agent, "rev-parse", "HEAD") == first
    (worked_example / "turns" / "05.md").write_text("the resumed session's turn\n")
    (worked_example / "turns" / "04.md").write_text("revised\n")
    (worked_example / "turns" / "03.md").rename(worked_example / "turns" / "03-renumbered.md")
    end_hook.commit_records(worked_example)
    kept = f"sessions/{worked_example.name}/turns"
    assert committed(agent) == [f"{kept}/{name}" for name in ("03-renumbered.md", "03.md", "04.md", "05.md")]
    assert git(agent, "ls-tree", "--name-only", "HEAD", f"{kept}/").split() == [
        f"{kept}/{name}" for name in ("01.md", "02.md", "03-renumbered.md", "04.md", "05.md")], "the renumbered record is gone under its old name"
    assert git(agent, "show", f"HEAD:{kept}/04.md") == "revised\n"


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
    assert [p for p in (agent / "sessions").rglob("*") if p.is_file()] == [], "nothing the commit did not hold stays in the checkout"


def test_a_failed_commit_puts_the_records_it_held_back_as_they_were(agent: Path, worked_example: Path) -> None:
    """A session that ends again after a resume and fails to commit leaves the agent repo's copy as
    its history last had it: the edited record as committed, the removed one back."""
    end_hook.commit_records(worked_example)
    hook = agent / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    (worked_example / "turns" / "04.md").write_text("revised\n")
    (worked_example / "turns" / "03.md").unlink()
    (worked_example / "turns" / "05.md").write_text("a new turn\n")
    assert end_hook.commit_records(worked_example).endswith("; unstaged")
    assert in_status(agent) == []
    kept = agent / "sessions" / worked_example.name / "turns"
    assert sorted(p.name for p in kept.iterdir()) == ["01.md", "02.md", "03.md", "04.md"]
    assert (kept / "04.md").read_text() != "revised\n"


def test_a_failed_commit_puts_back_records_the_agent_repo_held_untracked(agent: Path, worked_example: Path) -> None:
    """A session running since records went in the agent repo has them there, never committed: a
    failed commit leaves them as they were, not as the session's directory has them now."""
    kept = agent / "sessions" / worked_example.name / "turns" / "04.md"
    kept.parent.mkdir(parents=True)
    kept.write_text("as an older mx left it\n")
    hook = agent / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    assert end_hook.commit_records(worked_example).endswith("; unstaged")
    assert [p.name for p in kept.parent.iterdir()] == ["04.md"] and kept.read_text() == "as an older mx left it\n"


def test_a_directory_that_names_no_agent_repo_commits_nothing(worked_example: Path) -> None:
    (worked_example / "agent-repo").unlink()
    assert end_hook.commit_records(worked_example) == f"{worked_example} names no agent repo"


def test_an_agent_directory_inside_the_code_repo_gets_no_commit(worked_example: Path) -> None:
    """The records are the agent repo's history; where the agent directory is no repo of its own, a
    commit would land on the code repo's checked-out branch and reach its remote."""
    project = project_of(worked_example)
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
