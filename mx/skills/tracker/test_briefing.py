# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown"]  # the last three: the demo tracker and the board the shared fixtures import
# ///
"""The briefing session's schedule. Run: uv run test_briefing.py

The seam the spec names is `on_change`, a pure function of the cache file's state, the change's
time and the clock. The oracle is the Property of mx/skills/tracker/corpus/board-orients.md, in the
windows the user ruled on 2026-09-23 (ticket 16): the session is pinged once the tracker has gone
five minutes without a ticket's status moving, no sooner than ten minutes after the last briefing,
and never outlives its idle hour or its ping cap. `ping` is a second seam, which the Testing
Decisions does not name (ticket 13's D9): what the session is resumed with and what its answer does
to the cache, with `claude` stubbed.

A run of status changes and quiet ticks is drawn, driven through the schedule, and the answers are
read back against that Property. The spec's third retirement limit, the session's context, is not a
function of the cache file, so it is not checked here. Liveness is: a status change the session has
not been told about, once both windows have passed, reaches it.
"""

import json
import shlex
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

import briefing
from briefing import (CADENCE, DENIED, EFFORT, IDLE, MODEL, PING_CAP, QUIET, TOOLS, UNCHANGED, Briefing, cache_path,
                      on_change, ping)

START = datetime.fromisoformat("2026-09-21T09:00:00+02:00")
# Gaps up to 18 minutes over up to 80 ticks: long enough that a session retires on the idle hour over
# a few quiet ticks, short enough and long enough a run that the drawn runs reach the ping cap, which
# wider gaps never do (they retire the session first, leaving the Property's cap clause no witness).
RUN = st.lists(st.tuples(st.integers(min_value=0, max_value=18), st.booleans()), min_size=1, max_size=80)


def fresh(at: datetime, n: int) -> Briefing:
    return Briefing("where things stand", at, f"session-{n}", at, at, 0)


def retired(session: Briefing, now: datetime) -> bool:
    return now - session.last_activity >= IDLE or session.pings >= PING_CAP


def drive(run: list[tuple[int, bool]], primed: int | None = None) -> list[tuple[str, Briefing | None, datetime, datetime]]:
    """The schedule's answer to each tick of a run, with the state it was asked about: minutes since
    the last tick, and whether a ticket's status changed at this one. A tick with no change yet asks
    nothing; the watcher has nothing to tell the session about.

    `primed` is the pings already spent by the session in the cache file the run starts from, which
    is what a watcher restarted mid-afternoon reads; None starts from no cache file at all. Without
    it a drawn run never reaches the ping cap, since it retires sessions on the idle hour long
    before, and the Property's cap clause has no witness."""
    answers, session, changed_at, now, n = [], None if primed is None else replace(fresh(START, 0), pings=primed), None, START, 0
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


@given(run=RUN, primed=st.none() | st.integers(min_value=0, max_value=PING_CAP))
def test_the_briefing_session_is_pinged_a_quiet_window_after_a_status_moves_and_never_past_its_idle_hour_or_ping_cap(
    run: list[tuple[int, bool]], primed: int | None
) -> None:
    for verb, session, changed_at, now in drive(run, primed):
        assert verb in ("ping", "wait", "fresh")
        if verb in ("ping", "fresh") and session is not None:
            assert now - changed_at >= QUIET, "a briefing written while the tracker was still moving"
        if verb == "ping":
            assert session is not None, "a ping needs a session to resume"
            assert now - session.last_activity >= CADENCE, "two briefings inside ten minutes"
            assert not retired(session, now), "a session past its idle hour or ping cap still pinged"
        if verb == "fresh":
            assert session is None or retired(session, now), "a live session replaced instead of pinged"
            assert session is None or now - session.last_activity >= CADENCE, "a briefing inside ten minutes of the last"
        if verb == "wait":
            told = session is not None and session.last_activity >= changed_at
            moving = now - changed_at < QUIET
            recent = session is not None and now - session.last_activity < CADENCE
            assert told or moving or recent, "a change waiting past both its windows"


def test_a_session_retired_with_nothing_new_to_tell_it_is_left_where_it_is() -> None:
    """The spec: the session retires after an idle hour "and the next change starts a fresh one".
    A board watching a tracker that has not moved since its last briefing has no next change, so
    the hour passing is not itself a reason to explore the repo again."""
    told = fresh(START, 1)
    assert on_change(told, START, START + IDLE + timedelta(minutes=1)) == "wait"
    assert on_change(told, START + timedelta(minutes=1), START + IDLE + timedelta(minutes=1)) == "fresh"


def test_a_board_with_no_briefing_at_all_writes_one_without_waiting_out_a_window() -> None:
    """The board a returning user opens: the tracker has not moved precisely because they were away,
    and the two windows are about a tracker in motion (09's D3)."""
    assert on_change(None, START, START) == "fresh"


def test_the_two_windows_hold_a_briefing_back_and_then_let_it_through() -> None:
    """The worked example under the property above: a status moves, the tracker keeps moving, and
    the ping goes out once it has been quiet for five minutes and the last briefing is ten old."""
    wrote = fresh(START, 1)
    assert on_change(wrote, START + timedelta(minutes=1), START + timedelta(minutes=3)) == "wait", "the tracker is still moving"
    assert on_change(wrote, START + timedelta(minutes=1), START + timedelta(minutes=8)) == "wait", "a briefing eight minutes after the last"
    assert on_change(wrote, START + timedelta(minutes=1), START + timedelta(minutes=11)) == "ping"
    # and the quiet window is measured from the last status to move, not the first
    assert on_change(wrote, START + timedelta(minutes=9), START + timedelta(minutes=11)) == "wait"
    assert on_change(wrote, START + timedelta(minutes=9), START + timedelta(minutes=14)) == "ping"


def test_a_session_at_its_ping_cap_is_replaced_by_a_fresh_one_and_no_sooner_than_the_cadence() -> None:
    """The cap's own worked example, which the drawn runs above reach only now and then: a session
    that has spent its pings is replaced rather than pinged, and the ten-minute floor governs that
    replacement too, since a fresh exploration is the dearer of the two runs."""
    spent = replace(fresh(START, 1), pings=PING_CAP)
    assert on_change(spent, START + timedelta(minutes=1), START + timedelta(minutes=8)) == "wait", \
        "a briefing written eight minutes after the last one"
    assert on_change(spent, START + timedelta(minutes=1), START + timedelta(minutes=11)) == "fresh"
    assert on_change(replace(spent, pings=PING_CAP - 1), START + timedelta(minutes=1), START + timedelta(minutes=11)) == "ping", \
        "a session with a ping left explored the repo again instead of being told"


def test_the_schedule_and_the_launch_are_the_ones_the_spec_decides() -> None:
    """The property above reads its windows off the module, so the numbers themselves are checked
    here against the spec's Decisions under "The board briefing": five quiet minutes, a briefing
    every ten at most, the idle hour, and the model and effort a run is launched on.

    The spec gives no number for the ping cap, only that there is one, so what is checked is that a
    cap the schedule can reach: one it cannot leaves the Property's own clause unfalsifiable, which
    is what a cap raised "just for now" leaves behind. What a launch really carries to the API, this
    model included, was read off the wire by board-orients 16's demo, retired with that feature (git log --diff-filter=D finds it)."""
    assert QUIET == timedelta(minutes=5)
    assert CADENCE == timedelta(minutes=10)
    assert IDLE == timedelta(hours=1)
    assert CADENCE < IDLE, "a session retires before it can be pinged, so the cap is unreachable"
    assert (MODEL, EFFORT) == ("claude-opus-5-5", "medium")


def answered(said: str) -> str:
    return "printf '%s\\n' " + shlex.quote(json.dumps({"is_error": False, "session_id": "def-456", "result": said}))


def test_a_ping_the_session_answers_unchanged_keeps_the_briefing_and_spends_a_ping(
    tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer the prompt asks for where nothing it was told changes what it wrote. The briefing
    and the time it was written stay as they are, so the column does not claim to be newer than it
    is, and the ping is spent either way: it is what the session's retirement is counted in."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    claude = path_with("claude", answered(f"`{UNCHANGED}`."))
    cached = Briefing("where things stand", START, "abc-123", START, START, 3)
    now = START + timedelta(minutes=20)
    said = ping(cached, "new: agent/tickets/a-chore.md", tmp_path, now)
    assert said and (said.text, said.written) == (cached.text, cached.written), "it rewrote a briefing it left standing"
    assert (said.session, said.last_activity, said.pings) == ("def-456", now, 4)
    run = claude.read_text()
    assert f"--resume {cached.session}" in run, "the ping started a session of its own instead of resuming"
    assert f"--allowedTools {TOOLS}" in run and f"--disallowedTools {DENIED}" in run, "the unattended run could write"
    assert str(tmp_path / "cfg" / "CLAUDE.md") in run, "it was given the user's own memory to read"
    assert f"--model {MODEL} --effort {EFFORT}" in run, "the briefing ran on whatever this machine defaults to"
    assert '"outputStyle": "default"' in run, "it wore the user's own output style, which writes for them at a terminal"


def test_a_ping_the_session_answers_with_a_rewrite_replaces_the_briefing(
    tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    path_with("claude", answered("Two builds wait on your ruling.\n\n## next\n\n- **A chore**: it is quick."))
    cached = Briefing("where things stand", START, "abc-123", START, START, 3)
    now = START + timedelta(minutes=20)
    said = ping(cached, "new: agent/tickets/a-chore.md", tmp_path, now)
    assert said and said.text.startswith("Two builds wait on your ruling.")
    assert (said.written, said.pings) == (now, 4), "a rewritten briefing is one written now"


def test_a_ping_the_session_does_not_answer_leaves_the_cache_where_it_is(
    tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    path_with("claude", "echo '{\"is_error\": true}'")
    cached = Briefing("where things stand", START, "abc-123", START, START, 3)
    assert ping(cached, "new: agent/tickets/a-chore.md", tmp_path, START + timedelta(minutes=20)) is None
    assert briefing.SILENT, "a run that answered nothing said nothing of itself"


def test_the_cache_file_reads_back_what_it_was_written_with(tmp_path: Path) -> None:
    briefing = Briefing("two builds wait on you", START, "abc-123", START, START + IDLE, 3)
    path = cache_path(tmp_path / "board.html")
    briefing.write(path)
    assert Briefing.read(path) == briefing
    assert Briefing.read(tmp_path / "nothing.json") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
