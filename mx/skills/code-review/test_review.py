"""Checks for `review`'s range lock. Run: make test

The seam is the script itself, run in a scratch repo with a stand-in `claude` on PATH that works
for a set time and writes the report its brief names. The oracle is the ruling on D58: a review
that was killed, by kill -9 or a crash, never blocks a later one, and a review that is still
running is never disturbed by a second of its range.
"""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

REVIEW = Path(__file__).parent / "review"

FAKE_CLAUDE = r"""#!/usr/bin/env bash
brief=$(cat)
report=$(printf '%s' "$brief" | grep -o '/[^ `]*/agent/reviews/[^ `]*\.md' | grep -v '/briefs/' | head -1)
printf '%s\n' "$@" > "$FAKE_ARGV"
sleep "${FAKE_REVIEW_SECS:-0}"
[ -n "$report" ] && echo "No findings." > "$report"
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def commit(repo: Path, path: str, text: str) -> None:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)
    git(repo, "add", path)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", path)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo whose last commit touches a test file, so the Tests axis applies, and a spec beside it."""
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    commit(repo, ".gitignore", "agent/reviews/\n")
    commit(repo, "tests/test_one.py", "def test_one(): assert 1 + 1 == 2\n")
    (tmp_path / "spec.md").write_text("# Spec: add a test\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE)
    (bin_dir / "claude").chmod(0o755)
    return repo


def env(repo: Path, secs: int) -> dict[str, str]:
    bin_dir = repo.parent / "bin"
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_REVIEW_SECS": str(secs),
            "FAKE_ARGV": str(repo.parent / "argv")}


def start(repo: Path, secs: int, *args: str) -> subprocess.Popen:
    """A review in its own process group, so it can be killed whole, as a crash would."""
    return subprocess.Popen([str(REVIEW), "main~1", *args], cwd=repo, env=env(repo, secs),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(REVIEW), "main~1", *args], cwd=repo, env=env(repo, 0),
                          capture_output=True, text=True, timeout=60)


def wait_for(path: Path) -> None:
    for _ in range(200):
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"{path} never appeared")


def reviews(repo: Path) -> Path:
    return next((repo / "agent" / "reviews").iterdir())


def worktrees(repo: Path) -> int:
    return git(repo, "worktree", "list").count("\n")


def test_a_killed_review_does_not_block_the_next_one(repo, tmp_path):
    spec = str(tmp_path / "spec.md")
    first = start(repo, 30, "--axes", "tests", "--spec", spec)
    wait_for(tmp_path / "argv")  # the reviewer is running in its checkout
    assert worktrees(repo) == 2
    os.killpg(first.pid, signal.SIGKILL)
    first.wait()
    assert (reviews(repo) / "checkout").exists()

    again = run(repo, "--axes", "tests", "--spec", spec)

    assert again.returncode == 0, again.stderr
    assert "no longer running" in again.stderr
    assert (reviews(repo) / "tests.md").read_text() == "No findings.\n"
    assert worktrees(repo) == 1


def test_a_second_review_of_a_running_range_is_refused_and_touches_nothing(repo, tmp_path):
    first = start(repo, 30, "--axes", "correctness")
    wait_for(tmp_path / "argv")
    brief = reviews(repo) / "briefs" / "correctness.md"
    before = brief.stat().st_mtime_ns
    try:
        second = run(repo, "--axes", "correctness")
        assert second.returncode == 1
        assert "is running" in second.stderr
        assert brief.stat().st_mtime_ns == before
        assert first.poll() is None
    finally:
        os.killpg(first.pid, signal.SIGKILL)
        first.wait()


def test_a_checkout_a_killed_review_left_under_another_range_is_removed(repo, tmp_path):
    first = start(repo, 30, "--axes", "tests", "--spec", str(tmp_path / "spec.md"))
    wait_for(tmp_path / "argv")
    os.killpg(first.pid, signal.SIGKILL)
    first.wait()
    left = reviews(repo) / "checkout"
    commit(repo, "src/two.py", "TWO = 2\n")  # a new range, which the leftover is not under

    done = run(repo, "--axes", "correctness")

    assert done.returncode == 0, done.stderr
    assert not left.exists()
    assert worktrees(repo) == 1


def test_a_reviewer_starts_from_none_of_the_callers_setup(repo, tmp_path):
    assert run(repo, "--axes", "correctness").returncode == 0
    argv = (tmp_path / "argv").read_text().splitlines()
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert {"--strict-mcp-config", "--disable-slash-commands"} <= set(argv)
    assert argv[argv.index("--model") + 1] == "opus"
    assert argv[argv.index("--effort") + 1] == "high"
