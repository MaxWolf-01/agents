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

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

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
    shares. Keyed on the check's temp dir, which holds the toy and every worktree beside it, so a
    command run in a worktree lands on the server the toy's teardown takes down. Under /tmp and
    short, since a socket path over about a hundred bytes is refused."""
    return Path("/tmp") / f"dispatch-check-{hashlib.sha1(str(toy.parent).encode()).hexdigest()[:12]}"


@pytest.fixture
def toy(tmp_path: Path) -> Iterator[Path]:
    """A project on `main`: a code repo, its `agent/` a repo of its own inside it that the code repo
    ignores, and a tree of two tickets in it. Answers the code repo's root, and takes down the tmux
    server its workers ran on."""
    yield from project(tmp_path / "lamp")


@pytest.fixture
def dotted(tmp_path: Path) -> Iterator[Path]:
    """The toy under a name with a dot in it, as the dotfiles repo has."""
    yield from project(tmp_path / ".lamp")


def project(repo: Path) -> Iterator[Path]:
    tmp_path = repo.parent
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
    spawn hands its runner in place of the one the host's claude lists. The page it writes carries
    each source's spec with both ends pinned to short SHAs, as diffview's does, and its
    --sources-of reads them back off a page."""
    bin_dir = toy.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "diffview").write_text(
        '#!/bin/sh\n'
        '[ "$1" = --sources-of ] && { grep -o \'"spec": "[^"]*"\' "$2" | sed \'s/^"spec": "//; s/"$//\'; exit 0; }\n'
        f'printf "%s\\n" "$*" >> "{bin_dir / "diffview.args"}"\n'
        'echo "diffview: serving $2 at http://127.0.0.1:1/"\n'
        '[ "$1" = --serve ] && exit 0\n'
        'out=; page=\n'
        'while [ $# -gt 0 ]; do case $1 in -o) out=$2; shift 2 ;; --notes) shift 2 ;;'
        ' *) r=${1##*@}; page="$page{\\"spec\\": \\"${1%@*}@$(printf %.7s "${r%%..*}")..$(printf %.7s "${r#*..}")\\"}, "; shift ;;'
        ' esac; done\n'
        'printf \'{"sources": [%s]}\\n\' "$page" > "$out"\n')
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
        ["tmux", "capture-pane", "-p", "-J", "-t", f"=dispatch-{toy.name}-warm-preset:"],
        capture_output=True, text=True, env=environment(toy)).stdout
    return left[0]


def status_of(toy: Path, slug: str) -> str:
    return (tracked(toy) / f"{slug}.md").read_text().split("status: ")[1].split("\n")[0]


def ranges_of(toy: Path, slug: str) -> list[str]:
    """The ticket's `diff:` ranges, as the tracker reads them."""
    return subprocess.run([str(SKILL.parent / "tracker" / "tracker.py"), "get", slug, "diff"],
                          cwd=toy, capture_output=True, text=True).stdout.split()


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
    rules = tmp_path / "mx" / "installed" / "skills" / "session-page"
    rules.mkdir(parents=True, exist_ok=True)
    shutil.copy(SKILL.parent / "session-page" / "RULES.md", rules)
    return tmp_path / "mx" / "installed"


@pytest.fixture
def staged(toy: Path) -> Path:
    """The toy with a stub runner staged in the skill copy dispatch sends to a host."""
    return skill_copy(toy)


def skill_copy(toy: Path) -> Path:
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


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
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
    # the page shows code alone, so an assumption anchored on the report stays on the ticket
    assert [(one["id"], one["path"], one["line"]) for one in notes["notes"]] == [(1, "lamp.txt", 1)]

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

    # one page, over the code range alone: the report reaches the user through the ticket
    handed = (toy.parent / "bin" / "diffview.args").read_text().splitlines()
    pages = [line for line in handed if not line.startswith("--serve")]
    assert pages and all(line.startswith(f"{toy}@{cut['code']}..{tip['code']} --notes ") for line in pages), handed

    # the `done` retires the run: both worktrees and both branches go, and so does the record of it
    assert not (toy.parent / "lamp-warm-preset").exists()
    for at in (toy, agent):
        assert not git(at, "branch", "--list", "ticket/warm-preset")
    probed = subprocess.run([str(staged), "ctl", "probe"], cwd=toy, capture_output=True, text=True,
                            env=environment(toy), timeout=180)
    assert "no run recorded" in probed.stderr, probed.stderr


# The building stub as a tree's children run it: each commits a file of its own, so a child built on
# a sibling's merge carries that sibling's file and adds its own beside it.
BUILDING_ITS_OWN = BUILDING.replace(
    "printf 'the lamp, warm\\n' > lamp.txt\ngit add lamp.txt",
    "printf '%s\\n' \"$slug\" > \"$slug.txt\"\ngit add \"$slug.txt\"",
)


@pytest.mark.full_path
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
    assert not (toy.parent / "lamp-preset-format").exists(), "a hinge's `done` retires its run"

    assert "warm-preset" in frontier()
    built("warm-preset")
    assert "cool-preset" not in frontier(), "unmerged, the leaf holds its sibling"
    merged("warm-preset")  # the orchestrator's read passed it, and the user has not ruled
    assert status_of(toy, "warm-preset") == "review", "ruled with its parent, not alone"
    assert (toy.parent / "lamp-warm-preset").exists(), "kept for a resume until the ruling"
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
    # one commit carries the tree's `done`, and the next retires the tree it finished
    assert git(agent, "log", "-2", "--format=%s").splitlines() == ["retire lamp-ui: finished", "lamp-ui landed, ruled whole"]
    landed = lambda slug: git(agent, "show", f"HEAD~1:tickets/{slug}.md")  # noqa: E731
    assert f"code@{main}..{git(toy, 'rev-parse', 'lamp-ui').strip()}" in landed("lamp-ui"), "the parent's range"
    for slug in ("lamp-ui", "preset-format", "warm-preset", "cool-preset"):
        assert "status: done" in landed(slug), slug
        assert not (tickets / f"{slug}.md").exists(), f"{slug} retired"
    assert not git(agent, "status", "--porcelain", "--", "tickets")
    for slug in ("warm-preset", "cool-preset"):
        assert not (toy.parent / f"lamp-{slug}").exists(), f"the accept retires {slug}'s run"
        for at in (toy, agent):
            assert not git(at, "branch", "--list", f"ticket/{slug}")


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
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


def test_a_worker_is_told_the_asking_rule_from_its_one_home(tmp_path: Path) -> None:
    """`asking-rule-has-one-home`: worker-prompt.md names the asking rule as appended below it, so
    the runner appends that section of the install's RULES.md, and the prompt carries no copy."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)
    rules = (SKILL.parent / "session-page" / "RULES.md").read_text()
    section = re.split(r"\n#{1,2} ", rules[rules.index("## What the user decides"):])[0].strip()
    prompt = (SKILL / "worker-prompt.md").read_text()

    subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-1"],
                   cwd=tmp_path, capture_output=True, text=True, timeout=60,
                   env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))})

    assert section in (bin_dir / "claude.calls").read_text()
    assert not [clause for clause in re.split(r"[.:;]", section.splitlines()[-1]) if len(clause) > 20 and clause.strip() in prompt]


def test_a_runner_whose_install_lacks_the_asking_rule_starts_no_worker(tmp_path: Path) -> None:
    """A worker told the rule is appended below its prompt, with nothing there, would ask the user
    by no rule at all; the status line names the section that is missing."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)
    plugin = mx(tmp_path)
    rules = plugin / "skills" / "session-page" / "RULES.md"
    rules.write_text(rules.read_text().replace("## What the user decides", "## Something else"))

    done = subprocess.run(["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", "opus", "run-1"],
                          cwd=tmp_path, capture_output=True, text=True, timeout=60,
                          env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(plugin)})

    assert done.returncode == 1
    assert (state / "run-1.status").read_text().startswith(
        "attempts=0 exit=1 report=no session=- error=no '## What the user decides' section in")
    assert "older than" in (state / "run-1.status").read_text()
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


@pytest.mark.full_path
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


@pytest.mark.full_path
def test_a_worker_of_a_repo_with_a_dot_in_its_name_is_found_by_its_session_name(dotted: Path) -> None:
    """tmux reads a `.` in a target as the window separator, so `.lamp`'s worker session is named
    whole only with a `:` after it: a respawn reuses it, a cleanup kills it, and the spawn after
    that starts in a fresh one."""
    staged = skill_copy(dotted)
    state = dotted.parent / "home" / ".local" / "state" / "dispatch" / ".lamp-main"
    env = environment(dotted)

    def sessions() -> list[str]:
        """The live sessions' names. A pane's text is no witness: under load the shell echoes a
        typed line once more as it redraws it."""
        return subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"],
                              capture_output=True, text=True, env=env).stdout.split()

    run(dotted, "claim", "warm-preset")
    for _ in range(2):
        said = spawn(dotted, staged, "warm-preset", "Work it.\n")
        assert said.returncode == 0, said.stderr
        waited(dotted, state)
    assert "+ tmux new-session" not in said.stderr, "the respawn found the session the spawn made: " + said.stderr
    assert sessions() == ["dispatch-.lamp-warm-preset"]

    cleaned = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=dotted,
                             capture_output=True, text=True, env=env, timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert "no session" not in cleaned.stderr, cleaned.stderr
    assert sessions() == []

    said = spawn(dotted, staged, "warm-preset", "Work it.\n")
    assert said.returncode == 0, said.stderr
    assert "+ tmux new-session" in said.stderr, "the spawn after a cleanup starts a fresh session: " + said.stderr
    assert sessions() == ["dispatch-.lamp-warm-preset"]


@pytest.mark.full_path
def test_a_cleanup_removes_the_jobs_its_worker_left_in_its_worktree_and_no_others(toy: Path, staged: Path) -> None:
    """Workers rarely `job rm` their builds and test runs, so the cleanup does: every job whose cwd
    is the ticket's worktree or under it, running or done. A sibling worktree whose name extends
    the slug and anything outside the worktrees keep theirs."""
    job = shutil.which("job")
    if not job:
        pytest.skip("no `job` here, and a worker's jobs are what this cleans up")
    env = environment(toy)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)
    worktree = toy.parent / "lamp-warm-preset"
    places = {"warm-build": worktree, "warm-suite": worktree / "sub", "warm-more": toy.parent / "lamp-warm-preset-more",
              "elsewhere": toy}
    for name, cwd in places.items():
        cwd.mkdir(exist_ok=True)
        command = ["true"] if name == "warm-suite" else ["sleep", "600"]
        started = subprocess.run([job, "run", name, "--cwd", str(cwd), "--", *command],
                                 capture_output=True, text=True, env=env, timeout=30)
        assert started.returncode == 0, started.stderr
    assert subprocess.run([job, "wait", "warm-suite", "--deadline", "20"], capture_output=True, env=env, timeout=30).returncode == 0

    cleaned = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=toy,
                             capture_output=True, text=True, env=env, timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert {"removed warm-build", "removed warm-suite"} <= set(cleaned.stdout.splitlines()), cleaned.stdout
    left = sorted(p.name for p in (toy.parent / "jobs").iterdir())
    assert left == ["elsewhere", "warm-more"]
    sessions = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"],
                              capture_output=True, text=True, env=env).stdout.split()
    assert sorted(s for s in sessions if s.startswith("job-")) == ["job-elsewhere", "job-warm-more"]


@pytest.mark.full_path
def test_a_done_on_a_remote_host_retires_its_run_there_and_here_and_one_that_fails_is_said(toy: Path, staged: Path) -> None:
    """A done ticket has nothing left to resume: its `done` takes the host's worktrees and branches,
    the run record, and the fetched branches here. A host that does not answer leaves the `done`
    standing and says what tries again; the next `review` does."""
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    def review(env: dict[str, str]) -> subprocess.CompletedProcess:
        return subprocess.run([str(staged), "review", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, env=env, timeout=180).returncode == 0
    assert review(env).returncode == 0
    for top in (toy, toy / "agent"):
        git(top, "merge", "-q", "--no-ff", "-m", "warm-preset: landed", "ticket/warm-preset")

    gone = review({**env, "REMOTE_HOME": str(toy.parent / "nowhere")})
    assert gone.returncode != 0
    assert "warm-preset is done, and its cleanup on agent@far failed; `dispatch ctl cleanup warm-preset` from main tries again" in gone.stderr, gone.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert git(toy, "branch", "--list", "ticket/warm-preset"), "kept until the host is clean"

    again = review(env)
    assert again.returncode == 0, again.stderr
    assert not (remote / "repos" / "dispatch" / "lamp-warm-preset").exists()
    for top in (remote / "repos" / "dispatch" / "lamp.git", toy, toy / "agent"):
        assert not git(top, "branch", "--list", "ticket/warm-preset"), top
    probed = subprocess.run([str(staged), "ctl", "probe"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert "no run recorded" in probed.stderr, probed.stderr


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
def test_a_round_with_no_code_gets_no_review_page(toy: Path, staged: Path) -> None:
    """A research ticket's round: the agent branch carries the report and nothing in the code repo
    moved, so there is no diff of code to show and `review` says so rather than rendering one. A
    page already at the ticket's path, which a session rendered by hand, is left as it is."""
    (staged.parent / "run-worker.sh").write_text(BUILDING.replace(
        "printf 'the lamp, warm\\n' > lamp.txt\ngit add lamp.txt\ngit commit -q -m \"$slug: the warm preset\"\n", ""))
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)
    assert not git(toy, "diff", "--name-only", "main", "ticket/warm-preset").split()
    by_hand = toy / "agent" / "diffviews" / "warm-preset.html"
    by_hand.parent.mkdir(parents=True, exist_ok=True)
    by_hand.write_text("the code in a repo dispatch does not read\n")

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert "gets no review page" in said.stderr, said.stderr
    assert status_of(toy, "warm-preset") == "review"
    assert by_hand.read_text() == "the code in a repo dispatch does not read\n"
    assert not (toy.parent / "bin" / "diffview.args").exists()


# `tickets-land-in-listed-repos`: a ticket's round lands in the listed repos its `repos:` names
# beside the code repo and the agent repo. The oracle is each toy repo's own history, read with git:
# a round is one commit per branch, so a range is that commit's parent and the commit.


def listed_repo(at: Path, branch: str) -> Path:
    """A repo for the toy's repo list, with one commit on `branch`."""
    git(at.parent, "init", "-q", "-b", branch, str(at))
    (at / "README").write_text(f"{at.name}\n")
    git(at, "add", "-A")
    git(at, "commit", "-q", "-m", f"{at.name} begins")
    return at


def listing(toy: Path, slug: str, toml: str, repos: str) -> None:
    """The toy's repo list as `toml`, and `slug` claimed and naming `repos` in its `repos:`."""
    agent = toy / "agent"
    (agent / "repos.toml").write_text(toml)
    path = tracked(toy) / f"{slug}.md"
    path.write_text(path.read_text().replace("status: open", f"status: claimed\nrepos: [{repos}]", 1))
    git(agent, "add", "-A")
    git(agent, "commit", "-q", "-m", f"the repo list, and {slug} claimed")


def built_on(top: Path, branch: str, start: str, name: str) -> tuple[str, str]:
    """One commit on `branch` in `top`, cut from `start` unless it exists: (its parent, itself).
    `top` is left on the branch it had out."""
    had = git(top, "branch", "--show-current").strip()
    exists = subprocess.run(["git", "-C", str(top), "rev-parse", "-q", "--verify", f"refs/heads/{branch}"],
                            capture_output=True).returncode == 0
    git(top, "switch", "-q", *([branch] if exists else ["-c", branch, start]))
    (top / name).write_text(f"{branch} in {top.name}\n")
    git(top, "add", name)
    git(top, "commit", "-q", "-m", f"{branch}: {name}")
    git(top, "switch", "-q", had)
    return git(top, "rev-parse", f"{branch}~1").strip(), git(top, "rev-parse", branch).strip()


def merged_in(top: Path, onto: str, branch: str) -> None:
    """`branch` merged --no-ff into `onto` in `top`, which is left on the branch it had out."""
    had = git(top, "branch", "--show-current").strip()
    git(top, "switch", "-q", onto)
    git(top, "merge", "-q", "--no-ff", "-m", f"{branch} merged", branch)
    git(top, "switch", "-q", had)


def pages(toy: Path) -> list[str]:
    """The specs of every page `dispatch review` asked diffview for, in order, one line each."""
    handed = (toy.parent / "bin" / "diffview.args").read_text().splitlines()
    return [line.partition(" --notes ")[0] for line in handed if not line.startswith("--serve")]


def test_a_round_in_listed_repos_gets_one_page_and_names_each_range_before_and_after_its_merge(toy: Path) -> None:
    """`tickets-land-in-listed-repos#P4`: one page, a section per repo the round committed in: the
    code repo, `Backend` nested in the project, and `jarvis` beside it, whose PR merges at origin
    while its own `main` is behind. Each range names its repo, and is the same range before and
    after the merge."""
    agent = toy / "agent"
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n")
    git(toy, "commit", "-q", "-am", "Backend is a repo of its own")
    backend = listed_repo(toy / "Backend", "development").resolve()
    seed = listed_repo(toy.parent / "jarvis-seed", "main")
    git(toy.parent, "clone", "-q", "--bare", str(seed), str(toy.parent / "jarvis.git"))
    jarvis = toy.parent / "jarvis"
    git(toy.parent, "clone", "-q", str(toy.parent / "jarvis.git"), str(jarvis))
    jarvis = jarvis.resolve()
    # origin moves on after the clone, and the ticket branch is cut from there: a range against the
    # stale local `main` alone would start a commit early
    (seed / "later").write_text("later\n")
    git(seed, "add", "later")
    git(seed, "commit", "-q", "-m", "jarvis moves on")
    git(seed, "push", "-q", str(toy.parent / "jarvis.git"), "main")
    git(jarvis, "fetch", "-q")
    listing(toy, "warm-preset", f'[Backend]\npath = "Backend"\nintegration = "development"\n\n[jarvis]\npath = "{jarvis}"\n',
            "Backend, jarvis")

    rounds = {"code": built_on(toy, "ticket/warm-preset", "main", "warm.txt"),
              "agent": built_on(agent, "ticket/warm-preset", "main", "warm.md"),
              "Backend": built_on(backend, "ticket/warm-preset", "development", "warm.py"),
              "jarvis": built_on(jarvis, "ticket/warm-preset", "origin/main", "warm.rs")}
    assert rounds["jarvis"][0] != git(jarvis, "rev-parse", "main").strip()
    ranges = [f"{at}@{cut}..{tip}" for at, (cut, tip) in rounds.items()]
    page = (f"{toy}@{rounds['code'][0]}..{rounds['code'][1]} {backend}@{rounds['Backend'][0]}..{rounds['Backend'][1]} "
            f"{jarvis}@{rounds['jarvis'][0]}..{rounds['jarvis'][1]}")

    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "review"
    assert pages(toy) == [page]
    assert "-o " + str(agent / "diffviews" / "warm-preset.html") in (toy.parent / "bin" / "diffview.args").read_text()

    for top, onto in ((toy, "main"), (agent, "main"), (backend, "development")):
        merged_in(top, onto, "ticket/warm-preset")
    # the PR's merge, at origin, which `jarvis` has fetched and its own `main` has not taken in
    git(jarvis, "switch", "-q", "-c", "pr", "origin/main")
    git(jarvis, "merge", "-q", "--no-ff", "-m", "Merge pull request #1", "ticket/warm-preset")
    git(jarvis, "push", "-q", "origin", "pr:main")
    git(jarvis, "switch", "-q", "main")

    landed = run(toy, "review", "warm-preset")
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert ranges_of(toy, "warm-preset") == ranges
    assert pages(toy) == [page, page], "the same sections, read off the recorded ranges"


def test_an_assumption_in_a_listed_repo_is_noted_on_its_file_in_that_repos_section(toy: Path) -> None:
    """`assumption-notes-reach-listed-repos`: a worker anchors from its worktree root, where nested
    `Backend` sits at its place and `jarvis` beside it as `../jarvis-<slug>`, and each note reaches
    the page under the path its repo's own tree has, naming its repo as its source, so it lands in
    that repo's section where another repo's section also shows that path (the same file changed
    in two repos, or an untouched file another section holds too); nothing about that reaches
    stderr. A note in a listed repo with no section on the page stays on the ticket, as an agent
    one does."""
    agent = toy / "agent"
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n/Helix/\n")
    git(toy, "commit", "-q", "-am", "Backend and Helix are repos of their own")
    backend = listed_repo(toy / "Backend", "development").resolve()
    listed_repo(toy / "Helix", "main")
    jarvis = listed_repo(toy.parent / "jarvis", "main").resolve()
    listing(toy, "warm-preset", f'[Backend]\npath = "Backend"\nintegration = "development"\n\n'
            f'[Helix]\npath = "Helix"\nintegration = "main"\n\n[jarvis]\npath = "{jarvis}"\nintegration = "main"\n',
            "Backend, jarvis")
    for top, start, name in ((toy, "main", "warm.txt"), (toy, "main", "shared.txt"),
                             (backend, "development", "warm.py"), (backend, "development", "shared.txt"),
                             (jarvis, "main", "warm.rs")):
        built_on(top, "ticket/warm-preset", start, name)
    git(agent, "switch", "-q", "-c", "ticket/warm-preset")
    (agent / "show" / "warm-preset").mkdir(parents=True)
    (agent / "show" / "warm-preset" / "report.md").write_text(
        "## Comments\n\nThe warm preset lands in three repos, unmerged.\n\n- [D1] **Assumptions**\n"
        "  - A1 `warm.txt:1`: in the code repo.\n"
        "  - A2 `Backend/warm.py:1`: in the nested repo.\n"
        "  - A3 `../jarvis-warm-preset/warm.rs:1`: in the sibling repo.\n"
        "  - A4 `Backend/shared.txt:1`: a path the code repo's section shows too.\n"
        "  - A5 `agent/show/warm-preset/report.md:1`: in the agent repo.\n"
        "  - A6 `Backend/README:1`: untouched, and Backend's is the first section holding a README.\n"
        "  - A7 `../jarvis-warm-preset/README:1`: untouched, and Backend's section holds one first.\n"
        "  - A8 `Helix/README:1`: in a listed repo this ticket's page has no section for.\n")
    git(agent, "add", "show")
    git(agent, "commit", "-q", "-m", "warm-preset: the report")
    git(agent, "switch", "-q", "main")

    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    notes = json.loads((agent / "diffviews" / "warm-preset.notes.json").read_text())["notes"]
    assert [(one["id"], one["path"], one["line"], Path(one["source"]).resolve()) for one in notes] == [
        (1, "warm.txt", 1, toy.resolve()), (2, "warm.py", 1, backend), (3, "warm.rs", 1, jarvis),
        (4, "shared.txt", 1, backend), (6, "README", 1, backend), (7, "README", 1, jarvis)]
    assert "A4" not in said.stderr and "A7" not in said.stderr, said.stderr


def test_a_childs_later_round_in_a_listed_repo_renders_beside_the_rounds_it_carries(toy: Path) -> None:
    """A child built on its parent ticket's branch: in `Backend` its base is the parent's branch
    there, which is ahead of the integration branch. A round merged into it is recorded; the next
    round, in `Backend` alone and unmerged, renders after it on the same page, and is recorded once
    it merges."""
    agent = toy / "agent"
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n")
    git(toy, "commit", "-q", "-am", "Backend is a repo of its own")
    backend = listed_repo(toy / "Backend", "development").resolve()
    git(backend, "branch", "lamp-ui")
    built_on(backend, "lamp-ui", "development", "ui.py")  # the parent's branch, ahead of development
    worktree = toy.parent / "lamp-lamp-ui"
    git(toy, "worktree", "add", "-q", str(worktree), "-b", "lamp-ui")
    listing(toy, "warm-preset", '[Backend]\npath = "Backend"\nintegration = "development"\n', "Backend")

    first = {"code": built_on(toy, "ticket/warm-preset", "lamp-ui", "warm.txt"),
             "agent": built_on(agent, "ticket/warm-preset", "main", "warm.md"),
             "Backend": built_on(backend, "ticket/warm-preset", "lamp-ui", "warm.py")}
    git(worktree, "merge", "-q", "--no-ff", "-m", "warm-preset merged", "ticket/warm-preset")
    merged_in(agent, "main", "ticket/warm-preset")
    merged_in(backend, "lamp-ui", "ticket/warm-preset")
    said = run(worktree, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "review", "ruled with its parent"
    recorded = [f"{at}@{cut}..{tip}" for at, (cut, tip) in first.items()]
    assert ranges_of(toy, "warm-preset") == recorded

    # sent back: the resumed worker's next round touches Backend alone
    again = built_on(backend, "ticket/warm-preset", "", "warmer.py")
    assert again[0] == first["Backend"][1]
    said = run(worktree, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    sections = [f"{worktree}@{first['code'][0]}..{first['code'][1]}",
                f"{backend}@{first['Backend'][0]}..{first['Backend'][1]}"]
    assert pages(toy)[-1] == " ".join([*sections, f"{backend}@{again[0]}..{again[1]}"])
    assert ranges_of(toy, "warm-preset") == recorded, "unmerged, unrecorded"

    merged_in(backend, "lamp-ui", "ticket/warm-preset")
    said = run(worktree, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert ranges_of(toy, "warm-preset") == [*recorded, f"Backend@{again[0]}..{again[1]}"]
    assert pages(toy)[-1] == " ".join([*sections, f"{backend}@{again[0]}..{again[1]}"])


def claimed_with_code(toy: Path) -> tuple[str, str]:
    """warm-preset claimed, its round one commit in the code repo and one in the agent repo: the
    code range's (start, end)."""
    agent = toy / "agent"
    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("status: open", "status: claimed", 1))
    git(agent, "commit", "-q", "-am", "warm-preset claimed")
    built_on(agent, "ticket/warm-preset", "main", "warm.md")
    return built_on(toy, "ticket/warm-preset", "main", "warm.txt")


def test_a_page_showing_sources_review_does_not_render_is_left_as_it_is_and_said(toy: Path) -> None:
    """`tickets-land-in-listed-repos#P3` for a ticket with code: a page at the ticket's path that
    shows a source this review does not render is a session's, rendered by hand, and the render
    that would replace it does not happen; the rest of the review does, and the exit status says it
    was not whole. A page over the review's own sources is replaced, diffview's rewrite of it when
    its summary lands included."""
    cut, tip = claimed_with_code(toy)
    page = toy / "agent" / "diffviews" / "warm-preset.html"
    page.parent.mkdir(parents=True)

    def refused(by_hand: str) -> None:
        page.write_text(by_hand)
        said = run(toy, "review", "warm-preset")
        assert said.returncode != 0
        assert "leaves that page as it is" in said.stderr, said.stderr
        assert page.read_text() == by_hand
        assert status_of(toy, "warm-preset") == "review"

    elsewhere = '{"spec": "/elsewhere/Backend@1234567..89abcde"}'
    refused("the Backend diff, as a note\n")  # no diffview page at all
    refused('{"sources": [' + elsewhere + "]}\n")
    assert not (toy.parent / "bin" / "diffview.args").exists()

    page.unlink()  # moved aside, as the refusal says
    assert run(toy, "review", "warm-preset").returncode == 0
    ours = page.read_text()
    assert f"{toy}@{cut[:7]}..{tip[:7]}" in ours

    page.write_text(ours.replace("]}", "]} <p>the summary, landed</p>"))  # diffview's own rewrite
    assert run(toy, "review", "warm-preset").returncode == 0
    assert len(pages(toy)) == 2

    # a session's render over it: the review's own source, and the Backend diff the ticket lacks
    refused(ours.replace("]}", ", " + elsewhere + "]}"))
    # the same source with an end off the ticket's branch: a commit beside it, not under it
    _, beside = built_on(toy, "elsewhere", "main", "cool.txt")
    refused(ours.replace(f"..{tip[:7]}", f"..{beside[:7]}"))
    # the same source running past the ticket's tip, which the render would cut short
    _, beyond = built_on(toy, "beyond", tip, "warmest.txt")
    refused(ours.replace(f"..{tip[:7]}", f"..{beyond[:7]}"))
    assert len(pages(toy)) == 2


def test_a_round_grown_before_its_merge_renders_its_own_page_again(toy: Path) -> None:
    """An amend, or a resumed round fetched before its merge: the round records no range yet, so its
    page showed the range to the tip it had, and the range now runs from the same start to a tip
    that tip is an ancestor of. Nothing on the page is lost to the render over the longer range."""
    cut, tip = claimed_with_code(toy)
    page = toy / "agent" / "diffviews" / "warm-preset.html"
    first = run(toy, "review", "warm-preset")
    assert first.returncode == 0, first.stderr
    assert f"{toy}@{cut[:7]}..{tip[:7]}" in page.read_text()

    grown, later = built_on(toy, "ticket/warm-preset", "", "warmer.txt")
    assert grown == tip
    again = run(toy, "review", "warm-preset")
    assert again.returncode == 0, again.stderr
    assert pages(toy) == [f"{toy}@{cut}..{tip}", f"{toy}@{cut}..{later}"]
    assert f"{toy}@{cut[:7]}..{later[:7]}" in page.read_text()


def test_a_page_an_earlier_review_rendered_over_the_tickets_ranges_is_rendered_again(toy: Path) -> None:
    """A page over the ticket's own range, its ends pinned to SHAs of another length than
    diffview's and other JSON around them, as an earlier `dispatch review` left it: nothing on it is
    lost to a render over that range, so it is replaced with no move by hand."""
    cut, tip = claimed_with_code(toy)
    page = toy / "agent" / "diffviews" / "warm-preset.html"
    page.parent.mkdir(parents=True)
    page.write_text('<script>{"sources": [{"label": "lamp", "spec": "' + f"{toy}@{cut[:9]}..{tip[:9]}" + '"}]}</script>\n')
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert pages(toy) == [f"{toy}@{cut}..{tip}"]
    assert f"{toy}@{cut[:7]}..{tip[:7]}" in page.read_text()


# The building stub in a worktree holding `Backend` nested in it and `jarvis` beside it, as a spawn
# of a ticket naming both places them: a commit in each, then the report.
BUILDING_LISTED = BUILDING.replace(
    'mkdir -p "agent/show/$slug"',
    """for at in Backend "../jarvis-$slug"; do
    printf 'warm\\n' > "$at/warm.txt"
    git -C "$at" add warm.txt
    git -C "$at" commit -q -m "$slug: warm in $at"
done
mkdir -p "agent/show/$slug\"""",
)


def staged_listed(toy: Path) -> dict[str, Path]:
    """The toy listing three repos, and warm-preset claimed naming two of them: `Backend` nested in
    the project, `jarvis` beside it, cloned from a bare origin that has moved on since its own
    `main` was last pulled, and `secrets`, which warm-preset does not name. Answers each repo's
    checkout here, and jarvis's origin and the repo that feeds it."""
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n")
    git(toy, "commit", "-q", "-am", "Backend is a repo of its own")
    repos = {"Backend": listed_repo(toy / "Backend", "development").resolve(),
             "seed": listed_repo(toy.parent / "jarvis-seed", "main"),
             "secrets": listed_repo(toy.parent / "secrets", "main").resolve(),
             "origin": toy.parent / "jarvis.git"}
    git(toy.parent, "clone", "-q", "--bare", str(repos["seed"]), str(repos["origin"]))
    git(toy.parent, "clone", "-q", str(repos["origin"]), str(toy.parent / "jarvis"))
    repos["jarvis"] = (toy.parent / "jarvis").resolve()
    moved_on(repos)
    listing(toy, "warm-preset", '[Backend]\npath = "Backend"\nintegration = "development"\n\n'
            f'[jarvis]\npath = "{repos["jarvis"]}"\n\n[secrets]\npath = "{repos["secrets"]}"\nintegration = "main"\n', "Backend, jarvis")
    return repos


def moved_on(repos: dict[str, Path]) -> str:
    """jarvis's origin one commit further, fetched into the checkout here and not merged into its
    `main`: the new `origin/main`."""
    seed = repos["seed"]
    (seed / "later").write_text(git(seed, "rev-parse", "HEAD"))
    git(seed, "add", "later")
    git(seed, "commit", "-q", "-m", "jarvis moves on")
    git(seed, "push", "-q", str(repos["origin"]), "main")
    git(repos["jarvis"], "fetch", "-q")
    return git(repos["jarvis"], "rev-parse", "origin/main").strip()


@pytest.mark.full_path
def test_a_remote_host_receives_the_listed_repos_a_ticket_names_and_gives_their_branches_back(
        toy: Path, staged: Path) -> None:
    """`tickets-land-in-listed-repos#P5`: the host gets a bare repo for each repo warm-preset names
    and none for `secrets`, which the project lists and the ticket does not; the host's directory
    listing is the oracle. Each is cut where the brief says, from its base: `Backend` inside the
    ticket worktree at the path the project keeps it at, from its integration branch, and `jarvis`
    beside it, from origin's `main`, which is ahead of the local one. The fetch brings each branch
    back, `push` sends each base again once it moves, the cleanup takes each worktree and branch off
    the host, and the landing's `done` deletes the fetched branches here."""
    repos = staged_listed(toy)
    (staged.parent / "run-worker.sh").write_text(BUILDING_LISTED)
    remote, env = fake_remote(toy)
    hosted = remote / "repos" / "dispatch"
    state = remote / ".local" / "state" / "dispatch" / "lamp-main"
    jarvis_base = git(repos["jarvis"], "rev-parse", "origin/main").strip()
    assert jarvis_base != git(repos["jarvis"], "rev-parse", "main").strip()

    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)
    assert said.returncode == 0, said.stdout + said.stderr
    waited(toy, state)
    assert sorted(p.name for p in hosted.iterdir()) == [
        "jarvis-warm-preset", "lamp-Backend.git", "lamp-agent.git", "lamp-jarvis.git", "lamp-warm-preset", "lamp.git"]
    for at, cut in ((hosted / "lamp-warm-preset" / "Backend", git(repos["Backend"], "rev-parse", "development")),
                    (hosted / "jarvis-warm-preset", jarvis_base)):
        assert git(at, "branch", "--show-current").strip() == "ticket/warm-preset", at
        assert git(at, "rev-parse", "HEAD~1").strip() == cut.strip(), at
    (brief,) = state.glob("*.brief")
    assert "- Backend: `Backend/` in your worktree, from `development`" in brief.read_text()
    assert "- jarvis: `../jarvis-warm-preset`, beside your worktree, from `main`" in brief.read_text()

    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    for name in ("Backend", "jarvis"):
        assert git(repos[name], "log", "-1", "--format=%s", "ticket/warm-preset").strip().startswith("warm-preset: warm in"), name
    reviewed = subprocess.run([str(staged), "review", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert reviewed.returncode == 0, reviewed.stderr
    assert [spec.partition("@")[0] for spec in pages(toy)[-1].split()] == [str(toy), str(repos["Backend"]), str(repos["jarvis"])]

    later = moved_on(repos)
    pushed = subprocess.run([str(staged), "push"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert pushed.returncode == 0, pushed.stderr
    assert git(hosted / "lamp-jarvis.git", "rev-parse", "main").strip() == later

    cleaned = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert sorted(p.name for p in hosted.iterdir()) == ["lamp-Backend.git", "lamp-agent.git", "lamp-jarvis.git", "lamp.git"]
    for bare in ("lamp-Backend.git", "lamp-jarvis.git"):
        assert not git(hosted / bare, "branch", "--list", "ticket/warm-preset"), bare

    # the landing: its `done` deletes the fetched branches here, each once it has merged
    for top, onto in ((toy, "main"), (toy / "agent", "main"), (repos["Backend"], "development"), (repos["jarvis"], "main")):
        merged_in(top, onto, "ticket/warm-preset")
    landed = subprocess.run([str(staged), "review", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    for name in ("Backend", "jarvis"):
        assert not git(repos[name], "branch", "--list", "ticket/warm-preset"), name


@pytest.mark.full_path
def test_a_local_host_cuts_the_listed_repos_from_their_checkouts_here(toy: Path, staged: Path) -> None:
    """A child of lamp-ui, dispatched from lamp-ui's worktree onto this machine: `Backend` is cut
    from lamp-ui's branch there, which is ahead of its integration branch, into the ticket worktree,
    and `jarvis` from origin's `main` beside it, each from the checkout the repo list names. The
    fetch finds every branch here already, and the cleanup takes the worktrees and the branches out
    of those checkouts."""
    repos = staged_listed(toy)
    _, parents = built_on(repos["Backend"], "lamp-ui", "development", "ui.py")
    worktree = toy.parent / "lamp-lamp-ui"
    git(toy, "worktree", "add", "-q", str(worktree), "-b", "lamp-ui")
    (staged.parent / "run-worker.sh").write_text(BUILDING_LISTED)
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-lamp-ui"
    env = environment(toy)

    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=worktree, input="Work it.\n", text=True, check=True, env=env)
    said = subprocess.run([str(staged), "ctl", "--host", "local", "--setup-cmd", "true", "spawn", "warm-preset", "sonnet"],
                          cwd=worktree, capture_output=True, text=True, env=env, timeout=180)
    assert said.returncode == 0, said.stdout + said.stderr
    waited(toy, state)
    held = {"Backend": toy.parent / "lamp-warm-preset" / "Backend", "jarvis": toy.parent / "jarvis-warm-preset"}
    for name, cut in (("Backend", parents), ("jarvis", git(repos["jarvis"], "rev-parse", "origin/main").strip())):
        assert git(held[name], "rev-parse", "--path-format=absolute", "--git-common-dir").strip() == str(repos[name] / ".git")
        assert git(repos[name], "rev-parse", "ticket/warm-preset~1").strip() == cut, name
    (brief,) = state.glob("*.brief")
    assert "- Backend: `Backend/` in your worktree, from `lamp-ui`" in brief.read_text()

    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=worktree, capture_output=True, text=True, env=env, timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    assert "already here, in every repo" in fetched.stdout

    cleaned = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=worktree, capture_output=True, text=True, env=env, timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert not any(at.exists() for at in held.values())
    assert not (toy.parent / "lamp-warm-preset").exists()
    for name in ("Backend", "jarvis", "secrets"):
        assert not git(repos[name], "branch", "--list", "ticket/warm-preset"), name


@pytest.mark.full_path
def test_a_respawn_holds_only_the_listed_repos_its_ticket_names_now(toy: Path, staged: Path) -> None:
    """`tickets-land-in-listed-repos#P5` across spawns: `jarvis` named by mistake and dropped from
    `repos:` leaves the worker's tree at the next spawn, worktree and branch, and the brief stops
    naming it; while its worktree carries a commit the spawn stops instead, with that commit kept. A
    ticket that names none any more leaves the host holding no listed worktree, and
    that spawn makes no host call a ticket that never named a repo would not make."""
    repos = staged_listed(toy)
    remote, env = fake_remote(toy)
    hosted = remote / "repos" / "dispatch"
    state = remote / ".local" / "state" / "dispatch" / "lamp-main"
    path = tracked(toy) / "warm-preset.md"

    def respawn(names: str, refused: bool = False) -> subprocess.CompletedProcess:
        path.write_text(re.sub(r"repos: \[[^]]*\]\n", f"repos: [{names}]\n" if names else "", path.read_text()))
        git(toy / "agent", "commit", "-q", "--allow-empty", "-am", f"warm-preset names [{names}]")
        before = set(state.glob("*.status"))
        said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)
        assert (said.returncode != 0) == refused, said.stdout + said.stderr
        for _ in range(60):
            if refused or set(state.glob("*.status")) - before:
                break
            time.sleep(0.5)
        else:
            pytest.fail("no status line 30s after the respawn")
        return said

    respawn("Backend, jarvis")
    assert (hosted / "jarvis-warm-preset").is_dir()

    built_on(hosted / "jarvis-warm-preset", "ticket/warm-preset", "", "warm.rs")
    said = respawn("Backend", refused=True)
    assert "no longer names jarvis, whose worktree here carries work" in said.stderr, said.stderr
    assert git(hosted / "jarvis-warm-preset", "log", "-1", "--format=%s").strip() == "ticket/warm-preset: warm.rs"
    git(hosted / "jarvis-warm-preset", "reset", "-q", "--hard", "HEAD~1")  # fetched, and let go

    respawn("Backend")
    assert sorted(p.name for p in hosted.iterdir()) == [
        "lamp-Backend.git", "lamp-agent.git", "lamp-jarvis.git", "lamp-warm-preset", "lamp.git"]
    assert not git(hosted / "lamp-jarvis.git", "branch", "--list", "ticket/warm-preset")
    assert (hosted / "lamp-warm-preset" / "Backend").is_dir()
    newest = max(state.glob("*.brief"), key=lambda brief: brief.stat().st_mtime_ns).read_text()
    assert "- Backend: `Backend/` in your worktree" in newest and "jarvis" not in newest

    said = respawn("")
    assert not (hosted / "lamp-warm-preset" / "Backend").exists()
    assert not git(hosted / "lamp-Backend.git", "branch", "--list", "ticket/warm-preset")
    calls = [line.split("dispatch-ctl ")[1] for line in said.stderr.splitlines()
             if line.startswith("+ on_host agent@far bash") or line.startswith("+ on_host agent@far env")]
    assert calls == ["spawn warm-preset sonnet"], said.stderr


def test_a_ticket_merged_into_a_local_integration_branch_behind_origin_records_only_its_own_commits(
        toy: Path) -> None:
    """`jarvis`'s ticket branch is cut from origin's `main`, which is ahead of the local one, and the
    session merges it into the local `main`. The range recorded for `jarvis` starts at the ticket's
    own fork point, not at the merge's first parent, so it holds the ticket's commit alone, and the
    page over the range before the merge is review's to render again."""
    repos = staged_listed(toy)
    agent = toy / "agent"
    rounds = {"code": built_on(toy, "ticket/warm-preset", "main", "warm.txt"),
              "agent": built_on(agent, "ticket/warm-preset", "main", "warm.md"),
              "jarvis": built_on(repos["jarvis"], "ticket/warm-preset", "origin/main", "warm.rs")}
    assert rounds["jarvis"][0] == git(repos["jarvis"], "rev-parse", "origin/main").strip()
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr

    for top in (toy, agent, repos["jarvis"]):
        merged_in(top, "main", "ticket/warm-preset")
    landed = run(toy, "review", "warm-preset")
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert ranges_of(toy, "warm-preset") == [f"{at}@{cut}..{tip}" for at, (cut, tip) in rounds.items()]
    jarvis = f"{repos['jarvis']}@{rounds['jarvis'][0]}..{rounds['jarvis'][1]}"
    assert pages(toy)[-1].split()[-1] == jarvis
    assert len(pages(toy)) == 2 and pages(toy)[0] == pages(toy)[1], "the same page, rendered again"


@pytest.mark.full_path
def test_a_spawn_that_finds_its_branch_in_a_listed_repo_already_cuts_nothing_and_keeps_it(
        toy: Path, staged: Path) -> None:
    """On a local host a listed repo is the user's own checkout, and a `ticket/<slug>` there that
    this spawn did not cut is somebody's work: the spawn stops before cutting anything, and that
    branch keeps its commit, through the next spawn once `repos:` drops the repo and through the
    cleanup after it."""
    repos = staged_listed(toy)
    _, theirs = built_on(repos["jarvis"], "ticket/warm-preset", "main", "theirs.rs")

    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode != 0
    assert "jarvis already has ticket/warm-preset" in said.stderr, said.stderr
    assert git(repos["jarvis"], "rev-parse", "ticket/warm-preset").strip() == theirs
    assert not (toy.parent / "lamp-warm-preset").exists()
    assert not git(repos["Backend"], "branch", "--list", "ticket/warm-preset")

    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("repos: [Backend, jarvis]", "repos: [Backend]"))
    git(toy / "agent", "commit", "-q", "-am", "warm-preset names Backend alone")
    again = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert again.returncode == 0, again.stderr
    cleaned = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=toy, capture_output=True, text=True,
                             env=environment(toy), timeout=180)
    assert cleaned.returncode == 0, cleaned.stderr
    assert git(repos["jarvis"], "rev-parse", "ticket/warm-preset").strip() == theirs


def test_a_parents_accept_deletes_its_childs_branch_in_a_listed_repo_once_merged_there(toy: Path) -> None:
    """A child of lamp-ui whose work is in `Backend` alone, merged there into lamp-ui's branch, which
    has merged into the integration branch: the accept that writes the child's `done` deletes its
    fetched branch in `Backend`, and leaves the parent's own branch there, whose range in `Backend`
    the parent records beside its code range."""
    tickets = tracked(toy)
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n")
    git(toy, "commit", "-q", "-am", "Backend is a repo of its own")
    backend = listed_repo(toy / "Backend", "development").resolve()
    (toy / "agent" / "repos.toml").write_text('[Backend]\npath = "Backend"\nintegration = "development"\n')
    for slug, parent in (("lamp-ui", ""), ("warm-preset", "lamp-ui")):
        path = ticket(tickets, slug, status="review", parent=parent)
        if parent:
            path.write_text(path.read_text().replace("status: review", "status: review\nrepos: [Backend]", 1))
    git(toy / "agent", "add", "-A")
    git(toy / "agent", "commit", "-q", "-m", "the tree, for its ruling")
    fork, _ = built_on(backend, "lamp-ui", "development", "ui.py")
    built_on(backend, "ticket/warm-preset", "lamp-ui", "warm.py")
    merged_in(backend, "lamp-ui", "ticket/warm-preset")
    merged_in(backend, "development", "lamp-ui")
    code = built_on(toy, "lamp-ui", "main", "ui.txt")
    merged_in(toy, "main", "lamp-ui")

    accepted = run(toy, "accept", "lamp-ui")
    assert accepted.returncode == 0, accepted.stderr
    assert not git(backend, "branch", "--list", "ticket/warm-preset")
    assert git(backend, "branch", "--list", "lamp-ui")
    # the tree is retired by now, so the ticket is read as the accept's commit left it
    landed = git(toy / "agent", "log", "-1", "--format=%H", "--grep=lamp-ui landed, ruled whole").strip()
    assert git(toy / "agent", "show", f"{landed}:tickets/lamp-ui.md").count(
        f"diff: [code@{code[0]}..{code[1]}, Backend@{fork}..{git(backend, 'rev-parse', 'lamp-ui').strip()}]") == 1


@pytest.mark.full_path
def test_a_listed_repo_dropped_from_repos_after_the_spawn_is_fetched_and_its_run_kept_until_merged(
        toy: Path, staged: Path) -> None:
    """`jarvis` named at the spawn and dropped from `repos:` before the review: the fetch still
    brings its branch back from the host, which holds it, and the `done` the review writes leaves the
    run on the host while that branch is unmerged here, so its commit is in two places."""
    repos = staged_listed(toy)
    (staged.parent / "run-worker.sh").write_text(BUILDING_LISTED)
    remote, env = fake_remote(toy)
    hosted = remote / "repos" / "dispatch"
    state = remote / ".local" / "state" / "dispatch" / "lamp-main"
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, state)
    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("repos: [Backend, jarvis]", "repos: [Backend]"))
    git(toy / "agent", "commit", "-q", "-am", "warm-preset names Backend alone")

    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    assert "no longer names jarvis" in fetched.stderr, fetched.stderr
    work = git(repos["jarvis"], "log", "-1", "--format=%s", "ticket/warm-preset").strip()
    assert work.startswith("warm-preset: warm in"), work

    reviewed = subprocess.run([str(staged), "review", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert reviewed.returncode == 0, reviewed.stderr
    for top, onto in ((toy, "main"), (toy / "agent", "main"), (repos["Backend"], "development")):
        merged_in(top, onto, "ticket/warm-preset")
    landed = subprocess.run([str(staged), "review", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert landed.returncode != 0
    assert status_of(toy, "warm-preset") == "done"
    assert "ticket/warm-preset in jarvis is not merged" in landed.stderr, landed.stderr
    assert (hosted / "jarvis-warm-preset").is_dir()
    assert git(repos["jarvis"], "log", "-1", "--format=%s", "ticket/warm-preset").strip() == work


@pytest.mark.full_path
def test_a_nested_repos_place_the_code_repo_already_fills_is_cut_there(toy: Path, staged: Path) -> None:
    """The code repo records `Backend` as a submodule, so its worktree comes with an empty `Backend/`:
    the spawn cuts Backend's ticket branch into it all the same, where the brief says it is."""
    repos = staged_listed(toy)
    git(toy, "update-index", "--add", "--cacheinfo", f"160000,{git(repos['Backend'], 'rev-parse', 'HEAD').strip()},Backend")
    git(toy, "commit", "-q", "-m", "Backend as a submodule")
    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode == 0, said.stderr
    waited(toy)
    nested = toy.parent / "lamp-warm-preset" / "Backend"
    assert git(nested, "branch", "--show-current").strip() == "ticket/warm-preset"
    assert git(nested, "rev-parse", "--path-format=absolute", "--git-common-dir").strip() == str(repos["Backend"] / ".git")


def test_a_branch_in_a_listed_repo_not_merged_at_the_done_stays_and_says_so(toy: Path) -> None:
    """`secrets` is on the list and warm-preset does not name it, yet holds a `ticket/warm-preset`
    with a commit on no branch it merges into: the `done` keeps it, commit and all, and says so."""
    repos = staged_listed(toy)
    agent = toy / "agent"
    for top, start in ((toy, "main"), (agent, "main"), (repos["Backend"], "development")):
        built_on(top, "ticket/warm-preset", start, "warm.txt")
    _, theirs = built_on(repos["secrets"], "ticket/warm-preset", "main", "secret.txt")
    assert run(toy, "review", "warm-preset").returncode == 0
    for top, onto in ((toy, "main"), (agent, "main"), (repos["Backend"], "development")):
        merged_in(top, onto, "ticket/warm-preset")
    said = run(toy, "review", "warm-preset")
    assert said.returncode != 0
    assert status_of(toy, "warm-preset") == "done"
    assert "ticket/warm-preset in secrets is not merged into main, so it stays" in said.stderr, said.stderr
    assert git(repos["secrets"], "rev-parse", "ticket/warm-preset").strip() == theirs
    assert not git(repos["Backend"], "branch", "--list", "ticket/warm-preset")


def test_a_listed_repo_whose_remote_for_the_host_points_elsewhere_is_pushed_nothing(toy: Path, staged: Path) -> None:
    """`tickets-land-in-listed-repos#P7`'s guard on the forced push: jarvis already has a remote by
    the name dispatch gives its host, for a repo of somebody else's; the spawn stops, and that repo
    receives nothing."""
    repos = staged_listed(toy)
    _, env = fake_remote(toy)
    elsewhere = toy.parent / "elsewhere.git"
    git(toy.parent, "init", "-q", "--bare", str(elsewhere))
    git(repos["jarvis"], "remote", "add", "agent-far-lamp", str(elsewhere))
    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)
    assert said.returncode != 0
    assert f"remote agent-far-lamp at {repos['jarvis']} is not" in said.stderr, said.stderr
    assert not git(elsewhere, "for-each-ref")


def test_a_review_reads_the_list_for_a_range_in_a_listed_repo_the_ticket_does_not_name(toy: Path) -> None:
    """A range recorded by hand in `Backend` on a ticket whose `repos:` names nothing: the review
    reads the repo list for it, and the page has its section."""
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n")
    git(toy, "commit", "-q", "-am", "Backend is a repo of its own")
    backend = listed_repo(toy / "Backend", "development").resolve()
    cut, tip = built_on(backend, "elsewhere", "development", "warm.py")
    listing(toy, "warm-preset", '[Backend]\npath = "Backend"\nintegration = "development"\n', "")
    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("repos: []\n", f"diff: [Backend@{cut}..{tip}]\n", 1))
    git(toy / "agent", "commit", "-q", "-am", "warm-preset's Backend range, by hand")
    code = built_on(toy, "ticket/warm-preset", "main", "warm.txt")
    built_on(toy / "agent", "ticket/warm-preset", "main", "warm.md")
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert pages(toy) == [f"{backend}@{cut}..{tip} {toy}@{code[0]}..{code[1]}"]


# `dispatch review` against GitHub as two fakes: `gh` answers `pr view` from a file per pull request
# and records every call, and the listed repo's origin is a bare repo here, which git reaches through
# the GitHub URL the repo names as its origin. The oracle is the history the check writes there as
# GitHub would: a squash, a rebase or a merge commit on `development`, after a change of somebody
# else's.

FAKE_GH = """#!/bin/sh
printf '%s\\n' "$*" >> "$0.calls"
[ "$1 $2" = "pr view" ] || { echo "fake gh answers pr view alone" >&2; exit 1; }
number=$3 repo=
while [ $# -gt 0 ]; do [ "$1" = --repo ] && repo=$2; shift; done
cat "$0.answers/$(echo "$repo" | tr / _)_$number.json" 2>/dev/null || { echo "no pull requests found" >&2; exit 1; }
"""

# Hours apart, and days before any merge a check makes, as a pull request's commits are.
AUTHORED = ("2026-10-01T09:00:00Z", "2026-10-01T11:30:00Z")


def on_github(toy: Path, gh: str = "helferline/Backend#7", url: str = "git@github.com:helferline/Backend.git") -> Path:
    """`Backend` nested in the toy, cloned from `Backend.git` here, whose URL git rewrites from
    GitHub's `helferline/Backend`; warm-preset in `review` naming it, with `gh` in its `gh:`. Its round is
    a commit in the code repo and the agent repo, both merged into `main`, and two in Backend on
    `ticket/warm-preset`, authored at AUTHORED, pushed for its pull request. `url` is its origin's
    URL, in any form GitHub gives one. GitHub says #7 is open. Answers Backend."""
    agent = toy / "agent"
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n")
    git(toy, "commit", "-q", "-am", "Backend is a repo of its own")
    seed = listed_repo(toy.parent / "Backend-seed", "development")
    origin = toy.parent / "Backend.git"
    git(toy.parent, "clone", "-q", "--bare", str(seed), str(origin))
    git(toy.parent, "clone", "-q", "--config", f"url.{origin}.insteadOf={url}", url, str(toy / "Backend"))
    backend = (toy / "Backend").resolve()
    assert git(backend, "config", "--get", "remote.origin.url").strip() == url
    listing(toy, "warm-preset", '[Backend]\npath = "Backend"\nintegration = "development"\n', "Backend")
    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("repos: [Backend]", f"repos: [Backend]\ngh: [{gh}]", 1)
                    .replace("status: claimed", "status: review", 1))
    git(agent, "commit", "-q", "-am", "warm-preset's pull request, its build in review")
    for top in (toy, agent):
        built_on(top, "ticket/warm-preset", "main", "warm.txt")
        merged_in(top, "main", "ticket/warm-preset")
    git(backend, "switch", "-q", "-c", "ticket/warm-preset")
    for name, date in zip(("warm.py", "warmer.py"), AUTHORED):
        (backend / name).write_text(f"{name}\n")
        git(backend, "add", name)
        git(backend, "commit", "-q", "-m", f"warm-preset: {name}", f"--date={date}")
    git(backend, "push", "-q", "origin", "ticket/warm-preset")
    git(backend, "switch", "-q", "development")
    (toy.parent / "bin").mkdir(exist_ok=True)
    (toy.parent / "bin" / "gh").write_text(FAKE_GH)
    (toy.parent / "bin" / "gh").chmod(0o755)
    (toy.parent / "bin" / "gh.answers").mkdir()
    answer({"state": "OPEN", "baseRefName": "development", "mergeCommit": None, "commits": []}, backend)
    return backend


def merged_on_github(backend: Path, how: Literal["squash", "rebase", "merge"], number: int = 7,
                     branch: str = "ticket/warm-preset") -> tuple[str, str]:
    """`branch`'s pull request merged on `development` at origin as `how`, after a change of
    somebody else's, and `gh pr view` answering for it. Answers (that change, the tip of
    `development`)."""
    commits = [line.split("\t") for line in
               git(backend, "log", "--reverse", "--format=%H\t%at\t%s", f"development..{branch}").splitlines()]
    git(backend, "switch", "-q", "-c", "github", "development")
    (backend / "theirs.py").write_text("theirs\n")
    git(backend, "add", "theirs.py")
    git(backend, "commit", "-q", "-m", "somebody else's change")
    theirs = git(backend, "rev-parse", "HEAD").strip()
    if how == "squash":
        git(backend, "merge", "-q", "--squash", branch)
        git(backend, "commit", "-q", "-m", f"Warm preset (#{number})")
    elif how == "rebase":
        git(backend, "cherry-pick", f"development..{branch}")
    elif how == "merge":
        git(backend, "merge", "-q", "--no-ff", "-m", f"Merge pull request #{number}", branch)
    seen = git(backend, "rev-parse", "origin/development").strip()
    git(backend, "push", "-q", "origin", "github:development")
    git(backend, "update-ref", "refs/remotes/origin/development", seen)  # what this clone saw before GitHub merged
    tip = git(backend, "rev-parse", "HEAD").strip()
    git(backend, "switch", "-q", "development")
    git(backend, "branch", "-q", "-D", "github")
    answer({"state": "MERGED", "baseRefName": "development", "mergeCommit": {"oid": tip},
            "commits": [{"oid": oid, "messageHeadline": subject, "authoredDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(at)))}
                        for oid, at, subject in commits]}, backend, number)
    return theirs, tip


def answer(said: dict, backend: Path, number: int = 7) -> None:
    """What the fake `gh pr view` says for helferline/Backend#<number>."""
    (backend.parent.parent / "bin" / "gh.answers" / f"helferline_Backend_{number}.json").write_text(json.dumps(said))


def only_read(toy: Path) -> None:
    """`tickets-land-in-listed-repos#P7`: every call of `gh` was a read: review's `pr view`, and the
    query of the board it renders."""
    calls = (toy.parent / "bin" / "gh.calls").read_text().splitlines()
    assert any(call.startswith("pr view ") for call in calls), calls
    assert all(call.startswith(("pr view ", "api graphql -f query=query ")) for call in calls), calls


def round_ranges(toy: Path) -> list[str]:
    """warm-preset's code and agent ranges as `on_github` built them: each a commit on its ticket
    branch. Read before the review whose `done` deletes those branches."""
    return [f"{name}@{git(top, 'rev-parse', 'ticket/warm-preset~1').strip()}..{git(top, 'rev-parse', 'ticket/warm-preset').strip()}"
            for name, top in (("code", toy), ("agent", toy / "agent"))]


def test_a_squashed_pull_requests_commit_is_the_tickets_range_there_and_the_ticket_reaches_done(toy: Path) -> None:
    """The squash is one commit on `development`, and the ticket's two commits on no branch there:
    the review after it records `Backend@<merge>^..<merge>`, which no branch could give it, deletes
    the ticket branch the pull request carried, records the code and agent repos' ranges, writes
    `done`, which the tracker's done check allows, and renders the page over what landed in place of
    the one it rendered before. Origin's refs are as GitHub left them."""
    backend = on_github(toy)
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "review", "the pull request is open"
    assert "helferline/Backend#7 is open and not merged" in said.stderr, said.stderr
    code, agent = (git(top, "rev-parse", "ticket/warm-preset~1", "ticket/warm-preset").split() for top in (toy, toy / "agent"))
    fork = git(backend, "rev-parse", "development").strip()
    assert pages(toy) == [f"{toy}@{code[0]}..{code[1]} {backend}@{fork}..{git(backend, 'rev-parse', 'ticket/warm-preset').strip()}"]

    theirs, merge = merged_on_github(backend, "squash")
    origin = git(toy.parent / "Backend.git", "for-each-ref")
    done = run(toy, "review", "warm-preset")
    assert done.returncode == 0, done.stderr
    only_read(toy)
    assert git(toy.parent / "Backend.git", "for-each-ref") == origin
    assert status_of(toy, "warm-preset") == "done"
    assert ranges_of(toy, "warm-preset") == [f"Backend@{theirs}..{merge}", f"code@{code[0]}..{code[1]}",
                                            f"agent@{agent[0]}..{agent[1]}"]
    assert not git(backend, "branch", "--list", "ticket/warm-preset")
    assert pages(toy)[-1] == f"{backend}@{theirs}..{merge} {toy}@{code[0]}..{code[1]}"


def test_a_review_asks_github_nothing_once_every_listed_branch_has_merged(toy: Path) -> None:
    """Backend's branch merged --no-ff into `development` here, as in max's own repos: the ticket
    names a pull request all the same, and the review that writes `done` reads it off the merge and
    calls no `gh pr view`."""
    backend = on_github(toy)
    fork, tip = git(backend, "rev-parse", "development", "ticket/warm-preset").split()
    merged_in(backend, "development", "ticket/warm-preset")
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert f"Backend@{fork}..{tip}" in ranges_of(toy, "warm-preset")
    calls = toy.parent / "bin" / "gh.calls"
    assert not calls.exists() or "pr view" not in calls.read_text()


def test_a_rebase_merges_commits_replace_the_range_the_ticket_recorded_there(toy: Path) -> None:
    """A rebase merge puts the ticket's two commits on `development` as new commits: the range the
    ticket recorded in Backend, from the fork to the ticket's tip, is replaced where it stood by the
    two rebased ones, and the code repo's range beside it stays."""
    backend = on_github(toy)
    fork, tip = git(backend, "rev-parse", "development", "ticket/warm-preset").split()
    code = f"code@{git(toy, 'rev-parse', 'ticket/warm-preset~1').strip()}..{git(toy, 'rev-parse', 'ticket/warm-preset').strip()}"
    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("gh: [", f"diff: [Backend@{fork}..{tip}, {code}]\ngh: [", 1))
    git(toy / "agent", "commit", "-q", "-am", "warm-preset's ranges, by hand")

    theirs, merge = merged_on_github(backend, "rebase")
    assert git(backend, "rev-parse", f"{merge}~2").strip() == theirs
    agent = round_ranges(toy)[1]
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    only_read(toy)
    assert ranges_of(toy, "warm-preset") == [f"Backend@{theirs}..{merge}", code, agent]
    assert status_of(toy, "warm-preset") == "done"
    assert not git(backend, "branch", "--list", "ticket/warm-preset")
    assert pages(toy)[-1] == f"{backend}@{theirs}..{merge} {toy}@{code.partition('@')[2]}"


def test_a_pull_request_merged_with_a_merge_commit_is_recorded_as_its_branch(toy: Path) -> None:
    """A merge commit brings the ticket's own commits in as they were: the review reads origin's
    `development`, which now holds the ticket branch, records Backend's range from its fork, and
    writes `done`."""
    backend = on_github(toy)
    fork, tip = git(backend, "rev-parse", "development", "ticket/warm-preset").split()
    assert run(toy, "review", "warm-preset").returncode == 0
    merged_on_github(backend, "merge")
    done = run(toy, "review", "warm-preset")
    assert done.returncode == 0, done.stderr
    only_read(toy)
    assert "merge commit" in done.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert f"Backend@{fork}..{tip}" in ranges_of(toy, "warm-preset")


def test_a_ticket_branch_holding_commits_its_pull_request_did_not_carry_stays(toy: Path) -> None:
    """A commit made on the ticket branch after its pull request merged never reached GitHub: the
    range is still the squash's, the branch keeps that commit, the ticket stays in `review`, and the
    exit status says done waits."""
    backend = on_github(toy)
    theirs, merge = merged_on_github(backend, "squash")
    _, later = built_on(backend, "ticket/warm-preset", "", "warmest.py")
    said = run(toy, "review", "warm-preset")
    assert said.returncode != 0
    assert "holds commits its pull request did not carry" in said.stderr, said.stderr
    assert git(backend, "rev-parse", "ticket/warm-preset").strip() == later
    assert ranges_of(toy, "warm-preset") == [f"Backend@{theirs}..{merge}"]
    assert status_of(toy, "warm-preset") == "review"


def test_a_pull_request_not_merged_and_one_in_no_listed_repo_change_nothing_and_say_why(toy: Path) -> None:
    """An open pull request is every review before the team merges: Backend's record and branch stay
    as they are and the ticket waits in `review`. A reference to a repo the project does not list is
    said and asks GitHub nothing."""
    backend = on_github(toy, gh="helferline/Backend#7, helferline/Helix#3")
    tip = git(backend, "rev-parse", "ticket/warm-preset").strip()
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    only_read(toy)
    assert "helferline/Backend#7 is open and not merged" in said.stderr, said.stderr
    assert "helferline/Helix#3 is in no repo" in said.stderr, said.stderr
    assert "helferline/Helix" not in (toy.parent / "bin" / "gh.calls").read_text()
    assert status_of(toy, "warm-preset") == "review"
    assert ranges_of(toy, "warm-preset") == []
    assert git(backend, "rev-parse", "ticket/warm-preset").strip() == tip


@pytest.mark.parametrize("url", ["git@github.com:helferline/Backend.git", "https://github.com/Helferline/backend",
                                 "ssh://git@github.com/helferline/Backend.git/"])
def test_a_pull_request_is_read_in_the_repo_whose_origin_github_names_in_any_form(toy: Path, url: str) -> None:
    """GitHub's three forms of a repo's URL, and an owner or a repo spelled in another case than
    `gh:` spells it, all name helferline/Backend."""
    backend = on_github(toy, url=url)
    theirs, merge = merged_on_github(backend, "squash")
    rounds = round_ranges(toy)
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert ranges_of(toy, "warm-preset") == [f"Backend@{theirs}..{merge}", *rounds]


def test_a_merge_origin_does_not_hold_and_a_pull_request_github_does_not_answer_change_nothing(toy: Path) -> None:
    """#7 is reported merged as a commit `development` at origin does not hold, and GitHub answers
    nothing for #8: Backend's record and branch stay as they are, each is said, the ticket waits in
    `review`, and the exit status is nonzero."""
    backend = on_github(toy, gh="helferline/Backend#7, helferline/Backend#8")
    tip = git(backend, "rev-parse", "ticket/warm-preset").strip()
    _, nowhere = built_on(backend, "nowhere", "development", "nowhere.py")
    answer({"state": "MERGED", "baseRefName": "development", "mergeCommit": {"oid": nowhere}, "commits": []}, backend)
    said = run(toy, "review", "warm-preset")
    assert said.returncode != 0
    only_read(toy)
    assert f"merge {nowhere} is not on development as origin has it" in said.stderr, said.stderr
    assert "GitHub did not answer for helferline/Backend#8" in said.stderr, said.stderr
    assert ranges_of(toy, "warm-preset") == []
    assert status_of(toy, "warm-preset") == "review"
    assert git(backend, "rev-parse", "ticket/warm-preset").strip() == tip


def test_a_merge_commits_range_stands_beside_a_squash_in_the_same_repo(toy: Path) -> None:
    """Two pull requests in Backend: #7 squashed, #8 merged with a merge commit. Backend's record
    becomes both: the squash, and the commits #8's merge brought in."""
    backend = on_github(toy, gh="helferline/Backend#7, helferline/Backend#8")
    theirs, squash = merged_on_github(backend, "squash")
    git(backend, "fetch", "-q", "origin")
    _, other = built_on(backend, "other", "origin/development", "other.py")
    git(backend, "switch", "-q", "-c", "github", "origin/development")
    git(backend, "merge", "-q", "--no-ff", "-m", "Merge pull request #8", "other")
    git(backend, "push", "-q", "origin", "github:development")
    merge = git(backend, "rev-parse", "HEAD").strip()
    git(backend, "switch", "-q", "development")
    answer({"state": "MERGED", "baseRefName": "development", "mergeCommit": {"oid": merge},
            "commits": [{"oid": other, "messageHeadline": "other", "authoredDate": AUTHORED[0]}]}, backend, 8)
    rounds = round_ranges(toy)
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert ranges_of(toy, "warm-preset") == [f"Backend@{theirs}..{squash}", f"Backend@{squash}..{other}", *rounds]


def test_a_parents_squashed_pull_request_lands_it_and_the_tickets_under_it_on_its_accept(toy: Path) -> None:
    """lamp-ui is warm-preset's parent. warm-preset's Backend branch merged into lamp-ui's there, its
    range recorded as the review of that merge writes it, and lamp-ui's own branch, named by its
    slug as dispatch cuts a parent's, went to GitHub as #9 and was squashed. The parent's accept
    records the squash on both tickets, deletes both branches, which the done check reads, and writes
    both `done`s."""
    backend = on_github(toy)
    agent = toy / "agent"
    fork, tip = git(backend, "rev-parse", "development", "ticket/warm-preset").split()
    git(backend, "branch", "lamp-ui", "development")
    merged_in(backend, "lamp-ui", "ticket/warm-preset")
    for slug, front in (("warm-preset", f"status: review\ndiff: [Backend@{fork}..{tip}]"),
                        ("lamp-ui", "status: review\nrepos: [Backend]\ngh: [helferline/Backend#9]")):
        path = tracked(toy) / f"{slug}.md"
        path.write_text(re.sub(r"status: \w+", front, path.read_text(), count=1))
    git(agent, "commit", "-q", "-am", "the tree, for its ruling")
    theirs, merge = merged_on_github(backend, "squash", 9, branch="lamp-ui")

    built_on(toy, "lamp-ui", "main", "ui.txt")
    merged_in(toy, "main", "lamp-ui")
    accepted = run(toy, "accept", "lamp-ui")
    assert accepted.returncode == 0, accepted.stderr
    only_read(toy)
    assert not git(backend, "branch", "--list", "lamp-ui", "ticket/warm-preset")
    landed = lambda slug: git(agent, "show", f"HEAD~1:tickets/{slug}.md")  # noqa: E731  # retired since
    for slug in ("lamp-ui", "warm-preset"):
        assert "status: done" in landed(slug), slug
        assert f"Backend@{theirs}..{merge}" in landed(slug), slug
    assert f"Backend@{fork}..{tip}" not in landed("warm-preset")


@pytest.mark.full_path
def test_a_ticket_whose_branch_in_a_listed_repo_landed_as_a_squash_retires_its_run_on_the_host(
        toy: Path, staged: Path) -> None:
    """Backend's branch was squashed into `development` here and deleted, its range the squash,
    recorded by hand; the host still holds Backend for the ticket. The `done` retires the run all
    the same, since Backend is a repo the ticket names and its round has landed."""
    repos = staged_listed(toy)
    (staged.parent / "run-worker.sh").write_text(BUILDING_LISTED)
    remote, env = fake_remote(toy)
    hosted = remote / "repos" / "dispatch"
    state = remote / ".local" / "state" / "dispatch" / "lamp-main"
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, state)
    for command in ("fetch", "review"):
        said = subprocess.run([str(staged), command, "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
        assert said.returncode == 0, said.stderr
    for top in (toy, toy / "agent", repos["jarvis"]):
        merged_in(top, "main", "ticket/warm-preset")
    backend = repos["Backend"]
    fork = git(backend, "rev-parse", "development").strip()
    git(backend, "merge", "-q", "--squash", "ticket/warm-preset")
    git(backend, "commit", "-q", "-m", "Warm preset (#7)")
    git(backend, "branch", "-q", "-D", "ticket/warm-preset")
    squash = git(backend, "rev-parse", "HEAD").strip()
    subprocess.run([str(SKILL.parent / "tracker" / "tracker.py"), "set", "warm-preset", f"diff+=Backend@{fork}..{squash}"],
                   cwd=toy, check=True, capture_output=True)
    git(toy / "agent", "commit", "-q", "-am", "warm-preset: the range that landed in Backend")
    (toy / "agent" / "diffviews" / "warm-preset.html").unlink()  # the page over what landed is a new one

    landed = subprocess.run([str(staged), "review", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert not (hosted / "lamp-warm-preset").exists()
    assert not (hosted / "jarvis-warm-preset").exists()


def test_a_review_over_what_landed_leaves_a_page_it_did_not_render_as_it_is_and_says_so(toy: Path) -> None:
    """A page at the ticket's path showing a source neither the review before the landing nor the
    one after it renders, one a session rendered by hand: the review records what landed, writes
    `done`, leaves that page, and the exit status says so."""
    backend = on_github(toy)
    assert run(toy, "review", "warm-preset").returncode == 0
    page = toy / "agent" / "diffviews" / "warm-preset.html"
    page.write_text('{"sources": [{"spec": "/elsewhere@1234567..89abcde"}]}\n')
    theirs, merge = merged_on_github(backend, "squash")
    rounds = round_ranges(toy)
    said = run(toy, "review", "warm-preset")
    assert said.returncode != 0
    assert "leaves that page as it is" in said.stderr, said.stderr
    assert ranges_of(toy, "warm-preset") == [f"Backend@{theirs}..{merge}", *rounds]
    assert status_of(toy, "warm-preset") == "done"
    assert page.read_text() == '{"sources": [{"spec": "/elsewhere@1234567..89abcde"}]}\n'


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
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


@pytest.mark.full_path
def test_a_commit_hook_the_agent_repo_already_has_is_its_owners(toy: Path, staged: Path) -> None:
    """On a local host the agent repo is the user's own checkout, and a hook in it stays as it was."""
    theirs = toy / "agent" / ".git" / "hooks" / "pre-commit"
    theirs.write_text("#!/bin/sh\nexit 0\n")
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode == 0, said.stdout + said.stderr
    assert theirs.read_text() == "#!/bin/sh\nexit 0\n"
    assert "is not the tracker's" in said.stderr, said.stderr


STALE_JOB = "#!/bin/sh\necho stale\n"
CURRENT_JOB = "#!/bin/sh\necho current\n"


def init_with_job(toy: Path, job_dir: Path, fetch_fails: bool = False, on_path: str = "") -> subprocess.CompletedProcess:
    """`dispatch-ctl init` on a host whose first `job` on PATH is a stale one in `job_dir`, behind a
    `curl` that serves CURRENT_JOB, or fails as an unreachable network does. `on_path` is how PATH
    spells `job_dir`, itself unless given."""
    scratch = toy.parent / "scratch"
    scratch.mkdir()
    shutil.copy(SKILL / "dispatch-ctl", scratch / "dispatch-ctl")
    shutil.copy(SKILL.parent / "tracker" / "pre-commit", scratch / "pre-commit")
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job").write_text(STALE_JOB)
    (job_dir / "job").chmod(0o755)
    fakes = toy.parent / "fakes"
    fakes.mkdir()
    served = toy.parent / "served-job"
    served.write_text(CURRENT_JOB)
    curl = "exit 22" if fetch_fails else f'while [ "$1" != -o ]; do shift; done; cp "{served}" "$2"'
    (fakes / "curl").write_text(f"#!/bin/sh\n{curl}\n")
    (fakes / "curl").chmod(0o755)
    env = environment(toy)
    env["PATH"] = f"{on_path or job_dir}:{fakes}:{env['PATH']}"
    repos = toy.parent / "repos"
    return subprocess.run(["bash", str(scratch / "dispatch-ctl"), "init", "lamp", "main", str(repos / "lamp.git"),
                           str(repos), str(repos / "lamp-agent.git"), "main"],
                          capture_output=True, text=True, env=env, timeout=60)


@pytest.mark.parametrize("spelling", ["as HOME spells it", "through a symlink"])
def test_init_brings_the_job_it_fetched_current(toy: Path, spelling: str) -> None:
    """`dispatch-init-refreshes-fetched-job`: a host whose `job` is the copy at ~/.local/bin/job
    has the current one after `init`, however PATH spells that directory."""
    fetched = toy.parent / "home" / ".local" / "bin"
    on_path = {"as HOME spells it": "", "through a symlink": str(toy.parent / "linked-bin")}[spelling]
    if spelling == "through a symlink":
        (toy.parent / "linked-bin").symlink_to(fetched)
    said = init_with_job(toy, fetched, on_path=on_path)
    assert said.returncode == 0, said.stderr
    assert (fetched / "job").read_text() == CURRENT_JOB
    assert os.access(fetched / "job", os.X_OK)


def test_init_leaves_a_job_elsewhere_on_path_alone(toy: Path) -> None:
    """`dispatch-init-refreshes-fetched-job`: home-manager's `job` on the orchestrator's machine is
    not dispatch's to replace."""
    elsewhere = toy.parent / "nix-profile" / "bin"
    said = init_with_job(toy, elsewhere)
    assert said.returncode == 0, said.stderr
    assert (elsewhere / "job").read_text() == STALE_JOB
    assert not (toy.parent / "home" / ".local" / "bin" / "job").exists()


def test_init_that_cannot_fetch_job_keeps_the_copy_it_has_and_says_so(toy: Path) -> None:
    """`dispatch-init-refreshes-fetched-job`: the copy a failed fetch leaves still runs the wait loop."""
    fetched = toy.parent / "home" / ".local" / "bin"
    said = init_with_job(toy, fetched, fetch_fails=True)
    assert said.returncode == 0, said.stderr
    assert (fetched / "job").read_text() == STALE_JOB
    assert "could not fetch job" in said.stderr, said.stderr
    assert sorted(p.name for p in fetched.iterdir()) == ["job"]


def test_dispatch_ctl_help_needs_no_repo(tmp_path: Path) -> None:
    """`dispatch --help` names `dispatch ctl --help` as dispatch-ctl's reference, and the skill
    renders it on load wherever the session is."""
    first = (SKILL / "dispatch-ctl").read_text().splitlines()[1].removeprefix("# ")
    for args in (["ctl", "--help"], ["ctl"]):
        said = subprocess.run([str(DISPATCH), *args], cwd=tmp_path, capture_output=True, text=True)
        assert said.returncode == 0, said.stderr
        assert said.stdout.startswith(first), said.stdout


@pytest.mark.parametrize(("script", "budget"), [("dispatch", 600), ("dispatch-ctl", 400)])
def test_each_help_states_the_interface_within_its_budget(script: str, budget: int) -> None:
    """`/mx:dispatch` loads both helps into every dispatcher's context, so each holds what a
    dispatcher acts on, in at most `budget` words as `wc -w` counts them; the mechanism is in
    comments at the code."""
    said = subprocess.run([str(SKILL / script), "--help"], capture_output=True, text=True)
    assert said.returncode == 0, said.stderr
    words = subprocess.run(["wc", "-w"], input=said.stdout, capture_output=True, text=True, check=True)
    assert int(words.stdout) <= budget, f"{script} --help is {words.stdout.strip()} words"


@pytest.mark.full_path
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


@pytest.mark.full_path
def test_push_brings_both_repos_tips_to_the_host_a_run_is_on(toy: Path, staged: Path) -> None:
    """What a worker resumed to rebase is rebasing onto: this branch's tip in each repo, on its host."""
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    for at in (toy, toy / "agent"):
        (at / "moved.md").write_text("the branch moved\n")
        git(at, "add", "moved.md")
        git(at, "commit", "-q", "-m", "the branch moved")

    pushed = subprocess.run([str(staged), "push"], cwd=toy, capture_output=True, text=True, env=env, timeout=120)

    assert pushed.returncode == 0, pushed.stderr
    bare = remote / "repos" / "dispatch"
    assert git(bare / "lamp.git", "rev-parse", "main") == git(toy, "rev-parse", "main")
    assert git(bare / "lamp-agent.git", "rev-parse", "main") == git(toy / "agent", "rev-parse", "main")


@pytest.mark.full_path
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
