# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `dispatch ps`, `attach` and `peek`, and the host-side reader under them. Run: pytest test_dispatch_ps.py

One seam: the scripts as subprocesses, over scratch dirs laid out as `dispatch-ctl` leaves them, in
a HOME of the check's own and on a tmux server of its own. The adapters are a `worker-hosts` and an
`ssh` of the check's own on PATH, which is how the real ones arrive too; a host the check's ssh has
no answer for is a host that is off. The oracle is `dispatch-ctl`'s probe contract (a status file
is a finished run, a live runner process a running one, neither is `gone`), and
`agent/tickets/dispatch-ps.md` for the rest: P1 a host that did not answer is a row and a nonzero
exit; P2 a register that fails is an `incomplete` row and a nonzero exit; P3 a worker resolves
exactly, and a slug held twice resolves to nothing; P4 an empty worklog reads apart from an absent
one; P5 a Ctrl-C in a worker's pane leaves the status line a resume needs. `ps --follow` is held to
`agent/tickets/dispatch-ps-follow.md`, cited as dispatch-ps-follow P<n>: P1 one login per host plus
one per reconnect; P2 a silent host holds up no other; P3 what follow draws is what ps prints at
that moment.
"""

import hashlib
import os
import pwd
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from dispatch_checks import mx, stage_runner

SKILL = Path(__file__).parent
PS = SKILL / "dispatch-ps"
DISPATCH = SKILL / "dispatch"
ROOT = ".local/state/dispatch"
# This machine as a register names it, which `dispatch` reads locally under that name.
SELF = f"{pwd.getpwuid(os.getuid()).pw_name}@{os.uname().nodename}"

# ssh as a host that answers what the check put in ssh-answers/<host>, with the exit status in
# <host>.rc, and as a host that is off where it put nothing. Every call is recorded, host first.
FAKE_SSH = """#!/usr/bin/env bash
while [[ ${1:-} == -* ]]; do case $1 in -o) shift 2 ;; *) shift ;; esac; done
host=$1; shift
here=$(dirname "$0")
printf '%s\\t%s\\n' "$host" "$*" >> "$here/ssh.calls"
[ -f "$here/ssh-answers/$host" ] || { echo "ssh: Could not resolve hostname $host" >&2; exit 255; }
cat "$here/ssh-answers/$host"
exit "$(cat "$here/ssh-answers/$host.rc" 2>/dev/null || echo 0)"
"""


@pytest.fixture
def tmux(tmp_path: Path) -> Iterator[dict[str, str]]:
    """The environment every command here runs in: a tmux server of its own.

    $TMUX names the server of the pane the checks run in, and beats TMUX_TMPDIR, so it goes. The
    socket directory is short and under /tmp, since a socket path over about a hundred bytes is
    refused.

    ZDOTDIR is an empty directory: tmux runs a pane's command, and the fake ssh its remote one,
    through `$SHELL -c`, and a zsh reading the user's own config can put that user's PATH and
    TMUX_TMPDIR back (Home Manager's session variables do, in a shell started before the last
    switch), so the pane runs the real claude and talks to the user's tmux server.
    """
    sockets = Path("/tmp") / f"dispatch-ps-check-{hashlib.sha1(str(tmp_path).encode()).hexdigest()[:12]}"
    sockets.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    env["TMUX_TMPDIR"] = str(sockets)
    env["JOB_STATE_DIR"] = str(tmp_path / "jobs")
    (tmp_path / "zdotdir").mkdir()
    env["ZDOTDIR"] = str(tmp_path / "zdotdir")
    yield env
    subprocess.run(["tmux", "-S", str(sockets / f"tmux-{os.getuid()}" / "default"), "kill-server"],
                   capture_output=True)
    shutil.rmtree(sockets, ignore_errors=True)


def session(env: dict[str, str], name: str, command: str = "sleep 30") -> None:
    subprocess.run(["tmux", "new-session", "-d", "-s", name, command], env=env, check=True)


def scratch(root: Path, repo: str, base: str) -> Path:
    """A scratch dir as `dispatch-ctl init` leaves it, with that version's dispatch-ctl in it."""
    d = root / f"{repo}-{base}"
    d.mkdir(parents=True)
    (d / "config").write_text(
        f"repo={repo}\nbase={base}\ngit=/nowhere.git\nagent=/nowhere-agent.git\nagentbase=main\nworktrees=/nowhere\n")
    (d / "manifest").touch()
    shutil.copy(SKILL / "dispatch-ctl", d / "dispatch-ctl")
    return d


def spawned(d: Path, slug: str, *, at: int | None = None) -> str:
    """A run in the manifest, as `dispatch-ctl spawn` leaves it: name, run id, worktree, runner."""
    repo = (d / "config").read_text().split("repo=")[1].split("\n")[0]
    name = f"dispatch-{repo}-{slug}"
    run = f"{name}-{at or int(time.time())}"
    with (d / "manifest").open("a") as f:
        f.write(f"{name}\t{run}\t/nowhere/{repo}-{slug}\t{d / 'run-worker.sh'}\n")
    return run


def finished(d: Path, run: str) -> None:
    (d / f"{run}.status").write_text("attempts=1 exit=0 report=yes session=ccc models=claude-opus-5-5\n")


def rows(root: Path, env: dict[str, str]) -> list[list[str]]:
    out = subprocess.run(["bash", str(PS), str(root)], capture_output=True, text=True, check=True, env=env)
    return [line.split("\t") for line in out.stdout.splitlines()]


def running(d: Path, run: str) -> subprocess.Popen:
    """A live runner for <run>, as probe finds one: a process whose command line is the runner's."""
    runner = d / "run-worker.sh"
    runner.write_text("#!/usr/bin/env bash\nsleep 30\n")
    return subprocess.Popen(["bash", str(runner), "prompt", "slug", "opus", run])


# --- the host's side: dispatch-ps --------------------------------------------


def test_a_finished_run_reports_its_status_line_less_the_session(tmp_path: Path, tmux: dict[str, str]):
    d = scratch(tmp_path, "agents", "master")
    run = spawned(d, "hypofuzz-default", at=int(time.time()) - 3600)
    log = d / f"{run}.log"
    log.write_text("16:45 done: review round 4 landed\n")
    os.utime(log, (time.time() - 600, time.time() - 600))
    finished(d, run)

    ((base, ticket, state, age, idle, name, pane, detail),) = rows(tmp_path, tmux)
    assert (base, ticket, state) == ("agents/master", "hypofuzz-default", "exited")
    assert name == "dispatch-agents-hypofuzz-default"
    assert 3600 <= int(age) < 3660, "the run id's suffix is the second it was spawned"
    assert 600 <= int(idle) < 660, "the worklog's mtime is when the worker last said anything"
    assert detail == "attempts=1 exit=0 report=yes models=claude-opus-5-5"
    assert pane == "n", "nothing was started on this check's tmux server"


def test_a_run_without_status_or_runner_is_gone(tmp_path: Path, tmux: dict[str, str]):
    spawned(scratch(tmp_path, "agents", "master"), "greenlet-setting")

    (row,) = rows(tmp_path, tmux)
    assert row[2] == "gone"
    assert "runner dead" in row[7]


def test_a_live_runner_reports_its_worklogs_last_line(tmp_path: Path, tmux: dict[str, str]):
    d = scratch(tmp_path, "agents", "master")
    run = spawned(d, "attach-and-peek")
    (d / f"{run}.log").write_text("first line\nreview round 2: make test 45 passed\n")
    worker = running(d, run)
    try:
        (row,) = rows(tmp_path, tmux)
    finally:
        worker.kill()
        worker.wait()
    assert row[2] == "running"
    assert row[7] == "review round 2: make test 45 passed", "the worklog's last line, without the probe's `log:`"


@pytest.mark.parametrize(("worklog", "said"), [("", "(nothing written yet)"), (None, "(no worklog)")])
def test_an_empty_worklog_reads_apart_from_an_absent_one(tmp_path: Path, tmux: dict[str, str], worklog, said):
    """P4: beside an idle time of hours, a worker that has said nothing is the whole story."""
    d = scratch(tmp_path, "agents", "master")
    run = spawned(d, "hypofuzz-default")
    if worklog is not None:
        (d / f"{run}.log").write_text(worklog)
    worker = running(d, run)
    try:
        (row,) = rows(tmp_path, tmux)
    finally:
        worker.kill()
        worker.wait()
    assert row[2] == "running"
    assert row[7] == said


def test_only_the_newest_run_of_a_ticket_shows(tmp_path: Path, tmux: dict[str, str]):
    """A resumed ticket has several runs in the manifest; the worker is one row, at its latest."""
    d = scratch(tmp_path, "agents", "master")
    old = spawned(d, "hypofuzz-default", at=int(time.time()) - 7200)
    (d / f"{old}.status").write_text("attempts=3 exit=stopped report=no session=aaa models=-\n")
    new = spawned(d, "hypofuzz-default", at=int(time.time()) - 60)
    finished(d, new)

    (row,) = rows(tmp_path, tmux)
    assert row[7] == "attempts=1 exit=0 report=yes models=claude-opus-5-5"
    assert int(row[3]) < 120


def test_every_scratch_dir_on_the_host_is_read(tmp_path: Path, tmux: dict[str, str]):
    spawned(scratch(tmp_path, "agents", "master"), "hypofuzz-default")
    spawned(scratch(tmp_path, "jarvis", "discord-threads"), "thread-registry")
    spawned(scratch(tmp_path, ".dotfiles", "master"), "dns-filter-toggle")

    assert sorted(row[:2] for row in rows(tmp_path, tmux)) == [
        [".dotfiles/master", "dns-filter-toggle"], ["agents/master", "hypofuzz-default"],
        ["jarvis/discord-threads", "thread-registry"]]


def test_a_scratch_dir_that_never_spawned_gives_no_row(tmp_path: Path, tmux: dict[str, str]):
    scratch(tmp_path, "agents", "master")
    assert rows(tmp_path, tmux) == []


def test_a_scratch_dir_staged_per_feature_is_still_read(tmp_path: Path, tmux: dict[str, str]):
    """Before v1.0 a scratch dir was per feature and its worktrees carried the feature's name."""
    d = tmp_path / "agents-testing-workflow"
    d.mkdir()
    (d / "config").write_text("repo=agents\nfeature=testing-workflow\ngit=/nowhere.git\nworktrees=/nowhere\n")
    shutil.copy(SKILL / "dispatch-ctl", d / "dispatch-ctl")
    run = "dispatch-agents-testing-workflow-01-1790000000"
    (d / "manifest").write_text(
        f"dispatch-agents-testing-workflow-01\t{run}\t/nowhere/agents-testing-workflow-01-hypofuzz-default\trw\n")
    (d / f"{run}.status").write_text("attempts=1 exit=0 status=done session=ddd\n")

    (row,) = rows(tmp_path, tmux)
    assert row[:3] == ["agents/testing-workflow", "01-hypofuzz-default", "exited"]


def test_a_probe_that_fails_over_a_manifest_is_a_row_not_an_empty_scratch_dir(tmp_path: Path, tmux: dict[str, str]):
    """A half-staged scratch dir holds runs its probe cannot read; left out, the table would read short."""
    d = scratch(tmp_path, "agents", "master")
    spawned(d, "hypofuzz-default")
    (d / "dispatch-ctl").write_text("exit 3\n")

    (row,) = rows(tmp_path, tmux)
    assert row[:3] == ["agents/master", "-", "unreadable"]
    assert "exit 3" in row[7]


@pytest.mark.full_path
def test_a_live_session_is_a_pane_to_attach_to(tmp_path: Path, tmux: dict[str, str]):
    d = scratch(tmp_path, "agents", "master")
    finished(d, spawned(d, "hypofuzz-default"))
    session(tmux, "dispatch-agents-hypofuzz-default")

    (row,) = rows(tmp_path, tmux)
    assert row[6] == "y", "cleanup has not run, so the finished worker's scrollback is still there"


# --- the commands over those rows --------------------------------------------


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A home whose state root holds one finished worker, `hypofuzz-default` of agents/master."""
    home = tmp_path / "home"
    d = scratch(home / ROOT, "agents", "master")
    run = spawned(d, "hypofuzz-default")
    finished(d, run)
    (d / f"{run}.log").write_text("review round 4 landed\n")
    return home


def dispatch(env: dict[str, str], home: Path, *args: str, hosts: str = SELF, register_exit: int = 0,
             answers: dict[str, tuple[str, int]] | None = None, cwd: Path | None = None,
             ) -> subprocess.CompletedProcess:
    """`dispatch` in <home>, with a register that publishes <hosts> and exits <register_exit>, and an
    ssh that answers each host in <answers> with its rows and exit status."""
    env = adapters(env, home, hosts, FAKE_SSH, register_exit)
    (home / "bin" / "ssh-answers").mkdir(exist_ok=True)
    for host, (said, rc) in (answers or {}).items():
        (home / "bin" / "ssh-answers" / host).write_text(said + "\n")
        (home / "bin" / "ssh-answers" / f"{host}.rc").write_text(f"{rc}\n")
    return subprocess.run(["bash", str(DISPATCH), *args], capture_output=True, text=True, cwd=str(cwd or home),
                          timeout=60, env=env)


def adapters(env: dict[str, str], home: Path, hosts: str, ssh: str, register_exit: int = 0) -> dict[str, str]:
    """<env> as `dispatch` in <home> runs in it: a register that publishes <hosts> and exits
    <register_exit>, and the ssh script <ssh>, both in <home>/bin."""
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "worker-hosts").write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' {hosts}\nexit {register_exit}\n")
    (bin_dir / "ssh").write_text(ssh)
    for f in ("worker-hosts", "ssh"):
        (bin_dir / f).chmod(0o755)
    return {**env, "HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}", "GIT_CONFIG_GLOBAL": "/dev/null"}


def ssh_calls(home: Path) -> list[str]:
    calls = home / "bin" / "ssh.calls"
    return calls.read_text().splitlines() if calls.exists() else []


def elsewhere(slug: str, base: str = "agents/master", detail: str = "on the other host") -> tuple[str, int]:
    """A remote host's answer: one running worker, with its session up."""
    repo = base.split("/")[0]
    return f"{base}\t{slug}\trunning\t60\t5\tdispatch-{repo}-{slug}\ty\t{detail}", 0


def test_the_table_names_its_columns_and_the_worker(home: Path, tmux: dict[str, str]):
    out = dispatch(tmux, home, "ps")
    assert out.returncode == 0, out.stderr
    header, row, gap, tally = out.stdout.splitlines()
    assert header.split() == ["HOST", "BASE", "TICKET", "STATE", "AGE", "IDLE", "DETAIL"]
    assert row.split()[:4] == [SELF, "agents/master", "hypofuzz-default", "exited"]
    assert re.fullmatch(r"\d+s", row.split()[4]), "spawned seconds ago"
    assert (gap, tally) == ("", "0 running  1 exited"), "running and exited hold their places at zero"
    assert "\x1b[" not in out.stdout, "no color into a pipe unless asked"


def test_under_watch_the_table_is_cut_to_its_width_and_painted_when_asked(home: Path, tmux: dict[str, str]):
    """`watch` runs ps with no terminal and the width in COLUMNS, and shows color only with
    `watch -c` and `ps --color`. A running worker silent for a quarter hour is painted apart from
    one that is not."""
    far = {"agent@far": (elsewhere("quiet-one")[0].replace("\t5\t", "\t1000\t") + "\n"
                         + elsewhere("busy-one", detail="x" * 200)[0], 0)}
    cut = dispatch({**tmux, "COLUMNS": "90"}, home, "ps", hosts=f"{SELF} agent@far", answers=far)
    assert cut.returncode == 0, cut.stderr
    assert max(map(len, cut.stdout.splitlines())) == 90
    assert cut.stdout.splitlines()[-1] == "2 running  1 exited"

    painted = dispatch({**tmux, "COLUMNS": "90"}, home, "ps", "--color", hosts=f"{SELF} agent@far", answers=far)
    lines = {line.split()[2]: line for line in painted.stdout.splitlines() if "-one" in line}
    assert "\x1b[1;32mrunning" in lines["busy-one"]
    assert "\x1b[33m" in lines["quiet-one"] and "\x1b[33m" not in lines["busy-one"]
    assert max(len(re.sub(r"\x1b\[[0-9;]*m", "", line)) for line in painted.stdout.splitlines()) == 90

    assert "\x1b[" not in dispatch({**tmux, "NO_COLOR": "1"}, home, "ps", "--color", hosts=f"{SELF} agent@far", answers=far).stdout


def test_the_running_workers_come_first_and_the_exited_ones_last(home: Path, tmux: dict[str, str]):
    """Whatever host they are on: the live runs are what a glance at the table is for, and what did
    not get read comes next."""
    out = dispatch(tmux, home, "ps", hosts=f"{SELF} zz@far zz@off", answers={"zz@far": elsewhere("busy-one")})
    states = [line.split()[3] for line in out.stdout.splitlines()[1:-2]]
    assert states == ["running", "unreachable", "exited"], out.stdout


def test_within_a_state_the_youngest_worker_comes_first(home: Path, tmux: dict[str, str]):
    """By age, then by idle time, whatever their host, base or ticket."""
    def row(slug: str, age: int, idle: int) -> str:
        return f"aa/master\t{slug}\trunning\t{age}\t{idle}\tdispatch-aa-{slug}\ty\tworking"
    far = {"zz@far": ("\n".join([row("aaa-old", 9000, 5), row("bbb-quiet", 60, 50), row("zzz-new", 60, 5)]), 0)}
    out = dispatch(tmux, home, "ps", hosts="zz@far", answers=far)
    assert [line.split()[2] for line in out.stdout.splitlines()[1:-2]] == ["zzz-new", "bbb-quiet", "aaa-old"]


def test_the_hosts_are_the_registers_and_the_repos_runs_from_anywhere_in_it(home: Path, tmux: dict[str, str]):
    """The register names one host, the repo's runs another, and ps is run from a subdirectory on a
    branch no run was spawned from: both hosts are read."""
    repo = home / "repo"
    (repo / "deep" / "er").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "elsewhere", str(repo)], check=True)
    (repo / ".git" / "dispatch").mkdir()
    (repo / ".git" / "dispatch" / "runs").write_text("master\tsome-slug\tagent@far\n")

    out = dispatch(tmux, home, "ps", answers={"agent@far": elsewhere("far-away")}, cwd=repo / "deep" / "er")
    assert out.returncode == 0, out.stderr
    assert "hypofuzz-default" in out.stdout, "the register's host"
    assert "far-away" in out.stdout, "the host the repo's runs name"


def test_peek_without_a_worker_says_so(home: Path, tmux: dict[str, str]):
    """Its own message, not bash's `$1: unbound variable`."""
    out = dispatch(tmux, home, "peek")
    assert out.returncode != 0
    assert "takes a worker" in out.stderr


@pytest.mark.full_path
@pytest.mark.parametrize("worker", ["hypofuzz-default", "dispatch-agents-hypofuzz-default",
                                    f"{SELF}/hypofuzz-default", f"{SELF}/dispatch-agents-hypofuzz-default"])
def test_every_way_of_naming_one_worker(home: Path, tmux: dict[str, str], worker: str):
    session(tmux, "dispatch-agents-hypofuzz-default")

    out = dispatch(tmux, home, "peek", worker)
    assert out.returncode == 0, out.stderr
    assert "hypofuzz-default" in out.stderr


@pytest.mark.full_path
@pytest.mark.parametrize("fragment", ["hypofuzz", "hypofuzz-defaul", "dispatch-agents-hypofuzz",
                                      "agents/master/hypofuzz-default"])
def test_a_fragment_of_a_worker_names_none(home: Path, tmux: dict[str, str], fragment: str):
    """P3: a fragment that matched would make attach a guess."""
    session(tmux, "dispatch-agents-hypofuzz-default")

    out = dispatch(tmux, home, "peek", fragment)
    assert out.returncode != 0
    assert "no worker called" in out.stderr


@pytest.mark.full_path
def test_a_slug_that_is_only_a_number_is_still_a_name(home: Path, tmux: dict[str, str]):
    """`1` and `01` are equal numbers and different names; a slug is a name."""
    d = scratch(home / ROOT, "jarvis", "main")
    finished(d, spawned(d, "01"))
    session(tmux, "dispatch-jarvis-01")

    assert dispatch(tmux, home, "peek", "01").returncode == 0
    out = dispatch(tmux, home, "peek", "1")
    assert out.returncode != 0
    assert "no worker called" in out.stderr


def test_a_slug_on_two_hosts_lists_both_and_resolves_neither(home: Path, tmux: dict[str, str]):
    """P3: each candidate with the form that names it alone, its host's."""
    out = dispatch(tmux, home, "attach", "hypofuzz-default", hosts=f"{SELF} agent@far",
                   answers={"agent@far": elsewhere("hypofuzz-default")})
    assert out.returncode != 0
    assert "is 2 workers" in out.stderr
    assert f"dispatch attach {SELF}/hypofuzz-default" in out.stderr
    assert "dispatch attach agent@far/hypofuzz-default" in out.stderr
    assert [c for c in ssh_calls(home) if "tmux attach" in c] == [], "resolved to nothing, attached to nothing"


def test_a_slug_in_two_repos_on_one_host_is_told_apart_by_session(home: Path, tmux: dict[str, str]):
    """The host names both, so the form to type is the host and the session."""
    d = scratch(home / ROOT, "jarvis", "main")
    finished(d, spawned(d, "hypofuzz-default"))

    out = dispatch(tmux, home, "peek", "hypofuzz-default")
    assert out.returncode != 0
    assert "is 2 workers" in out.stderr
    assert f"dispatch peek {SELF}/dispatch-agents-hypofuzz-default" in out.stderr
    assert f"dispatch peek {SELF}/dispatch-jarvis-hypofuzz-default" in out.stderr


@pytest.mark.parametrize(("answer", "why"), [(None, "no answer from the host"), (("", 3), "dispatch-ps failed there")])
def test_a_host_that_does_not_answer_is_a_row_and_a_nonzero_exit(home: Path, tmux: dict[str, str], answer, why):
    """P1: dropped instead, it would read as a host with nothing running."""
    out = dispatch(tmux, home, "ps", hosts=f"{SELF} agent@off", answers={"agent@off": answer} if answer else None)
    assert out.returncode != 0
    (row,) = [line for line in out.stdout.splitlines() if line.startswith("agent@off")]
    assert "unreachable" in row and why in row
    assert "hypofuzz-default" in out.stdout, "the host that did answer is still read"
    assert out.stdout.splitlines()[-1] == "0 running  1 exited  1 unreachable", "the rest after them, as they appear"


def test_a_scratch_dir_left_unread_makes_the_table_incomplete(home: Path, tmux: dict[str, str]):
    d = scratch(home / ROOT, "jarvis", "main")
    spawned(d, "thread-registry")
    (d / "dispatch-ctl").write_text("exit 3\n")

    out = dispatch(tmux, home, "ps")
    assert out.returncode != 0
    assert "unreadable" in out.stdout
    assert "hypofuzz-default" in out.stdout, "the scratch dir beside it is still read"


@pytest.mark.full_path
def test_a_pane_that_cannot_be_read_is_a_failed_peek_not_an_empty_one(home: Path, tmux: dict[str, str]):
    """The session can end between the read that resolved it and the capture."""
    session(tmux, "dispatch-agents-hypofuzz-default")
    wrapper = home / "bin" / "tmux"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    real = shutil.which("tmux", path=tmux["PATH"])
    wrapper.write_text(f'#!/usr/bin/env bash\n[ "$1" = capture-pane ] && exit 1\nexec {real} "$@"\n')
    wrapper.chmod(0o755)

    out = dispatch(tmux, home, "peek", "hypofuzz-default")
    assert out.returncode != 0
    assert "could not read the pane" in out.stderr


def test_a_worker_not_found_while_a_host_was_missing_says_so(home: Path, tmux: dict[str, str]):
    """Plain `no such worker` would be wrong: it may be on the host that did not answer."""
    out = dispatch(tmux, home, "peek", "nowhere-slug", hosts=f"{SELF} agent@off")
    assert out.returncode != 0
    assert "agent@off did not" in out.stderr


def test_a_register_that_fails_is_a_row_beside_the_hosts_that_are_left(home: Path, tmux: dict[str, str]):
    """P2: its silence would shrink the host set under a table that still reads complete."""
    subprocess.run(["git", "init", "-q", str(home)], check=True)
    (home / ".git" / "dispatch").mkdir()
    (home / ".git" / "dispatch" / "runs").write_text("master\thypofuzz-default\tlocal\n")

    out = dispatch(tmux, home, "ps", hosts="", register_exit=2)
    assert out.returncode != 0, "a table missing a host it should have asked is no clean reading"
    (row,) = [line for line in out.stdout.splitlines() if line.startswith("worker-hosts")]
    assert "incomplete" in row
    assert "hypofuzz-default" in out.stdout, "the host the repo's runs name is still read"


def test_a_register_that_fails_with_nothing_left_names_itself(home: Path, tmux: dict[str, str]):
    """Dying with `publishes none` would blame the register for its own breakage."""
    out = dispatch(tmux, home, "ps", hosts="", register_exit=2)
    assert out.returncode != 0
    assert "worker-hosts --targets failed" in out.stderr


def test_a_run_recorded_on_local_is_listed_under_this_machines_name(home: Path, tmux: dict[str, str]):
    """A run recorded on `local`, as this machine was named before it was named like any other host,
    and this machine's register entry are one host: listed once, under the register's name, and
    read without ssh."""
    subprocess.run(["git", "init", "-q", str(home)], check=True)
    (home / ".git" / "dispatch").mkdir()
    (home / ".git" / "dispatch" / "runs").write_text("master\thypofuzz-default\tlocal\n")

    out = dispatch(tmux, home, "ps", hosts=SELF, answers={SELF: elsewhere("reached-by-ssh")})
    assert out.returncode == 0, out.stderr
    (_, row, _, _) = out.stdout.splitlines()
    assert row.split()[:3] == [SELF, "agents/master", "hypofuzz-default"]
    assert ssh_calls(home) == []


@pytest.mark.full_path
def test_peek_prints_the_last_lines_of_the_workers_pane(home: Path, tmux: dict[str, str]):
    session(tmux, "dispatch-agents-hypofuzz-default", "seq 1 40; sleep 30")
    time.sleep(0.5)

    out = dispatch(tmux, home, "peek", "hypofuzz-default", "3")
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["38", "39", "40"]
    assert "hypofuzz-default" in out.stderr, "which worker it is goes to stderr, so the pane pipes clean"


def test_a_worker_whose_session_is_gone_is_not_attached_to(home: Path, tmux: dict[str, str]):
    out = dispatch(tmux, home, "attach", "hypofuzz-default")
    assert out.returncode != 0
    assert "tmux session is gone" in out.stderr


def test_attach_to_a_remote_worker_is_ssh_with_a_terminal(home: Path, tmux: dict[str, str]):
    out = dispatch(tmux, home, "attach", "far-away", hosts=f"{SELF} agent@far",
                   answers={"agent@far": elsewhere("far-away")})
    assert out.returncode == 0, out.stderr
    assert ssh_calls(home)[-1] == "agent@far\ttmux attach -t \\=dispatch-agents-far-away:", \
        "the line on_host builds, its leading `=` escaped for a zsh login shell"
    assert (home / "bin" / "ssh.calls").read_text().count("\n") == 2, "one read, then the attach"


# ssh as the real one delivers a command: the arguments after the host joined into one line, run by
# the remote user's login shell, which is REMOTE_SHELL here, in the remote home.
LOGIN_SHELL_SSH = """#!/usr/bin/env bash
while [[ ${1:-} == -* ]]; do case $1 in -o) shift 2 ;; *) shift ;; esac; done
shift
cd "$REMOTE_HOME" && HOME=$REMOTE_HOME exec "$REMOTE_SHELL" -c "$*"
"""


@pytest.mark.full_path
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_remote_login_shell_hands_every_word_to_the_command_as_sent(
        tmp_path: Path, home: Path, tmux: dict[str, str], shell: str):
    """A tmux target starts with `=`, which zsh reads as the path of a command: `=name` unescaped
    never reaches tmux. The host is `agent@far`, whose home is <home> and whose login shell is
    <shell>; ps reads it, peek captures its pane and attach reaches its tmux, all through ssh."""
    login = shutil.which(shell)
    if login is None:
        pytest.skip(f"no {shell} here; the escaped form is pinned by the remote attach check")
    session(tmux, "dispatch-agents-hypofuzz-default", "printf 'said on far\\n'; sleep 30")
    here = tmp_path / "here"
    fakes = here / "bin"
    fakes.mkdir(parents=True)
    (fakes / "ssh").write_text(LOGIN_SHELL_SSH)
    (fakes / "ssh").chmod(0o755)
    (fakes / "worker-hosts").write_text("#!/bin/sh\necho agent@far\n")
    (fakes / "worker-hosts").chmod(0o755)
    real = shutil.which("tmux", path=tmux["PATH"])
    (fakes / "tmux").write_text(
        f'#!/usr/bin/env bash\n[ "$1" = attach ] || exec {real} "$@"\necho "$*" > {here / "attached"}\n')
    (fakes / "tmux").chmod(0o755)
    env = {**tmux, "HOME": str(here), "PATH": f"{fakes}:{tmux['PATH']}", "REMOTE_HOME": str(home),
           "REMOTE_SHELL": login}

    def dispatched(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(DISPATCH), *args], capture_output=True, text=True, cwd=here,
                              env=env, timeout=60)

    listed = dispatched("ps")
    assert listed.returncode == 0, listed.stderr
    assert "agent@far" in listed.stdout and "hypofuzz-default" in listed.stdout
    time.sleep(0.5)
    peeked = dispatched("peek", "hypofuzz-default", "12")
    assert peeked.returncode == 0, peeked.stderr
    assert "said on far" in peeked.stdout
    attached = dispatched("attach", "hypofuzz-default")
    assert attached.returncode == 0, attached.stderr
    assert (here / "attached").read_text().strip() == "attach -t =dispatch-agents-hypofuzz-default:"


@pytest.mark.full_path
def test_attach_to_a_local_worker_is_tmux_outside_any_session(home: Path, tmux: dict[str, str]):
    """Inside the caller's own tmux, a plain attach refuses to nest; TMUX unset, it nests."""
    session(tmux, "dispatch-agents-hypofuzz-default")
    wrapper = home / "bin" / "tmux"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    real = shutil.which("tmux", path=tmux["PATH"])
    wrapper.write_text(
        f'#!/usr/bin/env bash\n[ "$1" = attach ] || exec {real} "$@"\n'
        f'echo "TMUX=${{TMUX-unset}} $*" > {home / "attached"}\n')
    wrapper.chmod(0o755)

    out = dispatch({**tmux, "TMUX": "/tmp/somebodys-socket,1,0"}, home, "attach", "hypofuzz-default")
    assert out.returncode == 0, out.stderr
    assert (home / "attached").read_text().strip() == "TMUX=unset attach -t =dispatch-agents-hypofuzz-default:"
    assert "prefix twice" in out.stderr


@pytest.mark.full_path
def test_ctrl_c_in_a_pane_ends_the_run_the_way_stop_does(tmp_path: Path, tmux: dict[str, str]):
    """P5, what attach invites: a Ctrl-C leaves the status line a resume needs, rather than killing
    the runner before its last act."""
    state = tmp_path / "state"
    state.mkdir()
    stage_runner(state)
    (tmp_path / "message.md").write_text("Work it.\n")
    started = tmp_path / "started"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(f'#!/bin/sh\n[ "$1" = --version ] && exit 0\ntouch {started}\nsleep 30\n')
    (bin_dir / "claude").chmod(0o755)
    env = {**tmux, "PATH": f"{bin_dir}:{tmux['PATH']}", "HOME": str(tmp_path), "DISPATCH_PLUGIN_DIR": str(mx(tmp_path))}
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", "runner", "-c", str(tmp_path),
         f"bash {state / 'run-worker.sh'} {tmp_path / 'message.md'} warm-preset opus therun; sleep 30"],
        env=env, check=True)
    status = state / "therun.status"
    for _ in range(80):
        if started.exists():
            break
        time.sleep(0.25)
    assert started.exists(), "the worker never started"
    subprocess.run(["tmux", "send-keys", "-t", "=runner:", "C-c"], env=env, check=True)
    for _ in range(80):
        if status.exists():
            break
        time.sleep(0.25)
    assert status.exists(), "no status line: the run reads as a crash and cannot be resumed"
    written = status.read_text()
    assert "exit=stopped" in written
    assert re.search(r"session=[0-9a-f-]{36}", written), f"a resume needs the session id: {written}"


# --- following: ps --follow ---------------------------------------------------
# Each check follows for seconds of wall clock, so all of them are full-path checks.


# ssh to a host whose home is hosts/<host> beside it: the command runs there in bash, as a login
# shell runs it, and every call is recorded host first. A host with no home is off. Once
# hosts/<host>.hung exists, the host's output stops arriving (it leaves hosts/<host>.silent when it
# does) and the connection drops a third of ServerAliveInterval x ServerAliveCountMax seconds
# later, as ssh's keepalive drops it; with no keepalive it never drops.
FOLLOW_SSH = """#!/usr/bin/env bash
alive=0 count=3
while [[ ${1:-} == -* ]]; do
    case $1 in
        -o) case $2 in ServerAliveInterval=*) alive=${2#*=} ;; ServerAliveCountMax=*) count=${2#*=} ;; esac
            shift 2 ;;
        *)  shift ;;
    esac
done
host=$1; shift
here=$(dirname "$0")
printf '%s\\t%s\\n' "$host" "$*" >> "$here/ssh.calls"
home=$here/hosts/$host
[ -d "$home" ] || { echo "ssh: connect to host $host: No route to host" >&2; exit 255; }
cd "$home" && HOME=$home bash -c "$*" | while IFS= read -r line; do
    [ -e "$home.hung" ] && { touch "$home.silent"; exit; }
    printf '%s\\n' "$line"
done
rc=${PIPESTATUS[0]}
[ -e "$home.hung" ] || exit "$rc"
[ "$alive" -gt 0 ] || sleep infinity
sleep $((alive * count / 3))
exit 255
"""


def until(check, within: float = 20):
    """<check>'s first truthy answer, or its last one when <within> seconds run out."""
    deadline = time.monotonic() + within
    while not (answer := check()) and time.monotonic() < deadline:
        time.sleep(0.2)
    return answer


class Following:
    """`dispatch ps --follow` in <home>, over a register that publishes <hosts> and FOLLOW_SSH."""

    def __init__(self, env: dict[str, str], home: Path, hosts: str):
        self.home = home
        self.env = adapters(env, home, hosts, FOLLOW_SSH)
        self.out = home / "follow.out"
        with self.out.open("w") as out:
            # A session of its own, so the check can see what of it is left once it is stopped.
            self.proc = subprocess.Popen(["bash", str(DISPATCH), "ps", "--follow"], stdout=out,
                                         stderr=subprocess.STDOUT, cwd=home, env=self.env, start_new_session=True)

    def drawn(self) -> str:
        """The table on screen now: the last whole draw, as plain text."""
        draws = [d for d in self.out.read_text().split("\x1b[H") if d.endswith("\x1b[J")]
        return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", draws[-1]) if draws else ""

    def printed(self) -> str:
        """What `dispatch ps` prints now, over the same hosts."""
        return subprocess.run(["bash", str(DISPATCH), "ps"], capture_output=True, text=True, cwd=self.home,
                              env=self.env, timeout=60).stdout.rstrip("\n")

    def shows(self, check, within: float = 20) -> str:
        """The table drawn once <check> holds of it, or the last one drawn when <within> seconds run out."""
        def held() -> str | None:
            table = self.drawn()
            return table if check(table) else None
        return until(held, within) or self.drawn()

    def matches_ps(self, within: float = 20) -> tuple[str, str]:
        """The drawn table and ps's output, once they agree or <within> seconds run out."""
        def agreed() -> tuple[str, str] | None:
            pair = self.drawn(), self.printed()
            return pair if pair[0] == pair[1] else None
        return until(agreed, within) or (self.drawn(), self.printed())

    def logins(self, host: str) -> int:
        return sum(1 for c in ssh_calls(self.home) if c.split("\t")[0] == host)

    def left(self) -> list[str]:
        """Every process of the follow's session still running."""
        out = subprocess.run(["pgrep", "-a", "-s", str(self.proc.pid)], capture_output=True, text=True)
        return out.stdout.splitlines()

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)


@pytest.fixture
def follow(tmux: dict[str, str]) -> Iterator:
    """Starts a Following; every one started is stopped at the end, and anything left of it killed."""
    started: list[Following] = []

    def start(home: Path, hosts: str = SELF, **env: str) -> Following:
        started.append(Following({**tmux, **env}, home, hosts))
        return started[-1]

    yield start
    for f in started:
        f.stop()
        try:
            os.killpg(f.proc.pid, 9)
        except ProcessLookupError:
            pass


def remote(home: Path, name: str) -> Path:
    """The home of the host <name>, which FOLLOW_SSH reaches from <home>. Made before the follow
    starts, or its first connection finds a host that is off."""
    there = home / "bin" / "hosts" / name
    there.mkdir(parents=True, exist_ok=True)
    return there


def aged(root: Path, repo: str, slug: str, seconds: int) -> Path:
    """A finished run of <slug> spawned <seconds> ago, whose worklog last spoke then too; its
    scratch dir."""
    d = root / f"{repo}-master"
    if not d.exists():
        d = scratch(root, repo, "master")
    run = spawned(d, slug, at=int(time.time()) - seconds)
    log = d / f"{run}.log"
    log.write_text("said its last\n")
    os.utime(log, (time.time() - seconds, time.time() - seconds))
    finished(d, run)
    return d


@pytest.mark.full_path
def test_following_draws_what_ps_prints(tmp_path: Path, follow):
    """dispatch-ps-follow P3, across what a host's rows are read from: a worklog line, a runner
    that dies, a new run."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 7200)
    d = aged(remote(home, "agent@far") / ROOT, "jarvis", "thread-registry", 9000)
    live = spawned(d, "dns-filter-toggle", at=int(time.time()) - 7200)
    log = d / f"{live}.log"
    log.write_text("working\n")
    os.utime(log, (time.time() - 7200, time.time() - 7200))
    worker = running(d, live)
    f = follow(home, f"{SELF} agent@far")
    try:
        drawn, printed = f.matches_ps()
        assert re.search(r"dns-filter-toggle +running", drawn), drawn
        assert drawn == printed

        with log.open("a") as said:
            said.write("review round 2: make test 45 passed\n")
        drawn, printed = f.matches_ps()
        assert "review round 2" in drawn
        assert drawn == printed

        worker.kill()
        worker.wait()
        drawn, printed = f.matches_ps()
        assert re.search(r"dns-filter-toggle +gone", drawn)
        assert drawn == printed

        finished(d, spawned(d, "late-comer", at=int(time.time()) - 7200))
        drawn, printed = f.matches_ps()
        assert "late-comer" in drawn
        assert drawn == printed
    finally:
        worker.kill()


@pytest.mark.full_path
def test_a_frames_ages_count_on_until_the_next(tmp_path: Path, follow):
    """dispatch-ps-follow P3: nothing on the host changes, so no frame comes, and the age drawn is
    still the one ps prints."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 35)
    f = follow(home)
    assert re.search(r" [345]\ds ", f.shows(lambda t: "hypofuzz-default" in t))
    assert " 1m " in f.shows(lambda t: " 1m " in t, within=40)
    drawn, printed = f.matches_ps()
    assert drawn == printed


@pytest.mark.full_path
def test_a_silent_host_holds_up_no_other_and_comes_back_on_one_more_login(tmp_path: Path, follow):
    """dispatch-ps-follow P1 and P2: a change reaches the table over the one login; while a host is
    silent the other hosts' rows still move; it turns `unreachable` once its keepalive drops it, and
    its reconnect is the only other login."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 7200)
    far = remote(home, "agent@far")
    aged(far / ROOT, "jarvis", "far-one", 7200)
    stuck = remote(home, "agent@stuck")
    aged(stuck / ROOT, "jarvis", "stuck-one", 7200)
    f = follow(home, f"{SELF} agent@far agent@stuck")
    assert "stuck-one" in f.shows(lambda t: "far-one" in t and "stuck-one" in t)
    aged(stuck / ROOT, "jarvis", "stuck-two", 7200)
    assert "stuck-two" in f.shows(lambda t: "stuck-two" in t)
    assert f.logins("agent@stuck") == 1

    stuck.with_suffix(".hung").touch()
    assert until(stuck.with_suffix(".silent").exists)
    aged(far / ROOT, "jarvis", "far-two", 7200)
    aged(home / ROOT, "agents", "here-two", 7200)
    table = f.shows(lambda t: "far-two" in t and "here-two" in t, within=8)
    assert "far-two" in table and "here-two" in table and "stuck-one" in table

    table = f.shows(lambda t: "unreachable" in t)
    assert "stuck-one" not in table and "no answer from the host" in table
    stuck.with_suffix(".hung").unlink()
    assert "stuck-one" in f.shows(lambda t: "stuck-one" in t, within=30)
    assert f.logins("agent@stuck") == 2


@pytest.mark.full_path
def test_a_host_that_is_off_is_asked_less_and_less_often(tmp_path: Path, follow):
    """dispatch-ps-follow P1: a host that stays off costs a login per backoff, which doubles: 0, 2,
    6 and 14 seconds in, where a fixed retry would be twice as many."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 7200)
    f = follow(home, f"{SELF} agent@off")
    assert "agent@off" in f.shows(lambda t: "unreachable" in t)
    time.sleep(12)
    assert 2 <= f.logins("agent@off") <= 3


@pytest.mark.full_path
def test_a_host_silent_from_the_start_holds_up_no_other(tmp_path: Path, follow):
    """dispatch-ps-follow P2 before the first frame: the hosts that answered are drawn at once, the
    silent one as `connecting` until its connection drops."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 7200)
    stuck = remote(home, "agent@stuck")
    aged(stuck / ROOT, "jarvis", "stuck-one", 7200)
    stuck.with_suffix(".hung").touch()
    f = follow(home, f"{SELF} agent@stuck")
    table = f.shows(lambda t: "hypofuzz-default" in t, within=5)
    assert "hypofuzz-default" in table
    assert re.search(r"agent@stuck +- +- +connecting", table), table
    assert "unreachable" in f.shows(lambda t: "unreachable" in t)


@pytest.mark.full_path
def test_a_stopped_follow_leaves_nothing_running(tmp_path: Path, follow):
    """Its loops on the hosts end with it, rather than scanning on for nobody."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 7200)
    aged(remote(home, "agent@far") / ROOT, "jarvis", "far-one", 7200)
    f = follow(home, f"{SELF} agent@far")
    assert "far-one" in f.shows(lambda t: "far-one" in t)
    assert any("--follow" in p for p in f.left())

    f.stop()
    assert until(lambda: not f.left(), within=10), f.left()


@pytest.mark.full_path
def test_a_host_the_register_comes_to_publish_is_followed(tmp_path: Path, follow):
    """dispatch-ps-follow P3: ps asks for the hosts on every run, and a follow asks again every half
    minute."""
    home = tmp_path / "home"
    aged(home / ROOT, "agents", "hypofuzz-default", 7200)
    aged(remote(home, "agent@far") / ROOT, "jarvis", "far-one", 7200)
    f = follow(home)
    assert "hypofuzz-default" in f.shows(lambda t: "hypofuzz-default" in t)
    (home / "bin" / "worker-hosts").write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' {SELF} agent@far\n")
    drawn, printed = f.matches_ps(within=45)
    assert "far-one" in drawn
    assert drawn == printed


@pytest.mark.full_path
def test_a_table_taller_than_the_screen_keeps_its_header_and_tally(tmp_path: Path, follow):
    """Printed whole, it would scroll on every draw. LINES is the height with no terminal."""
    home = tmp_path / "home"
    for n in range(10):
        aged(home / ROOT, "agents", f"ticket-{n}", 7200)
    f = follow(home, LINES="8")
    printed = f.printed().splitlines()
    assert len(printed) == 13, "a header, ten rows, a blank line and the tally"
    drawn = f.shows(lambda t: "ticket-" in t).splitlines()
    assert drawn == [*printed[:5], "(6 more rows than the screen holds)", *printed[-2:]]


@pytest.mark.full_path
def test_a_table_taller_than_the_screen_folds_its_exited_workers_first(tmp_path: Path, follow):
    """Ten workers of one base that exited cleanly, which a screen 9 lines tall and 100 wide holds
    in two lines under TICKET, below the running one and the one that failed."""
    home = tmp_path / "home"
    for n in range(10):
        d = aged(home / ROOT, "agents", f"ticket-{n}", 7200)
    failed = spawned(d, "broke-one")
    (d / f"{failed}.status").write_text("attempts=1 exit=1 report=no session=ccc models=claude-opus-5-5\n")
    live = running(d, spawned(d, "busy-one"))
    try:
        f = follow(home, LINES="9", COLUMNS="100")
        drawn = f.shows(lambda t: "ticket-9" in t and "busy-one" in t).splitlines()
        assert len(drawn) == 8, drawn
        assert re.match(re.escape(SELF) + r" +agents/master +busy-one +running", drawn[1])
        assert re.match(re.escape(SELF) + r" +agents/master +broke-one +exited .* exit=1 report=no", drawn[2])
        assert drawn[3].split() == ["exited,", "each", "beside", "its", "IDLE"]
        ticket = drawn[3].index("exited")
        assert drawn[4][:ticket].split() == [SELF, "agents/master"] and not drawn[5][:ticket].strip()
        assert sorted(re.findall(r"ticket-\d 2h", drawn[4] + drawn[5])) == [f"ticket-{n} 2h" for n in range(10)]
        assert drawn[-2:] == ["", "1 running  11 exited"]
    finally:
        live.kill()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
