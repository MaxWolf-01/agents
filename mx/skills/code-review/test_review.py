# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `review`'s range lock, its reviewers' launch line and what `--spec` reads. Run: uv run test_review.py

The seam is the script itself, run in a scratch repo with a stand-in `claude` on PATH that
records its arguments, works for a set time and writes the report its brief names. The oracles
are the user's rulings in `agent/tickets/review-launcher.md`: D113, a review that was killed,
by kill -9 or a crash, never blocks a later one, and a review that is still running, or anything
it started, is never disturbed by another; D114 and D115, a reviewer starts from none of the
caller's setup and runs Opus at the effort the caller gives, `medium` by default; and
`agent/tickets/ticket-file-contract.md` P4, that a reviewer's context is the ticket's body with
every ancestor's, assembled by the one command that assembles a worker's brief.
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
           "FAKE_REVIEW_SECS": str(secs), "FAKE_ARGV": str(argv_file(repo)),
           "RUN_LOG": str(repo.parent / "runs.jsonl"), **extra}
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
        briefs = review_dir(repo) / "briefs"
        before = {path.name: path.stat().st_mtime_ns for path in briefs.iterdir()}

        second = run(repo, "--axes", "tests", "--spec", spec(repo))

        assert second.returncode == 1
        assert "is running" in second.stderr
        assert (review_dir(repo) / "checkout").exists()
        assert {path.name: path.stat().st_mtime_ns for path in briefs.iterdir()} == before
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


def test_every_reviewer_runs_opus_at_medium_effort_unless_told_otherwise(repo):
    assert run(repo, "--light").returncode == 0
    assert (value(launched(repo), "--model"), value(launched(repo), "--effort")) == ("opus", "medium")
    # `run-log`: one line per axis, naming the axis and the spec's ticket where one was given
    (logged,) = [json.loads(l) for l in (repo.parent / "runs.jsonl").read_text().splitlines()]
    assert (logged["site"], logged["axis"], logged["ticket"], logged["model"], logged["effort"]) == \
        ("review", "light", "", "opus", "medium")

    assert run(repo, "--light", "--effort", "low").returncode == 0
    assert value(launched(repo), "--effort") == "low"


# ticket-file-contract#P4: what --spec reads


def ticketed(repo: Path) -> Path:
    """The repo with a tracker in it: a parent ticket and the child ticket the work is for."""
    tickets = repo / "agent" / "tickets"
    for slug, body in (
        ("lamp", "---\nstatus: open\npriority: 2\nsize: L\n---\n\n# Lamp\n\n## Brief\n\nWhat the whole lamp is for.\n"),
        ("lamp-presets", "---\nstatus: claimed\nparent: lamp\npriority: 2\nsize: S\n---\n\n# Lamp presets\n\n## Brief\n\nThe preset file.\n"),
    ):
        commit(repo, f"agent/tickets/{slug}.md", body)
    return tickets


def test_every_reviewer_is_given_a_time_budget_the_caller_can_change(repo):
    """The budget is the brief's, which the reviewer paces its work to; the clock it checks against
    is `date`, so every reviewer may run that."""
    assert run(repo, "--light").returncode == 0
    brief = (review_dir(repo) / "briefs" / "light.md").read_text()
    assert "You have 10 minutes." in brief
    assert "Bash(date)" in launched(repo)
    assert run(repo, "--light", "--minutes", "25").returncode == 0
    assert "You have 25 minutes." in (review_dir(repo) / "briefs" / "light.md").read_text()
    refused = run(repo, "--light", "--minutes", "soon")
    assert refused.returncode != 0 and "--minutes takes a whole number" in refused.stderr


def test_a_spec_given_as_a_slug_is_the_ticket_with_every_ancestors_body(repo):
    ticketed(repo)

    done = run(repo, "--axes", "spec", "--spec", "lamp-presets")
    # `run-log`: the axis's line names the ticket the spec came from, and the range it read
    (logged,) = [json.loads(l) for l in (repo.parent / "runs.jsonl").read_text().splitlines()]
    assert (logged["site"], logged["axis"], logged["ticket"]) == ("review", "spec", "lamp-presets")
    assert logged["range"] and ".." in logged["range"]

    assert done.returncode == 0, done.stderr
    assembled = (review_dir(repo) / "ticket.md").read_text()
    assert assembled.startswith("## lamp-presets")
    assert "## parent ticket: lamp" in assembled
    assert "What the whole lamp is for." in assembled
    assert str(review_dir(repo) / "ticket.md") in (review_dir(repo) / "briefs" / "spec.md").read_text()


def test_a_spec_given_as_a_slug_that_names_no_ticket_is_refused_before_any_reviewer(repo):
    ticketed(repo)

    done = run(repo, "--axes", "spec", "--spec", "no-such-ticket")

    assert done.returncode == 1
    assert "neither a file nor a ticket of this tracker" in done.stderr
    assert not (review_dir(repo) / "briefs").exists(), "nothing was rendered, so nothing was started"


def test_light_mode_judges_the_diff_against_the_ticket_when_it_is_given_one(repo):
    """One reviewer, and the ticket's context in its brief: a small ticketed diff is read against
    what the ticket asked for rather than on its own terms, by the spec axis's own brief."""
    ticketed(repo)

    done = run(repo, "--light", "--spec", "lamp-presets")

    assert done.returncode == 0, done.stderr
    brief = (review_dir(repo) / "briefs" / "light.md").read_text()
    assert "## Spec: does it faithfully implement what was asked for?" in brief
    assert str(review_dir(repo) / "ticket.md") in brief
    assert (review_dir(repo) / "ticket.md").read_text().startswith("## lamp-presets")


def test_light_mode_without_a_spec_says_there_is_none_to_judge_against(repo):
    assert run(repo, "--light").returncode == 0
    brief = (review_dir(repo) / "briefs" / "light.md").read_text()
    assert "## Spec:" not in brief
    assert "invent no requirement for it" in brief
    assert not (review_dir(repo) / "ticket.md").exists()


def sources(brief: Path) -> list[Path]:
    return [Path(line[2:]) for line in brief.read_text().splitlines() if line.startswith("- /")]


def test_the_tests_reviewer_reads_the_test_smells_and_the_three_jobs_and_no_more_of_testing(repo):
    """The rest of /mx:testing restates the test-smell baseline for whoever writes a test, so the
    reviewer of one is handed the baseline and the three jobs its brief asks about: the skill's
    body above its first section, which a heading put above the jobs would cut short."""
    assert run(repo, "--axes", "tests", "--spec", spec(repo)).returncode == 0

    given = sources(review_dir(repo) / "briefs" / "tests.md")
    assert [path.name for path in given] == ["TEST-SMELLS.md", "testing-jobs.md"]
    body = (REVIEW.parent.parent / "testing" / "SKILL.md").read_text().split("---\n", 2)[2]
    jobs = given[1].read_text()
    assert jobs.strip() and body.startswith(jobs) and "\n## " not in jobs
    numbered = [line[:3] for line in jobs.splitlines() if line[:1].isdigit()]
    assert numbered == ["1. ", "2. ", "3. "], "the three jobs are not all above the skill's first section"


def test_the_light_reviewer_of_a_diff_with_tests_reads_what_the_tests_reviewer_does(repo):
    assert run(repo, "--light").returncode == 0

    given = sources(review_dir(repo) / "briefs" / "light.md")
    assert [path.name for path in given[-2:]] == ["TEST-SMELLS.md", "testing-jobs.md"]
    assert not any(path.parent.name == "testing" for path in given), "the whole testing skill was handed over"


def test_a_spec_given_as_a_file_is_read_as_the_file(repo):
    done = run(repo, "--axes", "spec", "--spec", spec(repo))

    assert done.returncode == 0, done.stderr
    assert spec(repo) in (review_dir(repo) / "briefs" / "spec.md").read_text()
    assert not (review_dir(repo) / "ticket.md").exists()


def test_a_missing_report_is_rerun_at_the_same_effort_and_on_the_spec_as_it_was_given(repo):
    ticketed(repo)
    done = run(repo, "--axes", "spec", "--effort", "low", "--spec", "lamp-presets", FAKE_NO_REPORT="1")

    assert done.returncode == 1
    rerun = done.stderr.strip().splitlines()[-1]
    assert "--axes spec" in rerun and "--effort low" in rerun
    assert "--spec lamp-presets" in rerun, f"the re-run reads the assembled file rather than the ticket: {rerun}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
