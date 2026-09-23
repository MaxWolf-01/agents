# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown"]  # the last three: the demo tracker and the board the shared fixtures import
# ///
"""The briefing session's schedule. Run: uv run test_briefing.py

The seam is `on_change`, a pure function of the cache file's state, the change's time and the
clock. The oracle is the Property of agent/tickets/board-orients/spec.md: the briefing session is
pinged at most once per debounce window, and never outlives its idle hour or its ping cap.

A run of tracker changes and quiet ticks is drawn, driven through the schedule, and the answers are
read back against that Property. The spec's third retirement limit, the session's context, is not a
function of the cache file, so it is not checked here. Liveness is: a change the session has not
been told about, once the debounce window has passed, reaches it.
"""

import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

from briefing import DEBOUNCE, IDLE, PING_CAP, Briefing, cache_path, on_change

START = datetime.fromisoformat("2026-09-21T09:00:00+02:00")
RUN = st.lists(st.tuples(st.integers(min_value=0, max_value=90), st.booleans()), min_size=1, max_size=60)


def fresh(at: datetime, n: int) -> Briefing:
    return Briefing("where things stand", at, f"session-{n}", at, at, 0)


def retired(session: Briefing, now: datetime) -> bool:
    return now - session.last_activity >= IDLE or session.pings >= PING_CAP


def drive(run: list[tuple[int, bool]]) -> list[tuple[str, Briefing | None, datetime, datetime]]:
    """The schedule's answer to each tick of a run, with the state it was asked about: minutes since
    the last tick, and whether the tracker changed at this one. A tick with no change yet asks
    nothing; the watcher has nothing to tell the session about."""
    answers, session, changed_at, now, n = [], None, None, START, 0
    for minutes, changed in run:
        now += timedelta(minutes=minutes)
        if changed:
            changed_at = now
        if changed_at is None:
            continue
        verb = on_change(session, changed_at, now)
        answers.append((verb, session, changed_at, now))
        if verb == "fresh":
            n += 1
            session = fresh(now, n)
        elif verb == "ping":
            session = replace(session, last_activity=now, pings=session.pings + 1)
    return answers


@given(run=RUN)
def test_the_briefing_session_is_pinged_once_a_window_and_never_past_its_idle_hour_or_ping_cap(run: list[tuple[int, bool]]) -> None:
    for verb, session, changed_at, now in drive(run):
        assert verb in ("ping", "wait", "fresh")
        if verb == "ping":
            assert session is not None, "a ping needs a session to resume"
            assert now - session.last_activity >= DEBOUNCE, "two pings inside one debounce window"
            assert not retired(session, now), "a session past its idle hour or ping cap still pinged"
        if verb == "fresh":
            assert session is None or retired(session, now), "a live session replaced instead of pinged"
        if verb == "wait":
            told = session is not None and session.last_activity >= changed_at
            assert told or now - changed_at < DEBOUNCE, "a change waiting past its debounce window"


def test_a_session_retired_with_nothing_new_to_tell_it_is_left_where_it_is() -> None:
    """The spec: the session retires after an idle hour "and the next change starts a fresh one".
    A board watching a tracker that has not moved since its last briefing has no next change, so
    the hour passing is not itself a reason to explore the repo again."""
    told = fresh(START, 1)
    assert on_change(told, START, START + IDLE + timedelta(minutes=1)) == "wait"
    assert on_change(told, START + timedelta(minutes=1), START + IDLE + timedelta(minutes=1)) == "fresh"


def test_the_windows_the_property_is_stated_in_are_the_spec_s() -> None:
    """The property above reads its windows off the module, so the spec's own numbers are checked
    here: five to ten minutes of debounce, and the idle hour."""
    assert timedelta(minutes=5) <= DEBOUNCE <= timedelta(minutes=10)
    assert IDLE == timedelta(hours=1)


def test_the_cache_file_reads_back_what_it_was_written_with(tmp_path: Path) -> None:
    briefing = Briefing("two builds wait on you", START, "abc-123", START, START + IDLE, 3)
    path = cache_path(tmp_path / "board.html")
    briefing.write(path)
    assert Briefing.read(path) == briefing
    assert Briefing.read(tmp_path / "nothing.json") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
