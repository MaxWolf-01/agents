# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `review`'s range lock, its reviewers' launch line, what `--spec` reads and what a changed
file hands a reviewer. Run: uv run test_review.py

The seam is the script itself, run in a scratch repo with a stand-in `claude` on PATH that
records its arguments, works for a set time and writes the report its prompt names. The oracles
are the user's rulings in `agent/tickets/review-launcher.md`: D113, a review that was killed,
by kill -9 or a crash, never blocks a later one, and a review that is still running, or anything
it started, is never disturbed by another; D114 and D115, a reviewer starts from none of the
caller's setup and runs Opus at the effort the caller gives, `medium` by default; and
`agent/tickets/ticket-file-contract.md` P4, that a reviewer's context is the ticket's body with
every ancestor's, assembled by the one command that assembles a worker's prompt; and
`agent/tickets/review-says-when-an-axis-died.md`, that a reviewer that died reads
differently from one that reported, and that a flag before the fixed point is refused naming the order;
and `agent/tickets/tickets-cut-by-independent-context.md`, that a review is one shape, two reviewers:
one reads the diff against the spec and the standards, one runs the suite.
"""

import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

REVIEW = Path(__file__).parent / "review"

FAKE_CLAUDE = r"""#!/usr/bin/env bash
prompt=$(cat)
report=$(printf '%s' "$prompt" | grep -o '/[^ `]*/mx/reviews/[^ `]*\.md' | grep -v '/prompts/' | head -1)
printf '%s\n' "$@" > "$FAKE_ARGV"
printf '%s\n' "${FORCE_PROMPT_CACHING_5M:-}" > "$FAKE_ARGV.cache"
[ -z "${FAKE_STARTED:-}" ] || echo > "$FAKE_STARTED"
sleep "${FAKE_REVIEW_SECS:-0}"
if [ -n "${FAKE_DIES:-}" ] && [[ $report == */$FAKE_DIES.md ]]; then
    echo "# Review" > "$report"
    echo "You've hit your limit · resets 3am"
    exit 1
fi
[ -n "$report" ] && [ -z "${FAKE_NO_REPORT:-}" ] && echo "No findings." > "$report"
# the end of a turn, as claude reports it
echo '{"type": "result", "subtype": "success"}'
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
    """A repo whose last commit touches a test file, so the tests reviewer runs, a spec beside it,
    and the stand-in `claude`."""
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    commit(repo, "README.md", "A scratch repo.\n")
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
           "MODEL_RUNS_LOG": str(repo.parent / "runs.jsonl"), "XDG_STATE_HOME": str(repo.parent / "state"), **extra}
    return {"args": [str(REVIEW), "main~1", *args], "cwd": repo, "env": env, "text": True}


def run(repo: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(**command(repo, 0, args, **extra), capture_output=True, timeout=60)


@contextmanager
def running(repo: Path, *args: str):
    """A review whose reviewer works for 30 s, in its own process group so it can be killed whole,
    as a crash would; yielded once its reviewer has started, and killed on the way out."""
    argv_file(repo).unlink(missing_ok=True)
    # The reviewer says it started down a pipe. The check holds a write end of its own, so the pipe
    # reads as empty until then rather than as closed, and no reviewer blocks writing to it.
    started = repo.parent / "started"
    started.unlink(missing_ok=True)
    os.mkfifo(started)
    ends = os.open(started, os.O_RDONLY | os.O_NONBLOCK), os.open(started, os.O_WRONLY)
    proc = subprocess.Popen(**command(repo, 30, args, FAKE_STARTED=str(started)), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try:
        if not select.select(ends[:1], [], [], 60)[0]:
            raise AssertionError("the reviewer never started")
        yield proc
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        for end in ends:
            os.close(end)


def killed(repo: Path, *args: str) -> None:
    with running(repo, *args):
        pass


def reviews(repo: Path) -> Path:
    """Where the reviews of the scratch repo land: the state directory, named for the repo's path."""
    return repo.parent / "state" / "mx" / "reviews" / str(repo).replace("/", "-")


def review_dir(repo: Path) -> Path:
    """The report directory of the range main~1..main."""
    base, head = (git(repo, "rev-parse", "--short=7", ref).strip() for ref in ("main~1", "main"))
    return reviews(repo) / f"{base}..{head}"


def worktrees(repo: Path) -> int:
    return git(repo, "worktree", "list").count("\n")


def launched(repo: Path) -> list[str]:
    return argv_file(repo).read_text().splitlines()


def value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


# review-inside-agent-repo: where the reports land


def test_a_review_leaves_the_reviewed_tree_as_it_found_it(repo):
    """Run from an agent repo, a listed repo or one nested in a worker's worktree, `review` once
    wrote its reports to an `agent/reviews/` of the tree it stood in, where nothing reads them and
    where they showed as untracked debris; the scratch repo has no `agent/` and ignores nothing."""
    done = run(repo, "--reviewers", "tests")

    assert done.returncode == 0, done.stderr
    assert git(repo, "status", "--porcelain", "--ignored") == ""
    assert done.stdout.strip() == str(review_dir(repo) / "tests.md")


# D113: the range lock


def test_a_killed_review_does_not_block_the_next_one(repo):
    killed(repo, "--reviewers", "tests")
    assert (review_dir(repo) / "checkout").exists()

    again = run(repo, "--reviewers", "tests")

    assert again.returncode == 0, again.stderr
    assert (review_dir(repo) / "tests.md").read_text() == "No findings.\n"
    assert worktrees(repo) == 1


def test_a_second_review_of_a_running_range_is_refused_and_touches_nothing(repo):
    with running(repo, "--reviewers", "tests") as first:
        prompts = review_dir(repo) / "prompts"
        before = {path.name: path.stat().st_mtime_ns for path in prompts.iterdir()}

        second = run(repo, "--reviewers", "tests")

        assert second.returncode == 1
        assert "is running" in second.stderr
        assert (review_dir(repo) / "checkout").exists()
        assert {path.name: path.stat().st_mtime_ns for path in prompts.iterdir()} == before
        assert first.poll() is None


def test_a_reviewer_that_outlives_its_killed_script_still_holds_the_range(repo):
    with running(repo, "--reviewers", "tests") as first:
        os.kill(first.pid, signal.SIGKILL)  # the script alone; its reviewer works on
        first.wait()

        second = run(repo, "--reviewers", "tests")

        assert second.returncode == 1
        assert (review_dir(repo) / "checkout").exists()


def test_a_checkout_a_killed_review_left_under_another_range_is_removed(repo):
    killed(repo, "--reviewers", "tests")
    left = review_dir(repo) / "checkout"
    commit(repo, "src/two.py", "TWO = 2\n")  # a new range, which the leftover is not under

    done = run(repo, "--reviewers", "read")

    assert done.returncode == 0, done.stderr
    assert not left.exists()
    assert worktrees(repo) == 1


def test_a_live_review_of_another_range_keeps_its_checkout(repo):
    with running(repo, "--reviewers", "tests") as first:
        live = review_dir(repo) / "checkout"
        commit(repo, "src/two.py", "TWO = 2\n")

        done = run(repo, "--reviewers", "read")

        assert done.returncode == 0, done.stderr
        assert live.exists()
        assert worktrees(repo) == 2
        assert first.poll() is None


def test_a_killed_reviews_directory_deleted_by_hand_does_not_block_its_range(repo):
    killed(repo, "--reviewers", "tests")
    shutil.rmtree(reviews(repo))  # git still lists the checkout

    again = run(repo, "--reviewers", "tests")

    assert again.returncode == 0, again.stderr
    assert worktrees(repo) == 1


def test_a_checkout_from_before_range_locks_is_left_and_named(repo):
    old = reviews(repo) / "aaaaaaa..bbbbbbb" / "checkout"
    git(repo, "worktree", "add", "-q", "--detach", str(old), "main~1")

    done = run(repo, "--reviewers", "read")

    assert done.returncode == 0, done.stderr
    assert old.exists()
    assert f"git worktree remove --force {old}" in done.stderr


# D114, D115: the reviewer's launch line


def test_a_reviewer_starts_from_none_of_the_callers_setup(repo):
    assert run(repo, "--reviewers", "read").returncode == 0
    argv = launched(repo)
    assert value(argv, "--setting-sources") == ""
    assert {"--strict-mcp-config", "--disable-slash-commands"} <= set(argv)
    assert json.loads(value(argv, "--settings")) == {"autoMemoryEnabled": False}
    # The file and shell tools; Write is the one that creates the report.
    assert set(value(argv, "--tools").split(",")) == {"Read", "Grep", "Glob", "Bash", "Edit", "Write"}


def test_every_reviewer_runs_opus_at_medium_effort_unless_told_otherwise(repo):
    assert run(repo, "--reviewers", "read").returncode == 0
    assert (value(launched(repo), "--model"), value(launched(repo), "--effort")) == ("opus", "medium")
    assert Path(f"{argv_file(repo)}.cache").read_text() == "1\n", "a reviewer writes its cache at the 5-minute rate"
    # `run-log`: one line per reviewer, naming it and the spec's ticket where one was given
    (logged,) = [json.loads(l) for l in (repo.parent / "runs.jsonl").read_text().splitlines()]
    assert (logged["site"], logged["axis"], logged["ticket"], logged["model"], logged["effort"]) == \
        ("review", "read", "", "opus", "medium")

    assert run(repo, "--reviewers", "read", "--effort", "low").returncode == 0
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
    """The budget is the prompt's, which the reviewer paces its work to; the clock it checks against
    is `date`, so every reviewer may run that."""
    assert run(repo, "--reviewers", "read").returncode == 0
    prompt = (review_dir(repo) / "prompts" / "read.md").read_text()
    assert "You have 10 minutes." in prompt
    assert "Bash(date)" in launched(repo)
    assert run(repo, "--reviewers", "read", "--minutes", "25").returncode == 0
    assert "You have 25 minutes." in (review_dir(repo) / "prompts" / "read.md").read_text()
    refused = run(repo, "--reviewers", "read", "--minutes", "soon")
    assert refused.returncode != 0 and "--minutes takes a whole number" in refused.stderr


def test_a_spec_given_as_a_slug_is_the_ticket_with_every_ancestors_body(repo):
    ticketed(repo)

    done = run(repo, "--reviewers", "read", "--spec", "lamp-presets")
    # `run-log`: the reviewer's line names the ticket the spec came from, and the range it read
    (logged,) = [json.loads(l) for l in (repo.parent / "runs.jsonl").read_text().splitlines()]
    assert (logged["site"], logged["axis"], logged["ticket"]) == ("review", "read", "lamp-presets")
    assert logged["range"] and ".." in logged["range"]

    assert done.returncode == 0, done.stderr
    assembled = (review_dir(repo) / "ticket.md").read_text()
    assert assembled.startswith("## lamp-presets")
    assert "## parent ticket: lamp" in assembled
    assert "What the whole lamp is for." in assembled
    assert str(review_dir(repo) / "ticket.md") in (review_dir(repo) / "prompts" / "read.md").read_text()


def test_a_spec_given_as_a_slug_that_names_no_ticket_is_refused_before_any_reviewer(repo):
    ticketed(repo)

    done = run(repo, "--spec", "no-such-ticket")

    assert done.returncode == 1
    assert "neither a file nor a ticket of this tracker" in done.stderr
    assert not (review_dir(repo) / "prompts").exists(), "nothing was rendered, so nothing was started"


def test_the_tests_reviewer_runs_when_the_diff_touches_a_test_and_read_runs_on_every_diff(repo):
    assert run(repo).stdout.split() == [str(review_dir(repo) / name) for name in ("read.md", "tests.md")]

    commit(repo, "docs/notes.md", "a diff that touches no test\n")

    assert run(repo).stdout.split() == [str(review_dir(repo) / "read.md")]


@pytest.mark.parametrize(("reviewer", "part"), [
    ("read", "## Spec: does it faithfully implement what was asked for?"),
    ("tests", "## Testing seams"),
])
def test_a_reviewer_judges_against_the_ticket_only_when_it_is_given_one(repo, reviewer, part):
    """Ticketed, the diff is read against what the ticket asked for and its tests against the seams
    it names; with no spec, both judge the diff on its own terms."""
    assert run(repo, "--reviewers", reviewer).returncode == 0
    assert part not in (review_dir(repo) / "prompts" / f"{reviewer}.md").read_text()
    assert not (review_dir(repo) / "ticket.md").exists()

    ticketed(repo)
    assert run(repo, "--reviewers", reviewer, "--spec", "lamp-presets").returncode == 0
    prompt = (review_dir(repo) / "prompts" / f"{reviewer}.md").read_text()
    assert part in prompt and str(review_dir(repo) / "ticket.md") in prompt


def test_read_works_its_passes_in_order_and_opens_the_standards_last(repo):
    """Progressive disclosure: one reviewer loads correctness, the spec and then the standards
    sources in turn, so the longest reading comes after the passes that need none of it."""
    assert run(repo, "--reviewers", "read", "--spec", spec(repo)).returncode == 0
    prompt = (review_dir(repo) / "prompts" / "read.md").read_text()
    passes = [prompt.index(f"## {name}:") for name in ("Correctness", "Spec", "Standards")]
    assert passes == sorted(passes), passes


def test_each_reviewer_numbers_its_findings_under_a_letter_of_its_own(repo):
    """A finding is cited `review <range> R13` outside its report (`fewer-workflow-concepts`), which
    reads as one finding only while no two reviewers of a review share a letter."""
    assert run(repo).returncode == 0
    heading = {name: re.findall(r"### ([A-Z])1\b", (review_dir(repo) / "prompts" / f"{name}.md").read_text())
               for name in ("read", "tests")}
    assert all(len(found) == 1 for found in heading.values()), f"each prompt asks for one heading form: {heading}"
    assert len({found[0] for found in heading.values()}) == 2, heading


def sources(prompt: Path) -> list[Path]:
    return [Path(line[2:]) for line in prompt.read_text().splitlines() if line.startswith("- /")]


def test_the_tests_reviewer_reads_the_test_smells_and_the_three_jobs_and_no_more_of_testing(repo):
    """The rest of /mx:testing restates the test-smell baseline for whoever writes a test, so the
    reviewer of one is handed the baseline and the three jobs its prompt asks about: the skill's
    body above its first section, which a heading put above the jobs would cut short."""
    assert run(repo, "--reviewers", "tests").returncode == 0

    given = sources(review_dir(repo) / "prompts" / "tests.md")
    assert [path.name for path in given] == ["TEST-SMELLS.md", "testing-jobs.md"]
    body = (REVIEW.parent.parent / "testing" / "SKILL.md").read_text().split("---\n", 2)[2]
    jobs = given[1].read_text()
    assert jobs.strip() and body.startswith(jobs) and "\n## " not in jobs
    numbered = [line[:3] for line in jobs.splitlines() if line[:1].isdigit()]
    assert numbered == ["1. ", "2. ", "3. "], "the three jobs are not all above the skill's first section"


@pytest.mark.parametrize(("touches_tests", "args", "handed"), [
    (True, ("--reviewers", "read"), True),
    (True, (), False),
    (False, (), False),
])
def test_the_test_sources_go_to_read_when_no_tests_reviewer_runs(repo, touches_tests, args, handed):
    """The read reviewer of a diff that touches tests reads them in the tests reviewer's place;
    beside a tests reviewer, or on a diff with no test in it, it needs no test baseline
    (`/mx:code-review`, What binds the review)."""
    if not touches_tests:
        commit(repo, "docs/notes.md", "a diff that touches no test\n")

    assert run(repo, *args).returncode == 0

    given = sources(review_dir(repo) / "prompts" / "read.md")
    if handed:
        assert [path.name for path in given[-2:]] == ["TEST-SMELLS.md", "testing-jobs.md"]
        assert not any(path.parent.name == "testing" for path in given), "the whole testing skill was handed over"
    else:
        assert not {"TEST-SMELLS.md", "testing-jobs.md"} & {path.name for path in given}


# What `review` takes a changed file for, by the conventions of the languages this workflow meets
# (pytest, Go, Rust, Jest, RSpec, JUnit) and of its own documents: a test, which hands the reader of
# the diff the test sources; a process document, which hands it writing-for-agents; and a glossary
# or an ADR, which hands it their formats.
CLASSED = {
    "test": ["test/lamp.sh", "tests/lamp.ts", "spec/lamp_helper.rb", "pkg/test_lamp.py", "pkg/conftest.py",
             "pkg/lamp_test.py", "lamp_test.go", "src/lamp_test.rs", "web/lamp_test.ts", "web/lamp_test.js",
             "web/lamp.test.tsx", "web/lamp.spec.js", "lib/lamp_spec.rb", "src/LampTest.java"],
    "process": ["SKILL.md", "sub/AGENTS.md", "CLAUDE.md", "mx/skills/lamp/run.sh", ".claude/commands/lamp.md",
                "claude/agents/lamp.md", "claude/output-styles/lamp.md", "worker-prompt.md"],
    "format": ["GLOSSARY.md", "docs/GLOSSARY-MAP.md", "decisions/0001-lamp.md"],
}
HANDS = {"test": "TEST-SMELLS.md", "process": "writing-for-agents", "format": "GLOSSARY-FORMAT.md"}
# Files whose names come near those without being any, all in one diff: it hands the reader none.
NEAR_MISSES = ["src/latest.py", "contest.py", "contests/lamp.py", "inspec/lamp.md", "pkg/attest_lamp.py",
               "docs/testing.md", "lamp_test.md", "README.md", "claude/settings.json", "my-decisions.md",
               "GLOSSARY.txt", "MYGLOSSARY.md", "my-decisions/lamp.md", "NOTSKILL.md", "myskills/lamp.sh",
               "myclaude/agents/lamp.md", "docs/prompt.txt", "prompts/lamp.sh", "prompts/lamp.md"]


def handed(repo: Path) -> str:
    """The standards a lone read reviewer of the last commit is handed, as one text."""
    done = run(repo, "--reviewers", "read")
    assert done.returncode == 0, done.stderr
    return "\n".join(map(str, sources(review_dir(repo) / "prompts" / "read.md")))


@pytest.mark.parametrize(("kind", "path"), [(kind, path) for kind, paths in CLASSED.items() for path in paths])
def test_a_changed_file_hands_the_reviewer_the_standards_of_its_kind(repo, kind, path):
    commit(repo, path, "changed\n")

    given = handed(repo)

    assert [k for k, source in HANDS.items() if source in given] == [kind]


def test_a_changed_file_of_no_kind_hands_the_reviewer_none_of_their_standards(repo):
    for path in NEAR_MISSES:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("changed\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "near misses")

    given = handed(repo)

    assert not [source for source in HANDS.values() if source in given], given


def test_a_spec_given_as_a_file_is_read_as_the_file(repo):
    done = run(repo, "--reviewers", "read", "--spec", spec(repo))

    assert done.returncode == 0, done.stderr
    assert spec(repo) in (review_dir(repo) / "prompts" / "read.md").read_text()
    assert not (review_dir(repo) / "ticket.md").exists()


def test_a_missing_report_is_rerun_at_the_same_effort_and_on_the_spec_as_it_was_given(repo):
    ticketed(repo)
    done = run(repo, "--reviewers", "read", "--effort", "low", "--spec", "lamp-presets", FAKE_NO_REPORT="1")

    assert done.returncode == 1
    rerun = done.stderr.strip().splitlines()[-1]
    assert "--reviewers read" in rerun and "--effort low" in rerun
    assert "--spec lamp-presets" in rerun, f"the re-run reads the assembled file rather than the ticket: {rerun}"


def test_a_reviewer_that_died_after_opening_its_report_reads_as_died_not_as_reported(repo):
    """The first four-axis review of testing-weight hit the usage limit: every reviewer had
    created its report and exited 1, and the paths were printed as if the reports had landed."""
    done = run(repo, FAKE_DIES="tests")

    assert done.returncode == 1
    assert done.stdout.split() == [str(review_dir(repo) / "read.md")]
    died = next(line for line in done.stderr.splitlines() if "tests reviewer died" in line)
    assert "exited 1" in died and "You've hit your limit" in died
    assert "--reviewers tests " in done.stderr.strip().splitlines()[-1]


def test_a_reviewer_of_no_such_name_is_refused_naming_the_two_before_anything_starts(repo):
    """`--axes` is gone, so the name a caller is likeliest to type wrong is an old axis's."""
    done = run(repo, "--reviewers", "correctness")

    assert done.returncode == 1
    assert "no reviewer named correctness: there are read and tests" in done.stderr
    assert not (review_dir(repo) / "prompts").exists()


def test_a_flag_before_the_fixed_point_is_refused_with_the_order(repo):
    cmd = command(repo, 0, ())
    done = subprocess.run(**{**cmd, "args": [str(REVIEW), "--effort", "main~1"]}, capture_output=True, timeout=60)

    assert done.returncode == 1
    assert done.stderr.strip() == "review: --effort came before the fixed point, which comes first: review <fixed-point> [flags]"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
