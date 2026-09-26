"""What the session page's checks share: the path entry that makes the modules beside them
importable, and the worked example both seams read."""

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from stop_hook import SESSIONS  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SESSION = "e5ca76dc-3093-419b-aa93-b8eb8f35811f"  # the session the worked example is of
TRANSCRIPT = FIXTURES / "transcript.jsonl"


@pytest.fixture
def worked_example(tmp_path: Path) -> Path:
    """The prototype's four turns as the session directory they describe, copied so that a check
    can corrupt or perturb a record.

    It sits under a repo root of its own (`tmp_path`), at the path the hook derives from a session
    id, so the two seams read the same fixture.
    """
    directory = tmp_path / SESSIONS / SESSION
    shutil.copytree(FIXTURES / "session", directory)
    for record in directory.rglob("*.md"):
        record.touch()  # the newest record is this turn's, however the hook reads "written this turn"
    return directory


@pytest.fixture(scope="session")
def transcript() -> Path:
    """The worked example's transcript: that session's own, trimmed to what a page is rendered
    from (`fixtures/README.md`)."""
    return TRANSCRIPT
