#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["markdown", "pyyaml", "tyro"]
# ///
"""Run the board's briefing session against the demo tracker and keep what it wrote.

`build.py` renders the board once, without watching, so no briefing session ever starts and the
column falls back to the board's own count. The README's screenshots are of the board a reader
runs, which does start one, so the answer a session really gave on this tracker is recorded here
once and planted in the cache before the shot. Re-run this when the fixture tracker changes enough
that the briefing stops describing it; it costs one model run and needs a Claude Code login.

    brief.py                       # rebuild the demo repo, ask, and write briefing.json
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

TRACKER = Path(__file__).parents[3] / "mx" / "skills" / "tracker"
sys.path.insert(0, str(TRACKER))

import board  # noqa: E402
import briefing  # noqa: E402

OUT = Path(__file__).parent / "briefing.json"


def main() -> None:
    build.build_repo()
    roots = board.tracker_roots(build.REPO / "agent" / "tickets")
    state = board.briefing_state(roots, build.REPO)
    said = briefing.first(state, build.REPO, datetime.now(timezone.utc))
    if not said:
        sys.exit(f"the briefing session answered nothing: {briefing.missing()}")
    said.write(OUT)
    print(OUT)
    print(said.text)


if __name__ == "__main__":
    main()
