---
status: proposed
---

# The show conventions get a mechanical check

Cut from the whole-feature review of figures-and-demos (`6c9ce66..5a322f6`), Tests axis. The feature fixed four conventions that are cheap to read mechanically and that nothing reads: a demo lives at a fixed path, takes no arguments and is executable; a show directory does not outlive the work it served; a figure's render is not tracked beside its source. Each is a spec Property the Testing Decisions disposes as *reviewed*, and the review found a live violation of the show-directory one on the branch (`agent/show/house-style-rulings/`, retired in this pass) which no slice had seen.

## What to build

One check, run by `make check`, over four readings:

- Every directory under `agent/show/` has a ticket, a feature directory or a branch of that name; one with none is named and the check fails.
- Every ticket in `review` or `done` under a feature has `agent/show/<feature>/<NN-slug>/demo` at mode `100755`, unless its closing comment's Demo line says the diff is the demo.
- `git ls-files 'agent/show/**/*.png' 'docs/figures/*.png'` is empty.
- Every `demo` found by `fd -t x '^demo$' agent/show` runs with no arguments, behind the `command -v` guards the demos already carry, in a fresh worktree. This last one costs minutes and a logged-in `claude` for two of the five, so it may want its own target rather than `make check`.

All four pass on the branch as it stands, which is what makes now the cheap moment.

Blocked on the "a demo that asserts" call in [the feature's queue](figures-and-demos/needs-human.md): the demos are the only automated reading the new `dispatch` code has, and whether an asserting demo is promoted out of its show directory before the feature retires is the user's ruling, not this ticket's.

## Acceptance criteria

- [ ] Each reading fails, naming the file, on a tree where it is violated, and passes on the tree as it stands.
- [ ] A reading whose tool is absent on the machine skips with a line saying so, as `render-check.md` asks of its own.
- [ ] Demo: the check run against the tree as it stands and against a tree with one violation of each kind.
