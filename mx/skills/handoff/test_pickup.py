# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `pickup.py`, the handoff skill's pickup command. Run: uv run test_pickup.py

The seam is the script, run as the agent runs it: the handoff's path as its argument, the session
id and Claude Code's config directory in the environment, in a throwaway project whose code repo
holds its agent repo. The oracle is the ticket handoff-pickup-command's Decisions: the handoff is
printed in full, its removal is committed alone in the agent repo, and `previous` is written for a
continuation another session wrote. How the pages then link is the session page's checks
(`../session-page/test_stop_hook.py`, under pages across handoffs).
"""

import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "pickup.py"
HANDOFF = "---\nsession: old-1\npurpose: continuation\n---\n\n# Where things stand\n\nThe ledger's second bank is next.\n"
IDENTITY = {f"GIT_{who}_{what}": value for who in ("AUTHOR", "COMMITTER") for what, value in (("NAME", "t"), ("EMAIL", "t@t"))}


def git(where: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(where), *args], check=True, capture_output=True, text=True, env={**os.environ, **IDENTITY}).stdout


def project(tmp_path: Path) -> Path:
    """A code repo holding its agent repo at agent/, with one handoff committed in it."""
    repo = tmp_path / "lamp"
    agent = repo / "agent"
    (agent / "tickets").mkdir(parents=True)
    (agent / "handoffs").mkdir()
    git(repo, "init", "-q")
    git(repo, "commit", "-q", "--allow-empty", "-m", "start")
    git(agent, "init", "-q")
    (agent / "handoffs" / "2026-10-06-ledger.md").write_text(HANDOFF)
    (agent / "tickets" / "ledger.md").write_text("# Ledger\n")
    git(agent, "add", ".")
    git(agent, "commit", "-q", "-m", "hand off")
    return repo


def pickup(cwd: Path, handoff: Path | str, tmp_path: Path, **env: str) -> subprocess.CompletedProcess:
    clean = {k: v for k, v in os.environ.items() if k not in ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")}
    return subprocess.run([str(SCRIPT), str(handoff)], cwd=cwd, capture_output=True, text=True, timeout=120,
                          env={**clean, **IDENTITY, "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-config"),
                               "CLAUDE_CODE_SESSION_ID": "new-1", **env})


def test_a_pickup_prints_the_handoff_and_commits_its_removal_alone(tmp_path: Path) -> None:
    repo = project(tmp_path)
    agent = repo / "agent"
    (agent / "tickets" / "ledger.md").write_text("# Ledger, staged by someone else\n")
    git(agent, "add", "tickets/ledger.md")
    done = pickup(repo, "agent/handoffs/2026-10-06-ledger.md", tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout == HANDOFF
    assert not (agent / "handoffs" / "2026-10-06-ledger.md").exists()
    assert git(agent, "show", "--name-status", "--format=%s", "HEAD").split() == ["pick", "up", "handoff", "2026-10-06-ledger",
                                                                                 "D", "handoffs/2026-10-06-ledger.md"]
    assert git(agent, "status", "--porcelain", "--untracked-files=no").splitlines() == ["M  tickets/ledger.md"], "what was staged stays staged"
    assert (agent / "sessions" / "new-1" / "previous").read_text() == "old-1\n"


def test_a_pickup_from_a_linked_worktree_writes_previous_in_the_main_checkouts_agent_repo(tmp_path: Path) -> None:
    """The session's directory is the one `session-page` prints, which every worktree shares."""
    repo = project(tmp_path)
    worktree = tmp_path / "lamp-ledger"
    git(repo, "worktree", "add", "-q", str(worktree), "-b", "ticket/ledger")
    done = pickup(worktree, repo / "agent" / "handoffs" / "2026-10-06-ledger.md", tmp_path)
    assert done.returncode == 0, done.stderr
    assert (repo / "agent" / "sessions" / "new-1" / "previous").read_text() == "old-1\n"
    assert not (worktree / "agent").exists()


@pytest.mark.parametrize("marker, value", [("DISPATCH_WORKLOG", "/tmp/log"), ("CLAUDE_CODE_SESSION_ATTENDED", "0")])
def test_a_worker_or_a_print_mode_session_picks_up_and_links_nothing(tmp_path: Path, marker: str, value: str) -> None:
    """every-session-gets-a-page#P4: neither gets a page, so neither gets a session directory."""
    repo = project(tmp_path)
    done = pickup(repo, repo / "agent" / "handoffs" / "2026-10-06-ledger.md", tmp_path, **{marker: value})
    assert done.returncode == 0, done.stderr
    assert done.stdout == HANDOFF
    assert not (repo / "agent" / "sessions").exists()


def test_a_file_outside_a_handoffs_directory_is_refused_untouched(tmp_path: Path) -> None:
    repo = project(tmp_path)
    ticket = repo / "agent" / "tickets" / "ledger.md"
    done = pickup(repo, ticket, tmp_path)
    assert done.returncode == 1 and "no file directly under an agent/handoffs/" in done.stderr
    assert done.stdout == "" and ticket.exists()
    assert git(repo / "agent", "log", "--format=%s").splitlines() == ["hand off"]


def never_committed(handoff: Path) -> Path:
    draft = handoff.with_name("2026-10-07-draft.md")
    draft.write_text(HANDOFF)
    return draft


def edited_since(handoff: Path) -> Path:
    handoff.write_text(HANDOFF + "\nA correction the user made.\n")
    return handoff


REFUSED = {"a handoff never committed": never_committed, "a handoff edited since it was committed": edited_since}


@pytest.mark.parametrize("change", REFUSED.values(), ids=REFUSED)
def test_a_handoff_git_would_refuse_to_remove_is_refused_before_anything_is_done(tmp_path: Path, change: Callable[[Path], Path]) -> None:
    """Refused before it is printed or linked, so a pickup run again once it is committed is clean."""
    repo = project(tmp_path)
    handoff = change(repo / "agent" / "handoffs" / "2026-10-06-ledger.md")
    done = pickup(repo, handoff, tmp_path)
    assert done.returncode == 1 and "nothing done" in done.stderr and "commit" in done.stderr
    assert done.stdout == "" and handoff.exists()
    assert not (repo / "agent" / "sessions").exists()
    assert git(repo / "agent", "log", "--format=%s").splitlines() == ["hand off"]


def test_the_pickup_says_how_to_read_the_handoff_again_once_it_is_removed(tmp_path: Path) -> None:
    """The Bash tool cuts a long output short, and the file is gone by then: git still has it."""
    repo = project(tmp_path)
    done = pickup(repo, repo / "agent" / "handoffs" / "2026-10-06-ledger.md", tmp_path)
    [again] = re.findall(r"read it again with `(.+?)`", done.stderr)
    assert subprocess.run(again, shell=True, capture_output=True, text=True).stdout == HANDOFF


def test_a_commit_git_refuses_anyway_fails_after_the_handoff_is_printed_and_linked(tmp_path: Path) -> None:
    """A pre-commit hook that says no: the session has read the handoff all the same."""
    repo = project(tmp_path)
    hook = repo / "agent" / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho no commits today >&2\nexit 1\n")
    hook.chmod(0o755)
    done = pickup(repo, repo / "agent" / "handoffs" / "2026-10-06-ledger.md", tmp_path)
    assert done.returncode == 1 and "git commit" in done.stderr and "no commits today" in done.stderr
    assert done.stdout == HANDOFF
    assert (repo / "agent" / "sessions" / "new-1" / "previous").read_text() == "old-1\n"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
