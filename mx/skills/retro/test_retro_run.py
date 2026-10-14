"""Checks for a workflow retro's run, at the seam "The run script's commit" (retro-semi-automated):
given a scratch agent repo in which another change is staged, the commit holds the report's files
alone and the other change is still staged after it; given one mid-rebase, nothing is committed
and the run log says why (P9). The oracle is git's own record of the commit and the index.
Run: make test, or pytest on this file with tyro, pyyaml and markdown-it-py.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

import retro_run  # noqa: E402
from test_retro_collect import IDENTITY, SINCE, Transcript, git  # noqa: E402

FIRST = datetime(2026, 10, 12, 2, tzinfo=UTC)
WEEK = timedelta(weeks=1)

# What each stage writes, keyed by the stage its prompt's first line names. It records its
# command line, one argument per line, and what the run directory held when it started; before
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
find . -path ./prompts -prune -o -type f -print | sort > "$STUB_LOG/$stage.seen"
if [ -n "${STUB_HANG:-}" ]; then trap "sleep 1; exit 143" TERM; sleep 300 & echo "$$ $!" > "$STUB_LOG/$stage.pids.tmp" && mv "$STUB_LOG/$stage.pids.tmp" "$STUB_LOG/$stage.pids"; wait; fi
case $stage in
    "read fresh") mkdir -p notes && echo "notes" > notes/git.md && for b in $(jq -r '.[].name' batches.json); do echo notes > "notes/$b.md"; done ;;
    "follow up") echo "follow-up" > follow-up.md ;;
    "go deep") mkdir -p deep && for f in architecture lenses permissions; do echo "deep" > "deep/$f.md"; done ;;
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


def last_logged(tmp_path: Path) -> str:
    """The message of the run log's last line, after its time and run."""
    return (tmp_path / "data/agents/runs.log").read_text().splitlines()[-1].split(" ", 2)[2]


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


def test_a_resumed_run_keeps_its_period_and_runs_only_the_stages_that_left_out_a_file(
        tmp_path: Path, stub: Path, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUB_SYNTHESIS_FAILS", "1")
    with pytest.raises(SystemExit):
        retro(tmp_path, repo, FIRST, SINCE)
    assert last_logged(tmp_path).startswith("failed: synthesize left out report.md")
    run = tmp_path / "data/agents/runs" / retro_run.dirname(FIRST)
    for argv in stub.glob("*.argv"):
        argv.unlink()
    monkeypatch.delenv("STUB_SYNTHESIS_FAILS")

    assert retro_run.run_retro(repo, tmp_path / "data", [tmp_path / ".claude/projects"], resume=run) == run

    assert [p.stem for p in stub.glob("*.argv")] == ["synthesize"], "the stages that wrote what they owe ran once"
    message = out(repo / "agent", "log", "-1", "--format=%B")
    assert f"Retro-since: {retro_run.stamp(SINCE)}" in message and f"Retro-until: {retro_run.stamp(FIRST)}" in message
    assert last_logged(tmp_path).startswith("committed ")


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
