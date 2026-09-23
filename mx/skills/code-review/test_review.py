# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `review`'s range lock and its reviewers' launch line. Run: uv run test_review.py

The seam is the script itself, run in a scratch repo with a stand-in `claude` on PATH that
records its arguments, works for a set time and writes the report its brief names. The oracles
are the user's rulings in `agent/tickets/review-launcher.md`: D113, a review that was killed,
by kill -9 or a crash, never blocks a later one, and a review that is still running, or anything
it started, is never disturbed by another; D114 and D115, a reviewer starts from none of the
caller's setup and runs Opus at the effort the caller gives, `high` by default.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

REVIEW = Path(__file__).parent / "review"

FAKE_CLAUDE = r"""#!/usr/bin/env bash
brief=$(cat)
report=$(printf '%s' "$brief" | grep -o '/[^ `]*/agent/reviews/[^ `]*\.md' | grep -v '/briefs/' | head -1)
printf '%s\n' "$@" > "$FAKE_ARGV"
sleep "${FAKE_REVIEW_SECS:-0}"
[ -n "$report" ] && [ -z "${FAKE_NO_REPORT:-}" ] && echo "No findings." > "$report"
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
    """A repo whose last commit touches a test file, so the Tests axis applies, a spec beside it,
    and the stand-in `claude`."""
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    commit(repo, ".gitignore", "agent/reviews/\n")
    commit(repo, "tests/test_one.py", "def test_one(): assert 1 + 1 == 2\n")
    (tmp_path / "spec.md").write_text("# Spec: add a test\n")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "claude").write_text(FAKE_CLAUDE)
    (tmp_path / "bin" / "claude").chmod(0o755)
    return repo


def spec(repo: Path) -> str:
    return str(repo.parent / "spec.md")


def argv_file(repo: Path) -> Path:
    """Where the stand-in writes the arguments of the reviewer that started last."""
    return repo.parent / "argv"


def command(repo: Path, secs: int, args: tuple[str, ...], **extra: str) -> dict:
    env = {**os.environ, "PATH": f"{repo.parent / 'bin'}:{os.environ['PATH']}",
           "FAKE_REVIEW_SECS": str(secs), "FAKE_ARGV": str(argv_file(repo)), **extra}
    return {"args": [str(REVIEW), "main~1", *args], "cwd": repo, "env": env, "text": True}


def run(repo: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(**command(repo, 0, args, **extra), capture_output=True, timeout=60)


@contextmanager
def running(repo: Path, *args: str):
    """A review whose reviewer works for 30 s, in its own process group so it can be killed whole,
    as a crash would; yielded once its reviewer has started, and killed on the way out."""
    argv_file(repo).unlink(missing_ok=True)
    proc = subprocess.Popen(**command(repo, 30, args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    try:
        for _ in range(200):
            if argv_file(repo).exists():
                break
            time.sleep(0.05)
        else:
            raise AssertionError("the reviewer never started")
        yield proc
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def killed(repo: Path, *args: str) -> None:
    with running(repo, *args):
        pass


def review_dir(repo: Path) -> Path:
    """The report directory of the range main~1..main."""
    base, head = (git(repo, "rev-parse", "--short=7", ref).strip() for ref in ("main~1", "main"))
    return repo / "agent" / "reviews" / f"{base}..{head}"


def worktrees(repo: Path) -> int:
    return git(repo, "worktree", "list").count("\n")


def launched(repo: Path) -> list[str]:
    return argv_file(repo).read_text().splitlines()


def value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


# D113: the range lock


def test_a_killed_review_does_not_block_the_next_one(repo):
    killed(repo, "--axes", "tests", "--spec", spec(repo))
    assert (review_dir(repo) / "checkout").exists()

    again = run(repo, "--axes", "tests", "--spec", spec(repo))

    assert again.returncode == 0, again.stderr
    assert (review_dir(repo) / "tests.md").read_text() == "No findings.\n"
    assert worktrees(repo) == 1


def test_a_second_review_of_a_running_range_is_refused_and_touches_nothing(repo):
    with running(repo, "--axes", "tests", "--spec", spec(repo)) as first:
        brief = review_dir(repo) / "briefs" / "tests.md"
        before = brief.stat().st_mtime_ns

        second = run(repo, "--axes", "tests", "--spec", spec(repo))

        assert second.returncode == 1
        assert "is running" in second.stderr
        assert (review_dir(repo) / "checkout").exists()
        assert brief.stat().st_mtime_ns == before
        assert first.poll() is None


def test_a_reviewer_that_outlives_its_killed_script_still_holds_the_range(repo):
    with running(repo, "--axes", "tests", "--spec", spec(repo)) as first:
        os.kill(first.pid, signal.SIGKILL)  # the script alone; its reviewer works on
        first.wait()

        second = run(repo, "--axes", "tests", "--spec", spec(repo))

        assert second.returncode == 1
        assert (review_dir(repo) / "checkout").exists()


def test_a_checkout_a_killed_review_left_under_another_range_is_removed(repo):
    killed(repo, "--axes", "tests", "--spec", spec(repo))
    left = review_dir(repo) / "checkout"
    commit(repo, "src/two.py", "TWO = 2\n")  # a new range, which the leftover is not under

    done = run(repo, "--axes", "correctness")

    assert done.returncode == 0, done.stderr
    assert not left.exists()
    assert worktrees(repo) == 1


def test_a_live_review_of_another_range_keeps_its_checkout(repo):
    with running(repo, "--axes", "tests", "--spec", spec(repo)) as first:
        live = review_dir(repo) / "checkout"
        commit(repo, "src/two.py", "TWO = 2\n")

        done = run(repo, "--axes", "correctness")

        assert done.returncode == 0, done.stderr
        assert live.exists()
        assert worktrees(repo) == 2
        assert first.poll() is None


def test_a_killed_reviews_directory_deleted_by_hand_does_not_block_its_range(repo):
    killed(repo, "--axes", "tests", "--spec", spec(repo))
    shutil.rmtree(repo / "agent" / "reviews")  # git still lists the checkout

    again = run(repo, "--axes", "tests", "--spec", spec(repo))

    assert again.returncode == 0, again.stderr
    assert worktrees(repo) == 1


def test_a_checkout_from_before_range_locks_is_left_and_named(repo):
    old = repo / "agent" / "reviews" / "aaaaaaa..bbbbbbb" / "checkout"
    git(repo, "worktree", "add", "-q", "--detach", str(old), "main~1")

    done = run(repo, "--axes", "correctness")

    assert done.returncode == 0, done.stderr
    assert old.exists()
    assert f"git worktree remove --force {old}" in done.stderr


# D114, D115: the reviewer's launch line


def test_a_reviewer_starts_from_none_of_the_callers_setup(repo):
    assert run(repo, "--axes", "correctness").returncode == 0
    argv = launched(repo)
    assert value(argv, "--setting-sources") == ""
    assert {"--strict-mcp-config", "--disable-slash-commands"} <= set(argv)
    assert json.loads(value(argv, "--settings")) == {"autoMemoryEnabled": False}
    # The file and shell tools; Write is the one that creates the report.
    assert set(value(argv, "--tools").split(",")) == {"Read", "Grep", "Glob", "Bash", "Edit", "Write"}


def test_every_reviewer_runs_opus_at_high_effort_unless_told_otherwise(repo):
    assert run(repo, "--light").returncode == 0
    assert (value(launched(repo), "--model"), value(launched(repo), "--effort")) == ("opus", "high")

    assert run(repo, "--light", "--effort", "low").returncode == 0
    assert value(launched(repo), "--effort") == "low"


def test_a_missing_report_is_rerun_at_the_same_effort(repo):
    done = run(repo, "--axes", "correctness", "--effort", "low", FAKE_NO_REPORT="1")

    assert done.returncode == 1
    rerun = done.stderr.strip().splitlines()[-1]
    assert "--axes correctness" in rerun and "--effort low" in rerun


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
