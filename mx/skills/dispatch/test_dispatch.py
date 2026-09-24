# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for what `dispatch` and `dispatch-ctl` read and write on a ticket. Run: pytest test_dispatch.py

One seam: the two scripts' command lines, run as subprocesses over a toy repo whose worker is a stub
on the `DISPATCH_RUNNER` seam dispatch-ctl documents, so what runs is dispatch and dispatch-ctl
themselves. The oracles are `agent/tickets/ticket-file-contract.md` (P4, that a worker's brief is the
ticket's body with every ancestor's, assembled by the one function; P7, that a worker writes no
ticket file and reports instead; `needs-user` as the one field that keeps a ticket from a worker)
and `/mx:tracker`'s Ticket state (a claim is taken from the frontier, and a claimed ticket is in
somebody's hands).

Every check that touches a ticket runs twice, once with the tracker in the code repo and once with
it in a repo of its own that the code repo names (`tracked`): the two are one flow, and the split is
what `git config mx.tracker` is for.

`agent/tickets/dispatch-scripts-under-test.md` is where the rest of these scripts' coverage is
argued; this file is the cases the ticket-file move made.
"""

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

SKILL = Path(__file__).parent
DISPATCH = SKILL / "dispatch"

# A worker as dispatch-ctl leaves the seam for one: argv and the log-then-status contract are the
# real runner's, and it keeps the brief it was sent so the check can read what a spawn carried.
RUNNER = """#!/usr/bin/env bash
set -eu
message=$1 slug=$2 run_id=$4
state=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cp "$message" "$state/$run_id.brief"
printf 'stub: built %s\\n' "$slug" >> "$state/$run_id.log"
printf 'attempts=1 exit=0 report=no session=stub\\n' > "$state/$run_id.status"
"""

# The same stub with something to show and nothing to review: the commit a worker makes, and no
# report, which is what a run that stopped short leaves.
STOPPED_SHORT = RUNNER.replace(
    "printf 'attempts=1 exit=0 report=no",
    """printf 'the lamp, half warm\\n' > lamp.txt
git add lamp.txt
git commit -q -m "$slug: as far as it got"
printf 'attempts=1 exit=1 report=no""",
)

# The same stub finishing: one commit on the ticket branch in the worktree it was started in, and
# the report beside the worklog, which is what the runner contract has a worker leave behind.
BUILDING = RUNNER.replace(
    "printf 'attempts=1 exit=0 report=no",
    """printf 'the lamp, warm\\n' > lamp.txt
git add lamp.txt
git commit -q -m "the warm preset"
cat > "$state/$run_id.report.md" <<'REPORT'
## Comments

The warm preset lands, unmerged, with one question under it.

- [D1] **Assumptions**
  - A1 `lamp.txt:1`: 2700K, since the bulb box says so.

## Questions

- [D2] **Warm at what temperature?** 2700K reads amber; 3000K is closer to the old bulb.
REPORT
printf 'attempts=1 exit=0 report=yes""",
)


def git(at: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(at), "-c", "user.email=toy@toy", "-c", "user.name=toy",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout


def ticket(root: Path, slug: str, status: str = "open", parent: str = "", needs_user: bool = False,
           brief: str = "What it is, cold.") -> Path:
    front = ["---", f"status: {status}"]
    front += [f"parent: {parent}"] if parent else []
    front += ["needs-user: true"] if needs_user else []
    front += ["priority: 1", "size: S", "---"]
    path = root / f"{slug}.md"
    path.write_text("\n".join(front) + f"\n\n# {slug.replace('-', ' ').capitalize()}\n\n## Brief\n\n{brief}\n")
    return path


@pytest.fixture
def toy(tmp_path: Path) -> Path:
    """A repo on `main` with a tree of two tickets, and a home of its own for dispatch's state."""
    repo = tmp_path / "lamp"
    (repo / "agent" / "tickets").mkdir(parents=True)
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    for key, value in (("user.email", "toy@toy"), ("user.name", "toy"), ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    root = repo / "agent" / "tickets"
    ticket(root, "lamp-ui", brief="The whole of giving the lamp presets.")
    ticket(root, "warm-preset", parent="lamp-ui", brief="One preset, warm.")
    ticket(root, "name-the-presets", needs_user=True, brief="Naming them is a conversation.")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the tracker")
    return repo


def environment(toy: Path, **extra: str) -> dict[str, str]:
    """What every command here runs in: a HOME of its own, and a `diffview` that records the
    arguments `dispatch review` hands it, since the review page is diffview's and the ranges are
    what dispatch has to get right."""
    bin_dir = toy.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "diffview").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{bin_dir / "diffview.args"}"\n'
        'echo "diffview: serving $2 at http://127.0.0.1:1/"\n')
    (bin_dir / "diffview").chmod(0o755)
    (toy.parent / "home").mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(toy.parent / "home"), "GIT_CONFIG_GLOBAL": "/dev/null",
           "JOB_STATE_DIR": str(toy.parent / "jobs"),
           "PATH": f"{bin_dir}:{os.environ['PATH']}", **extra}
    env.pop("DISPATCH_PERMISSION_MODE", None)
    return env


def run(toy: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(DISPATCH), *args], cwd=toy, capture_output=True, text=True,
                          env=environment(toy, **extra), timeout=180)


def status_of(tracked: Path, slug: str) -> str:
    return (tracked / f"{slug}.md").read_text().split("status: ")[1].split("\n")[0]


@pytest.fixture(params=["one repo", "two repos"])
def tracked(toy: Path, request: pytest.FixtureRequest) -> Path:
    """The tracker the toy plans with, and where every ticket change is committed: its own
    `agent/tickets`, or one in a repo of its own that the code repo names with `git config
    mx.tracker`, which is what lets the code live in a repo the tickets stay out of."""
    if request.param == "one repo":
        return toy / "agent" / "tickets"
    plans = toy.parent / "plans"
    (plans / "agent").mkdir(parents=True)
    git(toy.parent, "init", "-q", "-b", "main", str(plans))
    for key, value in (("user.email", "toy@toy"), ("user.name", "toy"), ("commit.gpgsign", "false")):
        git(plans, "config", key, value)
    shutil.move(str(toy / "agent" / "tickets"), str(plans / "agent" / "tickets"))
    git(toy, "commit", "-q", "-am", "the tracker moves out")
    git(plans, "add", "-A")
    git(plans, "commit", "-q", "-m", "the tracker")
    git(toy, "config", "mx.tracker", str(plans / "agent" / "tickets"))
    return plans / "agent" / "tickets"


def test_a_claim_is_taken_from_the_frontier_and_a_claimed_ticket_is_in_somebodys_hands(
    toy: Path, tracked: Path
) -> None:
    first = run(toy, "claim", "warm-preset")
    assert first.returncode == 0, first.stderr
    assert status_of(tracked, "warm-preset") == "claimed"
    assert "claim warm-preset" in git(tracked, "log", "-1", "--format=%s"), "committed in the tracker's checkout"

    again = run(toy, "claim", "warm-preset")
    assert again.returncode != 0
    assert "already claimed" in again.stderr, again.stderr


@pytest.fixture
def staged(toy: Path) -> Iterator[Path]:
    """The toy with a stub runner staged in the skill copy dispatch sends to a host.

    A worker's tmux session is named after the repo and the slug, so every run of these checks
    wants the same name: one left standing would have the next check's runner typed into a pane
    whose worktree is gone. They are killed either side of the check, since a crashed one is still
    there when the next starts."""
    skill = toy.parent / "skills"
    (skill / "dispatch").mkdir(parents=True)
    (skill / "tracker").mkdir()
    for name in ("dispatch", "dispatch-ctl", "worker-prompt.md"):
        shutil.copy(SKILL / name, skill / "dispatch" / name)
    shutil.copy(SKILL.parent / "tracker" / "tracker.py", skill / "tracker" / "tracker.py")
    (skill / "dispatch" / "run-worker.sh").write_text(RUNNER)
    kill_sessions()
    yield skill / "dispatch" / "dispatch"
    kill_sessions()


def kill_sessions() -> None:
    if not shutil.which("tmux"):
        pytest.skip("no tmux here, and a spawn types its runner into a tmux pane")
    listed = subprocess.run(["tmux", "ls", "-F", "#{session_name}"], capture_output=True, text=True)
    for session in listed.stdout.split():
        if session.startswith("dispatch-lamp-"):
            subprocess.run(["tmux", "kill-session", "-t", f"={session}"], capture_output=True)


def spawn(toy: Path, staged: Path, slug: str, message: str) -> subprocess.CompletedProcess:
    env = environment(toy)
    subprocess.run([str(staged), "prompt", slug], cwd=toy, input=message, text=True, check=True, env=env)
    return subprocess.run([str(staged), "ctl", "--host", "local", "--setup-cmd", "true", "spawn", slug, "sonnet"],
                          cwd=toy, capture_output=True, text=True, env=env, timeout=180)


def test_a_spawn_sends_the_orchestrators_message_with_the_tickets_context_under_it(toy: Path, tracked: Path, staged: Path) -> None:
    """`ticket-file-contract#P4`'s worker half: the brief is the ticket's body and every ancestor's,
    which is what `tracker context` assembles for the review's `--spec` too."""
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n")
    assert said.returncode == 0, said.stderr
    (brief,) = (toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.brief")
    written = brief.read_text()
    assert written.startswith("Work the ticket warm-preset.\n")
    assert "## warm-preset" in written and "One preset, warm." in written
    assert "## parent ticket: lamp-ui" in written and "The whole of giving the lamp presets." in written
    assert written.index("## warm-preset") < written.index("## parent ticket: lamp-ui")


def test_a_ticket_the_user_is_in_the_loop_for_is_never_handed_to_a_worker(toy: Path, tracked: Path, staged: Path) -> None:
    run(toy, "claim", "name-the-presets")
    said = spawn(toy, staged, "name-the-presets", "Work it.\n")
    assert said.returncode != 0
    assert "needs the user in the loop" in said.stderr, said.stderr
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.brief"))


def test_a_ticket_no_reader_can_read_reaches_no_worker(toy: Path, tracked: Path, staged: Path) -> None:
    """The guard the commit hook makes where a ticket file is written, made again where a worker is
    handed one: the host reads no ticket at all, so this is the reader that stands between a broken
    ticket and a worker."""
    run(toy, "claim", "warm-preset")
    broken = tracked / "warm-preset.md"
    broken.write_text(broken.read_text() + "\n## Comments\n\n- A1 no anchor in backticks here.\n")
    git(tracked, "commit", "-q", "-am", "a bullet no reader can read")
    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode != 0
    assert "warm-preset.md:" in said.stderr and "this assumption has no anchor" in said.stderr, said.stderr
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.brief"))


def test_a_worker_reports_and_the_orchestrator_writes_the_ticket(toy: Path, tracked: Path, staged: Path) -> None:
    """One ticket end to end, the tracker in either repo: claim, spawn, the report, the import, a
    question ruled before the merge, and the landing with the range the ticket keeps.

    `ticket-file-contract#P7`: nothing the worker did touched a ticket file, and every word it wrote
    for the user is in the tracker's own copy by the time the build waits for a ruling."""
    tracker = SKILL.parent / "tracker" / "tracker.py"
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    for _ in range(60):
        if list(state.glob("*.status")):
            break
        time.sleep(0.5)
    left = list(state.glob("*.status"))
    assert left, "no status line 30s after the spawn: " + subprocess.run(
        ["tmux", "capture-pane", "-p", "-J", "-t", "=dispatch-lamp-warm-preset"],
        capture_output=True, text=True).stdout
    assert "report=yes" in left[0].read_text(), "the runner says it left one"
    assert git(toy, "diff", "--name-only", "main", "ticket/warm-preset").split() == ["lamp.txt"], \
        "the ticket branch carries the code and nothing of the tracker"

    assert run(toy, "fetch", "warm-preset").returncode == 0
    fetched = toy / ".git" / "dispatch" / "reports" / "main" / "warm-preset.md"
    assert fetched.is_file(), "the report comes back with the branch"
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr

    written = (tracked / "warm-preset.md").read_text()
    assert status_of(tracked, "warm-preset") == "review"
    assert "The warm preset lands, unmerged" in written and "**Warm at what temperature?**" in written
    assert "warm-preset for review" in git(tracked, "log", "-1", "--format=%s")
    assert not fetched.exists() and fetched.with_suffix(".md.imported").is_file(), "one round, one import"
    notes = json.loads((tracked.parent / "diffviews" / "warm-preset.notes.json").read_text())
    assert [(one["id"], one["path"], one["line"]) for one in notes["notes"]] == [(1, "lamp.txt", 1)]

    # the ruling, before the merge: the question is in the tracker's copy from the import
    ruled = subprocess.run([str(tracker), "rule", "warm-preset", "D2", "2700K"], cwd=toy,
                           capture_output=True, text=True)
    assert ruled.returncode == 0, ruled.stderr
    git(tracked, "commit", "-q", "-am", "warm-preset: D2 ruled")

    # the stub makes one commit, so its parent is what the branch was cut from; read from git
    # rather than from the range under test
    cut = git(toy, "rev-parse", "ticket/warm-preset~1").strip()
    tip = git(toy, "rev-parse", "ticket/warm-preset").strip()
    git(toy, "merge", "-q", "--no-ff", "-m", "warm-preset: landed", "ticket/warm-preset")
    landed = run(toy, "review", "warm-preset")
    assert landed.returncode == 0, landed.stderr
    assert status_of(tracked, "warm-preset") == "done"
    got = subprocess.run([str(tracker), "get", "warm-preset", "diff"], cwd=toy, capture_output=True, text=True)
    (range_,) = got.stdout.split()
    qualified = not (toy / "agent" / "tickets").is_dir()
    assert range_.startswith("lamp@") == qualified, f"{range_} in the tracker's own repo: {not qualified}"
    assert range_.removeprefix("lamp@") == f"{cut}..{tip}", "the range the merge commit's parents give"
    # whatever the ticket says, the page is rendered from this checkout
    handed = (toy.parent / "bin" / "diffview.args").read_text().splitlines()
    assert [line for line in handed if line.startswith(f"{toy}@{cut}..{tip} ")], handed


def test_a_run_that_left_no_report_is_said_and_imported_from_nowhere(toy: Path, tracked: Path, staged: Path) -> None:
    """The other half of the finished signal: a worker that stopped short leaves no report, the
    fetch says so and exits 0, and the review that follows writes nothing of a worker's into the
    ticket."""
    (staged.parent / "run-worker.sh").write_text(STOPPED_SHORT)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    for _ in range(60):
        if list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.status")):
            break
        time.sleep(0.5)

    fetched = run(toy, "fetch", "warm-preset")
    assert fetched.returncode == 0, fetched.stderr
    assert "left no report" in fetched.stderr, fetched.stderr
    reports = toy / ".git" / "dispatch" / "reports" / "main"
    assert not list(reports.glob("*")), "a run that left none leaves nothing behind, half a file included"

    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(tracked, "warm-preset") == "review", "the branch is there to rule on either way"
    assert "## Questions" not in (tracked / "warm-preset.md").read_text()


@pytest.mark.parametrize("wrote, exits, says", [
    (True, 1, "attempts=1 exit=1 report=yes"),
    (False, 0, "attempts=1 exit=0 report=no"),
])
def test_the_runner_reads_the_report_as_the_run_leaving_something_to_review(
    tmp_path: Path, wrote: bool, exits: int, says: str
) -> None:
    """The shipped runner, with `claude` stubbed rather than the runner itself: a run that left a
    report is finished whatever it exited with, one that left none says so on its status line, and
    the retry loop ends either way."""
    state = tmp_path / "state"
    state.mkdir()
    for name in ("run-worker.sh", "worker-prompt.md"):
        shutil.copy(SKILL / name, state / name)
    (tmp_path / "message.md").write_text("Work the ticket warm-preset.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(
        "#!/bin/sh\n"
        + ('printf "## Comments\\n\\nit lands.\\n" > "$DISPATCH_REPORT"\n' if wrote else "")
        + f"exit {exits}\n")
    (bin_dir / "claude").chmod(0o755)

    done = subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet", "run-1"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)},
    )
    assert done.returncode == 0, done.stderr
    assert (state / "run-1.status").read_text().startswith(says), (state / "run-1.status").read_text()
    assert (state / "run-1.report.md").exists() is wrote
    assert "runner: started warm-preset" in (state / "run-1.log").read_text()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
