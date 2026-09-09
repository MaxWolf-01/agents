# What does a property-tests ticket produce, and does it earn its keep?

Two property files written against a documented seam of a real project, without changing the project, then measured with mutation testing against the project's existing example tests. Both files are kept verbatim; they ran in throwaway clones of the projects at the commits named below.

## memex, `find` seam (`memex_find_ranking_properties.py`)

memex `5c831b6` (v2.2.2), 151 example tests. The README states the ranking contract "exact title/alias > substring > fuzzy"; the file encodes its exact-match tier over generated vaults (1–10 notes, unique keys, 0–2 aliases each).

- Found no bug; the contract holds.
- Killed two mutants the 151 example tests could not: both flip `EXACT_BONUS + 100` to `- 100` in `_score_part`, the exact-match tier collapsing below a substring hit. The example fixture never contains a strong enough substring competitor; the generator does.
- Cost: 70 lines, +1.1 s on a 4.4 s suite.

## yapit, cache eviction seam (`yapit_cache_eviction_properties.py`)

yapit `baa372e` (v0.4.5), 474 example tests. `SqliteCache._enforce_max_size` documents itself as "evict oldest unpinned entries (by last_accessed) until under max_size_bytes"; three properties encode that sentence over generated cache contents.

- Found a live bug on the first run: a configured cap of zero reads as unlimited (`if not self._max_size_bytes`), so `max_size_mb=0` silently disables eviction. The strategy now starts at 1 and the finding is in the file's comment; yapit was not changed.
- Killed three mutants the 474 example tests could not: the under-cap early return, the eviction count, the LRU task creation.
- Cost: each example builds a real SQLite cache (~110 ms), so 200 examples put the suite from ~21 s to ~89 s; 50 examples is the setting to ship. Under mutation testing the same properties made the module's run 6.6× slower, because the tool's per-mutant budget scales with the covering tests' duration.

## Verdicts (the user's, testing-workflow grilling)

- The generator is the artefact worth the human's eyes: a few lines show the covered space in a way hundreds of example tests do not.
- Property tests are written by a worker that has the spec and the seam's interface and not the implementation (the ticket is scheduled before the slices it blocks).
- Property tests run under harden with a small example count; the suite's count is the project's to set.
