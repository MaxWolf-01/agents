"""What the checks of the retro's collect stage and of its run both build: the period's start, a
session's transcript entry by entry, and a git repo committed to as max at a given date."""

import json
import os
import re
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

SINCE = datetime(2026, 10, 5, tzinfo=UTC)


class Transcript:
    """One session's transcript under a profile's projects directory, entry by entry."""

    def __init__(self, projects: Path, cwd: str, start: datetime, entrypoint: str = "cli") -> None:
        self.sid, self.cwd, self.at, self.entrypoint = str(uuid.uuid4()), cwd, start, entrypoint
        self.path = projects / re.sub(r"[^A-Za-z0-9]", "-", cwd) / f"{self.sid}.jsonl"  # Claude Code's project name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []
        self.last: str | None = None

    def add(self, entry: dict, parent: str | None = "last") -> "Transcript":
        self.at += timedelta(minutes=1)
        me = str(uuid.uuid4())
        self.entries.append({"parentUuid": self.last if parent == "last" else parent, "isSidechain": False,
                             "uuid": me, "timestamp": self.at.isoformat().replace("+00:00", "Z"),
                             "entrypoint": self.entrypoint, "cwd": self.cwd, "sessionId": self.sid,
                             "version": "2.1.300", **entry})
        self.last = me
        self.path.write_text("".join(json.dumps(e) + "\n" for e in self.entries))
        return self

    def says(self, text: str, parent: str | None = "last") -> "Transcript":
        return self.add({"type": "user", "message": {"role": "user", "content": text}, "origin": {"kind": "human"}}, parent)

    def answers(self, text: str) -> "Transcript":
        return self.add({"type": "assistant", "message": {"model": "claude-opus-5-5", "role": "assistant",
                                                          "content": [{"type": "text", "text": text}]}})

    def calls(self, tool: str, inputs: dict, result: str, error: bool = False, denial: str | None = None,
              decision: dict | None = None) -> "Transcript":
        tid = f"toolu_{uuid.uuid4().hex[:12]}"
        self.add({"type": "assistant", "message": {"model": "claude-opus-5-5", "role": "assistant",
                                                   "content": [{"type": "tool_use", "id": tid, "name": tool, "input": inputs}]}})
        return self.add({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": result, "is_error": error}]},
            **({"toolDenialKind": denial} if denial else {}), **({"permissionDecision": decision} if decision else {})})


IDENTITY = {"GIT_AUTHOR_NAME": "max", "GIT_AUTHOR_EMAIL": "max@example.org", "GIT_COMMITTER_NAME": "max",
            "GIT_COMMITTER_EMAIL": "max@example.org", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo: Path, *args: str, when: datetime | None = None) -> str:
    """What git prints, run in `repo` as max, at `when` where it is given."""
    env = {**os.environ, **IDENTITY, **({"GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat()} if when else {})}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


def commit(repo: Path, files: dict[str, str | None], message: str, when: datetime) -> None:
    for name, text in files.items():
        path = repo / name
        if text is None:
            git(repo, "rm", "-q", name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message, when=when)


def ticket(status: str, repos: tuple[str, ...] = ()) -> str:
    listed = f"repos: [{', '.join(repos)}]\n" if repos else ""
    return f"---\nstatus: {status}\npriority: 2\n{listed}---\n\n# A ticket\n"
