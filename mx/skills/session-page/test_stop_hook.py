# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision
out, with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md — the Properties below, and its Decisions on what the hook does
with a turn — over the worked example in `fixtures/`, whose records a check corrupts one at a
time. test_chat_review.py beside the other Stop hook is the prior art for driving one.
"""

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import stop_hook
from session_page import PAGE
from stop_hook import SEND_BACK, decide

LIFTED = "decide is a stub; lifted by session-stop-hook"
STALE = "<html>the page the turn before rendered</html>"
RECORD = "turns/03.md"  # the record a check corrupts: the round that answers Q1 to Q3 and asks Q4


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict], None]:
    """Call the hook the way Claude Code does, on the payload given."""

    def call(payload: dict) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        stop_hook.main()

    return call


def payload(directory: Path, transcript: Path, reply: str = "One line, and the page's link.", **rest: object) -> dict:
    """The Stop hook JSON for a turn of the session whose directory is `directory`."""
    return {
        "session_id": directory.name,
        "cwd": str(directory.parents[2]),
        "transcript_path": str(transcript),
        "stop_hook_active": False,
        "last_assistant_message": reply,
        **rest,
    }


# ---- properties -------------------------------------------------------------

# A reply the page would have carried: longer than three lines, which is what sends the agent back
# in a session that has a page.
LONG = "\n".join(f"Line {n} of an answer that belongs on the page." for n in range(1, 6))

TURNS_THAT_NEEDED_NO_PAGE = {
    "a one-line answer": {},
    "an answer that would have needed a page": {"reply": LONG},
    "a turn the hook already spoke to": {"reply": LONG, "stop_hook_active": True},
    "a turn that said nothing": {"reply": ""},
}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@pytest.mark.parametrize("turn", TURNS_THAT_NEEDED_NO_PAGE.values(), ids=TURNS_THAT_NEEDED_NO_PAGE)
def test_a_session_that_never_needed_a_page_writes_nothing_under_the_sessions_directory(
    turn: dict, transcript: Path, tmp_path: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None]
) -> None:
    """session-page#P3: no record has ever been written for this session, so the hook neither
    creates its directory nor asks the agent for anything."""
    sessions = tmp_path / stop_hook.SESSIONS
    sessions.mkdir(parents=True)
    run(payload(sessions / "8e0f1c22-0000-0000-0000-000000000000", transcript, **turn))
    assert list(sessions.rglob("*")) == []
    assert capsys.readouterr().out == ""  # nothing is sent back, so the turn ends here


UNPARSEABLE = {
    # what the record says, and the line the hook names; None where the shape says only that
    # something is missing, not where
    "frontmatter that is not a mapping": (
        "---\ndate: 2026-09-23\nanswered: Q1: a\n---\n\n# Round 2\n\n## Details\n\nThe round.\n", 3),
    "a question that is not a question item": (
        "---\ndate: 2026-09-23\n---\n\n# Round 2\n\n## Questions\n\n- Q4: how is a turn laid out?\n", 9),
    "a section the record's shape does not have": (
        "---\ndate: 2026-09-23\n---\n\n# Round 2\n\n## Notes\n\nA fourth section.\n", 7),
    "no headline": ("---\ndate: 2026-09-23\n---\n\n## Details\n\nThe round.\n", None),
}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@pytest.mark.parametrize("text, line", UNPARSEABLE.values(), ids=UNPARSEABLE)
def test_a_turn_record_that_does_not_parse_is_sent_back_and_never_rendered(
    text: str, line: int | None, worked_example: Path, transcript: Path,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """session-page#P8: the record the turn before rendered from still stands, and the reason the
    agent reads names the file and the line the hook gave up on."""
    hook = payload(worked_example, transcript)
    assert decide(hook, worked_example).verb != SEND_BACK, "a record the renderer can read is never sent back"

    (worked_example / PAGE).write_text(STALE)
    (worked_example / RECORD).write_text(text)
    decision = decide(hook, worked_example)
    assert decision.verb == SEND_BACK
    assert decision.reason.startswith(f"{worked_example / RECORD}:{line}: " if line else str(worked_example / RECORD))

    run(hook)
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"] == decision.reason
    assert (worked_example / PAGE).read_text() == STALE, "the page is what the last record that parsed rendered"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
