"""Two main checkouts of one repo, the laptop's and another machine's, kept in step through git.

A checkout in step has pushed every commit of its branch to the branch's upstream and holds every
commit the upstream has. Getting there is a fetch, then the local commits replayed on top of what
the other checkout pushed, then a push; a push refused because the other checkout pushed in between
goes round again. Two machines that changed the same lines of one file stop at a conflict, as any
git rebase does, and nothing is pushed.

The replay keeps each merge a merge of the same commit: a `--no-ff` merge of a ticket branch is
redone onto the new base with the ticket's tip still its second parent, since that merge is how the
tracker finds what a ticket landed (decisions/0001). `git rebase --rebase-merges` would rewrite the
ticket's own commits onto the new base too, and the merge would no longer hold the tip.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
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
# answers nothing rather than refusing.
NETWORK_SECONDS = 60
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


def sync(top: Path, resolve: bool = False) -> Synced:
    """Bring the checkout at `top` in step with its branch's upstream. A conflict is undone, leaving
    the checkout as it was, unless `resolve`, which leaves the replay stopped at it for a person."""
    if os.environ.get(SYNCING):
        return Synced("skipped")
    branch = git(top, "branch", "--show-current").stdout.strip()
    if not branch:
        return Synced("skipped")
    gitdir = Path(git(top, "rev-parse", "--absolute-git-dir").stdout.strip())
    if underway := next((what for name, what in UNDERWAY.items() if (gitdir / name).exists()), None):
        return Synced("skipped", f"{top}: {underway} is underway, so {branch} was left as it is; `tracker sync` once it is done")
    remote = git(top, "config", f"branch.{branch}.remote").stdout.strip()
    merge = git(top, "config", f"branch.{branch}.merge").stdout.strip()
    if not remote or not merge or remote == ".":
        return Synced("skipped")
    with locked(top):
        return in_step(top, branch, remote, merge, resolve)


def in_step(top: Path, branch: str, remote: str, merge: str, resolve: bool) -> Synced:
    pulled = 0
    for _ in range(ROUNDS):
        fetched = git(top, "fetch", "-q", remote, timeout=NETWORK_SECONDS)
        if fetched.returncode != 0:
            return unreachable(top, branch, remote, fetched)
        behind = count(top, "HEAD..@{u}")
        if behind:
            replayed = replay(top, resolve)
            if replayed.outcome != "pulled":
                return replayed
            pulled = behind
        if not (ahead := count(top, "@{u}..HEAD")):
            return Synced("pulled", f"{top}: {branch} took {pulled} commit(s) from {remote}") if pulled else Synced("current")
        pushed = git(top, "push", "--porcelain", remote, f"HEAD:{merge}", timeout=NETWORK_SECONDS)
        if pushed.returncode == 0:
            return Synced("pushed", f"{top}: {branch} pushed {ahead} commit(s) to {remote}" + (f", after taking {pulled} from it" if pulled else ""))
        if not raced(pushed):
            if any(line.startswith("To ") for line in pushed.stdout.splitlines()):  # it answered, and said no
                return Synced("refused", f"{top}: {remote} refused {branch}: {said_by(pushed)}")
            return unreachable(top, branch, remote, pushed)
    return Synced("refused", f"{top}: {remote} took a push of its own before each of {ROUNDS} of {branch}'s; `tracker sync` tries again")


def replay(top: Path, resolve: bool) -> Synced:
    """This checkout's own commits, oldest first along the first parents, redone on top of the
    upstream: a commit picked, a merge merged again from the same second parent with its own
    message. A commit whose change the upstream already holds comes out empty and is dropped, which
    is a claim both machines wrote alike. Uncommitted changes are set aside for it and put back."""
    todo = []
    for commit in git(top, "rev-list", "--first-parent", "--reverse", "@{u}..HEAD").stdout.split():
        parents = git(top, "rev-list", "--parents", "-n", "1", commit).stdout.split()[1:]
        todo.append(f"merge -C {commit} {parents[1]}" if len(parents) == 2 else f"pick {commit}")
    script = Path(git(top, "rev-parse", "--absolute-git-dir").stdout.strip()) / "tracker-sync-todo"
    script.write_text("\n".join(todo or ["noop"]) + "\n")
    try:
        done = git(top, "rebase", "-i", "--autostash", "--empty=drop", "@{u}", env={"GIT_SEQUENCE_EDITOR": f"cp '{script}'"})
    finally:
        script.unlink(missing_ok=True)
    if done.returncode == 0:
        if "autostash resulted in conflicts" in done.stdout + done.stderr:
            return Synced("conflict", f"{top}: took what the upstream had, and the uncommitted changes here conflict with it; they are kept in `git stash list`, nothing was pushed")
        return Synced("pulled")
    files = git(top, "diff", "--name-only", "--diff-filter=U").stdout.split()
    named = ", ".join(files) or "a file"
    if resolve:
        return Synced("conflict", f"{top}: {named} changed here and upstream both; the replay is stopped at it: resolve, `git rebase --continue`, then `tracker sync`")
    git(top, "rebase", "--abort")
    return Synced("conflict", f"{top}: {named} changed here and upstream both, so nothing was pushed and the checkout is as it was; `tracker sync --resolve` stops at the conflict for you to resolve")


def unreachable(top: Path, branch: str, remote: str, failed: subprocess.CompletedProcess) -> Synced:
    waiting = count(top, "@{u}..HEAD")
    tail = f"; {waiting} commit(s) of {branch} wait here, and the next sync pushes them" if waiting else ""
    return Synced("offline", f"{top}: {remote} did not answer ({said_by(failed)}){tail}")


def raced(pushed: subprocess.CompletedProcess) -> bool:
    """Whether the push was refused for want of the commits the other checkout pushed meanwhile."""
    return any(line.startswith("!") and ("fetch first" in line or "non-fast-forward" in line) for line in pushed.stdout.splitlines())


def said_by(failed: subprocess.CompletedProcess) -> str:
    lines = [line.strip() for line in (failed.stderr + failed.stdout).splitlines() if line.strip() and not line.startswith(("To ", "Done"))]
    return lines[-1] if lines else f"exit {failed.returncode}"


def count(top: Path, span: str) -> int:
    return int(git(top, "rev-list", "--count", span).stdout.strip() or 0)


class locked:
    """One sync of a repo at a time on this machine: two sessions committing at once would otherwise
    replay the same checkout twice over."""

    def __init__(self, top: Path) -> None:
        common = Path(git(top, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
        self.path = common / "tracker-sync.lock"

    def __enter__(self) -> None:
        self.held = self.path.open("w")
        fcntl.flock(self.held, fcntl.LOCK_EX)

    def __exit__(self, *_: object) -> None:
        self.held.close()


def git(top: Path, *args: str, timeout: float | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    given = {key: value for key, value in os.environ.items() if key not in HOOK_ENV}
    given |= {SYNCING: "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", **(env or {})}
    try:
        return subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, env=given, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"no answer in {timeout:.0f}s")
