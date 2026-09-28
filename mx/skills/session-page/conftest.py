"""What the session page's checks share: the path entry that makes the modules beside them
importable, and the worked example both seams read."""

import os
import shutil
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from session_page import SESSIONS  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SESSION = "e5ca76dc-3093-419b-aa93-b8eb8f35811f"  # the session the worked example is of


@pytest.fixture
def worked_example(tmp_path: Path) -> Path:
    """The prototype's four turns as the session directory they describe, copied so that a check
    can corrupt or perturb a record.

    It sits under a project of its own (`tmp_path`, whose agent repo holds a tracker), at the path
    the hook derives from a session id, so the two seams read the same fixture. The records are
    stamped a second apart in their own order, so the last turn's is the newest by its modification
    time as well as by its write call.
    """
    directory = tmp_path / SESSIONS / SESSION
    shutil.copytree(FIXTURES / "session", directory)
    (tmp_path / "agent" / "tickets").mkdir()
    written = time.time()
    for number, record in enumerate(sorted((directory / "turns").glob("[0-9][0-9].md"))):
        os.utime(record, (written + number, written + number))
    return directory


@pytest.fixture(scope="session")
def transcript() -> Path:
    """The worked example's transcript: that session's own, trimmed to what a page is rendered
    from (`fixtures/README.md`)."""
    return FIXTURES / "transcript.jsonl"


@pytest.fixture(scope="session")
def stale_page() -> str:
    """A page in the session's directory from the turn before, which a render replaces and a turn
    the hook sends back leaves standing."""
    return "<html>the page the turn before rendered</html>"
