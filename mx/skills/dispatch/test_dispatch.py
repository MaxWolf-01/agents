# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for what `dispatch` and `dispatch-ctl` read and write on a ticket. Run: pytest test_dispatch.py

One seam: the two scripts' command lines, run as subprocesses over a toy repo whose worker is a stub
on the `DISPATCH_RUNNER` seam dispatch-ctl documents, so what runs is dispatch and dispatch-ctl
themselves. The oracles are `agent/tickets/ticket-file-contract.md` (P4, that a worker's brief is the
ticket's body with every ancestor's, assembled by the one function; `needs-user` as the one field
that keeps a ticket from a worker) and `/mx:tracker`'s Ticket state (a claim is taken from the
frontier, and a claimed ticket is in somebody's hands).

`agent/tickets/dispatch-scripts-under-test.md` is where the rest of these scripts' coverage is
argued; this file is the four cases the ticket-file move made.
"""

import os
import shutil
import subprocess
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
printf 'attempts=1 exit=0 status=claimed session=stub\\n' > "$state/$run_id.status"
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


def run(toy: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(toy.parent / "home"), "GIT_CONFIG_GLOBAL": "/dev/null",
           "JOB_STATE_DIR": str(toy.parent / "jobs"), "PATH": os.environ["PATH"], **extra}
    env.pop("DISPATCH_PERMISSION_MODE", None)
    (toy.parent / "home").mkdir(exist_ok=True)
    return subprocess.run([str(DISPATCH), *args], cwd=toy, capture_output=True, text=True, env=env, timeout=180)


def status_of(toy: Path, slug: str) -> str:
    return (toy / "agent" / "tickets" / f"{slug}.md").read_text().split("status: ")[1].split("\n")[0]


def test_a_claim_is_taken_from_the_frontier_and_a_claimed_ticket_is_in_somebodys_hands(toy: Path) -> None:
    first = run(toy, "claim", "warm-preset")
    assert first.returncode == 0, first.stderr
    assert status_of(toy, "warm-preset") == "claimed"
    assert "claim warm-preset" in git(toy, "log", "-1", "--format=%s")

    again = run(toy, "claim", "warm-preset")
    assert again.returncode != 0
    assert "already claimed" in again.stderr, again.stderr


@pytest.fixture
def staged(toy: Path) -> Path:
    """The toy with a stub runner staged in the skill copy dispatch sends to a host."""
    skill = toy.parent / "skills"
    (skill / "dispatch").mkdir(parents=True)
    (skill / "tracker").mkdir()
    for name in ("dispatch", "dispatch-ctl", "worker-prompt.md"):
        shutil.copy(SKILL / name, skill / "dispatch" / name)
    shutil.copy(SKILL.parent / "tracker" / "tracker.py", skill / "tracker" / "tracker.py")
    (skill / "dispatch" / "run-worker.sh").write_text(RUNNER)
    return skill / "dispatch" / "dispatch"


def spawn(toy: Path, staged: Path, slug: str, message: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(toy.parent / "home"), "GIT_CONFIG_GLOBAL": "/dev/null",
           "JOB_STATE_DIR": str(toy.parent / "jobs")}
    env.pop("DISPATCH_PERMISSION_MODE", None)
    (toy.parent / "home").mkdir(exist_ok=True)
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
    """The guard the commit hook makes on a host that has one, made again where a worker is handed a
    ticket. The spawn refuses where it assembles the brief, which is the first of the two readers a
    spawn runs; the second, on the host, is what refuses a ticket whose branch copy is the broken
    one."""
    run(toy, "claim", "warm-preset")
    broken = toy / "agent" / "tickets" / "warm-preset.md"
    broken.write_text(broken.read_text() + "\n## Comments\n\n- A1 no anchor in backticks here.\n")
    git(toy, "commit", "-q", "-am", "a bullet no reader can read")
    said = spawn(toy, staged, "warm-preset", "Work it.\n")
    assert said.returncode != 0
    assert "warm-preset.md:" in said.stderr and "this assumption has no anchor" in said.stderr, said.stderr
    assert not list((toy.parent / "home" / ".local" / "state" / "dispatch" / "lamp-main").glob("*.brief"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
