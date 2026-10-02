"""What the session page's checks share: the path entry that makes the modules beside them
importable, a session someone is sitting at whose prose reviewer is stubbed, and the worked example
the seams read. The reviewer stub sits at `turn_review.review`, the one call that reaches a model."""

import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import turn_review  # noqa: E402
from session_page import SESSIONS  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SESSION = "e5ca76dc-3093-419b-aa93-b8eb8f35811f"  # the session the worked example is of
# the sessions the hooks leave alone are marked in the environment, and the suite runs in one of
# them whenever a dispatched worker verifies its branch
UNATTENDED = ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")


@pytest.fixture(autouse=True)
def attended(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Every check is a turn of a session someone is sitting at, whose record the prose
    reviewer finds nothing in unless the check says otherwise: no check spends a model call. The
    log is the check's own, and handed back."""
    for marker in UNATTENDED:
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.setattr(turn_review, "review", lambda system, prompt: [])
    monkeypatch.setattr(turn_review, "LOG", tmp_path / "session-page.jsonl")
    return turn_review.LOG


def unreachable(system: str, prompt: str) -> list[dict]:
    """A reviewer stand-in for a check where no model call may be made. It fails the check through
    `pytest.fail`, which the review's fail-open handler does not catch."""
    pytest.fail("the reviewer was called where no model call may be made")


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


# The worked example's transcript ends with record 4's Write call, after the last prompt: that
# turn wrote its record. A prompt after it, with the records last touched before it, is a turn
# that wrote none.
SPOKEN_AFTER = {"type": "user", "message": {"role": "user", "content": "And the ledger's second bank?"},
                "timestamp": "2026-09-23T01:35:00.000Z"}
BEFORE_IT = datetime(2026, 9, 23, 1, 31, tzinfo=UTC).timestamp()


@pytest.fixture
def unrecorded(worked_example: Path, transcript: Path, tmp_path: Path) -> Path:
    """The worked example's transcript with a prompt after its newest record, which this turn
    answered without writing one."""
    for record in (worked_example / "turns").iterdir():
        os.utime(record, (BEFORE_IT, BEFORE_IT))
    spoken = tmp_path / "spoken.jsonl"
    spoken.write_text(transcript.read_text() + json.dumps(SPOKEN_AFTER) + "\n")
    return spoken
