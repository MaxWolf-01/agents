# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml"]
# ///
"""Checks for what `dispatch` and `dispatch-ctl` read and write on a ticket. Run: pytest test_dispatch.py

One seam: the two scripts' command lines, run as subprocesses over a toy project whose worker is a
stub on the `DISPATCH_RUNNER` seam dispatch-ctl documents, so what runs is dispatch and dispatch-ctl
themselves. The toy is a project in the layout every project has: a code repo, and its `agent/` a
git repo of its own inside it that the code repo ignores. The oracles are
`agent/tickets/ticket-file-contract.md` (P4, that a worker's prompt is the ticket's body with every
ancestor's, assembled by the one function; P7, that a worker writes no ticket file and reports
instead; `needs-user` as the one field that keeps a ticket from a worker) and `/mx:tracker`'s Ticket
state (a claim is taken from the frontier, and a claimed ticket is in somebody's hands). A ticket's
ranges are read back through the tracker module, as `tracker data` prints them (`ranges_of`): the
read is the oracle's, not the seam's, and in process it costs no tracker launch per check.

A second seam is `dispatch`'s own functions, the script sourced, for those whose input and output
are text: the run record (`host_of`, `runs_on`, `hosts_used`, `forget_run`), `scratch_dir`,
and `remote_line`, each held to the comment above it. The placer and the slots are the worker
hosts' own (`worker-hosts --place`, `host-slots`, in the dotfiles), each tested there; here they are
stand-ins, and what is checked is what dispatch asks of them and does with their answer.
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
from hypothesis import example, given, settings
from hypothesis import strategies as st

import tracker
from dispatch_checks import mx, stage_runner

SKILL = Path(__file__).parent
DISPATCH = SKILL / "dispatch"

# Git with no configuration of the machine's, for the commits a check makes and the ones dispatch makes in
# it: a hook or a setting of whoever runs the checks would write into the toy's history, which the board reads.
HERMETIC_GIT = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "maintenance.auto", "GIT_CONFIG_VALUE_0": "false"}
# Read before any check moves HOME: uv keeps its cache under HOME unless told otherwise, and a
# fresh cache puts a full dependency install in front of every tracker and board a check runs.
UV_CACHE = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()

# A worker as dispatch-ctl leaves the seam for one: argv and the log-then-status contract are the
# real runner's, and it keeps the prompt it was sent and the context file its worker would read, so
# the check can read what a round carried.
RUNNER = """#!/usr/bin/env bash
set -eu
message=$1 slug=$2 run_id=$4
state=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cp "$message" "$state/$run_id.prompt"
cp "$DISPATCH_CONTEXT" "$state/$run_id.context"
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
# the remote shell, run in the remote user's home, without the settings dispatch forwards on that
# line, which the caller's environment never carries across. scp copies into that home the same way.
# A host's login shell may be zsh, which reads some words apart from bash (`remote_line`), so where
# zsh is installed a line the two read as different words is refused, as one of the two hosts would
# fail it; where zsh is not, `test_a_remote_line_reaches_the_command_as_the_words_sent` says so.
FAKE_SSH = """#!/usr/bin/env bash
while [[ ${1:-} == -* ]]; do case $1 in -o|-p|-i|-l) shift 2 ;; *) shift ;; esac; done
shift
unset DISPATCH_EFFORT DISPATCH_PERMISSION_MODE DISPATCH_RUNNER
words() { "$@" "printf '%s\\0' $line" 2>&1 < /dev/null; }
line=$*
if command -v zsh > /dev/null && ! cmp -s <(words bash -c) <(words zsh -f -c); then
    echo "ssh: a zsh login shell reads this line as other words than bash does: $line" >&2
    exit 255
fi
cd "$REMOTE_HOME" && HOME=$REMOTE_HOME exec bash -c "$*"
"""
HOST_SLOTS = r"""#!/bin/sh
case $1 in take) pid=$2 word=$3 ;; hand) pid=$3 word=$4 ;; *) echo "0 1"; exit 0 ;; esac
if [ "$1" = take ] && [ -e "$HOME/slots-full" ]; then
    echo "take full" >> "$HOME/host-slots.calls"
    echo "host-slots: no slot free on this machine: 1 of 1 held" >&2
    exit 3
fi
tr '\0' ' ' < "/proc/$pid/cmdline" | grep -qF -- "$word" && how=carried || how="lacks $word"
echo "$1 $how" >> "$HOME/host-slots.calls"
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
        capture_output=True, text=True, env=HERMETIC_GIT,
    )
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout


def ticket(root: Path, slug: str, status: str = "open", parent: str = "", needs_user: bool = False,
           brief: str = "What it is, cold.", blocked_by: str = "") -> Path:
    front = ["---", f"status: {status}"]
    front += [f"parent: {parent}"] if parent else []
    front += [f"blocked-by: [{blocked_by}]"] if blocked_by else []
    front += ["needs-user: true"] if needs_user else []
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
    socket = tmux_dir(repo) / f"tmux-{os.getuid()}" / "default"
    if socket.exists():
        # Named by its socket and run outside the check's environment: a tmux guard that reads
        # TMUX_TMPDIR takes the default socket under it for the user's own server and refuses.
        subprocess.run(["tmux", "-S", str(socket), "kill-server"], capture_output=True)
        for _ in range(20):
            if subprocess.run(["tmux", "-S", str(socket), "list-sessions"], capture_output=True).returncode:
                break
            time.sleep(0.1)
        else:
            # The socket stays, since it is the only handle left on that server.
            pytest.fail(f"the check's tmux server outlived its kill-server: tmux -S {socket} kill-server")
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
    # A board that draws nothing and keeps what it was asked to draw (`boards`), since no check reads
    # the page, unless the check put the real one there (`on_github`).
    if not (bin_dir / "board").exists():
        (bin_dir / "board").write_text(f'#!/bin/sh\necho "$*" >> "{bin_dir / "board.calls"}"\n')
        (bin_dir / "board").chmod(0o755)
    # A register that publishes no host, so no check reads the machine's own, unless the check put
    # one there (`placer`).
    if not (bin_dir / "worker-hosts").exists():
        (bin_dir / "worker-hosts").write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / "worker-hosts").chmod(0o755)
    # The machine's slots are the check's own, never this machine's: a take is refused while
    # $HOME/slots-full exists, and each call is kept in $HOME/host-slots.calls with whether the
    # process it names carries its word, which is how the real one tells a live holder.
    (bin_dir / "host-slots").write_text(HOST_SLOTS)
    (bin_dir / "host-slots").chmod(0o755)
    (toy.parent / "home").mkdir(exist_ok=True)
    plugin = mx(toy.parent)
    tmux_dir(toy).mkdir(exist_ok=True)
    env = {**HERMETIC_GIT, "HOME": str(toy.parent / "home"), "UV_CACHE_DIR": UV_CACHE,
           "JOB_STATE_DIR": str(toy.parent / "jobs"), "TMUX_TMPDIR": str(tmux_dir(toy)),
           "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "DISPATCH_PLUGIN_DIR": str(plugin), **extra}
    env.pop("DISPATCH_PERMISSION_MODE", None)
    env.pop("DISPATCH_EFFORT", None)
    # A project's .envrc sets it, and every placement check here but one reads the personal account.
    "DISPATCH_ACCOUNT" in extra or env.pop("DISPATCH_ACCOUNT", None)
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
    """The ticket's `diff:` ranges, as `tracker data` prints them."""
    read = tracker.tracker_of(tracker.tracker_root(toy))
    return tracker.as_data(read.ticket(slug), read)["diff"]


def rule_open(toy: Path, slug: str, env: dict[str, str] | None = None) -> None:
    """Every question the ticket holds open, ruled as the user's accept answers it: a `done` waits
    for that, and the checks that reach one are about something else."""
    tracker_py = str(SKILL.parent / "tracker" / "tracker.py")
    read = tracker.tracker_of(tracker.tracker_root(toy))
    for asked in (one for one in read.ticket(slug).questions if not one.ruled):
        subprocess.run([tracker_py, "rule", slug, asked.tag, "accepted"], cwd=toy, check=True, capture_output=True,
                       env=env or environment(toy))


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
def runner(tmp_path: Path) -> Path:
    """The shipped runner staged in a state dir, the message a spawn hands it, and an empty bin dir
    for the `claude` a check stubs. Answers the state dir; `run_worker` starts what it staged."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    (tmp_path / "bin").mkdir()
    return state


def run_worker(state: Path, *args: str, claude: str = "", run_id: str = "run-1", model: str = "opus",
               cwd: Path | None = None, **env: str | None) -> subprocess.CompletedProcess:
    """The runner `runner` staged, started on its message as a spawn starts it, for warm-preset, with
    `args` after the run id. `claude` is the stub put first on PATH, FAKE_CLAUDE recording to
    `bin/claude.calls` unless given. HOME is the check's temp dir, DISPATCH_PLUGIN_DIR a fresh mx
    install and DISPATCH_EFFORT unset, unless `env` says otherwise; a None in it unsets the variable."""
    tmp_path = state.parent
    bin_dir = tmp_path / "bin"
    (bin_dir / "claude").write_text(claude or FAKE_CLAUDE.replace("CALLS", str(bin_dir / "claude.calls")))
    (bin_dir / "claude").chmod(0o755)
    environ = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)}
    environ.pop("DISPATCH_EFFORT", None)  # whatever the shell running these checks carries
    if "DISPATCH_PLUGIN_DIR" not in env:
        environ["DISPATCH_PLUGIN_DIR"] = str(mx(tmp_path))
    for key, value in env.items():
        if value is None:
            environ.pop(key, None)
        else:
            environ[key] = value
    return subprocess.run(
        ["bash", str(state / "run-worker.sh"), str(tmp_path / "message.md"), "warm-preset", model, run_id, *args],
        cwd=cwd or tmp_path, capture_output=True, text=True, timeout=120, env=environ)


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


def context_of(toy: Path, slug: str) -> str:
    """`tracker context <slug>` as the orchestrator's tracker prints it now: what
    `rounds-read-a-staged-context` holds a round's worker and reviewer to, byte for byte."""
    said = subprocess.run([str(SKILL.parent / "tracker" / "tracker.py"), "context", slug], cwd=toy,
                          capture_output=True, text=True, env=environment(toy), check=True)
    return said.stdout


def resume(toy: Path, staged: Path, slug: str, message: str) -> Path:
    """`message` written as the guidance and the run resumed on this machine: the new run's id, once
    its status line is there."""
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    before = set(state.glob("*.status"))
    # A run id is the second it started in, so a resume within the second of the run before it
    # would write over that run's files.
    time.sleep(max(0.0, max(int(one.stem.rsplit("-", 1)[1]) for one in before) + 1 - time.time()))
    subprocess.run([str(staged), "prompt", slug], cwd=toy, input=message, text=True, check=True, env=environment(toy))
    resumed = subprocess.run([str(staged), "ctl", "resume", slug, "sonnet"],
                             cwd=toy, capture_output=True, text=True, timeout=180, env=environment(toy))
    assert resumed.returncode == 0, resumed.stderr
    for _ in range(60):
        if new := set(state.glob("*.status")) - before:
            return state / next(iter(new)).stem
        time.sleep(0.5)
    raise AssertionError("no status line 30s after the resume")


@pytest.mark.full_path
def test_a_spawn_starts_the_worker_on_its_tickets_context_with_the_orchestrators_message_under_it(
    toy: Path, staged: Path
) -> None:
    """`ticket-file-contract#P4`'s worker half: what the worker reads is the ticket's body and every
    ancestor's, as `tracker context` assembles them, then the round's message, and the first round
    opens on that file."""
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n")
    assert said.returncode == 0, said.stderr
    run_id = waited(toy).with_suffix("")
    read = run_id.with_suffix(".context").read_text()
    assert read == context_of(toy, "warm-preset") + "\n## this round's message\n\nWork the ticket warm-preset.\n"
    assert read.index("One preset, warm.") < read.index("The whole of giving the lamp presets.") < read.index("Work the ticket")
    assert run_id.with_suffix(".prompt").read_text() == read


@pytest.mark.full_path
def test_a_resumed_worker_reads_its_ticket_as_amended_since_its_last_round(toy: Path, staged: Path) -> None:
    """`rounds-read-a-staged-context`: a ticket amended between rounds reaches the resumed worker
    with no push and no pasted text. Its message says so at the top while the context is new to
    it, and is the guidance alone once it is not."""
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    waited(toy)
    amended = tracked(toy) / "warm-preset.md"
    amended.write_text(amended.read_text().replace("One preset, warm.", "One preset, warm, at 2700K."))
    git(toy / "agent", "commit", "-q", "-am", "warm-preset: the temperature, ruled")

    changed = resume(toy, staged, "warm-preset", "continue\n")

    read = changed.with_suffix(".context").read_text()
    assert read == context_of(toy, "warm-preset") + "\n## this round's message\n\ncontinue\n"
    assert "at 2700K" in read
    sent = changed.with_suffix(".prompt").read_text()
    assert sent.startswith("Your ticket's context changed since your last round") and sent.endswith("\n\ncontinue\n")

    unchanged = resume(toy, staged, "warm-preset", "continue\n")
    assert unchanged.with_suffix(".prompt").read_text() == "continue\n"
    assert unchanged.with_suffix(".context").read_text() == read

    # A run staged by a dispatch that kept no record of the context it was given.
    (toy / ".git" / "dispatch" / "prompts" / "main" / "round" / "ticket-warm-preset.md").unlink()
    unrecorded = resume(toy, staged, "warm-preset", "continue\n").with_suffix(".prompt").read_text()
    assert unrecorded.startswith("Your ticket's context may have changed since your last round")
    assert unrecorded.endswith("\n\ncontinue\n")


@pytest.mark.full_path
def test_a_resume_stages_a_host_another_plugin_version_staged(toy: Path, staged: Path) -> None:
    """A resumed round runs on the contract and the dispatch-ctl of the orchestrator resuming it, as
    a spawned one does: an older contract would point the worker at no context file."""
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    scratch = waited(toy).parent
    (scratch / "stamp").write_text("an older version's\n")
    (scratch / "worker-prompt.md").write_text("An older contract, which names no context file.\n")

    resume(toy, staged, "warm-preset", "continue\n")

    assert (scratch / "worker-prompt.md").read_text() == (staged.parent / "worker-prompt.md").read_text()


@pytest.mark.full_path
def test_a_resumed_rounds_context_names_the_listed_repos_its_spawn_cut(toy: Path, staged: Path) -> None:
    """The worker is sent back to its context file whole, so a resumed round's file says where its
    listed repos are as the spawn's did."""
    staged_listed(toy)
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)

    read = resume(toy, staged, "warm-preset", "continue\n").with_suffix(".context").read_text()

    assert read.startswith(context_of(toy, "warm-preset") + "\n## this round's message\n\ncontinue\n")
    assert "- Backend: `Backend/` in your worktree, from `development`" in read
    assert "- jarvis: `../jarvis-warm-preset`, beside your worktree" in read


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
def test_the_effort_set_in_the_orchestrators_environment_reaches_a_remote_host(toy: Path, staged: Path) -> None:
    """`dispatch-forwards-effort`: `DISPATCH_EFFORT=medium dispatch ctl spawn` started five workers at
    high, since ssh carries none of the caller's environment to the host."""
    (staged.parent / "run-worker.sh").write_text(RUNNER.replace(
        "printf 'stub: built %s\\n' \"$slug\"", "printf 'stub: built %s at %s\\n' \"$slug\" \"${DISPATCH_EFFORT:-unset}\""))
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env={**env, "DISPATCH_EFFORT": "medium"})
    state = waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main").parent
    assert said.returncode == 0, said.stderr
    assert "effort=medium" in said.stdout, said.stdout
    assert "stub: built warm-preset at medium" in "".join(p.read_text() for p in state.glob("*.log"))


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
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.prompt"))


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
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.prompt"))


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
                           capture_output=True, text=True, env=environment(toy))
    assert ruled.returncode == 0, ruled.stderr
    assert not git(agent, "status", "--porcelain", "--", "tickets"), "the ruling is committed"

    # the stub makes one commit in each repo, so its parent is what that branch was cut from; read
    # from git rather than from the ranges under test
    cut, tip = {}, {}
    for at, top in (("code", toy), ("agent", agent)):
        cut[at] = git(top, "rev-parse", "ticket/warm-preset~1").strip()
        tip[at] = git(top, "rev-parse", "ticket/warm-preset").strip()
    # the user's accept: the code merged by hand, and the rest in one command
    git(toy, "merge", "-q", "--no-ff", "-m", "warm-preset: landed", "ticket/warm-preset")
    landed = run(toy, "accept", "warm-preset")
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert git(agent, "log", "-1", "--format=%P", "HEAD~1").split()[1] == tip["agent"], "the agent branch merged by the accept"
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
    """`speculative-first`'s review unit through the toy: three child tickets in a chain, each built
    on the one before while that one waits unruled in its parent's branch, and the parent's accept
    writing `done` on all four. `speculative-first#P1`: nothing reaches `main`
    before the parent's accept."""
    tickets, agent = tracked(toy), toy / "agent"
    ticket(tickets, "preset-format", parent="lamp-ui", brief="The shape every preset is stored in.")
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
        """The orchestrator's read passed it: its code merged by hand, and the review merges its agent branch."""
        git(worktree, "merge", "-q", "--no-ff", "-m", f"{slug}: merged", f"ticket/{slug}")
        said = run(worktree, "review", slug)
        assert said.returncode == 0, said.stderr
        assert git(agent, "merge-base", "--is-ancestor", f"ticket/{slug}", "main") == ""

    assert "warm-preset" not in frontier()
    built("preset-format")
    assert "warm-preset" not in frontier(), "unmerged, the shape holds what builds on it"
    assert "on preset-format (review)" in frontier(held=True)
    merged("preset-format")  # the orchestrator's read passed it: the shape every preset reads waits for its parent's ruling too
    assert status_of(toy, "preset-format") == "review", "no child is ruled alone"

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

    for slug in ("preset-format", "warm-preset", "cool-preset"):
        rule_open(toy, slug, env)
    early = run(toy, "accept", "lamp-ui")
    assert early.returncode != 0 and "not merged into main" in early.stderr, early.stderr
    subprocess.run([str(staged.parent.parent / "tracker" / "tracker.py"), "set", "lamp-ui", "status=review"],
                   cwd=toy, check=True, capture_output=True, env=env)  # its close-out: the whole tree waits for the ruling
    git(toy, "merge", "-q", "--no-ff", "-m", "lamp-ui: accepted whole", "lamp-ui")
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
    for slug in ("preset-format", "warm-preset", "cool-preset"):
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


# The building stub's next round, resumed: more code, and a report of its own that numbers its
# tags from D1 again, as a worker reading a stale ticket would.
SECOND_ROUND = BUILDING.replace("the lamp, warm\\n", "the lamp, warm and dim\\n").replace(
    "The warm preset lands, unmerged, with one question under it.", "The preset dims too, on the same branch.").replace(
    "**Warm at what temperature?**", "**Dim to what?**")


@pytest.mark.full_path
def test_a_round_sent_back_before_its_review_keeps_its_report_beside_the_next(toy: Path, staged: Path) -> None:
    """`land-takes-a-round-whole`'s first two criteria through dispatch: the orchestrator's read sends
    round one back unreviewed, the resume brings its report in before the worker can write over it,
    and round two's lands beside it, its tags numbered past round one's."""
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    assert "report=yes" in waited(toy).read_text()

    (staged.parent / "run-worker.sh").write_text(SECOND_ROUND)
    resumed = resume(toy, staged, "warm-preset", "A test belongs under tests/properties/ no more: move it.\n")
    assert status_of(toy, "warm-preset") == "claimed", "the resumed build holds its ticket again"
    sent = resumed.with_suffix(".context").read_text()
    assert "The warm preset lands, unmerged" in sent, "round one reached the ticket the resumed round reads"
    for _ in range(60):
        if resumed.with_suffix(".status").exists():
            break
        time.sleep(0.5)
    else:
        pytest.fail("round two left no status line 30s after its resume")

    assert run(toy, "fetch", "warm-preset").returncode == 0
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    written = (tracked(toy) / "warm-preset.md").read_text()
    assert written.count("The warm preset lands, unmerged") == 1 and written.count("The preset dims too") == 1
    read = tracker.tracker_of(tracker.tracker_root(toy)).ticket("warm-preset")
    assert [(one.tag, one.headline) for one in read.questions] == [("D2", "Warm at what temperature?"), ("D4", "Dim to what?")]
    assert [one.id for one in read.assumptions] == [1, 2, 3, 4]
    assert len(read.meta["reports"]) == 2 and status_of(toy, "warm-preset") == "review"


@pytest.mark.full_path
def test_a_review_after_the_ticket_branches_were_deleted_lands_from_their_merges(toy: Path, staged: Path) -> None:
    """`land-takes-a-round-whole`'s fifth criterion: merged by hand, the run cleaned up and its
    branches gone with it, `dispatch review` reads each repo's tip off the merge that names it."""
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    agent = toy / "agent"
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work the ticket warm-preset.\n").returncode == 0
    waited(toy)
    assert run(toy, "fetch", "warm-preset").returncode == 0
    assert run(toy, "review", "warm-preset").returncode == 0
    rule_open(toy, "warm-preset")
    tips = {}
    for at, top in (("code", toy), ("agent", agent)):
        tips[at] = (git(top, "rev-parse", "ticket/warm-preset~1").strip(), git(top, "rev-parse", "ticket/warm-preset").strip())
        git(top, "merge", "-q", "--no-ff", "--no-edit", "ticket/warm-preset")
    assert run(toy, "ctl", "cleanup", "warm-preset").returncode == 0
    for top in (toy, agent):
        git(top, "branch", "-q", "-D", "ticket/warm-preset") if git(top, "branch", "--list", "ticket/warm-preset") else None

    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert ranges_of(toy, "warm-preset") == [f"{at}@{cut}..{tip}" for at, (cut, tip) in tips.items()]


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
    (False, False, 0, "attempts=2 exit=0 report=no"),
    (True, False, 0, "attempts=2 exit=0 report=no"),
    (True, True, 0, "attempts=1 exit=0 report=yes"),
])
def test_the_runner_reads_the_report_as_the_run_leaving_something_to_review(
    tmp_path: Path, runner: Path, already: bool, wrote: bool, exits: int, says: str
) -> None:
    """The shipped runner, with `claude` stubbed rather than the runner itself: a run whose worker
    committed its report in the agent repo is finished whatever it exited with, one that committed
    none says so on its status line. A clean exit with no report is an early stop, resumed once on
    the budget a crash spends; a second is the worker's own stop, as a blocker's is.

    A resumed round starts with the round before it still committed there, so what the status line
    reads is whether this run wrote that file, never whether the file is there."""
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

    committing = (
        'mkdir -p agent/show/warm-preset\n'
        'printf "## Comments\\n\\nit lands.\\n" > agent/show/warm-preset/report.md\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false add -A\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -q -m report\n'
    )
    claude = '#!/bin/sh\n[ "$1" = --version ] && exit 0\n' + (committing if wrote else "") + f"exit {exits}\n"

    done = run_worker(runner, claude=claude, model="sonnet", cwd=worktree)
    assert done.returncode == 0, done.stderr
    assert (runner / "run-1.status").read_text().startswith(says), (runner / "run-1.status").read_text()
    assert "runner: started warm-preset" in (runner / "run-1.log").read_text()


def test_a_worker_that_stops_early_is_resumed_until_it_reports(tmp_path: Path, runner: Path) -> None:
    """`runner-resumes-early-stops`: a worker that ended its turn to wait on its own background work
    exits 0 with no report. The runner resumes that session, telling it why, on one attempt of its
    budget, and the worklog names the stop for what it was."""
    worktree = tmp_path / "lamp-warm-preset"
    (worktree / "agent").mkdir(parents=True)
    git(worktree / "agent", "init", "-q", "-b", "ticket/warm-preset", ".")
    git(worktree / "agent", "commit", "-q", "--allow-empty", "-m", "the agent repo")
    said = tmp_path / "said"
    claude = (
        '#!/bin/sh\n[ "$1" = --version ] && exit 0\n'
        f'n=$(ls {tmp_path} | grep -c "^said"); printf "%s\\n" "$*" > {said}$((n + 1))\n'
        '[ "$n" -lt 1 ] && exit 0\n'
        'mkdir -p agent/show/warm-preset\n'
        'printf "## Comments\\n\\nit lands.\\n" > agent/show/warm-preset/report.md\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false add -A\n'
        'git -C agent -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -q -m report\n'
    )

    done = run_worker(runner, claude=claude, model="sonnet", cwd=worktree)
    assert done.returncode == 0, done.stderr
    status = (runner / "run-1.status").read_text()
    assert status.startswith("attempts=2 exit=0 report=yes"), status
    session = status.split("session=")[1].split()[0]
    first, resumed = (tmp_path / "said1").read_text(), (tmp_path / "said2").read_text()
    assert "report was committed" not in first, first
    assert f"--resume {session} Your session ended before this round's report was committed" in resumed, resumed
    assert "attempt 1 exited 0 with no report, an early stop; resuming" in (runner / "run-1.log").read_text()


@pytest.mark.parametrize("given", ["", "low"])
def test_the_runner_passes_an_effort_to_every_attempt_high_unless_told(tmp_path: Path, runner: Path, given: str) -> None:
    """`model-effort-defaults`: every `claude` a worker runs on names its effort, so no worker runs
    at whatever the host's settings say; DISPATCH_EFFORT is how the spawn sets it."""
    run_worker(runner, DISPATCH_EFFORT=given or None)

    attempts = [line for line in (tmp_path / "bin" / "claude.calls").read_text().splitlines() if line.startswith("-p ")]
    assert attempts and all(f"--model opus --effort {given or 'high'} " in line for line in attempts), attempts
    assert f"on opus at {given or 'high'} effort" in (runner / "run-1.log").read_text().splitlines()[0]
    # `run-log`: the attempt left its line, in the log this HOME defaults to
    (logged,) = [json.loads(l) for l in (tmp_path / "logs" / "agent" / "runs.jsonl").read_text().splitlines()]
    assert (logged["site"], logged["ticket"], logged["attempt"], logged["model"], logged["effort"]) == \
        ("worker", "warm-preset", 1, "opus", given or "high")


def test_a_worker_inherits_the_projects_settings_and_the_hosts_mx_and_nothing_else(tmp_path: Path, runner: Path) -> None:
    """`unattended-launch`, as ruled on 2026-09-26: a worker keeps the project's settings and
    AGENTS.md or CLAUDE.md and the mx plugin the host's claude has installed, and none of the
    user's settings, CLAUDE.md, output style or hooks, no MCP server, and no auto memory. The
    worklog's first line names the mx install it runs."""
    plugin = mx(tmp_path)

    run_worker(runner)

    attempts = [line for line in (tmp_path / "bin" / "claude.calls").read_text().splitlines() if line.startswith("-p ")]
    inherits = ("--setting-sources project", "--strict-mcp-config", f"--plugin-dir {plugin}",
                '--settings {"autoMemoryEnabled": false}')
    assert attempts and all(flag in line for line in attempts for flag in inherits), attempts
    assert not any("claudeMdExcludes" in line or "outputStyle" in line for line in attempts), attempts
    assert f" and mx {plugin.name} (run-1)" in (runner / "run-1.log").read_text().splitlines()[0]


def test_a_runner_given_no_plugin_dir_starts_no_worker(tmp_path: Path, runner: Path) -> None:
    """A worker without the plugin has none of the skills its contract names, so a runner started
    without DISPATCH_PLUGIN_DIR says so on the status line rather than start one."""
    done = run_worker(runner, DISPATCH_PLUGIN_DIR=None)

    assert done.returncode == 1
    assert (runner / "run-1.status").read_text().startswith(
        "attempts=0 exit=1 report=no session=- error=DISPATCH_PLUGIN_DIR unset")
    assert not (tmp_path / "bin" / "claude.calls").exists(), "claude ran"


def test_a_worker_is_told_the_asking_rule_from_its_one_home(tmp_path: Path, runner: Path) -> None:
    """`asking-rule-has-one-home`: worker-prompt.md names the asking rule as appended below it, so
    the runner appends that section of the install's RULES.md, and the prompt carries no copy."""
    rules = (SKILL.parent / "session-page" / "RULES.md").read_text()
    section = re.split(r"\n#{1,2} ", rules[rules.index("## What the user decides"):])[0].strip()
    prompt = (SKILL / "worker-prompt.md").read_text()

    run_worker(runner)

    assert section in (tmp_path / "bin" / "claude.calls").read_text()
    assert not [clause for clause in re.split(r"[.:;]", section.splitlines()[-1]) if len(clause) > 20 and clause.strip() in prompt]


def test_a_runner_whose_install_lacks_the_asking_rule_starts_no_worker(tmp_path: Path, runner: Path) -> None:
    """A worker told the rule is appended below its prompt, with nothing there, would ask the user
    by no rule at all; the status line names the section that is missing."""
    plugin = mx(tmp_path)
    rules = plugin / "skills" / "session-page" / "RULES.md"
    rules.write_text(rules.read_text().replace("## What the user decides", "## Something else"))

    done = run_worker(runner, DISPATCH_PLUGIN_DIR=str(plugin))

    assert done.returncode == 1
    assert (runner / "run-1.status").read_text().startswith(
        "attempts=0 exit=1 report=no session=- error=no '## What the user decides' section in")
    assert "older than" in (runner / "run-1.status").read_text()
    assert not (tmp_path / "bin" / "claude.calls").exists(), "claude ran"


def test_a_worker_runs_under_its_run_id_whatever_run_spawned_it(tmp_path: Path, runner: Path) -> None:
    """`browsers-a-worker-can-kill`: MX_RUN is what the browsers a worker's checks launch are
    tagged with, so it names this run and not the one the orchestrator's shell was in."""
    seen = tmp_path / "mx-run"

    run_worker(runner, claude=f'#!/bin/sh\n[ "$1" = --version ] && exit 0\necho "$MX_RUN" >> {seen}\n',
               run_id="run-7", MX_RUN="the-orchestrators")

    assert seen.read_text().splitlines() == ["run-7"]


@pytest.mark.parametrize("resumed", [False, True])
def test_the_status_line_names_the_models_the_worker_ran_on(tmp_path: Path, runner: Path, resumed: bool) -> None:
    """`worker-hosts-run-the-current-claude`: `opus` on the command line says nothing about what
    answered, so the status line reads it off the session's transcript: the models this round's
    assistant turns carry, none of the rounds' before it on a resumed session, and none of the
    strings a turn merely mentions (an Agent call's `model` input) or claude's own `<synthetic>`
    error turns. The worklog's first line names the launcher's version."""
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
    claude = ('#!/usr/bin/env bash\n[ "$1" = --version ] && { echo "2.1.283 (Claude Code)"; exit 0; }\n'
              'while [ "$1" != --session-id ] && [ "$1" != --resume ]; do shift; done\n'
              f'cat >> "{project}/$2.jsonl" <<\'T\'\n{transcript}\nT\n')

    run_worker(runner, *([session] if resumed else []), claude=claude, CLAUDE_CONFIG_DIR=str(tmp_path / "profile"))
    status = (runner / "run-1.status").read_text()
    assert status.split()[-1] == "models=claude-opus-5-5,claude-sonnet-5", status
    assert "on opus at high effort with claude 2.1.283" in (runner / "run-1.log").read_text().splitlines()[0]


def test_what_a_worker_leaves_running_ends_with_its_attempt(tmp_path: Path, runner: Path) -> None:
    """A worker whose shell was killed before its cleanup line leaves its children behind, and a
    child that detached itself escapes even the process group `dispatch-ctl stop` signals. The
    runner's scope is what takes both down, on a host with a user systemd manager."""
    probe = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect", "--", "true"],
                           capture_output=True) if shutil.which("systemd-run") else None
    if probe is None or probe.returncode != 0:
        pytest.skip("no user systemd manager here, and the runner says so in the worklog instead")
    left = tmp_path / "left.pid"

    # The runner asks `claude --version` first, outside any attempt; only the attempt leaves a child.
    run_worker(runner, claude=f'#!/bin/sh\n[ "$1" = --version ] && exit 0\nsetsid sleep 3600 > /dev/null 2>&1 &\necho $! > {left}\nexit 0\n',
               run_id=f"check-{tmp_path.name}", model="sonnet")
    pid = left.read_text().strip()
    for _ in range(20):
        if not Path(f"/proc/{pid}").exists():
            break
        time.sleep(0.25)
    else:
        subprocess.run(["kill", pid])
        pytest.fail(f"the worker's detached sleep (pid {pid}) outlived the run")


def test_a_worktree_with_no_agent_repo_says_so_in_the_worklog(runner: Path) -> None:
    """Without that repo the worker has nowhere to commit a report, so every attempt would end in
    `report=no` with nothing saying why."""
    run_worker(runner, claude="#!/bin/sh\nexit 0\n", model="sonnet")
    assert "no agent repo at" in (runner / "run-1.log").read_text()
    assert "report=no" in (runner / "run-1.status").read_text()


def test_a_runner_staged_without_run_log_refuses_to_start(runner: Path) -> None:
    """Every attempt runs through run-log, so a staging that lacks it is said on the status line
    rather than run unlogged."""
    (runner / "run-log").unlink()
    done = run_worker(runner, model="sonnet")
    assert done.returncode == 1
    assert (runner / "run-1.status").read_text().startswith("attempts=0 exit=1 report=no session=- error=no run-log beside run-worker.sh")


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
def test_a_cleanup_refuses_over_work_no_spawn_put_in_the_worktree_and_force_deletes_it(toy: Path, staged: Path) -> None:
    """A worker once made worktrees of a mirror on the host inside its ticket worktree, and the
    cleanup deleted them with everything in them. Such a worktree, and a change not committed, stop
    the cleanup before it touches anything, each named; what the setup left does not, a repo it
    checked out included, though a file written into a directory it left does; --force deletes the
    lot, and the mirror's branch survives it."""
    env = environment(toy)
    run(toy, "claim", "warm-preset")
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)
    spawned = subprocess.run([str(staged), "ctl", "--host", "local", "--setup-cmd", "echo built > built.txt; mkdir out; touch out/a; git init -q deps/dep",
                              "spawn", "warm-preset", "sonnet"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert spawned.returncode == 0, spawned.stderr
    waited(toy)
    worktree = toy.parent / "lamp-warm-preset"
    mirror = toy.parent / "mirror.git"
    git(toy.parent, "clone", "-q", "--bare", str(toy), str(mirror))
    git(mirror, "worktree", "add", "-q", str(worktree / ".worktrees" / "pr-1"), "-b", "pr-1")
    (worktree / "notes.md").write_text("what the review found\n")
    (worktree / "out" / "notes.md").write_text("and what it found next\n")

    refused = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset"], cwd=toy,
                             capture_output=True, text=True, env=env, timeout=180)
    assert refused.returncode == 1, refused.stderr
    assert f"a repo at {worktree / '.worktrees' / 'pr-1'}, a checkout of {mirror}" in refused.stderr, refused.stderr
    assert f"not committed in {worktree}: ?? notes.md" in refused.stderr, refused.stderr
    assert f"not committed in {worktree}: ?? out/notes.md" in refused.stderr, refused.stderr
    assert not [left for left in ("built.txt", "out/a", "deps/dep") if left in refused.stderr], refused.stderr
    assert (worktree / ".worktrees" / "pr-1" / "lamp.txt").exists()
    assert git(toy, "branch", "--list", "ticket/warm-preset")
    assert "warm-preset exited" in run(toy, "ctl", "probe").stdout

    forced = subprocess.run([str(staged), "ctl", "cleanup", "warm-preset", "--force"], cwd=toy,
                            capture_output=True, text=True, env=env, timeout=180)
    assert forced.returncode == 0, forced.stderr
    assert not worktree.exists()
    assert not git(toy, "branch", "--list", "ticket/warm-preset")
    assert git(mirror, "branch", "--list", "pr-1")


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
    rule_open(toy, "warm-preset", env)
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


def built_on_host(toy: Path, staged: Path, host: str) -> tuple[dict[str, str], Path]:
    """warm-preset claimed, spawned on `host` (`local`, or `agent@far` behind the fake ssh) and
    built by a worker that reported: the environment that reaches the host, and the ticket's
    worktree there."""
    (staged.parent / "run-worker.sh").write_text(BUILDING)
    if host == "local":
        env, worktree, state = environment(toy), toy.parent / "lamp-warm-preset", None
    else:
        remote, env = fake_remote(toy)
        worktree, state = remote / "repos" / "dispatch" / "lamp-warm-preset", remote / ".local" / "state" / "dispatch" / "lamp-main"
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host=host, env=env).returncode == 0
    waited(toy, state)
    return env, worktree


def tracker_writes(toy: Path, env: dict[str, str], *args: str) -> None:
    """A session running `tracker` itself, outside dispatch, which commits what it wrote."""
    wrote = subprocess.run(["tracker", *args], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert wrote.returncode == 0, wrote.stdout + wrote.stderr
    assert not git(toy / "agent", "status", "--porcelain", "--", "tickets"), args


@pytest.mark.full_path
@pytest.mark.parametrize("host", ["local", "agent@far"])
@pytest.mark.parametrize("left", ["done", "retired"])
def test_a_run_whose_ticket_was_closed_outside_dispatch_leaves_its_host_at_the_next_probe(
        toy: Path, staged: Path, host: str, left: str) -> None:
    """The branches merged by hand and the `done` written by `tracker set`, as a bulk close-out
    writes it; or the tree then taken out of the tracker by `tracker retire`. The next probe retires
    the run as `review` would have: its worktree and branches on the host and here, its record."""
    env, worktree = built_on_host(toy, staged, host)
    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert fetched.returncode == 0, fetched.stderr
    for top in (toy, toy / "agent"):
        git(top, "merge", "-q", "--no-ff", "-m", "warm-preset: merged by hand", "ticket/warm-preset")
    for status in ("review", "done"):
        tracker_writes(toy, env, "set", "warm-preset", f"status={status}")
    if left == "retired":
        for status in ("claimed", "review", "done"):
            tracker_writes(toy, env, "set", "lamp-ui", f"status={status}")
        subprocess.run(["tracker", "retire"], cwd=toy, capture_output=True, env=env, check=True, timeout=180)
        assert not (tracked(toy) / "warm-preset.md").exists()
    assert worktree.is_dir(), "nothing has touched the run yet"

    probed = subprocess.run([str(staged), "ctl", "probe"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert "no run recorded for main" in probed.stderr, probed.stderr
    assert not worktree.exists()
    bare = [] if host == "local" else [worktree.parent / "lamp.git", worktree.parent / "lamp-agent.git"]
    for top in (toy, toy / "agent", *bare):
        assert not git(top, "branch", "--list", "ticket/warm-preset"), top
    sessions = subprocess.run(["tmux", "list-sessions", "-F", "#S"], capture_output=True, text=True, env=env).stdout
    assert "dispatch-lamp-warm-preset" not in sessions


@pytest.mark.full_path
@pytest.mark.parametrize("host, why", [
    ("local", "ticket/warm-preset in code has not merged into main here"),
    ("agent@far", "ticket/warm-preset in code holds commits this machine lacks"),
])
def test_a_run_of_a_ticket_gone_from_the_tracker_with_its_work_merged_nowhere_stays_and_says_why(
        toy: Path, staged: Path, host: str, why: str) -> None:
    """warm-preset dropped while its worker's commits sit on its branch alone: here and unmerged
    for a local host, on the host and never fetched for a remote one. The probe keeps the run, names
    it and says why, and lists it as before."""
    env, worktree = built_on_host(toy, staged, host)
    tracker_writes(toy, env, "drop", "warm-preset")

    probed = subprocess.run([str(staged), "ctl", "probe"], cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    assert probed.returncode == 0, probed.stderr
    assert f"warm-preset is gone from the tracker, and its run on {host} stays: {why}" in probed.stderr, probed.stderr
    assert "dispatch-lamp-warm-preset exited" in probed.stdout
    assert git(worktree, "log", "-1", "--format=%s").strip() == "warm-preset: the warm preset"


@pytest.mark.full_path
def test_a_run_of_a_ticket_gone_from_the_tracker_whose_worker_is_running_stays(toy: Path, staged: Path) -> None:
    """A worker still at it when its ticket left the tracker, its branch no further than main: the
    probe leaves it running in its worktree, and says why."""
    (staged.parent / "run-worker.sh").write_text(RUNNER.replace(
        "printf 'attempts=1", 'until [ -e "$state/release" ]; do sleep 0.2; done\nprintf \'attempts=1'))
    state = toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main"
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    for _ in range(60):
        if list(state.glob("*.log")):
            break
        time.sleep(0.5)
    tracker_writes(toy, environment(toy), "drop", "warm-preset")

    probed = run(toy, "ctl", "probe")
    (state / "release").touch()
    assert "warm-preset is gone from the tracker, and its run on local stays: its worker is still running" in probed.stderr, probed.stderr
    assert "dispatch-lamp-warm-preset running" in probed.stdout
    assert (toy.parent / "lamp-warm-preset").is_dir()


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


def test_a_round_with_no_code_lands_on_a_review_told_to_merge_it(toy: Path) -> None:
    """A research ticket's round, its code branch empty: no code merge says its build was read, so a
    review leaves its agent branch unmerged, and `review --merge` merges it and writes `done`."""
    agent = toy / "agent"
    path = tracked(toy) / "warm-preset.md"
    path.write_text(path.read_text().replace("status: open", "status: review"))
    git(agent, "commit", "-q", "-am", "warm-preset for review")
    git(toy, "branch", "ticket/warm-preset")
    built_on(agent, "ticket/warm-preset", "main", "notes.md")
    tip = git(agent, "rev-parse", "ticket/warm-preset").strip()

    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "review"
    merged = subprocess.run(["git", "-C", str(agent), "merge-base", "--is-ancestor", tip, "main"])
    assert merged.returncode == 1, "the agent branch waits for the word that its build was read"

    said = run(toy, "review", "warm-preset", "--merge")
    assert said.returncode == 0, said.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert git(agent, "rev-parse", "main~1^2").strip() == tip, "merged --no-ff, then landed"


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
                            capture_output=True, env=HERMETIC_GIT).returncode == 0
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


def boards(toy: Path) -> list[str]:
    """What dispatch asked the board to draw, once per run of it."""
    calls = toy.parent / "bin" / "board.calls"
    return calls.read_text().splitlines() if calls.exists() else []


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
    one does. A file of `Vendor`, nested in Backend, is Vendor's. The comment ids the round's
    `Addressed:` line names are the page's resolved list."""
    agent = toy / "agent"
    (toy / ".gitignore").write_text("/agent/\n/Backend/\n/Helix/\n")
    git(toy, "commit", "-q", "-am", "Backend and Helix are repos of their own")
    backend = listed_repo(toy / "Backend", "development").resolve()
    listed_repo(toy / "Helix", "main")
    jarvis = listed_repo(toy.parent / "jarvis", "main").resolve()
    vendor = listed_repo(backend / "vendor", "main")
    listing(toy, "warm-preset", f'[Backend]\npath = "Backend"\nintegration = "development"\n\n'
            f'[Helix]\npath = "Helix"\nintegration = "main"\n\n[jarvis]\npath = "{jarvis}"\nintegration = "main"\n\n'
            f'[Vendor]\npath = "Backend/vendor"\nintegration = "main"\n',
            "Backend, jarvis, Vendor")
    for top, start, name in ((toy, "main", "warm.txt"), (toy, "main", "shared.txt"),
                             (backend, "development", "warm.py"), (backend, "development", "shared.txt"),
                             (jarvis, "main", "warm.rs"), (vendor, "main", "warm.c")):
        built_on(top, "ticket/warm-preset", start, name)
    git(agent, "switch", "-q", "-c", "ticket/warm-preset")
    (agent / "show" / "warm-preset").mkdir(parents=True)
    (agent / "show" / "warm-preset" / "report.md").write_text(
        "## Comments\n\nAddressed: C1, C4\n\nThe warm preset lands in four repos, unmerged.\n\n- [D1] **Assumptions**\n"
        "  - A1 `warm.txt:1`: in the code repo.\n"
        "  - A2 `Backend/warm.py:1`: in the nested repo.\n"
        "  - A3 `../jarvis-warm-preset/warm.rs:1`: in the sibling repo.\n"
        "  - A4 `Backend/shared.txt:1`: a path the code repo's section shows too.\n"
        "  - A5 `agent/show/warm-preset/report.md:1`: in the agent repo.\n"
        "  - A6 `Backend/README:1`: untouched, and Backend's is the first section holding a README.\n"
        "  - A7 `../jarvis-warm-preset/README:1`: untouched, and Backend's section holds one first.\n"
        "  - A8 `Helix/README:1`: in a listed repo this ticket's page has no section for.\n"
        "  - A9 `Backend/vendor/warm.c:1`: in the repo nested in the nested one.\n")
    git(agent, "add", "show")
    git(agent, "commit", "-q", "-m", "warm-preset: the report")
    git(agent, "switch", "-q", "main")

    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    page = json.loads((agent / "diffviews" / "warm-preset.notes.json").read_text())
    assert [(one["id"], one["path"], one["line"], Path(one["source"]).resolve()) for one in page["notes"]] == [
        (1, "warm.txt", 1, toy.resolve()), (2, "warm.py", 1, backend), (3, "warm.rs", 1, jarvis),
        (4, "shared.txt", 1, backend), (6, "README", 1, backend), (7, "README", 1, jarvis), (9, "warm.c", 1, vendor)]
    assert page["resolved"] == ["C1", "C4"]
    assert "A4" not in said.stderr and "A7" not in said.stderr, said.stderr


def test_a_childs_later_round_in_a_listed_repo_renders_beside_the_rounds_it_carries(toy: Path) -> None:
    """A child built on its parent ticket's branch: in `Backend` its base is the parent's branch
    there, which is ahead of the trunk. A round merged into it is recorded; the next
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
    assert boards(toy) == [f"{tracked(toy)} --no-watch --no-open"], "the board shows the status the review wrote"


def test_a_merged_round_the_tracker_refuses_done_fails_the_review_and_says_why(toy: Path) -> None:
    """A round merged before any report reached the ticket, which is still claimed: the merge asks
    for `done`, the tracker refuses it, and the review fails with the tracker's reason rather than
    reading as a build waiting in review."""
    claimed_with_code(toy)
    for top in (toy, toy / "agent"):
        merged_in(top, "main", "ticket/warm-preset")
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 1 and "warm-preset claimed → done" in said.stderr, said.stderr
    assert status_of(toy, "warm-preset") == "claimed"
    assert not (toy.parent / "bin" / "diffview.args").exists(), "and renders nothing"


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
    listing is the oracle. Each is cut where the prompt says, from its base: `Backend` inside the
    ticket worktree at the path the project keeps it at, from its trunk, and `jarvis`
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
    (prompt,) = state.glob("*.prompt")
    assert "- Backend: `Backend/` in your worktree, from `development`" in prompt.read_text()
    assert "- jarvis: `../jarvis-warm-preset`, beside your worktree, from `main`" in prompt.read_text()

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
    rule_open(toy, "warm-preset", env)
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
    from lamp-ui's branch there, which is ahead of its trunk, into the ticket worktree,
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
    (prompt,) = state.glob("*.prompt")
    assert "- Backend: `Backend/` in your worktree, from `lamp-ui`" in prompt.read_text()

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
    `repos:` leaves the worker's tree at the next spawn, worktree and branch, and the prompt stops
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
    newest = max(state.glob("*.prompt"), key=lambda prompt: prompt.stat().st_mtime_ns).read_text()
    assert "- Backend: `Backend/` in your worktree" in newest and "jarvis" not in newest

    said = respawn("")
    assert not (hosted / "lamp-warm-preset" / "Backend").exists()
    assert not git(hosted / "lamp-Backend.git", "branch", "--list", "ticket/warm-preset")
    calls = [line.split("dispatch-ctl ")[1] for line in said.stderr.splitlines()
             if line.startswith("+ on_host agent@far bash") or line.startswith("+ on_host agent@far env")]
    assert calls == ["spawn warm-preset sonnet"], said.stderr


def test_the_page_over_a_listed_repo_cut_from_origin_is_rendered_again_once_its_round_merges(toy: Path) -> None:
    """`jarvis`'s ticket branch is cut from origin's `main`, which is ahead of the local one, and the
    session merges it into the local `main`: the review that lands the round renders the page it
    rendered before the merge, over the same ranges. Which range the merge gives `jarvis` is the
    tracker's to say (test_tracker.py); rendering the page from what it says is dispatch's."""
    repos = staged_listed(toy)
    agent = toy / "agent"
    rounds = {"code": built_on(toy, "ticket/warm-preset", "main", "warm.txt"),
              "agent": built_on(agent, "ticket/warm-preset", "main", "warm.md"),
              "jarvis": built_on(repos["jarvis"], "ticket/warm-preset", "origin/main", "warm.rs")}
    said = run(toy, "review", "warm-preset")
    assert said.returncode == 0, said.stderr
    for top in (toy, agent, repos["jarvis"]):
        merged_in(top, "main", "ticket/warm-preset")
    landed = run(toy, "review", "warm-preset")
    assert landed.returncode == 0, landed.stderr
    assert status_of(toy, "warm-preset") == "done"
    assert pages(toy)[-1].split()[-1] == f"{repos['jarvis']}@{rounds['jarvis'][0]}..{rounds['jarvis'][1]}"
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
    has merged into the trunk: the accept that writes the child's `done` deletes its
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
    rule_open(toy, "warm-preset", env)
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
    the spawn cuts Backend's ticket branch into it all the same, where the prompt says it is."""
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
    assert f"remote agent-far-lamp at {repos['jarvis']} names {elsewhere}, not agent@far:repos/dispatch/lamp-jarvis.git" in said.stderr, said.stderr
    assert not git(elsewhere, "for-each-ref")


def test_a_hosts_remote_left_at_the_bare_repo_of_an_older_repo_name_is_repointed_and_the_branch_lands_where_the_host_cuts(
        toy: Path, staged: Path) -> None:
    """The helferline staging: earlier waves named the repo `workspace`, so both repos still carry
    the host's remote at `workspace.git`; the project is `lamp` now, and the spawn's push lands in
    the bare repos the host's init made for it."""
    remote, env = fake_remote(toy)
    hosted = remote / "repos" / "dispatch"
    for top, old in ((toy, "workspace.git"), (toy / "agent", "workspace-agent.git")):
        git(toy.parent, "init", "-q", "--bare", str(hosted / old))
        git(top, "remote", "add", "agent-far", f"agent@far:repos/dispatch/{old}")
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)
    assert said.returncode == 0, said.stderr
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    for top, bare, old in ((toy, "lamp.git", "workspace.git"), (toy / "agent", "lamp-agent.git", "workspace-agent.git")):
        assert git(top, "remote", "get-url", "agent-far").strip() == f"agent@far:repos/dispatch/{bare}"
        assert git(hosted / bare, "branch", "--list", "main"), bare
        assert not git(hosted / old, "for-each-ref"), old


def test_a_hosts_remote_naming_a_repo_outside_dispatchs_on_that_host_stops_the_spawn_naming_both(
        toy: Path, staged: Path) -> None:
    remote, env = fake_remote(toy)
    elsewhere = toy.parent / "elsewhere.git"
    git(toy.parent, "init", "-q", "--bare", str(elsewhere))
    git(toy / "agent", "remote", "add", "agent-far", str(elsewhere))
    run(toy, "claim", "warm-preset")
    said = spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env)
    assert said.returncode != 0
    assert f"remote agent-far at {toy / 'agent'} names {elsewhere}, not agent@far:repos/dispatch/lamp-agent.git" in said.stderr, said.stderr
    assert git(toy / "agent", "remote", "get-url", "agent-far").strip() == str(elsewhere)
    assert not git(elsewhere, "for-each-ref")
    assert not (remote / "repos" / "dispatch" / "lamp-warm-preset").exists(), "no worker started"


@pytest.mark.parametrize("project, given, says", [
    ({"flake.nix": "{}\n"}, [], "the default for a flake.nix: {state} has no `setup` (`dispatch ctl --setup-cmd` writes one)"),
    ({"Makefile": "install:\n\ttrue\n"}, [], "the default for a Makefile with install: {state} has no `setup` (`dispatch ctl --setup-cmd` writes one)"),
    ({"flake.nix": "{}\n"}, ["--setup-cmd", "true"], "{state}/setup"),
])
def test_a_spawn_says_where_its_setup_came_from(
        toy: Path, staged: Path, project: dict[str, str], given: list[str], says: str) -> None:
    """A scratch dir new to a host holds no `setup` an older one did, so the spawn names the
    default it fell back to and why, or the `setup` it was given."""
    for name, body in project.items():
        (toy / name).write_text(body)
    git(toy, "add", "-A")
    git(toy, "commit", "-q", "-m", "a setup")
    fakes = toy.parent / "fakes"
    fakes.mkdir()
    (fakes / "nix").write_text("#!/bin/sh\nexit 0\n")  # `nix develop -c` with nothing to build
    (fakes / "nix").chmod(0o755)
    env = environment(toy)
    env["PATH"] = f"{fakes}:{env['PATH']}"
    run(toy, "claim", "warm-preset")
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)
    said = subprocess.run([str(staged), "ctl", "--host", "local", *given, "spawn", "warm-preset", "sonnet"],
                          cwd=toy, capture_output=True, text=True, env=env, timeout=180)
    state = waited(toy).parent
    assert said.returncode == 0, said.stderr
    assert "dispatch-ctl: setup from " + says.format(state=state) + "\n" in said.stderr, said.stderr


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
    # This repo's board, whose query of GitHub is one of the calls `only_read` reads, keeping what it
    # was asked to draw as the stub does.
    (toy.parent / "bin" / "board").write_text(f'#!/bin/sh\necho "$*" >> "{toy.parent / "bin" / "board.calls"}"\n'
                                              f'exec "{SKILL.parent / "tracker" / "board.py"}" "$@"\n')
    (toy.parent / "bin" / "board").chmod(0o755)
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


@pytest.mark.parametrize("landing", ["review", "accept"])
def test_a_squashed_pull_requests_commit_is_the_tickets_range_there_and_the_ticket_reaches_done(toy: Path, landing: str) -> None:
    """The squash is one commit on `development`, and the ticket's two commits on no branch there:
    the review or the accept after it records `Backend@<merge>^..<merge>`, which no branch could
    give it, deletes the ticket branch the pull request carried, records the code and agent repos'
    ranges, writes `done`, which the tracker's done check allows, and renders the page over what
    landed in place of the one it rendered before. Origin's refs are as GitHub left them."""
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
    done = run(toy, landing, "warm-preset")
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
    assert len(boards(toy)) == 1, "the board ran, with its own query of GitHub"


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
                   cwd=toy, check=True, capture_output=True, env=env)
    rule_open(toy, "warm-preset", env)
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


@pytest.mark.full_path
def test_push_that_a_host_refuses_for_one_repo_names_it_and_brings_the_other_there(toy: Path, staged: Path) -> None:
    """`dispatch push`'s exit 1: a host refused (named); the rest have it. The agent repo's bare
    repo on the host refuses every push, as a full disk or a hook there would."""
    remote, env = fake_remote(toy)
    run(toy, "claim", "warm-preset")
    assert spawn(toy, staged, "warm-preset", "Work it.\n", host="agent@far", env=env).returncode == 0
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    bare = remote / "repos" / "dispatch"
    hook = bare / "lamp-agent.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'refused: the disk is full' >&2\nexit 1\n")
    hook.chmod(0o755)
    for at in (toy, toy / "agent"):
        (at / "moved.md").write_text("the branch moved\n")
        git(at, "add", "moved.md")
        git(at, "commit", "-q", "-m", "the branch moved")

    pushed = subprocess.run([str(staged), "push"], cwd=toy, capture_output=True, text=True, env=env, timeout=120)

    assert pushed.returncode == 1, pushed.stderr
    assert "pushing main of the agent repo to agent@far failed" in pushed.stderr, pushed.stderr
    assert "of the code repo" not in pushed.stderr, pushed.stderr
    assert git(bare / "lamp.git", "rev-parse", "main") == git(toy, "rev-parse", "main")
    assert git(bare / "lamp-agent.git", "rev-parse", "main") != git(toy / "agent", "rev-parse", "main")


@pytest.mark.full_path
def test_a_fetch_whose_branch_one_of_the_hosts_repos_lacks_names_that_repo(toy: Path, staged: Path) -> None:
    """`dispatch fetch`'s exit 1: a branch did not come (named). The agent repo's ticket branch is
    gone from the host, as a cleanup run there by hand would leave it."""
    env, worktree = built_on_host(toy, staged, "agent@far")
    git(worktree.parent / "lamp-agent.git", "worktree", "remove", "--force", str(worktree / "agent"))
    git(worktree.parent / "lamp-agent.git", "branch", "-D", "ticket/warm-preset")

    fetched = subprocess.run([str(staged), "fetch", "warm-preset"], cwd=toy, capture_output=True, text=True,
                             env=env, timeout=180)

    assert fetched.returncode == 1, fetched.stderr
    assert f"fetching ticket/warm-preset from agent@far into {toy / 'agent'} failed" in fetched.stderr, fetched.stderr


def sourced(body: str, *args: str, **env: str) -> subprocess.CompletedProcess:
    """`body` run in bash with `dispatch` sourced, so its functions are defined and no command of it
    runs, and `args` as `body`'s `$@`."""
    return subprocess.run(["bash", "-c", f'source "{DISPATCH}" && {body}', "check", *args],
                          capture_output=True, text=True, env={**os.environ, **env}, timeout=30)


# The run record as `record_run` appends it, a branch, a ticket and a host a line: warm-preset ran
# here first and on agent@far since, while another branch, lamp-ui, has runs of its own, one of them
# of warm-preset too, on a host main has none on.
RUN_RECORD = (
    "main\twarm-preset\tlocal\n"
    "lamp-ui\twarm-preset\tagent@near\n"
    "main\twarm-preset\tagent@far\n"
    "main\tdim-preset\tlocal\n"
    "lamp-ui\tcold-preset\tagent@near\n"
)


def on_record(tmp_path: Path, base: str, call: str, record: str | None = RUN_RECORD) -> subprocess.CompletedProcess:
    """`call` run on the branch `base` over a run record holding `record`, or over none at all."""
    runs = tmp_path / "runs"
    if record is not None:
        runs.write_text(record)
    return sourced(f'base={base} runs="{runs}" && {call}')


def test_a_ticket_is_followed_to_the_host_its_branch_last_ran_it_on(tmp_path: Path) -> None:
    """`host_of`: newest line for a name wins, among the lines of the branch asking; nothing for a
    ticket it never ran, and nothing where no run was ever recorded."""
    assert on_record(tmp_path, "main", "host_of warm-preset").stdout == "agent@far\n"
    assert on_record(tmp_path, "lamp-ui", "host_of warm-preset").stdout == "agent@near\n"
    assert on_record(tmp_path, "main", "host_of cold-preset").stdout == ""
    never = on_record(tmp_path / "nowhere", "main", "host_of warm-preset", record=None)
    assert (never.returncode, never.stdout) == (0, "")


def test_a_host_holds_the_runs_of_a_branch_that_last_went_there(tmp_path: Path) -> None:
    """`runs_on`: every ticket this branch has a run of there, so one that moved on is no longer on
    the host it left."""
    def on(host: str) -> set[str]:
        return set(on_record(tmp_path, "main", f"runs_on {host}").stdout.split())

    assert on("local") == {"dim-preset"}
    assert on("agent@far") == {"warm-preset"}
    assert on("agent@near") == set(), "lamp-ui's runs are lamp-ui's"


def test_the_hosts_a_branch_fans_out_over_are_each_host_it_has_a_run_on_once(tmp_path: Path) -> None:
    """`hosts_used`, which `push` and `probe` go over: every host this branch has a run on."""
    assert sorted(on_record(tmp_path, "main", "hosts_used").stdout.split()) == ["agent@far", "local"]


def test_a_forgotten_run_leaves_every_other_run_on_file(tmp_path: Path) -> None:
    """`forget_run`: a cleaned-up run has nothing left on its host, so its lines go, and every line
    of another ticket or another branch, the same ticket's on lamp-ui among them, stays as it was."""
    forgot = on_record(tmp_path, "main", "forget_run warm-preset")

    assert forgot.returncode == 0, forgot.stderr
    assert (tmp_path / "runs").read_text() == (
        "lamp-ui\twarm-preset\tagent@near\n"
        "main\tdim-preset\tlocal\n"
        "lamp-ui\tcold-preset\tagent@near\n"
    )
    nothing = on_record(tmp_path / "nowhere", "main", "forget_run warm-preset", record=None)
    assert nothing.returncode == 0 and not (tmp_path / "nowhere" / "runs").exists()


def test_a_scratch_dir_is_the_repos_and_the_branchs_under_the_home_on_either_side(tmp_path: Path) -> None:
    """`scratch_dir`: per branch, named after the repo too, and relative to the home on a remote
    host, where ssh and scp resolve it, and under it here."""
    def scratch(host: str) -> str:
        return sourced(f"repo=lamp base=lamp-ui && scratch_dir {host}", HOME=str(tmp_path)).stdout

    assert scratch("agent@far") == ".local/state/dispatch/lamp-lamp-ui\n"
    assert scratch("local") == f"{tmp_path}/.local/state/dispatch/lamp-lamp-ui\n"


# A word as the shells read it: any text a C string holds, and the words the two read apart or treat
# as syntax, drawn often enough that every run meets them.
SHELL_WORD = st.one_of(
    st.text(st.characters(exclude_characters="\0", codec="utf-8")),
    st.sampled_from(["", "=", "=ls", "=tmux", "~", "~/x", "a b", "$HOME", "*", "!x", "^x", "#x",
                     "{a,b}", "x\ny", "'", '"', "\\", ";", "&&", "=dispatch-lamp-warm-preset:"]),
)


@pytest.mark.parametrize("shell", ["bash", "zsh"])
@given(words=st.lists(SHELL_WORD, min_size=1, max_size=6))
@settings(max_examples=60, deadline=None)
@example(words=["tmux", "attach", "-t", "=dispatch-lamp-warm-preset:"])
def test_a_remote_line_reaches_the_command_as_the_words_sent(shell: str, words: list[str]) -> None:
    """`remote_line`: each word is quoted for the remote login shell, which may be bash or zsh, so
    an empty one, one with a space and one zsh reads as a command's path (`=ls`) all arrive whole."""
    login = shutil.which(shell)
    if login is None:
        pytest.skip(f"no {shell} here, so no remote line is read as {shell} reads it, here or in the fake ssh")
    line = sourced('remote_line "$@"', *words)
    assert line.returncode == 0, line.stderr
    flags = ["-f", "-c"] if shell == "zsh" else ["-c"]
    read = subprocess.run([login, *flags, f"printf '%s\\0' {line.stdout}"], capture_output=True, timeout=30)
    assert read.stdout == b"".join(word.encode() + b"\0" for word in words), read.stderr.decode()


def placer(toy: Path, *lines: str, rc: int = 0) -> None:
    """A `worker-hosts` whose `--place` puts a spawn on `lines`, `self` in one being this machine's
    user@host, after a line of readings on stderr, and exits `rc`. Each call's arguments go to
    `placer.calls`."""
    bin_dir = toy.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    me = f"{subprocess.run(['id', '-un'], capture_output=True, text=True).stdout.strip()}@{os.uname().nodename}"
    said = toy.parent / "placed"
    said.write_text("".join(line.replace("self", me) + "\n" for line in lines))
    (bin_dir / "worker-hosts").write_text(
        f'#!/bin/sh\necho "$*" >> "{toy.parent / "placer.calls"}"\n[ "$1" = --place ] || exit 0\n'
        'printf "worker-hosts: placing from these readings:\\n  agent@far  0 of 8 slots held\\n" >&2\n'
        f'cat "{said}"\nexit {rc}\n')
    (bin_dir / "worker-hosts").chmod(0o755)


def placer_calls(toy: Path) -> list[str]:
    return (toy.parent / "placer.calls").read_text().splitlines()


def slot_runner(toy: Path) -> Path:
    """A runner whose worker runs in the worktree until the file `released/<worktree>` exists, and
    which writes `started <worktree>` and `ended <worktree>` to `workers`, and the permission mode
    it was given to `modes`."""
    (toy.parent / "released").mkdir()
    runner = toy.parent / "slot-runner"
    runner.write_text(f"""#!/usr/bin/env bash
run_id=$4
state=$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)
echo "slot runner: started" >> "$state/$run_id.log"
echo "$DISPATCH_PERMISSION_MODE" >> {toy.parent / "modes"}
echo "started ${{PWD##*/}}" >> {toy.parent / "workers"}
while [ ! -e "{toy.parent}/released/${{PWD##*/}}" ]; do sleep 0.1; done
echo "ended ${{PWD##*/}}" >> {toy.parent / "workers"}
printf 'attempts=1 exit=0 report=no session=stub\\n' > "$state/$run_id.status"
""")
    return runner


def until(what, said) -> None:
    """Returns once `what()` holds; fails with `said()` after a minute."""
    for _ in range(600):
        if what():
            return
        time.sleep(0.1)
    raise AssertionError(said())


def test_a_spawn_on_a_full_machine_waits_and_its_runner_holds_the_slot_it_takes(toy: Path, staged: Path) -> None:
    """P1 and P3 at the host: a spawn that names its host is held to that machine's slots too. While
    `host-slots` says every slot is held the spawn waits, and once one frees it takes it for its own
    process and hands it to the worker's runner, by a word on each one's command line, so the slot
    stays held after the spawn returns, for as long as the run lasts."""
    full = toy.parent / "home" / "slots-full"
    full.parent.mkdir(exist_ok=True)
    full.touch()
    env = environment(toy, DISPATCH_RUNNER=str(slot_runner(toy)), DISPATCH_SLOT_WAIT="1")
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)
    err = toy.parent / "spawn.err"
    spawning = subprocess.Popen([str(staged), "ctl", "--host", "local", "--setup-cmd", "true", "spawn", "warm-preset",
                                 "sonnet"], cwd=toy, env=env, stdout=subprocess.DEVNULL, stderr=err.open("w"))
    try:
        until(lambda: err.read_text().count("no slot free") >= 2, err.read_text)
        assert spawning.poll() is None, err.read_text()
        assert not (toy.parent / "workers").exists()

        full.unlink()
        assert spawning.wait(timeout=60) == 0, err.read_text()
        until(lambda: (toy.parent / "workers").exists(), err.read_text)
        calls = (toy.parent / "home" / "host-slots.calls").read_text().splitlines()
        assert calls[-2:] == ["take carried", "hand carried"], calls
        assert calls[:-2] and set(calls[:-2]) == {"take full"}, calls
    finally:
        (toy.parent / "released" / "lamp-warm-preset").touch()
        spawning.kill()


def test_a_spawn_without_a_host_is_placed_and_prints_the_readings_it_chose_from(toy: Path, staged: Path) -> None:
    """P2 through `dispatch ctl spawn`: the spawn starts on the first host `worker-hosts --place`
    names, on the personal account unless told otherwise, and shows what the placer read."""
    placer(toy, "self\tisolated", "agent@far\tisolated")
    env = environment(toy)
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)

    spawned = subprocess.run([str(staged), "ctl", "--setup-cmd", "true", "spawn", "warm-preset", "sonnet"],
                             cwd=toy, capture_output=True, text=True, env=env, timeout=180)

    assert spawned.returncode == 0, spawned.stderr
    assert "placing warm-preset on local" in spawned.stderr
    assert "placing from these readings:\n  agent@far  0 of 8 slots held" in spawned.stderr
    assert placer_calls(toy) == ["--place personal"]
    waited(toy)
    assert run(toy, "ctl", "probe").stdout.startswith("local  dispatch-lamp-warm-preset exited")


def test_a_placed_spawn_takes_its_account_from_the_environment(toy: Path, staged: Path) -> None:
    """D4: with no --account, DISPATCH_ACCOUNT names the account, as a project's .envrc sets it."""
    placer(toy, "self\tisolated")
    env = environment(toy, DISPATCH_ACCOUNT="helferline")
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)

    spawned = subprocess.run([str(staged), "ctl", "--setup-cmd", "true", "spawn", "warm-preset", "sonnet"],
                             cwd=toy, capture_output=True, text=True, env=env, timeout=180)

    assert spawned.returncode == 0, spawned.stderr
    assert placer_calls(toy) == ["--place helferline"]
    waited(toy)


def test_a_placed_spawn_its_best_machine_turns_away_goes_to_the_next(toy: Path, staged: Path) -> None:
    """P1 over P2: a reading is a moment old, so the best machine may have filled since. Its spawn is
    turned away, and the worker starts on the next machine, which the run record then names."""
    remote, env = fake_remote(toy)
    placer(toy, "self\tisolated", "agent@far\tisolated")
    (toy.parent / "home").mkdir(exist_ok=True)
    (toy.parent / "home" / "slots-full").touch()
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)

    spawned = subprocess.run([str(staged), "ctl", "--setup-cmd", "true", "spawn", "warm-preset", "sonnet"],
                             cwd=toy, capture_output=True, text=True, env=env, timeout=180)

    assert spawned.returncode == 0, spawned.stderr
    assert "no slot free on" in spawned.stderr
    assert "placing warm-preset on agent@far" in spawned.stderr
    waited(toy, remote / ".local" / "state" / "dispatch" / "lamp-main")
    assert run(toy, "ctl", "probe", **{"REMOTE_HOME": str(remote), "PATH": env["PATH"]}).stdout.startswith(
        "agent@far  dispatch-lamp-warm-preset exited")


@pytest.mark.parametrize(("isolated", "given", "mode"), [
    ("true", None, "bypassPermissions"), ("true", "auto", "auto"), ("false", None, "auto")])
def test_a_worker_on_an_isolated_host_bypasses_permissions_unless_told_otherwise(
        toy: Path, staged: Path, isolated: str, given: str | None, mode: str) -> None:
    """A host whose record says isolated: true is itself the boundary around its worker, so the worker
    runs with bypassPermissions there unless DISPATCH_PERMISSION_MODE says otherwise; elsewhere the
    host's default holds."""
    (toy.parent / "home").mkdir(exist_ok=True)
    (toy.parent / "home" / "HOST.md").write_text(f"---\nhost: this\nisolated: {isolated}\n---\n\n# This machine\n")
    env = environment(toy, DISPATCH_RUNNER=str(slot_runner(toy)))
    if given:
        env["DISPATCH_PERMISSION_MODE"] = given
    (toy.parent / "released" / "lamp-warm-preset").touch()

    assert spawn(toy, staged, "warm-preset", "Work it.\n", env=env).returncode == 0

    until(lambda: (toy.parent / "modes").exists(), lambda: "the runner never started")
    assert (toy.parent / "modes").read_text().split() == [mode]


def test_a_spawn_no_host_could_ever_take_is_refused_at_once(toy: Path, staged: Path) -> None:
    """A spawn needing a capability no machine offers would wait for ever, so it is refused."""
    placer(toy, rc=1)
    env = environment(toy)
    subprocess.run([str(staged), "prompt", "warm-preset"], cwd=toy, input="Work it.\n", text=True, check=True, env=env)

    spawned = subprocess.run([str(staged), "ctl", "--needs", "gpu", "spawn", "warm-preset", "sonnet"],
                             cwd=toy, capture_output=True, text=True, env=env, timeout=60)

    assert spawned.returncode == 1
    assert "no worker host could ever take warm-preset" in spawned.stderr, spawned.stderr
    assert placer_calls(toy) == ["--place personal --needs gpu"]


def test_a_ticket_whose_earlier_run_is_on_a_host_it_may_not_go_to_is_refused(toy: Path, staged: Path) -> None:
    """A run recorded earlier keeps its host, which holds its worktree; a spawn asking for what that
    host could never give is refused, rather than sent there."""
    assert spawn(toy, staged, "warm-preset", "Work it.\n").returncode == 0
    waited(toy)
    placer(toy, rc=1)
    env = environment(toy)

    spawned = subprocess.run([str(staged), "ctl", "--needs", "gpu", "spawn", "warm-preset", "sonnet"],
                             cwd=toy, capture_output=True, text=True, env=env, timeout=60)

    assert spawned.returncode == 1
    assert "earlier run is on local, where no spawn on account personal with --needs gpu may go" in spawned.stderr
    me = f"{subprocess.run(['id', '-un'], capture_output=True, text=True).stdout.strip()}@{os.uname().nodename}"
    assert placer_calls(toy) == [f"--place personal --needs gpu --on {me}"]


@pytest.mark.parametrize(("weight", "expected"), [(None, "100"), ("400", "400")])
def test_a_workers_attempt_carries_a_cpu_weight_and_no_cap(tmp_path: Path, runner: Path, weight: str | None,
                                                          expected: str) -> None:
    """Each attempt's scope shares a contended machine by its CPUWeight, equal by default and higher
    where the spawn asks, and caps no worker's CPU: a worker alone uses every core."""
    probe = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect", "--", "true"],
                           capture_output=True) if shutil.which("systemd-run") else None
    if probe is None or probe.returncode != 0:
        pytest.skip("no user systemd manager here, so an attempt runs in no scope")
    seen = tmp_path / "cpu"

    run_worker(runner, claude=f'#!/bin/sh\n[ "$1" = --version ] && exit 0\n'
                              f'cg=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup)\n'
                              f'cat "$cg/cpu.weight" "$cg/cpu.max" > {seen}\n',
               run_id=f"check-{tmp_path.name}", model="sonnet", DISPATCH_CPU_WEIGHT=weight)

    assert seen.read_text().split() == [expected, "max", "100000"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
