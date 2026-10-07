#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Pick up a handoff: print it in full, retire it from the agent repo, and link this session's page to the page of the session that wrote it.

After printing it, `git rm`s the handoff in the agent repo that holds it and commits that removal
alone. Where it is a continuation handoff another session wrote, this session's directory (the one
`session-page` prints) gets `previous`, naming that session, unless it has one already; that
session's page is then rendered again from its transcript, so that it links forward. A fork's
handoff, one this session wrote itself, and the pickup of a dispatched worker or a print-mode
session link nothing.

What it did is said on stderr, before the handoff, with the command that shows the handoff again
from git. Exits 1, saying why and having done nothing, where the file is no handoff directly under
an `agent/handoffs/`, or one never committed or edited since; and where git refuses the removal or
the commit anyway, after printing and linking the handoff.

Examples:

    pickup.py /home/u/lamp/agent/handoffs/2026-10-06-ledger.md
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated

import tyro
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "session-page"))
from session_page import PAGE, PREVIOUS, RecordError, left_alone, page, read_session, session_directory  # noqa: E402


@dataclass
class Args:
    handoff: Annotated[Path, tyro.conf.Positional]
    """The handoff file, in an `agent/handoffs/` directory."""


def main() -> None:
    handoff = tyro.cli(Args, description=__doc__).handoff.resolve()
    if handoff.parent.parts[-2:] != ("agent", "handoffs") or not handoff.is_file():
        sys.exit(f"{handoff} is no file directly under an agent/handoffs/ directory")
    if refused := uncommitted(handoff):
        sys.exit(f"pickup.py: nothing done: {refused}")
    text = handoff.read_text()
    say(f"linked: {link(text)}")
    retired, failed = retire(handoff)
    say(f"retired: {retired}")
    # the status comes first: a tool that cuts a long output short keeps its start
    print(text, end="" if text.endswith("\n") else "\n", flush=True)
    sys.exit(1 if failed else 0)


def say(line: str) -> None:
    print(f"pickup.py: {line}", file=sys.stderr, flush=True)


def link(text: str) -> str:
    """Write `previous` for this session where the handoff continues another one, render that
    session's page again, and say what came of it."""
    own = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    before = continues(text)
    if not before:
        return "nothing: the handoff is no continuation, or names no session"
    if before == own:
        return "nothing: this session wrote the handoff"
    if unread := left_alone():
        return f"nothing: a {unread} has no page"
    if not own:
        return "nothing: no session id, so no session directory (run it inside a Claude Code session)"
    if (directory := session_directory(Path.cwd(), own)) is None:
        return f"nothing: {Path.cwd()} is in no project with an agent repo"
    if (directory / PREVIOUS).exists():
        return f"nothing: {directory / PREVIOUS} already names {(directory / PREVIOUS).read_text().strip()}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / PREVIOUS).write_text(before + "\n")
    return f"{directory / PREVIOUS} names {before}; its page: {render(directory.parent / before)}"


def continues(text: str) -> str:
    """The session a continuation handoff's frontmatter names; empty for a fork's handoff, and where
    the frontmatter names no session by an id that is safe as a directory name."""
    m = re.match(r"---\n(.*?)\n---(?:\n|$)", text, re.S)
    try:
        front = yaml.load(m.group(1), Loader=yaml.BaseLoader) if m else None
    except yaml.YAMLError:
        return ""
    if not isinstance(front, dict) or front.get("purpose") != "continuation":
        return ""
    session = front.get("session")
    return session if isinstance(session, str) and re.fullmatch(r"[\w-]+", session) else ""


def render(directory: Path) -> str:
    """Render the page of the session whose directory is `directory` again, from its transcript
    under Claude Code's projects directory, and say what came of that."""
    if not directory.is_dir():
        return "no session directory, so no page to link forward"
    projects = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    if (theirs := next(projects.glob(f"*/{directory.name}.jsonl"), None)) is None:
        return f"no transcript under {projects}: it links forward from its next render"
    try:
        (directory / PAGE).write_text(page(read_session(directory, theirs), datetime.now()))
    except (RecordError, OSError) as e:
        return f"not rendered: {e}"
    return f"rendered again, linking forward: {directory / PAGE}"


def git(handoff: Path, *args: str) -> subprocess.CompletedProcess:
    """git run in the agent repo that holds the handoff, from its root, since removing the last
    handoff removes the directory that held it."""
    return subprocess.run(["git", "-C", str(handoff.parents[1]), *args], capture_output=True, text=True)


def uncommitted(handoff: Path) -> str:
    """Why git would refuse to remove the handoff (never committed, or edited since it was), with
    what to do about it; empty where nothing stands in the way."""
    name = handoff.name
    if git(handoff, "ls-files", "--error-unmatch", "--", f"handoffs/{name}").returncode != 0:
        return f"{handoff} was never committed in {handoff.parents[1]}: commit it there, then pick it up"
    if git(handoff, "status", "--porcelain", "--", f"handoffs/{name}").stdout.strip():
        return f"{handoff} has changes not committed in {handoff.parents[1]}: commit them, then pick it up"
    return ""


def retire(handoff: Path) -> tuple[str, bool]:
    """`git rm` the handoff and commit that removal alone; what came of it, and whether git refused."""
    name = f"handoffs/{handoff.name}"
    for step in (["rm", "-q", "--", name], ["commit", "-q", "-m", f"pick up handoff {handoff.stem}", "--", name]):
        if (done := git(handoff, *step)).returncode != 0:
            return f"git {' '.join(step)} in {handoff.parents[1]} failed: {(done.stderr or done.stdout).strip()}", True
    commit = git(handoff, "rev-parse", "--short", "HEAD").stdout.strip()
    return f"removed in {commit}; read it again with `git -C {handoff.parents[1]} show {commit}^:{name}`", False


if __name__ == "__main__":
    main()
