# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `dispatch`'s landing. Run: uv run test_landing.py

The seam is the two dispatch scripts themselves, driven through one landing on a toy repo by
`landing_e2e.sh`, with a stub worker on dispatch-ctl's runner seam. The oracle is `/mx:dispatch`'s
landing: `dispatch review` checks the ticket branch out beside the feature worktree and stages its
demo unrun, the user's Enter runs it, and the ruling leaves no session, worktree or job behind.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "landing_e2e.sh"


def test_a_landing_stages_the_demo_unrun_and_the_ruling_clears_it():
    for tool in ("tmux", "job"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to stage a demo in")
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    done = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-2000:]
    assert done.stdout.count("  ok  ") == 13, done.stdout[-4000:]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
