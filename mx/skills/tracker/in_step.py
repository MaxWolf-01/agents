"""Two main checkouts of one agent repo, the laptop's and another machine's, kept in step through git.

A checkout in step has pushed every commit of its branch to the branch's upstream. A push refused
because the other checkout pushed first merges what it pushed, a plain merge that rewrites nothing,
and pushes again. Two machines that changed the same lines of one file stop at a conflict, as any
git merge does: the merge is left for whoever resolves it, and nothing is pushed until it is
committed.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Set for every git command a sync runs: the merge it makes fires the merge hook, which would
# otherwise start a sync of the checkout this one holds the lock of.
SYNCING = "TRACKER_SYNCING"
# What git hands a hook, which would make a sync act on the commit's temporary index or another
# worktree rather than the checkout it names.
HOOK_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY")
# How long a fetch or a push may take before the remote counts as unreachable: a captive portal
# answers nothing rather than refusing, and the commit that fired the hook waits on it. An HTTPS
# remote that stalls mid-transfer is cut sooner, by git's own low-speed limit.
NETWORK_SECONDS = 30
NETWORK_CONFIG = ("-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=10")
# Pushes refused because the other checkout pushed first, before this one gives up for now.
ROUNDS = 3
UNDERWAY = {"rebase-merge": "a rebase", "rebase-apply": "a rebase", "MERGE_HEAD": "a merge",
            "CHERRY_PICK_HEAD": "a cherry-pick", "REVERT_HEAD": "a revert", "BISECT_LOG": "a bisect"}

Outcome = Literal["pushed", "pulled", "current", "offline", "conflict", "underway", "refused", "skipped"]
FAILS = ("conflict", "underway", "refused")  # what `tracker sync` exits 1 on


@dataclass(frozen=True)
class Synced:
    """What one sync of one checkout did, and the line that says so; `said` is empty where there is
    nothing worth a reader's line (no upstream, nothing to move)."""

    outcome: Outcome
    said: str = ""


class Failed(Exception):
    """A git command that has to succeed for the sync to know where it stands, and did not."""


def sync(top: Path) -> Synced:
    """Bring the checkout at `top` in step with its branch's upstream."""
    if os.environ.get(SYNCING):
        return Synced("skipped")
    try:
        with locked(top):
            if underway := underway_in(top):
                return Synced("underway", f"{top}: {underway} is underway, so nothing was pushed; once it is committed, the commit pushes")
            branch = git(top, "branch", "--show-current").strip()
            remote = tried(top, "config", f"branch.{branch}.remote").stdout.strip() if branch else ""
            merge = tried(top, "config", f"branch.{branch}.merge").stdout.strip() if branch else ""
            if not remote or not merge or remote == ".":  # detached, or a branch with no upstream
                return Synced("skipped")
            return in_step(top, branch, remote, merge)
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


def in_step(top: Path, branch: str, remote: str, merge: str) -> Synced:
    """Push what the upstream lacks; where the other checkout pushed first, merge it and push again.
    With nothing to push, what the upstream has is merged in, which is a fast-forward."""
    pulled = 0
    for _ in range(ROUNDS):
        if count(top, "@{u}..HEAD"):
            pushed = tried(top, *NETWORK_CONFIG, "push", "--porcelain", remote, f"HEAD:{merge}", timeout=NETWORK_SECONDS)
            if pushed.returncode == 0:
                return Synced("pushed", f"{top}: {branch} pushed to {remote}" + (f", after merging {pulled} commit(s) from it" if pulled else ""))
            if not raced(pushed):
                if any(line.startswith("To ") for line in pushed.stdout.splitlines()):  # it answered, and said no
                    return Synced("refused", f"{top}: {remote} refused {branch}: {said_by(pushed)}")
                return unreachable(top, branch, remote, pushed)
        fetched = tried(top, *NETWORK_CONFIG, "fetch", "-q", remote, timeout=NETWORK_SECONDS)
        if fetched.returncode != 0:
            return unreachable(top, branch, remote, fetched)
        if not (behind := count(top, "HEAD..@{u}")):
            if count(top, "@{u}..HEAD"):
                continue  # the push raced a remote that has since settled: push again
            return Synced("pulled", f"{top}: {branch} took {pulled} commit(s) from {remote}") if pulled else Synced("current")
        merged = tried(top, "merge", "-q", "--no-edit", "@{u}")
        if merged.returncode != 0:
            return stopped(top, branch, remote, merged)
        pulled += behind
    return Synced("refused", f"{top}: {remote} moved on before each of {ROUNDS} pushes of {branch}; `tracker sync` tries again")


def stopped(top: Path, branch: str, remote: str, merged: subprocess.CompletedProcess) -> Synced:
    """A merge of the upstream that did not go through: a conflict, left for whoever resolves it, or
    a merge git would not start, which changed nothing."""
    if files := tried(top, "diff", "--name-only", "--diff-filter=U").stdout.split():
        return Synced("conflict", f"{top}: {', '.join(files)} changed here and at {remote} both, so the merge of {remote}'s {branch} is stopped at the conflict and nothing was pushed; resolve it and commit, and the commit pushes")
    return Synced("refused", f"{top}: the merge of {remote}'s {branch} did not run ({said_by(merged)}), so nothing was pushed; `tracker sync` once that is cleared")


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
    merge into the same checkout twice over."""
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


def tried(top: Path, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    """A git command whose failing is an answer: a remote that does not answer, a merge that stops."""
    given = {key: value for key, value in os.environ.items() if key not in HOOK_ENV}
    given |= {SYNCING: "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    try:
        return subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, env=given, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"no answer in {timeout:.0f}s")
