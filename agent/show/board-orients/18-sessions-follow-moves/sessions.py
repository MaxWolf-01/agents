#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown", "pyyaml", "tyro"]
# ///
"""Print the board's own reading of one ticket file: every session its loader finds, the dates of
that session's first and last commit on it, and the title this machine's transcripts give it.

A session with no transcript here is one the board leaves off the ticket, since it can hand out no
command that resumes it. Read by `demo` beside this file.

Examples:

    sessions.py /tmp/ledger agent/tickets/debrief-ticket.md
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

sys.path.insert(0, str(Path(__file__).parents[4] / "mx" / "skills" / "tracker"))

import board  # noqa: E402


@dataclass
class Args:
    repo: Annotated[Path, tyro.conf.Positional]
    """A checkout of the repo whose log is read."""
    ticket: Annotated[str, tyro.conf.Positional]
    """The ticket's path from the top of that checkout, which is how the log names it."""


def main(args: Args) -> None:
    for sid, (first, last) in board.session_log(args.repo).get(args.ticket, {}).items():
        named = board.transcript(sid, board.TRANSCRIPTS)
        when = first if first == last else f"{first} -> {last}"
        print(f"{sid}  {when}  ({named[0] if named else 'no transcript here'})")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
