"""Two main checkouts of one repo, the laptop's and another machine's, kept in step through git.

A checkout in step has pushed every commit of its branch to the branch's upstream and holds every
commit the upstream has. Getting there is a fetch, then the local commits replayed on top of what
the other checkout pushed, then a push; a push refused because the other checkout pushed in between
goes round again. Two machines that changed the same lines of one file stop at a conflict, as any
git rebase does, and nothing is pushed.

The replay keeps each merge a merge of the same commit: a `--no-ff` merge of a ticket branch is
redone onto the new base with the ticket's tip still its second parent, since that merge is how the
tracker finds what a ticket landed (decisions/0001-every-merge-is-no-ff.md). `git rebase
--rebase-merges` would rewrite the ticket's own commits onto the new base too, and the merge would
no longer hold the tip. For the same reason a commit some other branch here is built on is never
replayed: the copy and the original would both end up on the branch once that one merges.
"""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Set for every git command a sync runs: the commits its replay makes fire the commit hook, which
# would otherwise start a sync of the checkout this one holds the lock of.
SYNCING = "TRACKER_SYNCING"
# What git hands a hook, which would make a sync act on the commit's temporary index or another
# worktree rather than the checkout it names.
HOOK_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY")
# How long a fetch or a push may take before the remote counts as unreachable: a captive portal
# answers nothing rather than refusing, and every ticket write waits on the fetch. An HTTPS remote
# that stalls mid-transfer is cut sooner, by git's own low-speed limit, without capping a large one.
NETWORK_SECONDS = 30
NETWORK_CONFIG = ("-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=10")
# Pushes refused because the other checkout pushed first, before this one gives up for now.
ROUNDS = 3
UNDERWAY = {"rebase-merge": "a rebase", "rebase-apply": "a rebase", "MERGE_HEAD": "a merge",
            "CHERRY_PICK_HEAD": "a cherry-pick", "REVERT_HEAD": "a revert", "BISECT_LOG": "a bisect"}

Outcome = Literal["pushed", "pulled", "current", "offline", "conflict", "refused", "skipped"]


@dataclass(frozen=True)
class Synced:
    """What one sync of one checkout did, and the line that says so; `said` is empty where there is
    nothing worth a reader's line (no upstream, nothing to move)."""

    outcome: Outcome
    said: str = ""


class Failed(Exception):
    """A git command that has to succeed for the sync to know where it stands, and did not."""


def sync(top: Path, resolve: bool = False) -> Synced:
    """Bring the checkout at `top` in step with its branch's upstream. A conflict is undone, leaving
    the checkout as it was, unless `resolve`, which leaves the replay stopped at it for a person."""
    if os.environ.get(SYNCING):
        return Synced("skipped")
    try:
        branch = git(top, "branch", "--show-current").strip()
        remote = tried(top, "config", f"branch.{branch}.remote").stdout.strip() if branch else ""
        merge = tried(top, "config", f"branch.{branch}.merge").stdout.strip() if branch else ""
        if not remote or not merge or remote == ".":  # detached, or a branch with no upstream
            return Synced("skipped")
        with locked(top):
            # under the lock, so a replay another sync left stopped for a person is seen as one
            if underway := underway_in(top):
                return Synced("skipped", f"{top}: {underway} is underway, so {branch} was left as it is; `tracker sync` once it is done")
            return in_step(top, branch, remote, merge, resolve)
    except Failed as failed:
        return Synced("refused", f"{top}: {failed}")


def underway_in(top: Path) -> str | None:
    """The operation the checkout is in the middle of, where it is in one. A merge whose commit is
    made is over, though git keeps its `MERGE_HEAD` until the post-merge hook has run."""
    gitdir = Path(git(top, "rev-parse", "--absolute-git-dir").strip())
    for name, what in UNDERWAY.items():
        if not (gitdir / name).exists():
            continue
        if name == "MERGE_HEAD" and tried(top, "rev-parse", "-q", "--verify", "HEAD^2").stdout.strip() == (gitdir / name).read_text().strip():
            continue
        return what
    return None


def in_step(top: Path, branch: str, remote: str, merge: str, resolve: bool) -> Synced:
    pulled = 0
    for _ in range(ROUNDS):
        fetched = tried(top, *NETWORK_CONFIG, "fetch", "-q", remote, timeout=NETWORK_SECONDS)
        if fetched.returncode != 0:
            return unreachable(top, branch, remote, fetched)
        if behind := count(top, "HEAD..@{u}"):
            replayed = replay(top, branch, resolve)
            if replayed.outcome != "pulled":
                return replayed
            pulled += behind
        if not (ahead := count(top, "@{u}..HEAD")):
            return Synced("pulled", f"{top}: {branch} took {pulled} commit(s) from {remote}") if pulled else Synced("current")
        pushed = tried(top, *NETWORK_CONFIG, "push", "--porcelain", remote, f"HEAD:{merge}", timeout=NETWORK_SECONDS)
        if pushed.returncode == 0:
            return Synced("pushed", f"{top}: {branch} pushed {ahead} commit(s) to {remote}" + (f", after taking {pulled} from it" if pulled else ""))
        if not raced(pushed):
            if any(line.startswith("To ") for line in pushed.stdout.splitlines()):  # it answered, and said no
                return Synced("refused", f"{top}: {remote} refused {branch}: {said_by(pushed)}")
            return unreachable(top, branch, remote, pushed)
    return Synced("refused", f"{top}: {remote} moved on before each of {ROUNDS} pushes of {branch}; `tracker sync` tries again")


def replay(top: Path, branch: str, resolve: bool) -> Synced:
    """This checkout's own commits, oldest first along the first parents, redone on top of the
    upstream: a commit picked, a merge merged again from the same second parent with its own
    message. A commit whose change the upstream already holds comes out empty and is dropped, which
    is a claim both machines wrote alike. Uncommitted changes are set aside for it and put back."""
    todo, under = [], set()
    for commit in git(top, "rev-list", "--first-parent", "--reverse", "@{u}..HEAD").split():
        parents = git(top, "rev-list", "--parents", "-n", "1", commit).split()[1:]
        todo.append(f"merge -C {commit} {parents[1]}" if len(parents) == 2 else f"pick {commit}")
        under |= set(git(top, "for-each-ref", "--contains", commit, "--format=%(refname:short)", "refs/heads").split()) - {branch}
    if under:
        return Synced("refused", f"{top}: {', '.join(sorted(under))} is built on commits of {branch} the upstream lacks, so replaying them would copy them; {branch} was left as it is: push it before the other machine's commits arrive, or merge the upstream in by hand")
    before = git(top, "rev-parse", "HEAD").strip()
    script = Path(git(top, "rev-parse", "--absolute-git-dir").strip()) / "tracker-sync-todo"
    script.write_text("\n".join(todo or ["noop"]) + "\n")
    try:
        done = tried(top, "rebase", "-i", "--autostash", "--empty=drop", "@{u}", env={"GIT_SEQUENCE_EDITOR": f"cp '{script}'"})
    finally:
        script.unlink(missing_ok=True)
    files = tried(top, "diff", "--name-only", "--diff-filter=U").stdout.split()
    if done.returncode == 0 and files:
        return unstashed(top, before, done, files)
    if done.returncode == 0:
        return Synced("pulled")
    stopped = (Path(git(top, "rev-parse", "--absolute-git-dir").strip()) / "rebase-merge").exists()
    if files and resolve:
        return Synced("conflict", f"{top}: {', '.join(files)} changed here and upstream both; the replay is stopped at it: resolve, `git rebase --continue`, then `tracker sync`")
    if stopped:
        tried(top, "rebase", "--abort")
    if files:
        return Synced("conflict", f"{top}: {', '.join(files)} changed here and upstream both, so nothing was pushed and the checkout is as it was; `tracker sync --resolve` stops at the conflict for you to resolve")
    return Synced("refused", f"{top}: the replay onto the upstream did not run ({said_by(done)}), so nothing was pushed and the checkout is as it was")


def unstashed(top: Path, before: str, done: subprocess.CompletedProcess, files: list[str]) -> Synced:
    """The checkout put back as it was before a replay whose commits went through and whose
    uncommitted changes, set aside for it, conflict with what came in: git leaves the conflict in
    the working tree and the changes in the stash."""
    stash = re.search(r"Created autostash: ([0-9a-f]+)", done.stdout + done.stderr)
    git(top, "reset", "-q", "--hard", before)
    if stash:
        git(top, "stash", "apply", "-q", stash[1])
        for line in git(top, "stash", "list", "--format=%gd %H").splitlines():
            if line.split()[1].startswith(stash[1]):
                git(top, "stash", "drop", "-q", line.split()[0])
    return Synced("conflict", f"{top}: {', '.join(files)} changed upstream and in uncommitted changes here, so nothing was pushed and the checkout is as it was; commit or set those changes aside, then `tracker sync`")


def unreachable(top: Path, branch: str, remote: str, failed: subprocess.CompletedProcess) -> Synced:
    waiting = count(top, "@{u}..HEAD")
    tail = f"; {waiting} commit(s) of {branch} wait here, and the next sync pushes them" if waiting else ""
    return Synced("offline", f"{top}: {remote} did not answer ({said_by(failed)}){tail}")


def raced(pushed: subprocess.CompletedProcess) -> bool:
    """Whether the push was refused for want of the commits the other checkout pushed meanwhile:
    before this push started, or while it was under way, which the remote refuses on the old value
    the push was sent with."""
    lost = ("fetch first", "non-fast-forward", "incorrect old value", "cannot lock ref")
    return any(line.startswith("!") and any(why in line for why in lost) for line in pushed.stdout.splitlines())


def said_by(failed: subprocess.CompletedProcess) -> str:
    lines = [line.strip() for line in (failed.stderr + failed.stdout).splitlines() if line.strip() and not line.startswith(("To ", "Done"))]
    return lines[-1] if lines else f"exit {failed.returncode}"


def count(top: Path, span: str) -> int:
    return int(git(top, "rev-list", "--count", span).strip())


@contextmanager
def locked(top: Path) -> Iterator[None]:
    """One sync of a repo at a time on this machine: two sessions committing at once would otherwise
    replay the same checkout twice over."""
    common = Path(git(top, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    with (common / "tracker-sync.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        yield


def git(top: Path, *args: str) -> str:
    """A git command that has to succeed: its stdout, or `Failed` saying what git said."""
    done = tried(top, *args)
    if done.returncode != 0:
        raise Failed(f"git {' '.join(args)} failed: {said_by(done)}")
    return done.stdout


def tried(top: Path, *args: str, timeout: float | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """A git command whose failing is an answer: a remote that does not answer, a replay that stops."""
    given = {key: value for key, value in os.environ.items() if key not in HOOK_ENV}
    given |= {SYNCING: "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", **(env or {})}
    try:
        return subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, env=given, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"no answer in {timeout:.0f}s")
