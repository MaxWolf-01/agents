"""Properties of the cache's size-capped LRU eviction, over arbitrary cache contents.

`SqliteCache._enforce_max_size` documents itself as "evict oldest unpinned entries (by
last_accessed) until under max_size_bytes". Three properties encode that sentence:

- a pinned entry is never evicted, whatever the cap and whatever the sizes;
- eviction respects last-accessed order: nothing unpinned survives that is older than
  something evicted;
- driving eviction to a fixed point leaves the unpinned bytes at or below the cap.

The example tests in TestLRUEviction and TestPinning cover the same contract with four
hand-written entries of equal size.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from yapit.gateway.cache import CacheConfig, SqliteCache

# One call to _enforce_max_size deletes an estimate's worth of entries, so a cache far over its
# cap needs several. The bound is what makes "converges" a testable claim rather than a hang.
MAX_ENFORCE_PASSES = 50


def run(coro):
    """Run one scenario on its own loop, leaving the session loop the way we found it.

    The properties are sync so Hypothesis drives them, but `asyncio.run` ends with
    `set_event_loop(None)`, and this suite's session-scoped loop is what every later async test
    resumes on: without the restore they fail with `There is no current event loop`.
    """
    try:
        previous = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        previous = None
    try:
        return asyncio.run(coro)
    finally:
        if previous is not None:
            asyncio.set_event_loop(previous)


@dataclass(frozen=True)
class Entry:
    """One cache row as the eviction query sees it: a size in bytes and a pin."""

    size: int
    pinned: bool


entries = st.lists(
    st.builds(Entry, size=st.integers(min_value=1, max_value=4096), pinned=st.booleans()),
    min_size=1,
    max_size=12,
)
# A cap of 0 is excluded: `_enforce_max_size` opens with `if not self._max_size_bytes`, so zero
# reads as "unlimited" rather than "evict everything", and the convergence property fails on it.
caps = st.integers(min_value=1, max_value=8192)


@dataclass(frozen=True)
class Eviction:
    survivors: dict[str, Entry]
    evicted: dict[str, Entry]
    access_order: dict[str, int]
    unpinned_bytes: int
    passes: int


async def _evict_to_fixed_point(contents: list[Entry], max_bytes: int) -> Eviction:
    """Fill a fresh cache with `contents` (index order == access order, oldest first)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SqliteCache(CacheConfig(path=Path(tmpdir)))
        cache._max_size_bytes = max_bytes
        access_order = {f"key{i}": i for i in range(len(contents))}
        by_key = {f"key{i}": entry for i, entry in enumerate(contents)}
        try:
            db = await cache._get_writer()
            for key, entry in by_key.items():
                await db.execute(
                    "REPLACE INTO cache(key, data, size, created_at, last_accessed, pinned) VALUES(?,?,?,?,?,?)",
                    (key, b"\0" * entry.size, entry.size, 0.0, float(access_order[key]), int(entry.pinned)),
                )
            await db.commit()

            passes = 0
            while passes < MAX_ENFORCE_PASSES and await cache._enforce_max_size():
                passes += 1

            async with db.execute("SELECT key FROM cache") as cursor:
                remaining = {row[0] for row in await cursor.fetchall()}
            async with db.execute("SELECT COALESCE(SUM(size), 0) FROM cache WHERE pinned=0") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                unpinned_bytes = row[0]
        finally:
            await cache.close()

    return Eviction(
        survivors={k: v for k, v in by_key.items() if k in remaining},
        evicted={k: v for k, v in by_key.items() if k not in remaining},
        access_order=access_order,
        unpinned_bytes=unpinned_bytes,
        passes=passes,
    )


@given(entries, caps)
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_pinned_entries_are_never_evicted(contents: list[Entry], max_bytes: int) -> None:
    result = run(_evict_to_fixed_point(contents, max_bytes))
    assert not [key for key, entry in result.evicted.items() if entry.pinned]


@given(entries, caps)
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_eviction_takes_the_least_recently_accessed_first(contents: list[Entry], max_bytes: int) -> None:
    result = run(_evict_to_fixed_point(contents, max_bytes))
    newest_evicted = max((result.access_order[key] for key in result.evicted), default=-1)
    oldest_unpinned_survivor = min(
        (result.access_order[key] for key, entry in result.survivors.items() if not entry.pinned),
        default=len(contents),
    )
    assert newest_evicted < oldest_unpinned_survivor


@given(entries, caps)
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_eviction_converges_to_the_cap(contents: list[Entry], max_bytes: int) -> None:
    result = run(_evict_to_fixed_point(contents, max_bytes))
    assert result.passes < MAX_ENFORCE_PASSES
    assert result.unpinned_bytes <= max_bytes
