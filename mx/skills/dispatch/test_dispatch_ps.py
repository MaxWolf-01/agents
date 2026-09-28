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
one; P5 a Ctrl-C in a worker's pane leaves the status line a resume needs.
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

from test_dispatch import stage_runner

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
    """
    sockets = Path("/tmp") / f"dispatch-ps-check-{hashlib.sha1(str(tmp_path).encode()).hexdigest()[:12]}"
    sockets.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    env["TMUX_TMPDIR"] = str(sockets)
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

    assert sorted(row[0] for row in rows(tmp_path, tmux)) == ["agents/master", "jarvis/discord-threads"]


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


def test_a_live_session_is_a_pane_to_attach_to(tmp_path: Path, tmux: dict[str, str]):
    d = scratch(tmp_path, "agents", "master")
    finished(d, spawned(d, "hypofuzz-default"))
    session(tmux, "dispatch-agents-hypofuzz-default")

    (row,) = rows(tmp_path, tmux)
    assert row[6] == "y", "cleanup has not run, so the finished worker's scrollback is still there"


def test_a_fuzz_run_is_a_row_with_ticket_fuzz(tmp_path: Path, tmux: dict[str, str]):
    """It holds no manifest line: its session is the whole of its state."""
    scratch(tmp_path, "agents", "master")
    session(tmux, "fuzz-agents-master")

    (row,) = rows(tmp_path, tmux)
    assert row[:3] == ["agents/master", "fuzz", "running"]
    assert row[5] == "fuzz-agents-master"
    assert row[4] == "-", "no worklog, so nothing to be idle against"
    assert int(row[3]) < 60


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


def dispatch(env: dict[str, str], home: Path, *args: str, hosts: str = "local", register_exit: int = 0,
             answers: dict[str, tuple[str, int]] | None = None, cwd: Path | None = None,
             ) -> subprocess.CompletedProcess:
    """`dispatch` in <home>, with a register that publishes <hosts> and exits <register_exit>, and an
    ssh that answers each host in <answers> with its rows and exit status."""
    bin_dir = home / "bin"
    (bin_dir / "ssh-answers").mkdir(parents=True, exist_ok=True)
    register = bin_dir / "worker-hosts"
    register.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' {hosts}\nexit {register_exit}\n")
    register.chmod(0o755)
    (bin_dir / "ssh").write_text(FAKE_SSH)
    (bin_dir / "ssh").chmod(0o755)
    for host, (said, rc) in (answers or {}).items():
        (bin_dir / "ssh-answers" / host).write_text(said + "\n")
        (bin_dir / "ssh-answers" / f"{host}.rc").write_text(f"{rc}\n")
    return subprocess.run(
        ["bash", str(DISPATCH), *args], capture_output=True, text=True, cwd=str(cwd or home), timeout=60,
        env={**env, "HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}", "GIT_CONFIG_GLOBAL": "/dev/null"},
    )


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
    header, row = out.stdout.splitlines()
    assert header.split() == ["HOST", "BASE", "TICKET", "STATE", "AGE", "IDLE", "DETAIL"]
    assert row.split()[:4] == ["local", "agents/master", "hypofuzz-default", "exited"]
    assert re.fullmatch(r"\d+s", row.split()[4]), "spawned seconds ago"


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


@pytest.mark.parametrize("worker", ["hypofuzz-default", "dispatch-agents-hypofuzz-default",
                                    "local/hypofuzz-default", "local/dispatch-agents-hypofuzz-default"])
def test_every_way_of_naming_one_worker(home: Path, tmux: dict[str, str], worker: str):
    session(tmux, "dispatch-agents-hypofuzz-default")

    out = dispatch(tmux, home, "peek", worker)
    assert out.returncode == 0, out.stderr
    assert "hypofuzz-default" in out.stderr


@pytest.mark.parametrize("fragment", ["hypofuzz", "fuzz", "hypofuzz-defaul", "dispatch-agents-hypofuzz",
                                      "agents/master/hypofuzz-default"])
def test_a_fragment_of_a_worker_names_none(home: Path, tmux: dict[str, str], fragment: str):
    """P3: a fragment that matched would make attach a guess, and `fuzz` is a worker of its own."""
    session(tmux, "dispatch-agents-hypofuzz-default")

    out = dispatch(tmux, home, "peek", fragment)
    assert out.returncode != 0
    assert "no worker called" in out.stderr


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
    out = dispatch(tmux, home, "attach", "hypofuzz-default", hosts="local agent@far",
                   answers={"agent@far": elsewhere("hypofuzz-default")})
    assert out.returncode != 0
    assert "is 2 workers" in out.stderr
    assert "dispatch attach local/hypofuzz-default" in out.stderr
    assert "dispatch attach agent@far/hypofuzz-default" in out.stderr
    assert [c for c in ssh_calls(home) if "tmux attach" in c] == [], "resolved to nothing, attached to nothing"


def test_a_slug_in_two_repos_on_one_host_is_told_apart_by_session(home: Path, tmux: dict[str, str]):
    """The host names both, so the form to type is the host and the session."""
    d = scratch(home / ROOT, "jarvis", "main")
    finished(d, spawned(d, "hypofuzz-default"))

    out = dispatch(tmux, home, "peek", "hypofuzz-default")
    assert out.returncode != 0
    assert "is 2 workers" in out.stderr
    assert "dispatch peek local/dispatch-agents-hypofuzz-default" in out.stderr
    assert "dispatch peek local/dispatch-jarvis-hypofuzz-default" in out.stderr


@pytest.mark.parametrize(("answer", "why"), [(None, "no answer from the host"), (("", 3), "dispatch-ps failed there")])
def test_a_host_that_does_not_answer_is_a_row_and_a_nonzero_exit(home: Path, tmux: dict[str, str], answer, why):
    """P1: dropped instead, it would read as a host with nothing running."""
    out = dispatch(tmux, home, "ps", hosts="local agent@off", answers={"agent@off": answer} if answer else None)
    assert out.returncode != 0
    (row,) = [line for line in out.stdout.splitlines() if line.startswith("agent@off")]
    assert "unreachable" in row and why in row
    assert "hypofuzz-default" in out.stdout, "the host that did answer is still read"


def test_a_scratch_dir_left_unread_makes_the_table_incomplete(home: Path, tmux: dict[str, str]):
    d = scratch(home / ROOT, "jarvis", "main")
    spawned(d, "thread-registry")
    (d / "dispatch-ctl").write_text("exit 3\n")

    out = dispatch(tmux, home, "ps")
    assert out.returncode != 0
    assert "unreadable" in out.stdout
    assert "hypofuzz-default" in out.stdout, "the scratch dir beside it is still read"


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
    out = dispatch(tmux, home, "peek", "nowhere-slug", hosts="local agent@off")
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


def test_this_machine_is_one_host_under_both_its_names(home: Path, tmux: dict[str, str]):
    """`local` and this machine's register entry are one home: listed once, under the register's
    name, and read without ssh."""
    subprocess.run(["git", "init", "-q", str(home)], check=True)
    (home / ".git" / "dispatch").mkdir()
    (home / ".git" / "dispatch" / "runs").write_text("master\thypofuzz-default\tlocal\n")

    out = dispatch(tmux, home, "ps", hosts=SELF, answers={SELF: elsewhere("reached-by-ssh")})
    assert out.returncode == 0, out.stderr
    (_, row) = out.stdout.splitlines()
    assert row.split()[:3] == [SELF, "agents/master", "hypofuzz-default"]
    assert ssh_calls(home) == []


def test_peek_prints_the_last_lines_of_the_workers_pane(home: Path, tmux: dict[str, str]):
    session(tmux, "dispatch-agents-hypofuzz-default", "seq 1 40; sleep 30")
    time.sleep(0.5)

    out = dispatch(tmux, home, "peek", "hypofuzz-default", "3")
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["38", "39", "40"]
    assert "hypofuzz-default" in out.stderr, "which worker it is goes to stderr, so the pane pipes clean"


def test_the_fuzz_run_is_named_like_any_other_worker(home: Path, tmux: dict[str, str]):
    session(tmux, "fuzz-agents-master", "printf 'Falsifying example\\n'; sleep 30")
    time.sleep(0.5)

    out = dispatch(tmux, home, "peek", "fuzz")
    assert out.returncode == 0, out.stderr
    assert "Falsifying example" in out.stdout


def test_a_worker_whose_session_is_gone_is_not_attached_to(home: Path, tmux: dict[str, str]):
    out = dispatch(tmux, home, "attach", "hypofuzz-default")
    assert out.returncode != 0
    assert "tmux session is gone" in out.stderr


def test_attach_to_a_remote_worker_is_ssh_with_a_terminal(home: Path, tmux: dict[str, str]):
    out = dispatch(tmux, home, "attach", "far-away", hosts="local agent@far",
                   answers={"agent@far": elsewhere("far-away")})
    assert out.returncode == 0, out.stderr
    assert ssh_calls(home)[-1] == "agent@far\ttmux attach -t \\=dispatch-agents-far-away", \
        "the line on_host builds, its leading `=` escaped for a zsh login shell"
    assert (home / "bin" / "ssh.calls").read_text().count("\n") == 2, "one read, then the attach"


# ssh as the real one delivers a command: the arguments after the host joined into one line, run by
# the remote user's login shell, which is REMOTE_SHELL here, in the remote home.
LOGIN_SHELL_SSH = """#!/usr/bin/env bash
while [[ ${1:-} == -* ]]; do case $1 in -o) shift 2 ;; *) shift ;; esac; done
shift
cd "$REMOTE_HOME" && HOME=$REMOTE_HOME exec "$REMOTE_SHELL" -c "$*"
"""


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
    assert (here / "attached").read_text().strip() == "attach -t =dispatch-agents-hypofuzz-default"


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
    assert (home / "attached").read_text().strip() == "TMUX=unset attach -t =dispatch-agents-hypofuzz-default"
    assert "prefix twice" in out.stderr


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
    env = {**tmux, "PATH": f"{bin_dir}:{tmux['PATH']}", "HOME": str(tmp_path)}
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
