---
status: open
type: legwork
---

# Report the mutation-tooling defects upstream

Filed from the testing-workflow grilling; the harden script works around each of these, and an upstream fix would delete the workaround. File each with `/mx:upstream-issue`, minimal repro from the prototype clones (`/var/tmp/memex-proto`, `/var/tmp/yapit-proto`) and the research snapshots `agent/research/04`, `05`, `07`.

mutmut 3.7.0 (`boxed/mutmut`):

- The three string-literal mutations (wrap in `XX`, lowercase, uppercase) cannot be switched off, and the case flips are equivalent mutants by construction wherever they survive (SQL keywords, encoding names, header names): 25% of survivors on memex, 11% on yapit. Filed as [mutmut#577](https://github.com/boxed/mutmut/issues/577).
- `mutate_only_covered_lines` runs the suite in-process and evicts every imported module afterwards, which crashes on projects whose tests import C-extension or registry-holding modules (numpy, PyYAML, SQLAlchemy, asyncpg): segfault in asyncpg, double registration in SQLAlchemy's inspection registry. Filed as a [comment on mutmut#528](https://github.com/boxed/mutmut/issues/528#issuecomment-5607227417).
- The fork-per-mutant runner inherits a dead asyncio loop, so every mutant of an async suite times out; a fresh interpreter per mutant gives real verdicts (15 of 15 `create_reservation` mutants: 158 s of timeouts versus 17 s of verdicts). Filed as [mutmut#578](https://github.com/boxed/mutmut/issues/578).
- Decorated functions are skipped with no opt-in: every FastAPI handler and pydantic validator (17% of yapit's functions) is invisible.
- The per-mutant time budget counts only the `call` phase of the covering tests, so interpreter start-up and fixture setup (testcontainers) are unbudgeted.

coverage.py: nothing to file. The lines lost after an `await` into SQLAlchemy are the documented behaviour of a greenlet program whose coverage config does not name greenlet; `[tool.coverage.run] concurrency = ["thread", "greenlet"]` records the same line set as the `sysmon` core (`agent/research/upstream-coveragepy-greenlet-await.md`).

## Comments

**2026-09-09** The three marked above are filed against mutmut 3.7.0, each carrying a minimal repro built and run in a clean directory and inlined in the issue.
