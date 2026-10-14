"""Checks for a workflow retro's run, at the seam "The run script's commit" (retro-semi-automated):
given a scratch agent repo in which another change is staged, the commit holds the report's files
alone and the other change is still staged after it; given one mid-rebase, nothing is committed
and the run log says why (P9). The oracle is git's own record of the commit and the index.
Run: make test, or pytest on this file with tyro, pyyaml and markdown-it-py[linkify].

Each run goes through the whole command, its model runs a stub `claude` on PATH that records what
the run directory held when it started and writes what its stage owes. The same runs show that
read-fresh is given no earlier report (P6), and that the later stages read the last runs' reports
from git history.

Four checks enter elsewhere. The run's batches: given a run directory's `sessions.jsonl` and
digests, the names and contents `batches.json` gets, the oracle being the batch size's arithmetic.
A run stopped or killed: the command run as a process of its own, sent a signal while its stage's
stub runs, the oracle being whether the stub's processes still run, read from `/proc`. A resumed
run: the oracle being the stub's record of which stages it ran and the period on the commit. A run
in-process: the oracle being the signal handlers before it and after.

A repo retro runs through the same command, on a repo other than the agents repo: which stages
run, in which order, what its run directory holds and what its stages may reach, the oracle being
the stub's record and the stages' command lines (retro-semi-automated#P10); and which repos are
refused and which weeks skipped, the oracle being git's record of the agent repo and the run log.
"""

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import retro_run
from retro_checks import IDENTITY, SINCE, Transcript, commit, git, ticket

FIRST = datetime(2026, 10, 12, 2, tzinfo=UTC)
WEEK = timedelta(weeks=1)

# What each stage writes, keyed by the stage its prompt's first line names. It records its
# command line, one argument per line, the order the stages ran in, and what the run directory
# held when it started; before
# synthesis writes, it runs $STUB_BEFORE_SYNTHESIS, which stands for a session working meanwhile.
# With $STUB_SYNTHESIS_FAILS set, synthesis writes nothing. With $STUB_HANG set it starts a child
# and waits on it instead, recording both pids, and takes a second to end on TERM, as a model run
# ending its work does; the child ends only by its own TERM. Run as `claude auto-mode config`, as
# collect runs it, it prints a config.
STUB = r"""#!/usr/bin/env bash
[ "$1" = auto-mode ] && { echo '{"allow": []}'; exit 0; }
prompt=$(cat)
stage=$(head -1 <<< "$prompt" | sed 's/.*: //')
printf '%s\n' "$@" > "$STUB_LOG/$stage.argv"
echo "$stage" >> "$STUB_LOG/order"
find . -path ./prompts -prune -o -type f -print | sort > "$STUB_LOG/$stage.seen"
if [ -n "${STUB_HANG:-}" ]; then trap "sleep 1; exit 143" TERM; sleep 300 & echo "$$ $!" > "$STUB_LOG/$stage.pids.tmp" && mv "$STUB_LOG/$stage.pids.tmp" "$STUB_LOG/$stage.pids"; wait; fi
case $stage in
    "read fresh") mkdir -p notes && echo "notes" > notes/git.md && for b in $(jq -r '.[].name' batches.json); do echo notes > "notes/$b.md"; done ;;
    "follow up") echo "follow-up" > follow-up.md ;;
    "go deep") mkdir -p deep && for f in leading-words permissions; do echo "deep" > "deep/$f.md"; done ;;
    "lens pass") mkdir -p lens-pass && for f in architecture bloat tests footguns escaped-defects; do echo "lens" > "lens-pass/$f.md"; done ;;
    synthesize) [ -n "${STUB_SYNTHESIS_FAILS:-}" ] && exit 0; eval "${STUB_BEFORE_SYNTHESIS:-}"; echo "# Workflow retro: $(basename "$PWD")" > report.md && echo "<html>" > report.html ;;
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
    """The agents repo, holding the mx plugin, and its agent repo with a staged ticket and `retro/repos`."""
    repo = tmp_path / "agents"
    (repo / "mx/.claude-plugin").mkdir(parents=True)
    (repo / "mx/.claude-plugin/plugin.json").write_text('{"version": "1.0.0"}')
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "mx", when=SINCE - timedelta(days=1))
    agent = repo / "agent"
    (agent / "retro").mkdir(parents=True)
    (agent / "retro/repos").write_text(f"# the repos\n{repo}\n")
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


def out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def last_logged(tmp_path: Path, repo: str = "agents") -> str:
    """The message of the run log's last line, after its time and run."""
    return (tmp_path / f"data/{repo}/runs.log").read_text().splitlines()[-1].split(" ", 2)[2]


def alive(pid: int) -> bool:
    """Whether a process runs: it exists and is not a zombie waiting to be reaped."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (FileNotFoundError, IndexError):
        return False


def eventually(check: Callable[[], bool], seconds: float = 30) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.1)
    return check()


def test_the_commit_holds_the_reports_files_alone_and_another_staged_change_stays_staged(
        tmp_path: Path, stub: Path, repo: Path) -> None:
    run = retro(tmp_path, repo, FIRST, SINCE)
    agent = repo / "agent"
    assert (stub / "order").read_text().split("\n")[:-1] == ["read fresh", "follow up", "go deep", "lens pass", "synthesize"]
    assert (run / "touched.md").is_file()
    assert out(agent, "show", "--name-only", "--format=", "HEAD").split() == ["retro/report.html", "retro/report.md"]
    assert out(agent, "diff", "--cached", "--name-only").split() == ["tickets/a.md"], \
        "the session's staged ticket is neither committed nor unstaged"
    assert (agent / "retro/report.md").read_text() == (run / "report.md").read_text()
    assert last_logged(tmp_path).startswith("committed ")


def test_mid_rebase_nothing_is_committed_and_the_run_log_says_why(tmp_path: Path, stub: Path, repo: Path) -> None:
    agent = repo / "agent"
    git(agent, "commit", "-qm", "the staged ticket")
    git(agent, "checkout", "-qb", "side", "HEAD~")
    (agent / "tickets/a.md").write_text("status: done\n")
    git(agent, "commit", "-qam", "side")
    git(agent, "checkout", "-q", "-")
    assert subprocess.run(["git", "-C", agent, "rebase", "side"], capture_output=True).returncode != 0, "a conflict stops the rebase"
    head = out(agent, "rev-parse", "HEAD")
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST, SINCE)
    assert out(agent, "rev-parse", "HEAD") == head
    assert not (agent / "retro/report.md").exists()
    assert last_logged(tmp_path).startswith(f"not committed: {agent} is mid-rebase; the report stays in {tmp_path}/data/agents/runs/")


@pytest.mark.parametrize("verdict", ["committed while the run ran", "staged"])
def test_a_verdict_written_into_the_report_is_never_overwritten(
        tmp_path: Path, stub: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, verdict: str) -> None:
    agent = repo / "agent"
    retro(tmp_path, repo, FIRST, SINCE)
    edit = f"echo 'F1 dismissed by max' >> {agent}/retro/report.md && git -C {agent} add retro/report.md"
    if verdict == "staged":
        subprocess.run(edit, shell=True, check=True)
    else:
        monkeypatch.setenv("STUB_BEFORE_SYNTHESIS", f"{edit} && git -C {agent} commit -qm verdict -- retro/report.md")
    head = out(agent, "rev-parse", "HEAD")
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST + WEEK)
    assert "F1 dismissed by max" in (agent / "retro/report.md").read_text()
    assert out(agent, "rev-parse", "HEAD") == head if verdict == "staged" else out(agent, "log", "-1", "--format=%s") == "verdict\n"
    assert last_logged(tmp_path).startswith("not committed: ")


def test_read_fresh_sees_no_earlier_report_and_the_later_stages_read_the_last_three_from_git_history(
        tmp_path: Path, stub: Path, repo: Path) -> None:
    runs = [retro(tmp_path, repo, FIRST, SINCE)] + [retro(tmp_path, repo, FIRST + n * WEEK) for n in (1, 2, 3)]
    fresh = (stub / "read fresh.seen").read_text()
    assert "sessions/" in fresh and "previous" not in fresh
    args = (stub / "read fresh.argv").read_text().splitlines()
    assert "--add-dir" not in args and "Bash" not in args[args.index("--tools") + 1], \
        "read-fresh can reach nothing outside its run directory, an earlier report included"
    later = {Path(p).name for p in (stub / "follow up.seen").read_text().split() if "/previous/" in p}
    assert later == {"current.md", *(f"{retro_run.dirname(FIRST + n * WEEK)}.md" for n in (0, 1, 2))}
    assert (runs[-1] / "previous/current.md").read_text() == (runs[-2] / "report.md").read_text()
    rows = [json.loads(line) for line in (runs[-1] / "sessions.jsonl").read_text().splitlines()]
    period = [r for r in rows if r["set"] == "sessions"]
    assert period and all(r["start"] >= retro_run.stamp(FIRST + 2 * WEEK) for r in period), \
        "each period starts where the last ended"


def test_an_older_sample_bigger_than_a_batch_is_read_in_batches_of_its_own(tmp_path: Path) -> None:
    run = tmp_path / "run"
    rows = []

    def digest(where: str, sid: str, chars: int, start: str) -> None:
        (run / where).mkdir(parents=True, exist_ok=True)
        (run / where / f"{sid}.md").write_text("x" * chars)
        rows.append(dict(id=sid, set=where, project="/home/u/repos/agents", start=start))

    digest("sessions", "now", 1000, "2026-10-06T09:00:00Z")
    third = retro_run.BATCH_CHARS // 3 + 1  # two fit in a batch, three do not
    for day in (5, 4, 3, 2, 1):
        digest("sample", f"day{day}", third, f"2026-09-0{day}T09:00:00Z")
    (run / "sessions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    retro_run.write_batches(run)

    batches = json.loads((run / "batches.json").read_text())
    assert [(b["name"], b["digests"]) for b in batches] == [
        ("batch-01", ["sessions/now.md"]),
        ("sample-01", ["sample/day1.md", "sample/day2.md"]),
        ("sample-02", ["sample/day3.md", "sample/day4.md"]),
        ("sample-03", ["sample/day5.md"]),
    ]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc, and the parent-death signal is Linux's")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGKILL], ids=["stopped", "killed"])
def test_a_run_stopped_or_killed_ends_the_stage_it_is_in(
        tmp_path: Path, stub: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, sig: signal.Signals) -> None:
    monkeypatch.setenv("STUB_HANG", "1")
    pids = stub / "read fresh.pids"
    run = subprocess.Popen([sys.executable, retro_run.__file__, str(repo), "--since", SINCE.isoformat(),
                            "--data", str(tmp_path / "data"), "--projects", str(tmp_path / ".claude/projects")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started: list[int] = []
    try:
        assert eventually(pids.exists), "the read-fresh stage started its model run"
        started = [int(p) for p in pids.read_text().split()]
        run.send_signal(sig)
        run.wait(60)
        if sig == signal.SIGTERM:  # a stopped run waits for its stage, which takes a second to end
            assert not any(map(alive, started)), "the stage's model run and its child ended before the run did"
        assert eventually(lambda: not any(map(alive, started))), "the stage's model run and its child ended with the run"
    finally:
        run.kill()
        for pid in filter(alive, started):
            os.kill(pid, signal.SIGKILL)
    if sig == signal.SIGTERM:
        assert run.returncode == 128 + signal.SIGTERM
        assert last_logged(tmp_path).startswith("stopped: SIGTERM during read-fresh, which ended with it")


@pytest.mark.parametrize("kind", ["workflow retro", "repo retro"])
def test_a_resumed_run_keeps_its_period_and_runs_only_the_stages_that_left_out_a_file(
        tmp_path: Path, stub: Path, repo: Path, code: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    repo, name = (repo, "agents") if kind == "workflow retro" else (code, "dotfiles")
    monkeypatch.setenv("STUB_SYNTHESIS_FAILS", "1")
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST, SINCE)
    assert last_logged(tmp_path, name).startswith("failed: synthesize left out report.md")
    run = tmp_path / f"data/{name}/runs" / retro_run.dirname(FIRST)
    for argv in stub.glob("*.argv"):
        argv.unlink()
    monkeypatch.delenv("STUB_SYNTHESIS_FAILS")

    assert retro_run.run_retro(repo, tmp_path / "data", [tmp_path / ".claude/projects"], resume=run) == run

    assert [p.stem for p in stub.glob("*.argv")] == ["synthesize"], "the stages that wrote what they owe ran once"
    message = out(repo / "agent", "log", "-1", "--format=%B")
    assert f"Retro-since: {retro_run.stamp(SINCE)}" in message and f"Retro-until: {retro_run.stamp(FIRST)}" in message
    assert last_logged(tmp_path, name).startswith("committed ")


def test_a_run_leaves_its_callers_signal_handlers_as_it_found_them(tmp_path: Path, stub: Path, repo: Path) -> None:
    """A run in-process once left TERM ignored, and every process started after it unstoppable."""
    found = {s: signal.getsignal(s) for s in retro_run.STOP}
    retro(tmp_path, repo, FIRST, SINCE)
    assert {s: signal.getsignal(s) for s in retro_run.STOP} == found


def test_a_run_directory_from_before_run_json_resumes_with_the_start_it_is_given(
        tmp_path: Path, stub: Path, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUB_SYNTHESIS_FAILS", "1")
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST, SINCE)
    monkeypatch.delenv("STUB_SYNTHESIS_FAILS")
    run = tmp_path / "data/agents/runs" / retro_run.dirname(FIRST)
    (run / "run.json").unlink()
    projects = [tmp_path / ".claude/projects"]

    with pytest.raises(SystemExit, match="pass --since"):
        retro_run.run_retro(repo, tmp_path / "data", projects, resume=run)
    retro_run.run_retro(repo, tmp_path / "data", projects, SINCE, resume=run)

    message = out(repo / "agent", "log", "-1", "--format=%B")
    assert f"Retro-since: {retro_run.stamp(SINCE)}" in message and f"Retro-until: {retro_run.stamp(FIRST)}" in message


@pytest.mark.parametrize("kept", [True, False], ids=["run.json", "before run.json"])
def test_a_run_is_not_resumed_over_a_verdict_committed_since_it_began(
        tmp_path: Path, stub: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, kept: bool) -> None:
    monkeypatch.setenv("STUB_SYNTHESIS_FAILS", "1")
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST, SINCE)
    monkeypatch.delenv("STUB_SYNTHESIS_FAILS")
    run = tmp_path / "data/agents/runs" / retro_run.dirname(FIRST)
    if not kept:
        (run / "run.json").unlink()
    agent = repo / "agent"
    (agent / "retro/report.md").write_text("F1 dismissed by max\n")
    git(agent, "add", "retro/report.md")
    git(agent, "commit", "-qm", "verdict", "--", "retro/report.md")

    with pytest.raises(SystemExit, match="was committed to since"):
        retro_run.run_retro(repo, tmp_path / "data", [tmp_path / ".claude/projects"], None if kept else SINCE, resume=run)
    assert (agent / "retro/report.md").read_text() == "F1 dismissed by max\n"
    assert out(agent, "log", "-1", "--format=%s") == "verdict\n", "nothing was committed over it"


def commit_by(repo: Path, author: str, when: datetime) -> None:
    """A commit in `repo` whose author is `author` and whose committer is max, as a worker's is once merged."""
    (repo / f"{when:%H%M%S}-{author.split()[0]}").write_text(author)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", f"by {author}", f"--author={author}", when=when)


def test_a_week_with_no_session_or_commit_of_maxs_is_skipped_and_the_run_log_says_so(
        tmp_path: Path, stub: Path, repo: Path) -> None:
    projects = tmp_path / ".claude/projects"
    Transcript(projects, str(repo), SINCE + timedelta(days=1), entrypoint="sdk-cli").says("a worker's prompt")
    late = Transcript(projects, str(repo), SINCE - timedelta(minutes=3)).says("before the period")
    late.answers("still").answers("working").answers("past the period's start")
    commit_by(repo, f"max <{IDENTITY['GIT_AUTHOR_EMAIL']}>", SINCE - timedelta(days=1))
    commit_by(repo, "worker <worker@example.org>", SINCE + timedelta(days=1))

    with pytest.raises(SystemExit) as stopped:
        retro_run.run_retro(repo, tmp_path / "data", [projects], SINCE, until=FIRST, if_active=True)

    assert stopped.value.code == retro_run.SKIPPED
    assert last_logged(tmp_path) == f"skipped: no session or commit of max's since {retro_run.stamp(SINCE)}"
    assert not list(stub.glob("*.argv")), "no stage ran"
    assert not (repo / "agent/retro/report.md").exists()


@pytest.mark.parametrize("sign", ["a message", "a commit"])
def test_a_week_with_a_message_or_a_commit_of_maxs_runs(tmp_path: Path, stub: Path, repo: Path, sign: str) -> None:
    projects = tmp_path / ".claude/projects"
    projects.mkdir(parents=True)
    if sign == "a message":
        Transcript(projects, str(repo), SINCE + timedelta(days=3)).says("why is the suite so slow")
    else:
        commit_by(repo, f"max <{IDENTITY['GIT_AUTHOR_EMAIL']}>", SINCE + timedelta(days=3))

    retro_run.run_retro(repo, tmp_path / "data", [projects], SINCE, until=FIRST, if_active=True)

    started = (tmp_path / "data/agents/runs.log").read_text().splitlines()[0]
    assert f"new since: {sign} of max's at {retro_run.stamp(SINCE + timedelta(days=3, minutes=1 if sign == 'a message' else 0))}" in started
    assert last_logged(tmp_path).startswith("committed ")


# ── a repo retro ─────────────────────────────────────────────────────────────


@pytest.fixture
def code(tmp_path: Path) -> Path:
    """A repo other than the agents repo, with a commit either side of the period's start, and its
    agent repo with a proposed ticket and a session page."""
    code, agent = tmp_path / ".dotfiles", tmp_path / ".dotfiles" / "agent"
    for r in (code, agent):
        r.mkdir(parents=True)
        git(r, "init", "-q", "-b", "main")
    (code / ".gitignore").write_text("agent/\n")
    commit(code, {".gitignore": "agent/\n", "old.sh": "1"}, "before the period", SINCE - timedelta(days=1))
    commit(code, {"backup.sh": "1"}, "backup: retry once", SINCE + timedelta(days=1))
    commit(agent, {"tickets/flaky-backup.md": ticket("proposed")}, "file flaky-backup", SINCE + timedelta(days=1))
    (agent / "sessions/0123abcd/turns").mkdir(parents=True)
    (agent / "sessions/0123abcd/session.md").write_text("what max was shown\n")
    return code


def test_a_repo_retro_reads_its_repos_commits_and_proposed_tickets_and_no_session(
        tmp_path: Path, stub: Path, code: Path) -> None:
    projects = tmp_path / ".claude/projects"
    Transcript(projects, str(code), SINCE + timedelta(days=2)).says("the backup failed again")

    run = retro_run.run_retro(code, tmp_path / "data", [projects], SINCE, until=FIRST)

    assert (stub / "order").read_text().split("\n")[:-1] == ["follow up", "lens pass", "synthesize"]
    assert not any((run / d).exists() for d in ("sessions", "sample", "sessions.jsonl", "batches.json")), \
        "no session was digested (retro-semi-automated#P10)"
    assert not (tmp_path / "data/dotfiles/digest-cache").exists()
    assert "backup: retry once" in (run / "git/dotfiles.md").read_text()
    assert (run / "touched.md").is_file()
    assert (run / "proposed/flaky-backup.md").read_text() == ticket("proposed")
    for stage in ("follow up", "lens pass", "synthesize"):
        args = (stub / f"{stage}.argv").read_text().splitlines()
        assert f"Read(/{code / 'agent/sessions'}/**)" in args, "no stage may read the agent repo's session pages"
        assert not [a for a in args if a.startswith(f"Bash(git -C {code / 'agent'}")], \
            "nor run git in the agent repo, which shows a committed page without naming it"
        assert [a for a in args if a.startswith("Edit(")] == [f"Edit(/{run}/**)"], \
            "a stage writes in its run directory alone, a proposed ticket untouched (retro-semi-automated#P5)"
    agent = code / "agent"
    assert out(agent, "show", "--name-only", "--format=%s", "HEAD").split("\n")[0] == \
        f"retro: the repo retro of {SINCE.date()} to {FIRST.date()}"
    assert (agent / "retro/report.md").is_file()


def test_a_repo_whose_agent_directory_is_no_repo_of_its_own_is_refused_with_the_reason(
        tmp_path: Path, stub: Path) -> None:
    code = tmp_path / "quartz-knowledge-base"
    code.mkdir()
    git(code, "init", "-q", "-b", "main")
    commit(code, {"agent/tickets/a.md": ticket("open"), "note.md": "1"}, "notes", SINCE + timedelta(days=1))
    head = out(code, "rev-parse", "HEAD")

    with pytest.raises(SystemExit, match=f"{code / 'agent'} is no agent repo"):
        retro_run.run_retro(code, tmp_path / "data", [tmp_path / ".claude/projects"], SINCE, until=FIRST)

    assert out(code, "rev-parse", "HEAD") == head, "nothing was committed in the code repo"
    assert not (code / "agent/retro").exists() and not list(stub.glob("*.argv"))


def test_a_repo_retros_first_run_takes_the_four_weeks_before_it(tmp_path: Path, stub: Path, code: Path) -> None:
    retro_run.run_retro(code, tmp_path / "data", [], until=FIRST)

    message = out(code / "agent", "log", "-1", "--format=%B")
    assert f"Retro-since: {retro_run.stamp(FIRST - timedelta(weeks=4))}" in message


def test_a_repo_retro_with_no_commit_since_its_last_run_is_skipped_and_one_with_a_commit_runs(
        tmp_path: Path, stub: Path, code: Path) -> None:
    retro_run.run_retro(code, tmp_path / "data", [], SINCE, until=FIRST)
    for argv in stub.glob("*.argv"):
        argv.unlink()

    with pytest.raises(SystemExit) as stopped:
        retro_run.run_retro(code, tmp_path / "data", [], until=FIRST + WEEK, if_active=True)
    assert stopped.value.code == retro_run.SKIPPED
    assert last_logged(tmp_path, "dotfiles") == f"skipped: no commit in {code} since {retro_run.stamp(FIRST)}"
    assert not list(stub.glob("*.argv"))

    git(code, "checkout", "-qb", "worker")
    commit_by(code, "worker <worker@example.org>", FIRST + timedelta(days=1))
    sha = out(code, "rev-parse", "--short=7", "HEAD").strip()
    git(code, "checkout", "-q", "main")
    retro_run.run_retro(code, tmp_path / "data", [], until=FIRST + WEEK, if_active=True)
    started = (tmp_path / "data/dotfiles/runs.log").read_text().splitlines()[-5]
    assert f"new since: a commit at {retro_run.stamp(FIRST + timedelta(days=1))} in {code} ({sha})" in started
    assert last_logged(tmp_path, "dotfiles").startswith("committed ")
