---
status: proposed
priority: 2
size: XS
---

# `make harden` is prescribed and this repo has no target for it

## Brief

`/mx:dispatch` runs `make harden` at every feature's close-out, and this repo's Makefile has no such target, so every mutation survivor here is found by hand.

Cut from the whole-feature review of figures-and-demos (`6c9ce66..5a322f6`), Tests axis. `/mx:dispatch` step 3 says `make harden ARGS="--integration-branch ..."` runs once from the feature worktree when the frontier empties, and `/mx:testing` says the same. `mx/bin/harden` exists and answers `--help`. This repo's `Makefile` has `check`, `test`, `version` and three release targets, and `make -n harden` says there is no rule to make it.

So every survivor this repo has found was found by hand, one mutation at a time. The review that cut this ticket did exactly that, and the self-review then found two more survivors of the one test it wrote, both inside a target the range touched: `make harden` lists both by construction.

## What to build

A `harden` target beside `test`, running `mx/bin/harden` with the same dependency set `test` uses, passing `ARGS` through as the dispatch skill types it.

## Acceptance criteria

- [ ] `make harden ARGS="--integration-branch master"` runs to a report on this repo.
- [ ] The dependency list matches `test`'s, so the two targets do not drift.
- [ ] Demo: `agent/show/harden-has-no-target/demo`, executable, no arguments: the target run over one module, and one survivor from its report read against the test that should have caught it.
