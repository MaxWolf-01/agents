# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for what `dispatch` and `dispatch-ctl` read and write on a ticket. Run: pytest test_dispatch.py

One seam: the two scripts' command lines, run as subprocesses over a toy project whose worker is a
stub on the `DISPATCH_RUNNER` seam dispatch-ctl documents, so what runs is dispatch and dispatch-ctl
themselves. The toy is a project in the layout every project has: a code repo, and its `agent/` a
git repo of its own inside it that the code repo ignores. The oracles are
`agent/tickets/ticket-file-contract.md` (P4, that a worker's brief is the ticket's body with every
ancestor's, assembled by the one function; P7, that a worker writes no ticket file and reports
instead; `needs-user` as the one field that keeps a ticket from a worker) and `/mx:tracker`'s Ticket
state (a claim is taken from the frontier, and a claimed ticket is in somebody's hands).

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

# The same stub with something to show and nothing to review: the commits a worker makes in the two
# repos it holds, and no report, which is what a run that stopped short leaves.
STOPPED_SHORT = RUNNER.replace(
    "printf 'attempts=1 exit=0 report=no",
    """git() { command git -c user.email=stub@toy -c user.name=stub -c commit.gpgsign=false "$@"; }
printf 'the lamp, half warm\\n' > lamp.txt
git add lamp.txt
git commit -q -m "$slug: as far as it got"
printf 'attempts=1 exit=1 report=no""",
)

# The same stub finishing: its code on the code repo's ticket branch, and its demo and its report on
# the agent repo's, which is the worktree at `agent` inside the one it was started in. The report
# being committed there is what says the worker finished.
BUILDING = RUNNER.replace(
    "printf 'attempts=1 exit=0 report=no",
    """git() { command git -c user.email=stub@toy -c user.name=stub -c commit.gpgsign=false "$@"; }
printf 'the lamp, warm\\n' > lamp.txt
git add lamp.txt
git commit -q -m "$slug: the warm preset"
mkdir -p "agent/show/$slug"
printf '#!/usr/bin/env bash\\necho "the warm preset"\\n' > "agent/show/$slug/demo"
chmod +x "agent/show/$slug/demo"
cat > "agent/show/$slug/report.md" <<'REPORT'
## Comments

The warm preset lands, unmerged, with one question under it. It meets the ticket's one acceptance
criterion.

**Demo**

    agent/show/warm-preset/demo

- [D1] **Assumptions**
  - A1 `lamp.txt:1`: 2700K, since the bulb box says so.

## Questions

- [D2] **Warm at what temperature?** 2700K reads amber; 3000K is closer to the old bulb.
REPORT
git -C agent add -A
git -C agent commit -q -m "$slug: the demo and the report"
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
    """A project on `main`: a code repo, its `agent/` a repo of its own inside it that the code repo
    ignores, and a tree of two tickets in it. Answers the code repo's root."""
    repo = tmp_path / "lamp"
    (repo / "agent" / "tickets").mkdir(parents=True)
    for at in (repo, repo / "agent"):
        git(tmp_path, "init", "-q", "-b", "main", str(at))
        for key, value in (("user.email", "toy@toy"), ("user.name", "toy"), ("commit.gpgsign", "false")):
            git(at, "config", key, value)
    (repo / ".gitignore").write_text("/agent/\n")
    (repo / "lamp.txt").write_text("the lamp\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the lamp")

    root = repo / "agent" / "tickets"
    ticket(root, "lamp-ui", brief="The whole of giving the lamp presets.")
    ticket(root, "warm-preset", parent="lamp-ui", brief="One preset, warm.")
    ticket(root, "name-the-presets", needs_user=True, brief="Naming them is a conversation.")
    git(repo / "agent", "add", "-A")
    git(repo / "agent", "commit", "-q", "-m", "the tracker")
    return repo


def tracked(toy: Path) -> Path:
    """Where this project's ticket files are: the agent repo's, in its main checkout."""
    return toy / "agent" / "tickets"


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


def waited(toy: Path) -> Path:
    """The status line the runner's last act writes, once it is there: a check that carried on
    without it would read a worker that timed out or died as one that finished."""
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    for _ in range(60):
        if list(state.glob("*.status")):
            break
        time.sleep(0.5)
    left = list(state.glob("*.status"))
    assert left, "no status line 30s after the spawn: " + subprocess.run(
        ["tmux", "capture-pane", "-p", "-J", "-t", "=dispatch-lamp-warm-preset"],
        capture_output=True, text=True).stdout
    return left[0]


def status_of(toy: Path, slug: str) -> str:
    return (tracked(toy) / f"{slug}.md").read_text().split("status: ")[1].split("\n")[0]


def test_a_claim_is_taken_from_the_frontier_and_a_claimed_ticket_is_in_somebodys_hands(toy: Path) -> None:
    first = run(toy, "claim", "warm-preset")
    assert first.returncode == 0, first.stderr
    assert status_of(toy, "warm-preset") == "claimed"
    assert "claim warm-preset" in git(toy / "agent", "log", "-1", "--format=%s"), "committed in the agent repo"
    assert "claim" not in git(toy, "log", "-1", "--format=%s"), "and on no branch of the code repo"

    again = run(toy, "claim", "warm-preset")
    assert again.returncode != 0
    assert "already claimed" in again.stderr, again.stderr


def test_a_parent_tickets_worktree_finds_the_tracker_and_writes_where_it_is(toy: Path) -> None:
    """The tree flow: the orchestrator holds the branch its child tickets merge into, in a worktree
    of the code repo that has no `agent/` in it at all, and the agent repo keeps the branch it has
    out. Every ticket change still goes to the agent repo's main checkout."""
    worktree = toy.parent / "lamp-lamp-ui"
    git(toy, "worktree", "add", "-q", str(worktree), "-b", "lamp-ui")
    assert not (worktree / "agent").exists(), "the code repo ignores it and holds none of it"

    claimed = run(worktree, "claim", "warm-preset")
    assert claimed.returncode == 0, claimed.stderr
    assert status_of(toy, "warm-preset") == "claimed"
    assert "claim warm-preset" in git(toy / "agent", "log", "-1", "--format=%s")
    assert git(toy / "agent", "branch", "--show-current").strip() == "main", "on the branch it had out"


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
        if session.startswith(("dispatch-lamp-", "job-lamp-")):  # the worker's, and a staged demo's
            subprocess.run(["tmux", "kill-session", "-t", f"={session}"], capture_output=True)


def spawn(toy: Path, staged: Path, slug: str, message: str) -> subprocess.CompletedProcess:
    env = environment(toy)
    subprocess.run([str(staged), "prompt", slug], cwd=toy, input=message, text=True, check=True, env=env)
    return subprocess.run([str(staged), "ctl", "--host", "local", "--setup-cmd", "true", "spawn", slug, "sonnet"],
                          cwd=toy, capture_output=True, text=True, env=env, timeout=180)


def test_a_spawn_sends_the_orchestrators_message_with_the_tickets_context_under_it(toy: Path, staged: Path) -> None:
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


def test_a_ticket_the_user_is_in_the_loop_for_is_never_handed_to_a_worker(toy: Path, staged: Path) -> None:
    run(toy, "claim", "name-the-presets")
    said = spawn(toy, staged, "name-the-presets", "Work it.\n")
    assert said.returncode != 0
    assert "needs the user in the loop" in said.stderr, said.stderr
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.brief"))


def test_a_ticket_no_reader_can_read_reaches_no_worker(toy: Path, staged: Path) -> None:
    """The guard the commit hook makes where a ticket file is written, made again where a worker is
    handed one: the host reads no ticket at all, so this is the reader that stands between a broken
    ticket and a worker."""
    run(toy, "claim", "warm-preset")
    broken = tracked(toy) / "warm-preset.md"
    broken.write_text(broken.read_text() + "\n## Comments\n\n- A1 no anchor in backticks here.\n")
    git(toy / "agent", "commit", "-q", "-am", "a bullet no reader can read")
    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode != 0
    assert "warm-preset.md:" in said.stderr and "this assumption has no anchor" in said.stderr, said.stderr
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.brief"))


def test_a_worker_reports_and_the_orchestrator_writes_the_ticket(toy: Path, staged: Path) -> None:
    """One ticket end to end, the tracker in either repo: claim, spawn, the report, the import, a
    question ruled before the merge, and the landing with the range the ticket keeps.

    `ticket-file-contract#P7`: nothing the worker did touched a ticket file, and every word it wrote
    for the user is in the tracker's own copy by the time the build waits for a ruling."""
    tracker = SKILL.parent / "tracker" / "tracker.py"
    agent = toy / "agent"
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    assert "report=yes" in waited(toy).read_text(), "the runner reads the report it committed"
    assert git(toy, "diff", "--name-only", "main", "ticket/warm-preset").split() == ["lamp.txt"]
    assert sorted(git(agent, "diff", "--name-only", "main", "ticket/warm-preset").split()) == [
        "show/warm-preset/demo", "show/warm-preset/report.md"], \
        "the agent branch carries the report and the demo, and no ticket file"

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr

    written = (tracked(toy) / "warm-preset.md").read_text()
    assert status_of(toy, "warm-preset") == "review"
    assert "The warm preset lands, unmerged" in written and "**Warm at what temperature?**" in written
    assert "warm-preset for review" in git(agent, "log", "-1", "--format=%s")
    notes = json.loads((agent / "diffviews" / "warm-preset.notes.json").read_text())
    assert [(one["id"], one["path"], one["line"]) for one in notes["notes"]] == [(1, "lamp.txt", 1)]

    # the demo waiting for the user: the two branches checked out as the project keeps them
    demo = toy.parent / "lamp-warm-preset"
    assert (demo / "agent" / "show" / "warm-preset" / "demo").is_file(), \
        "the agent repo is checked out inside the code worktree, where the demo's path leads"
    assert "job-lamp-warm-preset-demo" in said.stdout + said.stderr, said.stderr

    # the ruling, before the merge: the question is in the tracker's copy from the import
    ruled = subprocess.run([str(tracker), "rule", "warm-preset", "D2", "2700K"], cwd=toy,
                           capture_output=True, text=True)
    assert ruled.returncode == 0, ruled.stderr
    git(agent, "commit", "-q", "-am", "warm-preset: D2 ruled")

    # the stub makes one commit in each repo, so its parent is what that branch was cut from; read
    # from git rather than from the ranges under test
    cut, tip = {}, {}
    for at, top in (("code", toy), ("agent", agent)):
        cut[at] = git(top, "rev-parse", "ticket/warm-preset~1").strip()
        tip[at] = git(top, "rev-parse", "ticket/warm-preset").strip()
        git(top, "merge", "-q", "--no-ff", "-m", "warm-preset: landed", "ticket/warm-preset")
    landed = run(toy, "review", "warm-preset")
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    got = subprocess.run([str(tracker), "get", "warm-preset", "diff"], cwd=toy, capture_output=True, text=True)
    assert got.stdout.split() == [f"code@{cut['code']}..{tip['code']}", f"agent@{cut['agent']}..{tip['agent']}"], got.stdout

    # one page, both repos' ranges on it, each rendered from the repo it names
    handed = (toy.parent / "bin" / "diffview.args").read_text().splitlines()
    assert [line for line in handed
            if line.startswith(f"{toy}@{cut['code']}..{tip['code']} {agent}@{cut['agent']}..{tip['agent']} ")], handed

    # the cleanup the accept runs: both worktrees and both branches go, the agent one first
    cleaned = subprocess.run([str(staged), "ctl", "--host", "local", "cleanup", "warm-preset"],
                             cwd=toy, capture_output=True, text=True, env=environment(toy), timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert not (toy.parent / "lamp-warm-preset").exists()
    for at in (toy, agent):
        assert "ticket/warm-preset" not in git(at, "branch", "--list", "ticket/warm-preset")


def test_a_run_that_left_no_report_is_said_and_imported_from_nowhere(toy: Path, staged: Path) -> None:
    """The other half of the finished signal: a worker that stopped short leaves no report, the
    fetch says so and exits 0, and the review that follows writes nothing of a worker's into the
    ticket."""
    (staged.parent / "run-worker.sh").write_text(STOPPED_SHORT)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)

    fetched = run(toy, "fetch", "warm-preset")
    assert fetched.returncode == 0, fetched.stderr
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert "left nothing to review" in said.stderr, said.stderr
    assert status_of(toy, "warm-preset") == "review", "the branches are there to rule on either way"
    assert "## Questions" not in (tracked(toy) / "warm-preset.md").read_text()


def test_a_ticket_file_written_on_an_agent_branch_stops_the_import(toy: Path, staged: Path) -> None:
    """`ticket-file-contract#P7` where the orchestrator reads the branch: a worker that wrote a
    ticket file wrote a second copy of one, and nothing of that round is imported."""
    (staged.parent / "run-worker.sh").write_text(BUILDING.replace(
        "git -C agent add -A",
        'printf "\\nWhat it built, written where no worker writes.\\n" >> "agent/tickets/$slug.md"\n'
        "git -C agent add -A"))
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode != 0
    assert "writes a ticket file" in said.stderr and "tickets/warm-preset.md" in said.stderr, said.stderr
    assert status_of(toy, "warm-preset") == "claimed", "nothing of that round is in the ticket"


@pytest.mark.parametrize("wrote, exits, says", [
    (True, 1, "attempts=1 exit=1 report=yes"),
    (False, 0, "attempts=1 exit=0 report=no"),
])
def test_the_runner_reads_the_report_as_the_run_leaving_something_to_review(
    tmp_path: Path, wrote: bool, exits: int, says: str
) -> None:
    """The shipped runner, with `claude` stubbed rather than the runner itself: a run whose worker
    committed its report in the agent repo is finished whatever it exited with, one that committed
    none says so on its status line, and the retry loop ends either way."""
    state = tmp_path / "state"
    state.mkdir()
    for name in ("run-worker.sh", "worker-prompt.md"):
        shutil.copy(SKILL / name, state / name)
    (tmp_path / "message.md").write_text("Work the ticket warm-preset.\n")
    worktree = tmp_path / "lamp-warm-preset"
    (worktree / "agent").mkdir(parents=True)
    git(worktree / "agent", "init", "-q", "-b", "ticket/warm-preset", ".")
    (worktree / "agent" / "README.md").write_text("the agent repo\n")
    git(worktree / "agent", "add", "-A")
    git(worktree / "agent", "commit", "-q", "-m", "the agent repo")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    committing = (
        'mkdir -p agent/show/warm-preset\n'
        'printf "## Comments\\n\\nit lands.\\n" > agent/show/warm-preset/report.md\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false add -A\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -q -m report\n'
    )
    (bin_dir / "claude").write_text("#!/bin/sh\n" + (committing if wrote else "") + f"exit {exits}\n")
    (bin_dir / "claude").chmod(0o755)

    done = subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet", "run-1"],
        cwd=worktree, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)},
    )
    assert done.returncode == 0, done.stderr
    assert (state / "run-1.status").read_text().startswith(says), (state / "run-1.status").read_text()
    assert "runner: started warm-preset" in (state / "run-1.log").read_text()


def test_a_worktree_with_no_agent_repo_says_so_in_the_worklog(tmp_path: Path) -> None:
    """Without that repo the worker has nowhere to commit a report, so every attempt would end in
    `report=no` with nothing saying why."""
    state = tmp_path / "state"
    state.mkdir()
    for name in ("run-worker.sh", "worker-prompt.md"):
        shutil.copy(SKILL / name, state / name)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "claude").chmod(0o755)

    subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet", "run-1"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)},
    )
    assert "no agent repo at" in (state / "run-1.log").read_text()
    assert "report=no" in (state / "run-1.status").read_text()


def test_a_project_whose_agent_directory_is_not_a_repo_is_refused_by_name(toy: Path) -> None:
    """The state every project is in before the split, and the message that says what to run."""
    plain = toy.parent / "unsplit"
    (plain / "agent" / "tickets").mkdir(parents=True)
    git(toy.parent, "init", "-q", "-b", "main", str(plain))
    (plain / "agent" / "tickets" / "one-flow.md").write_text(
        "---\nstatus: open\npriority: 1\nsize: S\n---\n\n# One flow\n\n## Brief\n\nWhat it is.\n")
    git(plain, "add", "-A")
    git(plain, "commit", "-q", "-m", "a project with its agent directory tracked")

    said = run(plain, "claim", "one-flow")
    assert said.returncode != 0
    assert "not two repos yet" in said.stderr and "project-setup" in said.stderr, said.stderr


def test_a_round_that_built_nothing_is_no_landing(toy: Path, staged: Path) -> None:
    """A worker that died before its first commit: both branches are the base, so there is no range,
    nothing to render and nothing to rule on, and the ticket keeps the claim it had."""
    (staged.parent / "run-worker.sh").write_text(RUNNER)  # starts, logs, leaves both repos untouched
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert "built nothing to review" in said.stderr, said.stderr
    assert status_of(toy, "warm-preset") == "claimed"


def test_a_host_staged_before_the_agent_repo_says_so(toy: Path, staged: Path) -> None:
    """The version skew a host is left in when an older plugin staged it: its config carries no
    agent repo, and every command on that host says which one it is."""
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    config = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main" / "config"
    config.write_text("".join(line for line in config.read_text().splitlines(keepends=True)
                              if not line.startswith("agent")))

    said = subprocess.run(["bash", str(config.parent / "dispatch-ctl"), "log", "warm-preset"],
                          capture_output=True, text=True, env=environment(toy))
    assert said.returncode != 0
    assert "predates the agent repo" in said.stderr, said.stderr


def test_the_report_the_scripts_read_is_the_one_the_contract_names() -> None:
    """Three files carry the report's path: the prompt a worker reads, the runner that takes it for
    the finished signal, and the import. They agree here or nowhere."""
    prompt = (SKILL / "worker-prompt.md").read_text()
    assert "agent/show/<slug>/report.md" in prompt
    assert 'HEAD:show/$slug/report.md' in (SKILL / "run-worker.sh").read_text()
    assert "reported=show/$id/report.md" in (SKILL / "dispatch").read_text()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
