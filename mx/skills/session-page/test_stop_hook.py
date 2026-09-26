# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pyyaml", "markdown-it-py"]
# ///
"""The Stop hook's properties. Run: uv run test_stop_hook.py

The seam is the hook at its input: the hook's JSON and the session directory in, its decision out,
with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/session-page.md, its Properties and its Decisions on what the hook does with a turn,
over the worked example in `fixtures/`, whose records a check corrupts one at a time.
test_chat_review.py beside the other Stop hook is the prior art for driving one.
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
from stop_hook import SESSIONS, decide, session_directory

LIFTED = "decide is a stub; lifted by session-stop-hook"
BOTH = "decide is a stub; lifted by session-stop-hook"
# the sessions the hook leaves alone are marked in the environment, and the suite runs in one of
# them whenever a dispatched worker verifies its branch
UNATTENDED = ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")


@pytest.fixture(autouse=True)
def attended(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every check here is a turn of a session someone is sitting at, whose record the prose
    reviewer found nothing in: no check spends a model call, as test_chat_review.py spends none."""
    for marker in UNATTENDED:
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.setattr(stop_hook, "review", lambda session: [])


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
        "cwd": str(directory.parents[len(SESSIONS.parts)]),
        "transcript_path": str(transcript),
        "stop_hook_active": False,
        "last_assistant_message": reply,
        **rest,
    }


def test_a_session_keeps_its_page_under_the_repos_own_agent_directory() -> None:
    """Where the Decisions put a session's records, pinned as a literal: the hook's cwd is the
    repo the session ran in, and its id is the directory's name."""
    assert session_directory({"cwd": "/r", "session_id": "s1"}) == Path("/r/agent/sessions/s1")


# ---- properties -------------------------------------------------------------

# A reply the page would have carried: longer than three lines, which is what sends the agent back
# in a session that has a page.
LONG = "\n".join(f"Line {n} of an answer that belongs on the page." for n in range(1, 6))

TURNS_THAT_NEEDED_NO_PAGE = {
    "a one-line answer": {},
    "an answer that would have needed a page": {"reply": LONG},
    "a turn another hook sent back once already": {"reply": LONG, "stop_hook_active": True},
    "a turn that said nothing": {"reply": ""},
}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@pytest.mark.parametrize("turn", TURNS_THAT_NEEDED_NO_PAGE.values(), ids=TURNS_THAT_NEEDED_NO_PAGE)
def test_a_session_that_never_needed_a_page_writes_nothing_under_the_sessions_directory(
    turn: dict, transcript: Path, tmp_path: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], None]
) -> None:
    """session-page#P3: no record has ever been written for this session, so the hook neither
    creates its directory nor asks the agent for anything."""
    sessions = tmp_path / SESSIONS
    sessions.mkdir(parents=True)
    run(payload(sessions / "8e0f1c22-0000-0000-0000-000000000000", transcript, **turn))
    assert list(sessions.rglob("*")) == []
    assert capsys.readouterr().out == ""  # nothing is sent back, so the turn ends here


# The record the turn just wrote is 04.md, the one the Decisions have the hook validate; 03.md is
# two rounds back, and a hook that read only the newest record would let it through. Each case is
# what the record says and the line the hook names, None where the shape says only that something
# is missing and not where.
UNPARSEABLE = {
    "frontmatter that is not YAML": (
        "04.md", "---\ndate: 2026-09-23\nanswered: Q1: a\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 3),
    "frontmatter that is not a mapping": (
        "04.md", "---\n- a\n- b\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 2),
    "a question that is not a question item": (
        "04.md", "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n## Questions\n\n- Q7: what reviews the prose?\n", 9),
    "a section the record's shape does not have": (
        "04.md", "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n## Notes\n\nA fourth section.\n", 7),
    "no headline": ("04.md", "---\ndate: 2026-09-23\n---\n\n## Details\n\nThe round.\n", None),
    "a record from an earlier turn": (
        "03.md", "---\ndate: 2026-09-23\n---\n\n# Round 2\n\n## Notes\n\nA fourth section.\n", 7),
}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=LIFTED)
@pytest.mark.parametrize("name, text, line", UNPARSEABLE.values(), ids=UNPARSEABLE)
def test_a_turn_record_that_does_not_parse_is_sent_back_and_never_rendered(
    name: str, text: str, line: int | None, worked_example: Path, transcript: Path, stale_page: str,
    capsys: pytest.CaptureFixture, run: Callable[[dict], None],
) -> None:
    """session-page#P8: the page the turn before rendered still stands, and the reason the agent
    reads names the file and the line the hook gave up on."""
    record = worked_example / "turns" / name
    hook = payload(worked_example, transcript)
    assert decide(hook, worked_example).verb == "render", "a turn whose records read is what renders the page"

    (worked_example / PAGE).write_text(stale_page)
    record.write_text(text)
    decision = decide(hook, worked_example)
    assert decision.verb == "send back"
    assert decision.reason.startswith(f"{record}:{line}: " if line else f"{record}: ")

    run(hook)
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"] == decision.reason
    assert (worked_example / PAGE).read_text() == stale_page, "the page is what the last records that parsed rendered"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=BOTH)
def test_a_session_that_needed_a_page_has_one_beside_its_records(
    worked_example: Path, transcript: Path, stale_page: str, run: Callable[[dict], None]
) -> None:
    """The other side of session-page#P3: the turn that wrote a record is what renders the page,
    and the page is that directory's index.html."""
    hook = payload(worked_example, transcript)
    (worked_example / PAGE).write_text(stale_page)
    run(hook)
    assert sorted(path.name for path in worked_example.iterdir()) == ["index.html", "session.md", "turns"]
    assert (worked_example / "index.html").read_text() != stale_page


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
