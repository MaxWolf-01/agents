"""What the board's checks share: the path entry that makes the scripts beside them importable, and
the demo tracker, built once per run."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from demo_tracker import Demo, build  # noqa: E402


@pytest.fixture(scope="session")
def demo(tmp_path_factory: pytest.TempPathFactory) -> Demo:
    """A tracker exercising every element the board shows, with its git history, sessions and
    review pages: the fixture the layout and session checks read."""
    return build(tmp_path_factory.mktemp("demo-tracker"))
