"""Checks for a workflow retro's run, at the seam "The run script's commit" (retro-semi-automated):
given a scratch agent repo in which another change is staged, the commit holds the report's files
alone and the other change is still staged after it; given one mid-rebase, nothing is committed
and the run log says why (P9). The oracle is git's own record of the commit and the index.
Run: make test, or pytest on this file with tyro, pyyaml and markdown-it-py.

Each run goes through the whole command, its model runs a stub `claude` on PATH that records how it
was started and what it could see, and writes what its stage owes, so the same runs show that
read-fresh is given no earlier report (P6), that the later stages read the last run's from git
history, and that every stage may write in its run directory alone (P9).
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import retro_run  # noqa: E402
from test_retro_collect import SINCE, Transcript, git  # noqa: E402

FIRST = datetime(2026, 10, 12, 2, tzinfo=UTC)
SECOND = FIRST + timedelta(weeks=1)
IDENTITY = {"GIT_AUTHOR_NAME": "max", "GIT_AUTHOR_EMAIL": "max@example.org", "GIT_COMMITTER_NAME": "max",
            "GIT_COMMITTER_EMAIL": "max@example.org", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}

# What each stage writes, keyed by the stage its prompt's first line names. It records its
# command line, one argument per line, and what the run directory held when it started.
STUB = r"""#!/usr/bin/env bash
prompt=$(cat)
stage=$(head -1 <<< "$prompt" | sed 's/.*: //')
printf '%s\n' "$@" > "$STUB_LOG/$stage.argv"
find . -path ./prompts -prune -o -type f -print | sort > "$STUB_LOG/$stage.seen"
case $stage in
    "read fresh") mkdir -p notes && echo "notes" > notes/batch-01.md ;;
    "follow up") echo "follow-up" > follow-up.md ;;
    "go deep") mkdir -p deep && echo "deep" > deep/tests.md ;;
    synthesize) echo "# Workflow retro: $(basename "$PWD")" > report.md && echo "<html>" > report.html ;;
esac
"""


@pytest.fixture
def stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "stub"
    (log / "bin").mkdir(parents=True)
    (log / "bin" / "claude").write_text(STUB)
    (log / "bin" / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{log / 'bin'}:{os.environ['PATH']}")
    for key, value in IDENTITY.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("STUB_LOG", str(log))
    monkeypatch.setenv("RUN_LOG", str(tmp_path / "runs.jsonl"))
    return log


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """The agents repo, holding the mx plugin, and its agent repo with a staged ticket and `retro/`'s lists."""
    repo = tmp_path / "agents"
    (repo / "mx/.claude-plugin").mkdir(parents=True)
    (repo / "mx/.claude-plugin/plugin.json").write_text('{"version": "1.0.0"}')
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "mx", when=SINCE - timedelta(days=1))
    agent = repo / "agent"
    (agent / "retro").mkdir(parents=True)
    (agent / "retro/repos").write_text(f"# the repos\n{repo}\n")
    (agent / "retro/excluded-sessions").write_text("/home/u/work/org/*\n")
    (agent / "tickets").mkdir()
    (agent / "tickets/a.md").write_text("status: proposed\n")
    git(agent, "init", "-q")
    git(agent, "add", ".")
    git(agent, "commit", "-qm", "tracker", when=SINCE - timedelta(days=1))
    (agent / "tickets/a.md").write_text("status: proposed\n\nedited by a session\n")
    git(agent, "add", "tickets/a.md")
    return repo


def retro(tmp_path: Path, repo: Path, until: datetime, since: datetime | None = None) -> Path:
    projects = tmp_path / ".claude/projects"
    Transcript(projects, str(repo), until - timedelta(days=2)).says("why is the suite so slow").answers("Looking.")
    return retro_run.run_retro(repo, tmp_path / "data", [projects], since, until=until)


def argv(stub: Path, stage: str) -> list[str]:
    return (stub / f"{stage}.argv").read_text().splitlines()


def test_the_commit_holds_the_reports_files_alone_and_another_staged_change_stays_staged(
        tmp_path: Path, stub: Path, repo: Path) -> None:
    run = retro(tmp_path, repo, FIRST, SINCE)
    agent = repo / "agent"
    committed = subprocess.run(["git", "-C", agent, "show", "--name-only", "--format=", "HEAD"],
                               capture_output=True, text=True, check=True).stdout.split()
    assert committed == ["retro/report.html", "retro/report.md"]
    staged = subprocess.run(["git", "-C", agent, "diff", "--cached", "--name-only"],
                            capture_output=True, text=True, check=True).stdout.split()
    assert staged == ["tickets/a.md"], "the session's staged ticket is neither committed nor unstaged"
    assert (agent / "retro/report.md").read_text() == (run / "report.md").read_text()
    log = (tmp_path / "data/agents/runs.log").read_text()
    assert "committed" in log.splitlines()[-1]


def test_mid_rebase_nothing_is_committed_and_the_run_log_says_why(tmp_path: Path, stub: Path, repo: Path) -> None:
    agent = repo / "agent"
    git(agent, "commit", "-qm", "the staged ticket")
    git(agent, "checkout", "-qb", "side", "HEAD~")
    (agent / "tickets/a.md").write_text("status: done\n")
    git(agent, "commit", "-qam", "side")
    git(agent, "checkout", "-q", "-")
    assert subprocess.run(["git", "-C", agent, "rebase", "side"], capture_output=True).returncode != 0, "a conflict stops the rebase"
    head = subprocess.run(["git", "-C", agent, "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST, SINCE)
    assert subprocess.run(["git", "-C", agent, "rev-parse", "HEAD"], capture_output=True, text=True).stdout == head
    assert not (agent / "retro/report.md").exists()
    last = (tmp_path / "data/agents/runs.log").read_text().splitlines()[-1]
    assert "not committed" in last and "mid-rebase" in last
    assert str(tmp_path / "data/agents/runs") in last, "the log names where the report stays"


def test_read_fresh_sees_no_earlier_report_and_the_later_stages_read_the_last_runs_from_git_history(
        tmp_path: Path, stub: Path, repo: Path) -> None:
    first = retro(tmp_path, repo, FIRST, SINCE)
    second = retro(tmp_path, repo, SECOND)
    fresh = (stub / "read fresh.seen").read_text()
    assert "sessions/" in fresh and "previous" not in fresh
    later = (stub / "follow up.seen").read_text().split()
    assert "./previous/current.md" in later and "./previous/2026-10-12.md" in later
    assert (second / "previous/current.md").read_text() == (first / "report.md").read_text()
    rows = [json.loads(line) for line in (second / "sessions.jsonl").read_text().splitlines()]
    period = [r for r in rows if r["set"] == "sessions"]
    assert period and all(r["start"] >= retro_run.stamp(FIRST) for r in period), "the second period starts where the first ended"


def test_every_stage_may_write_in_its_run_directory_alone(tmp_path: Path, stub: Path, repo: Path) -> None:
    run = retro(tmp_path, repo, FIRST, SINCE)
    for stage in ("read fresh", "follow up", "go deep", "synthesize"):
        args = argv(stub, stage)
        assert {"--restricted", "--setting-sources", "--strict-mcp-config"} <= set(args)
        assert args[args.index("--permission-mode") + 1] == "manual"
        assert args[args.index("--permission-prompts") + 1] == "none"
        rules = args[args.index("--allowedTools") + 1:args.index("--tools")]
        assert [r for r in rules if not r.startswith("Bash(git -C ")] == [f"Edit(/{run}/**)"], stage
        assert all(r.split()[3].rstrip(")") in retro_run.GIT_READS for r in rules if r.startswith("Bash("))
    fresh = argv(stub, "read fresh")
    assert "--add-dir" not in fresh and "Bash" not in fresh[fresh.index("--tools") + 1]
