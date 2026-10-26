#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""SessionEnd hook: a session's records reach the agent repo's history as the session ends.

It reads the SessionEnd hook JSON on stdin, copies the session's `session.md` and `turns/`, with the
artefacts of its own work under `show/`, from its directory, which is outside every checkout, into
`sessions/<id>/` of the agent repo the directory names, so that they stand there as they stand in
the directory, a file it no longer holds removed, and commits them there, in a commit holding those
paths and nothing else, with a `Session:` trailer. Where `sessions/` is ignored, they are
force-added. The page (`index.html`) is derived and stays where it is, and so is whatever under
`show/` the agent repo's ignore rules for its own `show/` keep out (a runnable artefact's `out/`, a
PNG rendered on demand), which a force-add would otherwise sweep in. A session that ends again after
a resume commits what changed since; one whose records are as last committed commits nothing.

The commit runs in a child detached from the hook, since every SessionEnd hook shares a budget of
about a second and a half, and git killed mid-commit leaves the index locked for every session
sharing the checkout. The child waits out another session's lock for a few seconds.

It leaves alone a session nobody reads the page of (`session_page.left_alone`): a dispatched
worker's records sit in its own worktree, and committing them would put them in the ticket's diff.

Every decision, and what came of the commit, is one JSON line in `turn_review.LOG`.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import turn_review  # noqa: E402
from session_page import SESSIONS, agent_repo_of, left_alone, session_directory  # noqa: E402

RECORDS = ("session.md", "turns")  # what a session's directory holds that its history keeps
ARTEFACTS = "show"  # where in a session's directory its own work's artefacts go (/mx:show)
LOCK_WAIT = 5.0  # seconds the child waits out another process holding the agent repo's index lock


def main() -> None:
    if sys.argv[1:2] == ["commit"]:  # the detached child, told the session's directory and the log
        directory, turn_review.LOG = Path(sys.argv[2]), Path(sys.argv[3])
        try:
            committed = commit_records(directory)
        except Exception as error:  # the child's stderr goes nowhere, so the log is the one place a failure shows
            committed = f"failed: {error!r}"
        turn_review.log(directory.name, committed=committed)
        return
    hook = json.load(sys.stdin)
    session_id = hook["session_id"]
    directory = session_directory(Path(hook["cwd"]), session_id)
    if unread := left_alone():
        why = unread
    elif directory is None:
        why = "no project with an agent repo"
    elif not any((directory / name).exists() for name in RECORDS):
        why = "no records"
    else:
        subprocess.Popen([sys.executable, __file__, "commit", str(directory), str(turn_review.LOG)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        why = "commit started"
    turn_review.log(session_id, ended=hook.get("reason"), why=why, directory=directory and str(directory))


def commit_records(directory: Path) -> str:
    """Copy the records in `directory`, a session's, into the agent repo it names and commit them
    there, and say what came of it.

    Only where that agent directory is a repo of its own: where it is part of the code repo, the
    commit would land on whatever branch its main checkout holds and travel to its remote. A commit
    that fails unstages the records again, since the index is shared and the next session's commit
    would carry them, and puts the agent repo's copy back as it was, so nothing of the session is
    left in the checkout that its history does not hold. Another process's commit landing between
    the add and the commit could sweep them all the same; the two run back to back to keep that
    window short."""
    session_id = directory.name
    if (agent := agent_repo_of(directory)) is None:
        return f"{directory} names no agent repo"
    top = git(agent, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()) != agent.resolve():
        return "the agent directory is not a repo of its own"
    records = sorted(p.relative_to(directory).as_posix()
                     for name in RECORDS for p in [directory / name, *(directory / name).rglob("*")] if p.is_file())
    if not records:
        return "no records"
    sessions = agent / SESSIONS.name
    kept = RECORDS
    try:
        records += artefacts(directory, agent)
        kept += (ARTEFACTS,)
        without = ""
    except (RuntimeError, OSError) as error:  # the records still go; the artefacts wait for the next end
        without = f", without its artefacts: {error}"
    # -z: without it git quotes a path holding a non-ASCII character, and a space would split one in two
    listed = git(agent, "ls-files", "-z", "--", *(f"{SESSIONS.name}/{session_id}/{name}" for name in kept)).stdout
    tracked = {path for path in listed.split("\0") if path}
    tracked = {path.removeprefix(f"{SESSIONS.name}/") for path in tracked}
    wanted = {f"{session_id}/{record}" for record in records}
    # what git cannot put back: each untracked path the copy writes, as it was, None where it was not there
    untracked = {path: (sessions / path).read_bytes() if (sessions / path).is_file() else None for path in wanted - tracked}
    for record in records:
        (sessions / session_id / record).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(directory / record, sessions / session_id / record)
    for path in tracked - wanted:
        (sessions / path).unlink(missing_ok=True)
    paths = sorted(wanted | tracked)
    message = f"session {session_id}: its records as it ended"
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        done = git(sessions, "add", "--force", "--", *paths)
        if done.returncode == 0:
            if git(sessions, "diff", "--cached", "--quiet", "--", *paths).returncode == 0:
                return "nothing changed since the last commit"
            done = git(sessions, "commit", "--quiet", "-m", message, "--trailer", f"Session: {session_id}", "--", *paths)
            if done.returncode == 0:
                return "committed " + " ".join(f"{sessions.name}/{path}" for path in paths) + without
        if "index.lock" not in done.stderr or time.monotonic() > deadline:
            unstaged = git(sessions, "reset", "--quiet", "--", *paths)
            left = "unstaged" if unstaged.returncode == 0 else f"left staged: {unstaged.stderr.strip()}"
            for path, was in untracked.items():
                if was is None:
                    (sessions / path).unlink(missing_ok=True)
                else:
                    (sessions / path).write_bytes(was)
            if tracked:
                git(sessions, "checkout", "--", *sorted(tracked))
            return f"git {done.args[3]} failed: {done.stderr.strip()}; {left}"
        time.sleep(0.2)


def artefacts(directory: Path, agent: Path) -> list[str]:
    """The files under the session's `show/`, relative to its directory, less those `agent` would
    ignore were they under its own `show/`: one set of rules says what a show directory keeps,
    wherever it sits. `check-ignore --no-index` reads the rules for a path that need not exist.
    Raises RuntimeError, git's own words, where git cannot say which files it ignores, and OSError
    where `show/` cannot be walked."""
    show = directory / ARTEFACTS
    files = sorted(path.relative_to(show).as_posix() for path in show.rglob("*") if path.is_file())
    if not files:
        return []
    # -z on both ends: without it git quotes a path holding a non-ASCII character
    asked = subprocess.run(["git", "-C", str(agent), "check-ignore", "--no-index", "--stdin", "-z"],
                           input="".join(f"{ARTEFACTS}/{directory.name}/{path}\0" for path in files),
                           capture_output=True, text=True)
    if asked.returncode not in (0, 1):  # 1 is "none of them ignored"
        raise RuntimeError(f"git check-ignore failed: {asked.stderr.strip()}")
    ignored = set(asked.stdout.split("\0"))
    return [f"{ARTEFACTS}/{path}" for path in files if f"{ARTEFACTS}/{directory.name}/{path}" not in ignored]


def git(where: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True)


if __name__ == "__main__":
    main()
