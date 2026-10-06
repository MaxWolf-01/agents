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
import subprocess
import sys
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


def test_a_removal_git_refuses_fails_after_the_handoff_is_printed(tmp_path: Path) -> None:
    """A handoff never committed: git refuses the rm, and the session has read it all the same."""
    repo = project(tmp_path)
    untracked = repo / "agent" / "handoffs" / "2026-10-07-draft.md"
    untracked.write_text(HANDOFF)
    done = pickup(repo, untracked, tmp_path)
    assert done.returncode == 1 and "git rm" in done.stderr
    assert done.stdout == HANDOFF
    assert untracked.exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
