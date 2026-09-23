---
status: proposed
priority: 3
size: XS
---

# harden's end-to-end test fails under load

## Brief

`test_end_to_end_a_deleted_test_brings_its_function_back` in `mx/skills/testing/test_harden.py` failed once in a full `make test` run of the board-orients branch, and passes alone on that branch and on master. A test that fails only when the machine is busy trains everyone to rerun and ignore red.

Cut from the orchestrator's verification of the master merge into board-orients (2026-09-23). The failing assertion was that the deleted test's function, `pkg.mod.x_fits`, is the only new survivor. Under load the run found no survivor there. That fits a mutant timing out and being counted as killed, not a logic change: the branch touches nothing under `mx/skills/testing/`.

## What to build

Find what makes the result depend on load, most likely mutmut's per-mutant timeout against a slow machine, and make the test hold whatever the load: a timeout the fixture sets generously, or a report that tells a timed-out mutant from a killed one.

## Acceptance criteria

- [ ] The test passes in ten consecutive full `make test` runs, alongside the board's browser checks.
- [ ] If the cause is a timeout, `harden`'s report says when a mutant timed out rather than counting it as killed.
