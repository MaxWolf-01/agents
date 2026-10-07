"""What the session page's checks import by name. It lives outside `conftest.py` because every
skill's checks put their own directory on the import path, so `from conftest import` reaches
whichever skill's conftest got there first."""

from datetime import UTC, datetime

import pytest

SESSION = "e5ca76dc-3093-419b-aa93-b8eb8f35811f"  # the session the worked example is of
# the sessions the hooks leave alone are marked in the environment, and the suite runs in one of
# them whenever a dispatched worker verifies its branch
UNATTENDED = ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")

# The worked example's transcript ends with record 4's Write call, after the last prompt: that
# turn wrote its record. A prompt after it, with the records last touched before it, is a turn
# that wrote none.
SPOKEN_AFTER = {"type": "user", "message": {"role": "user", "content": "And the ledger's second bank?"},
                "timestamp": "2026-09-23T01:35:00.000Z"}
BEFORE_IT = datetime(2026, 9, 23, 1, 31, tzinfo=UTC).timestamp()


def unreachable(system: str, prompt: str) -> list[dict]:
    """A reviewer stand-in for a check where no model call may be made. It fails the check through
    `pytest.fail`, which the review's fail-open handler does not catch."""
    pytest.fail("the reviewer was called where no model call may be made")
