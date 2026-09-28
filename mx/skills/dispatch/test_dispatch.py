# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "libcst"]
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
argued; this file is the cases the ticket-file move made, and the repo's fuzz run. The fuzz checks
answer to `agent/tickets/fuzz-run-on-integration-branch.md`: P1 a finding survives the run being
stopped, restarted and its worktrees removed; P3 the next run reuses the corpus; P4 a finding reaches
the repo as a committed example and the tracker as a proposed ticket; P6 the project knows nothing
of being fuzzed. Their oracles are the patch Hypothesis wrote in that ticket's prototype, a push
into the host's bare repo, and the database directory outliving what stops and removes the run.
"""

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

SKILL = Path(__file__).parent
DISPATCH = SKILL / "dispatch"
# Read before any check moves HOME: uv keeps its cache under HOME unless told otherwise, and a
# fresh cache puts a full dependency install in front of every tracker and board a check runs.
UV_CACHE = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()

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

# The same stub finishing: its code on the code repo's ticket branch, and its report on
# the agent repo's, which is the worktree at `agent` inside the one it was started in. The report
# being committed there is what says the worker finished.
BUILDING = RUNNER.replace(
    "printf 'attempts=1 exit=0 report=no",
    """git() { command git -c user.email=stub@toy -c user.name=stub -c commit.gpgsign=false "$@"; }
printf 'the lamp, warm\\n' > lamp.txt
git add lamp.txt
git commit -q -m "$slug: the warm preset"
mkdir -p "agent/show/$slug"
cat > "agent/show/$slug/report.md" <<'REPORT'
## Comments

The warm preset lands, unmerged, with one question under it. It meets the ticket's one acceptance
criterion.

- [D1] **Assumptions**
  - A1 `lamp.txt:1`: 2700K, since the bulb box says so.
  - A2 `agent/show/warm-preset/report.md:1`: the report itself, anchored from the worktree root.

## Questions

- [D2] **Warm at what temperature?** 2700K reads amber; 3000K is closer to the old bulb.
REPORT
git -C agent add -A
git -C agent commit -q -m "$slug: the report"
printf 'attempts=1 exit=0 report=yes""",
)

# ssh as the real one behaves: every argument after the host joined with spaces into one line for
# the remote shell, run in the remote user's home. scp copies into that home the same way.
FAKE_SSH = """#!/usr/bin/env bash
while [[ ${1:-} == -* ]]; do case $1 in -o|-p|-i|-l) shift 2 ;; *) shift ;; esac; done
shift
cd "$REMOTE_HOME" && HOME=$REMOTE_HOME exec bash -c "$*"
"""
FAKE_SCP = """#!/usr/bin/env bash
files=(); for a; do [[ $a == -* ]] || files+=("$a"); done
dest=${files[-1]#*:}; [[ $dest == /* ]] || dest=$REMOTE_HOME/$dest
cp "${files[@]:0:${#files[@]}-1}" "$dest"
"""

# The host's claude as a spawn meets it: it records what it was asked, starts on 2.1.243 and its
# updater takes it to 2.1.283, or fails when CLAUDE_UPDATE_FAILS is set. Plugin commands succeed
# and do nothing.
FAKE_CLAUDE = """#!/bin/sh
printf '%s\\n' "$*" >> CALLS
case $1 in
    --version) echo "$(cat CALLS.version 2>/dev/null || echo 2.1.243) (Claude Code)" ;;
    update) [ -z "${CLAUDE_UPDATE_FAILS:-}" ] || { echo "update: network unreachable" >&2; exit 1; }
            echo 2.1.283 > CALLS.version ;;
esac
"""


def git(at: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(at), "-c", "user.email=toy@toy", "-c", "user.name=toy",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout


def ticket(root: Path, slug: str, status: str = "open", parent: str = "", needs_user: bool = False,
           brief: str = "What it is, cold.", hinge: bool = False, blocked_by: str = "") -> Path:
    front = ["---", f"status: {status}"]
    front += [f"parent: {parent}"] if parent else []
    front += [f"blocked-by: [{blocked_by}]"] if blocked_by else []
    front += ["needs-user: true"] if needs_user else []
    front += ["hinge: true"] if hinge else []
    front += ["priority: 1", "size: S", "---"]
    path = root / f"{slug}.md"
    path.write_text("\n".join(front) + f"\n\n# {slug.replace('-', ' ').capitalize()}\n\n## Brief\n\n{brief}\n")
    return path


def tmux_dir(toy: Path) -> Path:
    """The socket directory of this check's own tmux server. A worker's session is named after the
    repo and the slug, the same in every check, so each check runs a server no other check or user
    shares. Under /tmp and short, since a socket path over about a hundred bytes is refused."""
    return Path("/tmp") / f"dispatch-check-{hashlib.sha1(str(toy).encode()).hexdigest()[:12]}"


@pytest.fixture
def toy(tmp_path: Path) -> Iterator[Path]:
    """A project on `main`: a code repo, its `agent/` a repo of its own inside it that the code repo
    ignores, and a tree of two tickets in it. Answers the code repo's root, and takes down the tmux
    server its workers ran on."""
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
    yield repo
    subprocess.run(["tmux", "kill-server"], capture_output=True, env=environment(repo))
    shutil.rmtree(tmux_dir(repo), ignore_errors=True)


def tracked(toy: Path) -> Path:
    """Where this project's ticket files are: the agent repo's, in its main checkout."""
    return toy / "agent" / "tickets"


def environment(toy: Path, **extra: str) -> dict[str, str]:
    """What every command here runs in: a HOME of its own, a `diffview` that records the
    arguments `dispatch review` hands it, since the review page is diffview's and the ranges are
    what dispatch has to get right, and DISPATCH_PLUGIN_DIR at an mx directory of its own, which a
    spawn hands its runner in place of the one the host's claude lists."""
    bin_dir = toy.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "diffview").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{bin_dir / "diffview.args"}"\n'
        'echo "diffview: serving $2 at http://127.0.0.1:1/"\n')
    (bin_dir / "diffview").chmod(0o755)
    (bin_dir / "claude").write_text(FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)
    # The commit hook dispatch installs runs whichever `tracker` is on PATH and passes where there is
    # none, so every host runs the checks against this repo's own.
    (bin_dir / "tracker").write_text(f'#!/bin/sh\nexec "{SKILL.parent / "tracker" / "tracker.py"}" "$@"\n')
    (bin_dir / "tracker").chmod(0o755)
    (toy.parent / "home").mkdir(exist_ok=True)
    plugin = mx(toy.parent)
    tmux_dir(toy).mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(toy.parent / "home"), "UV_CACHE_DIR": UV_CACHE, "GIT_CONFIG_GLOBAL": "/dev/null",
           "JOB_STATE_DIR": str(toy.parent / "jobs"), "TMUX_TMPDIR": str(tmux_dir(toy)),
           "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "DISPATCH_PLUGIN_DIR": str(plugin), **extra}
    env.pop("DISPATCH_PERMISSION_MODE", None)
    env.pop("DISPATCH_EFFORT", None)
    env.pop("TMUX", None)  # names the server of the pane pytest runs in, which beats TMUX_TMPDIR
    return env


def run(toy: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(DISPATCH), *args], cwd=toy, capture_output=True, text=True,
                          env=environment(toy, **extra), timeout=180)


def waited(toy: Path, state: Path | None = None) -> Path:
    """The status line the runner's last act writes, once it is there: a check that carried on
    without it would read a worker that timed out or died as one that finished. `state` is the
    scratch dir, this machine's unless given."""
    state = state or toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    for _ in range(60):
        if list(state.glob("*.status")):
            break
        time.sleep(0.5)
    left = list(state.glob("*.status"))
    assert left, "no status line 30s after the spawn: " + subprocess.run(
        ["tmux", "capture-pane", "-p", "-J", "-t", "=dispatch-lamp-warm-preset"],
        capture_output=True, text=True, env=environment(toy)).stdout
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


def stage_runner(state: Path) -> None:
    """The shipped runner and what it reads beside itself, as `dispatch` stages them on a host."""
    for name in ("run-worker.sh", "worker-prompt.md"):
        shutil.copy(SKILL / name, state / name)
    shutil.copy(SKILL.parent / "run-log" / "run-log", state / "run-log")


def mx(tmp_path: Path) -> Path:
    """The mx install `dispatch-ctl` names to a runner in DISPATCH_PLUGIN_DIR: a directory made here,
    shaped like a real one, whose leaf the lines that name the install print."""
    (tmp_path / "mx" / "installed").mkdir(parents=True, exist_ok=True)
    return tmp_path / "mx" / "installed"


@pytest.fixture
def staged(toy: Path) -> Path:
    """The toy with a stub runner staged in the skill copy dispatch sends to a host."""
    if not shutil.which("tmux"):
        pytest.skip("no tmux here, and a spawn types its runner into a tmux pane")
    skill = toy.parent / "skills"
    (skill / "dispatch").mkdir(parents=True)
    (skill / "tracker").mkdir()
    for name in ("dispatch", "dispatch-ctl", "worker-prompt.md"):
        shutil.copy(SKILL / name, skill / "dispatch" / name)
    for name in ("tracker.py", "pre-commit"):
        shutil.copy(SKILL.parent / "tracker" / name, skill / "tracker" / name)
    (skill / "run-log").mkdir()
    shutil.copy(SKILL.parent / "run-log" / "run-log", skill / "run-log" / "run-log")
    (skill / "dispatch" / "run-worker.sh").write_text(RUNNER)
    return skill / "dispatch" / "dispatch"


def spawn(toy: Path, staged: Path, slug: str, message: str, host: str = "local",
          env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = env or environment(toy)
    subprocess.run([str(staged), "prompt", slug], cwd=toy, input=message, text=True, check=True, env=env)
    return subprocess.run([str(staged), "ctl", "--host", host, "--setup-cmd", "true", "spawn", slug, "sonnet"],
                          cwd=cwd or toy, capture_output=True, text=True, env=env, timeout=180)


def fake_remote(toy: Path, **extra: str) -> tuple[Path, dict[str, str]]:
    """A remote host `agent@far` behind the fake ssh and scp, with a `claude` whose plugin update
    fails as a host's may: its home, and the environment a command reaches it in."""
    remote = toy.parent / "remote"
    remote.mkdir()
    fakes = toy.parent / "fakes"
    fakes.mkdir()
    for name, body in (("ssh", FAKE_SSH), ("scp", FAKE_SCP), ("claude", "#!/bin/sh\nexit 1\n")):
        (fakes / name).write_text(body)
        (fakes / name).chmod(0o755)
    env = environment(toy, REMOTE_HOME=str(remote), **extra)
    env["PATH"] = f"{fakes}:{env['PATH']}"
    return remote, env


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


@pytest.mark.parametrize("fails", [False, True])
def test_a_spawn_brings_claude_current_before_the_worker_starts(toy: Path, staged: Path, fails: bool) -> None:
    """`worker-hosts-run-the-current-claude`: a model alias is whatever the host's claude resolves
    it to, so the updater runs before every worker, and one that fails is said out loud while the
    worker starts on the version the host has, which the spawn names either way."""
    calls = toy.parent / "bin" / "claude.calls"
    (staged.parent / "run-worker.sh").write_text(RUNNER.replace(
        "set -eu\n", f"set -eu\nprintf 'worker starts\\n' >> {calls}\n"))
    run(toy, "claim", "warm-preset")

    said = spawn(toy, staged, "warm-preset", "Work it.\n",
                 env=environment(toy, **({"CLAUDE_UPDATE_FAILS": "1"} if fails else {})))
    waited(toy)

    assert said.returncode == 0, said.stderr
    asked = calls.read_text().splitlines()
    assert asked.index("update") < asked.index("worker starts")
    assert f"claude={'2.1.243' if fails else '2.1.283'}" in said.stdout, said.stdout
    assert ("claude update failed" in said.stderr) == fails, said.stderr


def test_the_effort_a_spawn_names_reaches_the_runner_high_unless_given(toy: Path, staged: Path) -> None:
    """`model-effort-defaults`: the worker's effort is set where its model is, at the spawn, `high`
    when the orchestrator says nothing, and it reaches the runner with the permission mode."""
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    def logs() -> str:
        return "".join(p.read_text() for p in state.glob("*.log"))
    (staged.parent / "run-worker.sh").write_text(RUNNER.replace(
        "printf 'stub: built %s\\n' \"$slug\"", "printf 'stub: built %s at %s\\n' \"$slug\" \"${DISPATCH_EFFORT:-unset}\""))
    run(toy, "claim", "warm-preset")
    env = environment(toy)
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)

    said = subprocess.run([str(staged), "ctl", "--host", "local", "--setup-cmd", "true", "spawn", "warm-preset", "sonnet"],
                          cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    waited(toy)
    assert said.returncode == 0, said.stderr
    assert "model=sonnet  effort=high" in said.stdout, said.stdout
    assert "stub: built warm-preset at high" in logs()

    said = subprocess.run([str(staged), "ctl", "spawn", "warm-preset", "sonnet", "--effort", "low"],
                          cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    for _ in range(60):
        if "at low" in logs():
            break
        time.sleep(0.5)
    assert said.returncode == 0, said.stderr
    assert "effort=low" in said.stdout, said.stdout
    assert "stub: built warm-preset at low" in logs()


def test_a_spawn_hands_the_runner_the_hosts_mx_install(toy: Path, staged: Path) -> None:
    """`unattended-launch`: a worker reads no user settings, so the mx its contract names skills from
    reaches it by path, and the path travels on the line the spawn types into the pane. The spawn
    names the install it gave."""
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    (staged.parent / "run-worker.sh").write_text(RUNNER.replace(
        "printf 'stub: built %s\\n' \"$slug\"", "printf 'stub: built %s with %s\\n' \"$slug\" \"${DISPATCH_PLUGIN_DIR:-unset}\""))
    run(toy, "claim", "warm-preset")
    plugin = mx(toy.parent)

    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    waited(toy)

    assert said.returncode == 0, said.stderr
    assert f"mx={plugin.name}" in said.stdout, said.stdout
    assert f"stub: built warm-preset with {plugin}\n" in "".join(p.read_text() for p in state.glob("*.log"))


def test_a_host_whose_claude_lists_no_mx_starts_no_worker(toy: Path, staged: Path) -> None:
    """Without the plugin a worker has none of the skills its contract names, so a spawn on a host
    whose claude lists no user-scope mx stops before the pane, once, rather than in every run."""
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    run(toy, "claim", "warm-preset")
    env = environment(toy)
    env.pop("DISPATCH_PLUGIN_DIR")

    said = spawn(toy, staged, "warm-preset", "Work it.\n", env=env)

    assert said.returncode != 0
    assert "no mx plugin for dispatch-lamp-warm-preset" in said.stderr, said.stderr
    assert not list(state.glob("dispatch-lamp-warm-preset-*.log")), "a worker started without the plugin"


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
    """One ticket end to end: claim, spawn, the report, the import, a question ruled before the
    merge, and the landing with the range the ticket keeps.

    `ticket-file-contract#P7`: nothing the worker did touched a ticket file, and every word it wrote
    for the user is in the tracker's own copy by the time the build waits for a ruling."""
    tracker = SKILL.parent / "tracker" / "tracker.py"
    agent = toy / "agent"
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    assert "report=yes" in waited(toy).read_text(), "the runner reads the report it committed"
    assert git(toy, "diff", "--name-only", "main", "ticket/warm-preset").split() == ["lamp.txt"]
    assert git(agent, "diff", "--name-only", "main", "ticket/warm-preset").split() == [
        "show/warm-preset/report.md"], "the agent branch carries the report, and no ticket file"

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr

    written = (tracked(toy) / "warm-preset.md").read_text()
    assert status_of(toy, "warm-preset") == "review"
    assert "The warm preset lands, unmerged" in written and "**Warm at what temperature?**" in written
    assert "warm-preset for review" in git(agent, "log", "-1", "--format=%s")
    notes = json.loads((agent / "diffviews" / "warm-preset.notes.json").read_text())
    # a worker anchors from its worktree root, and the agent repo is rendered from its own root
    assert [(one["id"], one["path"], one["line"]) for one in notes["notes"]] == [
        (1, "lamp.txt", 1), (2, "show/warm-preset/report.md", 1)]

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


# The building stub as a tree's children run it: each commits a file of its own, so a child built on
# a sibling's merge carries that sibling's file and adds its own beside it.
BUILDING_ITS_OWN = BUILDING.replace(
    "printf 'the lamp, warm\\n' > lamp.txt\ngit add lamp.txt",
    "printf '%s\\n' \"$slug\" > \"$slug.txt\"\ngit add \"$slug.txt\"",
)


def test_a_parent_ruled_whole_lands_its_tree_on_its_accept(toy: Path, staged: Path) -> None:
    """`speculative-first`'s review unit through the toy: a hinge ruled alone, then two leaves, the
    second built on the first while the first waits unruled in its parent's branch, and the
    parent's accept writing `done` on all four. `speculative-first#P1`: nothing reaches `main`
    before the parent's accept."""
    tickets, agent = tracked(toy), toy / "agent"
    ticket(tickets, "preset-format", parent="lamp-ui", hinge=True, brief="The shape every preset is stored in.")
    ticket(tickets, "cool-preset", parent="lamp-ui", blocked_by="warm-preset", brief="One preset, cool.")
    ticket(tickets, "warm-preset", parent="lamp-ui", blocked_by="preset-format", brief="One preset, warm.")
    git(agent, "add", "-A")
    git(agent, "commit", "-q", "-m", "the tree")
    (staged.parent / "run-worker.sh").write_text(BUILDING_ITS_OWN)
    worktree = toy.parent / "lamp-lamp-ui"
    git(toy, "worktree", "add", "-q", str(worktree), "-b", "lamp-ui")
    assert run(worktree, "claim", "lamp-ui").returncode == 0
    main = git(toy, "rev-parse", "main").strip()
    env = environment(toy)
    def frontier(held: bool = False) -> str:
        """The frontier's ready lines, or with `held` its waiting ones."""
        said = subprocess.run([str(staged.parent.parent / "tracker" / "tracker.py"), "frontier"], cwd=worktree,
                              capture_output=True, text=True, env=env)
        assert said.returncode == 0, said.stderr
        return said.stdout.partition("waiting\n")[2 if held else 0]

    def built(slug: str) -> None:
        assert run(worktree, "claim", slug).returncode == 0
        subprocess.run([str(staged), "prompt", slug], cwd=worktree, input=f"Work {slug}.\n", text=True, check=True, env=env)
        spawned = subprocess.run([str(staged), "ctl", "--host", "local", "--setup-cmd", "true", "spawn", slug, "sonnet"],
                                 cwd=worktree, capture_output=True, text=True, env=env, timeout=180)
        assert spawned.returncode == 0, spawned.stderr
        assert run(worktree, "wait", slug, "--deadline", "60").returncode == 0
        assert run(worktree, "fetch", slug).returncode == 0
        said = run(worktree, "review", slug)
        assert said.returncode == 0, said.stderr
        assert status_of(toy, slug) == "review"

    def merged(slug: str) -> None:
        git(worktree, "merge", "-q", "--no-ff", "-m", f"{slug}: merged", f"ticket/{slug}")
        git(agent, "merge", "-q", "--no-ff", "-m", f"{slug}: merged", f"ticket/{slug}")
        said = run(worktree, "review", slug)
        assert said.returncode == 0, said.stderr

    assert "warm-preset" not in frontier()
    built("preset-format")
    assert "warm-preset" not in frontier(), "a hinge in review holds its dependents"
    assert "on preset-format (review, a hinge)" in frontier(held=True)
    merged("preset-format")  # the user's accept of the hinge, ruled alone
    assert status_of(toy, "preset-format") == "done"

    assert "warm-preset" in frontier()
    built("warm-preset")
    assert "cool-preset" not in frontier(), "unmerged, the leaf holds its sibling"
    merged("warm-preset")  # the orchestrator's read passed it, and the user has not ruled
    assert status_of(toy, "warm-preset") == "review", "ruled with its parent, not alone"
    assert "diff: [code@" in (tickets / "warm-preset.md").read_text(), "its ranges are final once merged"

    assert "cool-preset" in frontier(), "a merged leaf in review unblocks its sibling"
    built("cool-preset")
    assert git(toy, "show", "ticket/cool-preset:warm-preset.txt") == "warm-preset\n", "built on the unruled sibling"
    merged("cool-preset")
    assert status_of(toy, "cool-preset") == "review"
    assert git(toy, "rev-parse", "main").strip() == main, "nothing reached the branch above the parent"

    early = run(toy, "accept", "lamp-ui")
    assert early.returncode != 0 and "not merged into main" in early.stderr, early.stderr
    subprocess.run([str(staged.parent.parent / "tracker" / "tracker.py"), "set", "lamp-ui", "status=review"],
                   cwd=toy, check=True, capture_output=True, env=env)  # its close-out: the whole tree waits for the ruling
    git(agent, "commit", "-q", "-am", "lamp-ui for review")
    git(toy, "merge", "-q", "--no-ff", "-m", "lamp-ui: accepted whole", "lamp-ui")

    # a ticket file of the tree edited and not committed: refused, and the edit kept
    parent = tickets / "lamp-ui.md"
    parent.write_text(parent.read_text() + "\nA note not committed yet.\n")
    dirty = run(toy, "accept", "lamp-ui")
    assert dirty.returncode != 0 and "uncommitted changes" in dirty.stderr, dirty.stderr
    assert parent.read_text().endswith("A note not committed yet.\n")
    git(agent, "checkout", "-q", "--", "tickets/lamp-ui.md")
    # a child in review the orchestrator never merged: the tracker refuses it, and none is written
    ticket(tickets, "dim-preset", status="review", parent="lamp-ui")
    git(agent, "add", "tickets/dim-preset.md")
    git(agent, "commit", "-q", "-m", "dim-preset for review")
    dim = git(toy, "commit-tree", "lamp-ui^{tree}", "-p", "lamp-ui", "-m", "dim-preset: built").strip()
    git(toy, "branch", "ticket/dim-preset", dim)
    before = {path.name: path.read_text() for path in tickets.glob("*.md")}
    partial = run(toy, "accept", "lamp-ui")
    assert partial.returncode != 0 and "dim-preset" in partial.stderr, partial.stderr
    assert {path.name: path.read_text() for path in tickets.glob("*.md")} == before
    assert not git(agent, "status", "--porcelain", "--", "tickets")
    git(agent, "rm", "-q", "tickets/dim-preset.md")
    git(agent, "commit", "-q", "-m", "dim-preset dropped")

    accepted = run(toy, "accept", "lamp-ui")
    assert accepted.returncode == 0, accepted.stderr
    assert f"code@{main}..{git(toy, 'rev-parse', 'lamp-ui').strip()}" in parent.read_text(), "the parent's range"
    assert {slug: status_of(toy, slug) for slug in ("lamp-ui", "preset-format", "warm-preset", "cool-preset")} == dict.fromkeys(
        ("lamp-ui", "preset-format", "warm-preset", "cool-preset"), "done")
    assert "lamp-ui landed" in git(agent, "log", "-1", "--format=%s")
    assert not git(agent, "status", "--porcelain", "--", "tickets"), "one commit carries the tree"


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


def test_a_resumed_round_that_wrote_no_report_imports_the_round_before_it_nowhere(
    toy: Path, staged: Path
) -> None:
    """Every round after the first starts with the round before it still committed on the agent
    branch. What is imported is the report a round wrote, so a resume that left none brings nothing
    in: the first round's closing comment would otherwise land under `## Comments` twice, and its
    question's tag be refused as taken."""
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    assert "report=yes" in waited(toy).read_text()
    assert run(toy, "fetch", "warm-preset").returncode == 0
    assert run(toy, "review", "warm-preset").returncode == 0
    once = (tracked(toy) / "warm-preset.md").read_text()
    assert once.count("The warm preset lands, unmerged") == 1
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    before = set(state.glob("*.status"))

    # the round the user sent back, resumed on a worker that stops before writing one of its own,
    # from a runner outside the scratch dir: the resume copies it in, beside the log and status
    # line a run writes.
    quiet = toy.parent / "quiet-runner.sh"
    quiet.write_text(RUNNER)
    resumed = subprocess.run([str(staged), "ctl", "--host", "local", "resume", "warm-preset", "sonnet"],
                             cwd=toy, capture_output=True, text=True, timeout=180,
                             env=environment(toy, DISPATCH_RUNNER=str(quiet)))
    assert resumed.returncode == 0, resumed.stderr
    assert status_of(toy, "warm-preset") == "claimed", "a resumed build holds its ticket again"
    for _ in range(60):
        if fresh := set(state.glob("*.status")) - before:
            break
        time.sleep(0.5)
    assert fresh, "no status line 30s after the resume"

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert "left none of its own to import" in said.stderr, said.stderr
    assert (tracked(toy) / "warm-preset.md").read_text() == once, "nothing of the first round said twice"


def test_a_ticket_file_written_on_an_agent_branch_stops_the_import(toy: Path, staged: Path) -> None:
    """`ticket-file-contract#P7` where the orchestrator reads the branch: a worker that wrote a
    ticket file wrote a second copy of one, and nothing of that round is imported. That read is the
    line for an agent repo whose commit hook is its owner's; the tracker's own hook refuses the
    commit first (`test_tracker.py`, `test_a_ticket_branch_is_refused_the_ticket_file_it_staged`)."""
    (toy / "agent" / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
    (toy / "agent" / ".git" / "hooks" / "pre-commit").chmod(0o755)
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


@pytest.mark.parametrize("already, wrote, exits, says", [
    (False, True, 1, "attempts=1 exit=1 report=yes"),
    (False, False, 0, "attempts=1 exit=0 report=no"),
    (True, False, 0, "attempts=1 exit=0 report=no"),
    (True, True, 0, "attempts=1 exit=0 report=yes"),
])
def test_the_runner_reads_the_report_as_the_run_leaving_something_to_review(
    tmp_path: Path, already: bool, wrote: bool, exits: int, says: str
) -> None:
    """The shipped runner, with `claude` stubbed rather than the runner itself: a run whose worker
    committed its report in the agent repo is finished whatever it exited with, one that committed
    none says so on its status line, and the retry loop ends either way.

    A resumed round starts with the round before it still committed there, so what the status line
    reads is whether this run wrote that file, never whether the file is there."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work the ticket warm-preset.\n")
    worktree = tmp_path / "lamp-warm-preset"
    (worktree / "agent").mkdir(parents=True)
    git(worktree / "agent", "init", "-q", "-b", "ticket/warm-preset", ".")
    (worktree / "agent" / "README.md").write_text("the agent repo\n")
    git(worktree / "agent", "add", "-A")
    git(worktree / "agent", "commit", "-q", "-m", "the agent repo")
    if already:
        (worktree / "agent" / "show" / "warm-preset").mkdir(parents=True)
        (worktree / "agent" / "show" / "warm-preset" / "report.md").write_text(
            "## Comments\n\nthe round before, which the user sent back.\n")
        git(worktree / "agent", "add", "-A")
        git(worktree / "agent", "commit", "-q", "-m", "the round before's report")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    committing = (
        'mkdir -p agent/show/warm-preset\n'
        'printf "## Comments\\n\\nit lands.\\n" > agent/show/warm-preset/report.md\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false add -A\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -q -m report\n'
    )
    (bin_dir / "claude").write_text(
        '#!/bin/sh\n[ "$1" = --version ] && exit 0\n' + (committing if wrote else "") + f"exit {exits}\n")
    (bin_dir / "claude").chmod(0o755)

    done = subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet", "run-1"],
        cwd=worktree, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))},
    )
    assert done.returncode == 0, done.stderr
    assert (state / "run-1.status").read_text().startswith(says), (state / "run-1.status").read_text()
    assert "runner: started warm-preset" in (state / "run-1.log").read_text()


@pytest.mark.parametrize("given", ["", "low"])
def test_the_runner_passes_an_effort_to_every_attempt_high_unless_told(tmp_path: Path, given: str) -> None:
    """`model-effort-defaults`: every `claude` a worker runs on names its effort, so no worker runs
    at whatever the host's settings say; DISPATCH_EFFORT is how the spawn sets it."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))}
    env.pop("DISPATCH_EFFORT", None)
    if given:
        env["DISPATCH_EFFORT"] = given

    subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-1"],
                   cwd=tmp_path, capture_output=True, text=True, timeout=120, env=env)

    attempts = [line for line in (bin_dir / "claude.calls").read_text().splitlines() if line.startswith("-p ")]
    assert attempts and all(f"--model opus --effort {given or 'high'} " in line for line in attempts), attempts
    assert f"on opus at {given or 'high'} effort" in (state / "run-1.log").read_text().splitlines()[0]
    # `run-log`: the attempt left its line, in the log this HOME defaults to
    (logged,) = [json.loads(l) for l in (tmp_path / "logs" / "agent" / "runs.jsonl").read_text().splitlines()]
    assert (logged["site"], logged["ticket"], logged["attempt"], logged["model"], logged["effort"]) == \
        ("worker", "warm-preset", 1, "opus", given or "high")


def test_a_worker_inherits_the_projects_settings_and_the_hosts_mx_and_nothing_else(tmp_path: Path) -> None:
    """`unattended-launch`, as ruled on 2026-09-26: a worker keeps the project's settings and
    CLAUDE.md and the mx plugin the host's claude has installed, and none of the user's settings,
    CLAUDE.md, output style or hooks, no MCP server, and no auto memory. The worklog's first line
    names the mx install it runs."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)
    plugin = mx(tmp_path)

    subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-1"],
                   cwd=tmp_path, capture_output=True, text=True, timeout=120,
                   env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))})

    attempts = [line for line in (bin_dir / "claude.calls").read_text().splitlines() if line.startswith("-p ")]
    inherits = ("--setting-sources project", "--strict-mcp-config", f"--plugin-dir {plugin}",
                '--settings {"autoMemoryEnabled": false}')
    assert attempts and all(flag in line for line in attempts for flag in inherits), attempts
    assert not any("claudeMdExcludes" in line or "outputStyle" in line for line in attempts), attempts
    assert f" and mx {plugin.name} (run-1)" in (state / "run-1.log").read_text().splitlines()[0]


def test_a_runner_given_no_plugin_dir_starts_no_worker(tmp_path: Path) -> None:
    """A worker without the plugin has none of the skills its contract names, so a runner started
    without DISPATCH_PLUGIN_DIR says so on the status line rather than start one."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)

    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)}
    env.pop("DISPATCH_PLUGIN_DIR", None)  # whatever the shell running these checks carries

    done = subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-1"],
                          cwd=tmp_path, capture_output=True, text=True, timeout=60, env=env)

    assert done.returncode == 1
    assert (state / "run-1.status").read_text().startswith(
        "attempts=0 exit=1 report=no session=- error=DISPATCH_PLUGIN_DIR unset")
    assert not (bin_dir / "claude.calls").exists(), "claude ran"


def test_a_worker_runs_under_its_run_id_whatever_run_spawned_it(tmp_path: Path) -> None:
    """`browsers-a-worker-can-kill`: MX_RUN is what the browsers a worker's checks launch are
    tagged with, so it names this run and not the one the orchestrator's shell was in."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    seen = tmp_path / "mx-run"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(f'#!/bin/sh\n[ "$1" = --version ] && exit 0\necho "$MX_RUN" >> {seen}\n')
    (bin_dir / "claude").chmod(0o755)

    subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-7"],
                   cwd=tmp_path, capture_output=True, text=True, timeout=120,
                   env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path),
                        "DISPATCH_PLUGIN_DIR": str(mx(tmp_path)), "MX_RUN": "the-orchestrators"})

    assert seen.read_text().splitlines() == ["run-7"]


@pytest.mark.parametrize("resumed", [False, True])
def test_the_status_line_names_the_models_the_worker_ran_on(tmp_path: Path, resumed: bool) -> None:
    """`worker-hosts-run-the-current-claude`: `opus` on the command line says nothing about what
    answered, so the status line reads it off the session's transcript: the models this round's
    assistant turns carry, none of the rounds' before it on a resumed session, and none of the
    strings a turn merely mentions (an Agent call's `model` input) or claude's own `<synthetic>`
    error turns. The worklog's first line names the launcher's version."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    session = "5e55-10n"
    project = tmp_path / "profile" / "projects" / "-toy"
    project.mkdir(parents=True)
    if resumed:
        (project / f"{session}.jsonl").write_text(
            json.dumps({"type": "assistant", "message": {"model": "claude-opus-5", "content": "a round"}}) + "\n")
    turns = [
        {"type": "user", "message": {"role": "user", "content": "Work it."}},
        {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": [
            {"type": "tool_use", "name": "Agent", "input": {"model": "sonnet", "prompt": "review"}}]}},
        {"type": "assistant", "message": {"model": "<synthetic>", "content": "API Error"}},
        {"type": "assistant", "message": {"model": "claude-sonnet-5", "content": "done"}},
    ]
    transcript = "\n".join(json.dumps(turn) for turn in turns)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(
        '#!/usr/bin/env bash\n[ "$1" = --version ] && { echo "2.1.283 (Claude Code)"; exit 0; }\n'
        'while [ "$1" != --session-id ] && [ "$1" != --resume ]; do shift; done\n'
        f'cat >> "{project}/$2.jsonl" <<\'T\'\n{transcript}\nT\n')
    (bin_dir / "claude").chmod(0o755)

    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path)),
           "CLAUDE_CONFIG_DIR": str(tmp_path / "profile")}
    env.pop("DISPATCH_EFFORT", None)  # whatever the shell running these checks carries
    subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-1",
         *([session] if resumed else [])],
        cwd=tmp_path, capture_output=True, text=True, timeout=120, env=env,
    )
    status = (state / "run-1.status").read_text()
    assert status.split()[-1] == "models=claude-opus-5-5,claude-sonnet-5", status
    assert "on opus at high effort with claude 2.1.283" in (state / "run-1.log").read_text().splitlines()[0]


def test_what_a_worker_leaves_running_ends_with_its_attempt(tmp_path: Path) -> None:
    """A worker whose shell was killed before its cleanup line leaves its children behind, and a
    child that detached itself escapes even the process group `dispatch-ctl stop` signals. The
    runner's scope is what takes both down, on a host with a user systemd manager."""
    probe = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect", "--", "true"],
                           capture_output=True) if shutil.which("systemd-run") else None
    if probe is None or probe.returncode != 0:
        pytest.skip("no user systemd manager here, and the runner says so in the worklog instead")
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    left = tmp_path / "left.pid"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # The runner asks `claude --version` first, outside any attempt; only the attempt leaves a child.
    (bin_dir / "claude").write_text(
        f'#!/bin/sh\n[ "$1" = --version ] && exit 0\nsetsid sleep 3600 > /dev/null 2>&1 &\necho $! > {left}\nexit 0\n')
    (bin_dir / "claude").chmod(0o755)

    subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet",
         f"check-{tmp_path.name}"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))},
    )
    pid = left.read_text().strip()
    for _ in range(20):
        if not Path(f"/proc/{pid}").exists():
            break
        time.sleep(0.25)
    else:
        subprocess.run(["kill", pid])
        pytest.fail(f"the worker's detached sleep (pid {pid}) outlived the run")


def test_a_worktree_with_no_agent_repo_says_so_in_the_worklog(tmp_path: Path) -> None:
    """Without that repo the worker has nowhere to commit a report, so every attempt would end in
    `report=no` with nothing saying why."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "claude").chmod(0o755)

    subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet", "run-1"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))},
    )
    assert "no agent repo at" in (state / "run-1.log").read_text()
    assert "report=no" in (state / "run-1.status").read_text()


def test_a_runner_staged_without_run_log_refuses_to_start(tmp_path: Path) -> None:
    """Every attempt runs through run-log, so a staging that lacks it is said on the status line
    rather than run unlogged."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (state / "run-log").unlink()
    (tmp_path / "message.md").write_text("Work it.\n")
    done = subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "sonnet", "run-1"],
                          cwd=tmp_path, capture_output=True, text=True, timeout=60, env={**os.environ, "HOME": str(tmp_path)})
    assert done.returncode == 1
    assert (state / "run-1.status").read_text().startswith("attempts=0 exit=1 report=no session=- error=no run-log beside run-worker.sh")


def test_a_hosts_run_log_lines_come_back_on_a_fetch_and_a_cleanup_and_a_local_host_has_none_to_pull(toy: Path, staged: Path) -> None:
    """`run-log`: a worker host's lines reach this machine's log when its ticket is fetched or
    cleaned up, each once; a pull that fails is said and stops nothing; a local host writes this
    machine's log itself."""
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    theirs = remote / "logs" / "agent" / "runs.jsonl"
    theirs.parent.mkdir(parents=True)
    theirs.write_text('{"id": "r1", "at": "2026-09-27T10:00:00Z", "site": "worker"}\n{"id": "r2", "at": "2026-09-27T10:05:00Z", "site": "review"}\n')
    mine = toy.parent / "home" / "logs" / "agent" / "runs.jsonl"

    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    assert "pulled 2 new run(s) from agent@far" in fetched.stdout
    assert [json.loads(l)["id"] for l in mine.read_text().splitlines()] == ["r1", "r2"]

    theirs.write_text(theirs.read_text() + '{"id": "r3", "at": "2026-09-27T10:09:00Z", "site": "worker"}\n')
    cleaned = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert "pulled 1 new run(s)" in cleaned.stdout
    assert [json.loads(l)["id"] for l in mine.read_text().splitlines()] == ["r1", "r2", "r3"]

    # the host's log unreadable: the fetch still lands, and says the pull is to try again
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    theirs.unlink()
    theirs.mkdir()
    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    assert "could not be pulled; run-log pull agent@far tries again" in fetched.stderr
    subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)


def test_a_local_host_writes_this_machines_log_itself_so_a_fetch_pulls_nothing(toy: Path, staged: Path) -> None:
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)
    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True, env=environment(toy), timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    assert "pulled" not in fetched.stdout + fetched.stderr


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


def test_the_report_the_contract_names_is_the_one_the_scripts_read() -> None:
    """The worker reads the path out of prose, which no check of the runner or the import can
    exercise; the two scripts are held to it by the runs above."""
    assert "agent/show/<slug>/report.md" in (SKILL / "worker-prompt.md").read_text()


def test_the_first_spawn_on_a_remote_host_stages_it_whole(toy: Path, staged: Path) -> None:
    """The first spawn on a remote host passes `dispatch-ctl init` empty arguments for the host's
    own defaults; each has to arrive as the argument it was, or the agent repo's branch lands in
    the code repo's slot and no ticket branch can be cut. The agent repo is on a branch of its own
    name, as a project's is."""
    git(toy / "agent", "branch", "-m", "plans")
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")

    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)

    assert said.returncode == 0, said.stdout + said.stderr
    config = dict(line.split("=", 1) for line in
                  (remote / ".local" / "state" / "dispatch" / "lamp-main" / "config").read_text().splitlines())
    assert config["git"] == f"{remote}/repos/dispatch/lamp.git"
    assert config["agent"] == f"{remote}/repos/dispatch/lamp-agent.git"
    assert config["agentbase"] == "plans"
    worktree = remote / "repos" / "dispatch" / "lamp-warm-preset"
    assert git(worktree, "branch", "--show-current").strip() == "ticket/warm-preset"
    assert git(worktree / "agent", "branch", "--show-current").strip() == "ticket/warm-preset"


def test_a_remote_hosts_agent_repo_gets_the_trackers_commit_hook(toy: Path, staged: Path) -> None:
    """`report-checked-before-commit`: a worker commits its report in the host's agent repo, and
    that repo's commit hook refuses a report the import would."""
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)
    assert said.returncode == 0, said.stdout + said.stderr
    installed = remote / "repos" / "dispatch" / "lamp-agent.git" / "hooks" / "pre-commit"
    assert installed.read_text() == (SKILL.parent / "tracker" / "pre-commit").read_text()
    assert os.access(installed, os.X_OK)


def test_a_commit_hook_the_agent_repo_already_has_is_its_owners(toy: Path, staged: Path) -> None:
    """On a local host the agent repo is the user's own checkout, and a hook in it stays as it was."""
    theirs = toy / "agent" / ".git" / "hooks" / "pre-commit"
    theirs.write_text("#!/bin/sh\nexit 0\n")
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode == 0, said.stdout + said.stderr
    assert theirs.read_text() == "#!/bin/sh\nexit 0\n"
    assert "is not the tracker's" in said.stderr, said.stderr


def test_dispatch_ctl_help_needs_no_repo(tmp_path: Path) -> None:
    """`dispatch --help` names `dispatch ctl --help` as dispatch-ctl's reference, and the skill
    renders it on load wherever the session is."""
    first = (SKILL / "dispatch-ctl").read_text().splitlines()[1].removeprefix("# ")
    for args in (["ctl", "--help"], ["ctl"]):
        said = subprocess.run([str(DISPATCH), *args], cwd=tmp_path, capture_output=True, text=True)
        assert said.returncode == 0, said.stderr
        assert said.stdout.startswith(first), said.stdout


def test_a_remote_spawn_runs_the_runner_it_was_given(toy: Path, staged: Path) -> None:
    """DISPATCH_RUNNER set on the orchestrator reaches a remote host and is the one its worker runs.
    It is renamed after the ticket whatever its own name: this one is called `manifest`, the file
    on the host that records every run. Given relative to a subdirectory the spawn runs in, which
    dispatch leaves for the repo's root before it reads anything."""
    (toy / "docs").mkdir()
    (toy.parent / "runners").mkdir()
    (toy.parent / "runners" / "manifest").write_text(RUNNER.replace("stub: built", "replacement: built"))
    remote, env = fake_remote(toy, DISPATCH_RUNNER="../../runners/manifest")
    run(toy, "claim", "warm-preset")

    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env, cwd=toy / "docs")

    assert said.returncode == 0, said.stdout + said.stderr
    state = remote / ".local" / "state" / "dispatch" / "lamp-main"
    waited(toy, state)
    (log,) = state.glob("dispatch-lamp-warm-preset-*.log")
    assert "replacement: built warm-preset" in log.read_text()
    record = (state / "manifest").read_text().split("\t")
    assert record[0] == "dispatch-lamp-warm-preset", record
    assert record[-1].strip() == f"{state}/runner-warm-preset", record


def test_a_resume_given_no_runner_runs_the_one_the_run_was_spawned_on(toy: Path, staged: Path) -> None:
    """A resume hands the worker its old session id, which only the harness that made it knows."""
    replacement = toy.parent / "replacement.sh"
    replacement.write_text(RUNNER.replace("printf 'stub: built %s\\n' \"$slug\"", "printf 'replacement: built %s at %s\\n' \"$slug\" \"${DISPATCH_EFFORT:-unset}\""))
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n",
                 env=environment(toy, DISPATCH_RUNNER=str(replacement))).returncode == 0
    state = waited(toy).parent
    before = set(state.glob("*.log"))

    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="continue\n", text=True, check=True,
                   env=environment(toy))
    resumed = subprocess.run([str(staged), "ctl", "--host", "local", "resume", "warm-preset", "sonnet", "--effort", "low"],
                             cwd=toy, capture_output=True, text=True, timeout=180, env=environment(toy))
    assert resumed.returncode == 0, resumed.stderr
    assert "effort=low" in resumed.stdout, resumed.stdout
    (log,) = set(state.glob("*.log")) - before
    for _ in range(60):
        if "at low" in log.read_text():
            break
        time.sleep(0.5)
    assert "replacement: built warm-preset at low" in log.read_text(), "a resume takes --effort as a spawn does"


def test_a_runner_that_is_no_file_stops_the_spawn_before_the_host_is_touched(toy: Path, staged: Path) -> None:
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n",
                 env=environment(toy, DISPATCH_RUNNER="no-such-runner.sh"))
    assert said.returncode != 0
    assert "no-such-runner.sh is not a file" in said.stderr, said.stderr
    assert not (toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").exists()


# --- the repo's fuzz run -------------------------------------------------------------------------
#
# The toy as a project with properties and bugs under them. One is the prototype's
# (`agent/prototypes/fuzz-lifecycle`): `zzz` does not survive the round trip. The other fails on
# any integer from 1000 up, and sorts first, so two findings are read out of one suite run. Its
# `make fuzz` is the plain loop a work repo runs, so the run ends on its findings. Its default
# Hypothesis profile only replays the database, so the ordinary suite fails exactly when the
# database holds a finding. Nothing in it knows dispatch (P6).

LAB = '''def encode(s: str) -> str:
    # Planted bug: a run of three or more 'z' is mangled.
    if "zzz" in s:
        return s.replace("zzz", "zz")
    return s

def decode(s: str) -> str:
    return s
'''
PROPERTY = '''from hypothesis import given, strategies as st
from lab import decode, encode

@given(st.text(alphabet="az", min_size=0, max_size=12))
def test_roundtrip(s):
    assert decode(encode(s)) == s

@given(st.integers())
def test_fine(n):
    assert n + 0 == n
'''
BOUND = '''from hypothesis import given, strategies as st

@given(st.integers())
def test_small(n):
    assert n < 1000
'''
CONFTEST = '''import os
from hypothesis import Phase, settings
settings.register_profile("fuzz", max_examples=5000, deadline=None)
settings.register_profile("replay", phases=[Phase.explicit, Phase.reuse, Phase.shrink])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "replay"))
'''
MAKEFILE = '''PY ?= python
install:
\t@true
test:
\t$(PY) -m pytest -q -p no:cacheprovider tests
fuzz:
\twhile HYPOTHESIS_PROFILE=fuzz $(PY) -m pytest -q -p no:cacheprovider tests/properties; do :; done
'''
# The patch Hypothesis wrote in the prototype's run, `hypothesis-wrote-this.patch` there: what
# `fuzz patch` applies, whatever layout the Hypothesis of the day gives its `@example`.
PROTOTYPE_PATCH = '''--- ./tests/properties/test_roundtrip.py
+++ ./tests/properties/test_roundtrip.py
@@ -2,6 +2,7 @@
 from lab import decode, encode
 
 @given(st.text(alphabet="az", min_size=0, max_size=12))
+@example(s="zzz").via("discovered failure")
 def test_roundtrip(s):
     assert decode(encode(s)) == s
 
'''
NODE = "tests/properties/test_roundtrip.py::test_roundtrip"
FINDING = "fuzz-tests-properties-test-roundtrip-test-roundtrip"
BOUND_NODE = "tests/properties/test_bound.py::test_small"
BOUND_FINDING = "fuzz-tests-properties-test-bound-test-small"


@pytest.fixture
def fuzzable(toy: Path) -> Path:
    """The toy with the two properties and their bugs committed on `main`."""
    if not shutil.which("tmux"):
        pytest.skip("no tmux here, and the fuzz run is a job in a tmux session")
    for path, text in (("lab/__init__.py", LAB), ("tests/properties/test_roundtrip.py", PROPERTY),
                       ("tests/properties/test_bound.py", BOUND), ("tests/conftest.py", CONFTEST),
                       ("Makefile", MAKEFILE)):
        (toy / path).parent.mkdir(parents=True, exist_ok=True)
        (toy / path).write_text(text)
    git(toy, "add", "-A")
    git(toy, "commit", "-q", "-m", "properties, and bugs under them")
    return toy


def mend(toy: Path) -> None:
    """Both bugs fixed on `main`, so a run on it fuzzes until it is stopped."""
    (toy / "lab" / "__init__.py").write_text(LAB.replace('s.replace("zzz", "zz")', "s"))
    (toy / "tests" / "properties" / "test_bound.py").write_text(BOUND.replace("n < 1000", "n + 0 == n"))
    git(toy, "commit", "-q", "-am", "the round trip keeps zzz, and no bound")


def fuzz(toy: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """`dispatch fuzz`. The toy's suite runs on this interpreter, which is why the checks take
    Hypothesis, and libcst, without which Hypothesis writes no patch."""
    env = {**(env or environment(toy)), "PY": sys.executable}
    return subprocess.run([str(DISPATCH), "fuzz", *args], cwd=toy, capture_output=True, text=True,
                          env=env, timeout=180)


def fuzz_job(toy: Path) -> Path:
    return toy.parent / "jobs" / "fuzz-lamp"


def fuzz_ended(toy: Path) -> str:
    """The fuzz job's status line, once it has ended."""
    job = fuzz_job(toy)
    for _ in range(120):
        if (job / "status").exists():
            return (job / "status").read_text()
        time.sleep(0.5)
    log = (job / "log").read_text() if (job / "log").exists() else "(no log)"
    raise AssertionError(f"the fuzz job never ended; its log:\n{log}")


def fuzz_pid(toy: Path) -> str:
    return (fuzz_job(toy) / "meta").read_text().split("pid=")[1].split("\n")[0]


def local_scratch(toy: Path) -> Path:
    return toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"


def examples(db: Path) -> set[Path]:
    return {p.relative_to(db) for p in (db / "examples").rglob("*") if p.is_file()}


def read_out(check: str) -> dict[str, str]:
    """`fuzz check`'s findings: each node id with the case printed under it."""
    cases: dict[str, str] = {}
    node = ""
    for line in check.splitlines():
        if line.startswith("FAILED "):
            node = line.removeprefix("FAILED ")
            cases[node] = ""
        elif line.startswith("    ") and node:
            cases[node] += line.strip()
    return cases


def ps_rows(toy: Path, env: dict[str, str] | None = None) -> list[list[str]]:
    """`dispatch ps`'s rows, with a register that publishes no host, so the ones read are the
    repo's own."""
    register = toy.parent / "bin" / "worker-hosts"
    register.write_text("#!/bin/sh\n")
    register.chmod(0o755)
    listed = subprocess.run([str(DISPATCH), "ps"], cwd=toy, capture_output=True, text=True,
                            env=env or environment(toy), timeout=120)
    assert listed.returncode == 0, listed.stderr
    return [row.split() for row in listed.stdout.splitlines()[1:]]


def test_a_fuzz_run_is_one_job_on_the_host_it_designates_with_its_database_beside_the_worktree(
        fuzzable: Path) -> None:
    remote, env = fake_remote(fuzzable)

    started = fuzz(fuzzable, "start", "--host", "agent@far", env=env)

    assert started.returncode == 0, started.stdout + started.stderr
    assert git(fuzzable, "config", "dispatch.fuzz.host").strip() == "agent@far"
    assert git(fuzzable, "config", "dispatch.fuzz.branch").strip() == "main"
    worktree = remote / "repos" / "dispatch" / "lamp-main-fuzz"
    assert git(worktree, "rev-parse", "HEAD") == git(fuzzable, "rev-parse", "main"), "cut from the tip it pushed"
    db = remote / ".local" / "state" / "dispatch" / "lamp-main" / "fuzz.hypothesis"
    assert (worktree / ".hypothesis").resolve() == db
    fuzz_ended(fuzzable)
    assert examples(db), "the findings are in the database, beside the worktree"

    for host in ("agent@far", "local"):
        again = fuzz(fuzzable, "start", "--host", host, env=env)
        assert again.returncode != 0
        assert "already fuzzes on agent@far" in again.stderr, again.stderr


def test_a_push_of_the_integration_branch_restarts_the_run_on_its_tips_and_leaves_the_database(
        fuzzable: Path) -> None:
    remote, env = fake_remote(fuzzable)
    assert fuzz(fuzzable, "start", "--host", "agent@far", env=env).returncode == 0
    ended = fuzz_ended(fuzzable)
    db = remote / ".local" / "state" / "dispatch" / "lamp-main" / "fuzz.hypothesis"
    (db / "kept").write_text("the restart never touches this\n")
    worktree = remote / "repos" / "dispatch" / "lamp-main-fuzz"
    before = git(worktree, "rev-parse", "HEAD")

    other = subprocess.run(["git", "-C", str(fuzzable), "push", "-q", "agent-far", "main:elsewhere"],
                           capture_output=True, text=True, env=env, timeout=120)
    assert other.returncode == 0, other.stderr
    assert (fuzz_job(fuzzable) / "status").read_text() == ended, "a push of another branch restarts nothing"

    mend(fuzzable)
    (fuzzable / "agent" / "notes.md").write_text("the agent repo moved too\n")
    git(fuzzable / "agent", "add", "notes.md")
    git(fuzzable / "agent", "commit", "-q", "-m", "a note")
    pushed = subprocess.run([str(DISPATCH), "push"], cwd=fuzzable, capture_output=True, text=True,
                            env={**env, "PY": sys.executable}, timeout=120)

    assert pushed.returncode == 0, pushed.stderr
    assert git(worktree, "rev-parse", "HEAD") == git(fuzzable, "rev-parse", "main") != before
    assert git(worktree / "agent", "rev-parse", "HEAD") == git(fuzzable / "agent", "rev-parse", "main")
    assert not (fuzz_job(fuzzable) / "status").exists(), "a fresh job, fuzzing the mended code with no end in sight"
    assert (db / "kept").exists()
    checked = fuzz(fuzzable, "check", env=env)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "no failure" in checked.stdout


def test_stop_ends_a_running_run_and_start_resumes_it_on_the_tip(fuzzable: Path) -> None:
    """User story 3: stopping frees the machine, a push to it restarts nothing until the next
    `start`, and that start takes the tip there is by then."""
    mend(fuzzable)
    remote, env = fake_remote(fuzzable)
    assert fuzz(fuzzable, "start", "--host", "agent@far", env=env).returncode == 0
    pid = fuzz_pid(fuzzable)
    again = fuzz(fuzzable, "start", env=env)
    assert again.returncode != 0
    assert "already fuzzing" in again.stderr, again.stderr
    assert fuzz_pid(fuzzable) == pid, "the running job is left alone"
    assert [row[:4] for row in ps_rows(fuzzable, env)] == [["agent@far", "lamp/main", "fuzz", "running"]]

    stopped = fuzz(fuzzable, "stop", env=env)

    assert stopped.returncode == 0, stopped.stderr
    assert "exit=143" in fuzz_ended(fuzzable)
    assert not (remote / "repos" / "dispatch" / "lamp.git" / "hooks" / "post-receive").exists()
    worktree = remote / "repos" / "dispatch" / "lamp-main-fuzz"
    stopped_at = git(worktree, "rev-parse", "HEAD")
    (fuzzable / "lamp.txt").write_text("the lamp, brighter\n")
    git(fuzzable, "commit", "-q", "-am", "brighter")
    assert subprocess.run([str(DISPATCH), "push"], cwd=fuzzable, capture_output=True, env=env,
                          timeout=120).returncode == 0
    assert git(worktree, "rev-parse", "HEAD") == stopped_at, "no hook, no restart"
    assert (fuzz_job(fuzzable) / "status").exists()

    resumed = fuzz(fuzzable, "start", env=env)

    assert resumed.returncode == 0, resumed.stderr
    assert git(worktree, "rev-parse", "HEAD") == git(fuzzable, "rev-parse", "main")
    assert not (fuzz_job(fuzzable) / "status").exists(), "running again"
    assert (remote / "repos" / "dispatch" / "lamp.git" / "hooks" / "post-receive").exists()


def test_stop_and_clean_leave_the_finding_and_the_next_start_resumes_on_it(fuzzable: Path) -> None:
    """P1 and P3, on `local`, whose repo is the user's own checkout and takes no hook of the run's,
    nor loses one of its own."""
    (fuzzable / "hooks").mkdir()
    (fuzzable / "hooks" / "post-receive").write_text("#!/bin/sh\n# the project's own\n")
    git(fuzzable, "add", "hooks")
    git(fuzzable, "commit", "-q", "-m", "a hook the project ships")
    assert fuzz(fuzzable, "start", "--host", "local").returncode == 0
    fuzz_ended(fuzzable)
    worktree = fuzzable.parent / "lamp-main-fuzz"
    db = local_scratch(fuzzable) / "fuzz.hypothesis"
    found = examples(db)
    assert found

    stopped = fuzz(fuzzable, "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert worktree.is_dir() and examples(db) == found
    assert [row[:4] for row in ps_rows(fuzzable)] == [["local", "lamp/main", "fuzz", "exited"]]

    cleaned = fuzz(fuzzable, "clean")
    assert cleaned.returncode == 0, cleaned.stderr
    assert not worktree.exists()
    for at in (fuzzable, fuzzable / "agent"):
        assert "fuzz/main" not in git(at, "branch", "--list")
    assert examples(db) == found
    assert (fuzzable / "hooks" / "post-receive").exists()

    again = fuzz(fuzzable, "start")
    assert again.returncode == 0, again.stderr
    assert (worktree / ".hypothesis").resolve() == db, "the corpus the next run starts on"
    checked = fuzz(fuzzable, "check")
    assert checked.returncode != 0
    assert read_out(checked.stdout) == {BOUND_NODE: "Failing test case: test_small(n=1000,)",
                                        NODE: "Failing test case: test_roundtrip(s='zzz',)"}, checked.stdout


def test_a_project_that_sets_its_own_database_is_refused_and_left_undesignated(fuzzable: Path) -> None:
    (fuzzable / "tests" / "conftest.py").write_text(CONFTEST.replace("deadline=None", "deadline=None, database=None"))
    git(fuzzable, "commit", "-q", "-am", "no database")

    refused = fuzz(fuzzable, "start", "--host", "local")

    assert refused.returncode != 0
    assert "tests/conftest.py:3" in refused.stderr, refused.stderr
    assert not (fuzzable.parent / "lamp-main-fuzz").exists()
    assert "dispatch.fuzz" not in git(fuzzable, "config", "--list")
    unread = fuzz(fuzzable, "check")
    assert unread.returncode != 0
    assert "no fuzz run designated" in unread.stderr


def test_patch_brings_each_finding_here_as_an_example_and_to_the_tracker_as_one_proposed_ticket(
        fuzzable: Path, tmp_path: Path) -> None:
    """P4, with the prototype's patch as the oracle: the property as the tree has it once the patch
    Hypothesis wrote there is applied, compared as Python rather than as layout."""
    expected = tmp_path / "expected"
    (expected / "tests" / "properties").mkdir(parents=True)
    (expected / "tests" / "properties" / "test_roundtrip.py").write_text(PROPERTY)
    (expected / "prototype.patch").write_text(PROTOTYPE_PATCH)
    subprocess.run(["git", "apply", "prototype.patch"], cwd=expected, check=True)
    want = ast.dump(ast.parse((expected / "tests" / "properties" / "test_roundtrip.py").read_text()))
    assert fuzz(fuzzable, "start", "--host", "local").returncode == 0
    fuzz_ended(fuzzable)

    patched = fuzz(fuzzable, "patch")

    assert patched.returncode == 0, patched.stdout + patched.stderr
    have = (fuzzable / "tests" / "properties" / "test_roundtrip.py").read_text()
    assert ast.dump(ast.parse(have)) == want, have
    assert "tests/properties/test_roundtrip.py" in git(fuzzable, "status", "--porcelain"), "left for the user to commit"
    ticket = tracked(fuzzable) / f"{FINDING}.md"
    assert status_of(fuzzable, FINDING) == "proposed"
    assert NODE in ticket.read_text() and "s='zzz'" in ticket.read_text()
    assert "n=1000" in (tracked(fuzzable) / f"{BOUND_FINDING}.md").read_text(), "each case on its own property's ticket"
    assert "s='zzz'" not in (tracked(fuzzable) / f"{BOUND_FINDING}.md").read_text()
    assert git(fuzzable / "agent", "status", "--porcelain") == "", "filed and committed"

    # The user retitles the ticket and someone garbles its brief; the next patch restores the brief.
    text = ticket.read_text()
    title = next(line for line in text.splitlines() if line.startswith("# "))
    ticket.write_text(text.replace(title, "# The round trip loses a z").replace("s='zzz'", "s='?'"))
    git(fuzzable / "agent", "commit", "-q", "-am", "retitled")

    again = fuzz(fuzzable, "patch")

    assert again.returncode == 0, again.stdout + again.stderr
    assert ast.dump(ast.parse((fuzzable / "tests" / "properties" / "test_roundtrip.py").read_text())) == want, \
        "taken in once"
    assert sorted(p.name for p in tracked(fuzzable).glob("fuzz-*.md")) == [f"{BOUND_FINDING}.md", f"{FINDING}.md"]
    text = ticket.read_text()
    assert "# The round trip loses a z" in text
    assert text.count("s='zzz'") == 1 and "s='?'" not in text, text
    assert git(fuzzable / "agent", "log", "-1", "--format=%s").strip() == f"fuzz: {FINDING} brief rewritten"


def test_a_finding_whose_ticket_is_in_somebodys_hands_is_said_and_left_out_of_it(fuzzable: Path) -> None:
    assert fuzz(fuzzable, "start", "--host", "local").returncode == 0
    fuzz_ended(fuzzable)
    assert fuzz(fuzzable, "patch").returncode == 0
    assert run(fuzzable, "claim", FINDING).returncode == 0
    ticket = (tracked(fuzzable) / f"{FINDING}.md").read_text()

    again = fuzz(fuzzable, "patch")

    assert again.returncode != 0
    assert f"{FINDING} is claimed" in again.stderr, again.stderr
    assert (tracked(fuzzable) / f"{FINDING}.md").read_text() == ticket


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
