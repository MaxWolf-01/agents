---
status: proposed
priority: 3
size: S
---

# The show conventions get a mechanical check

## Brief

The show conventions as one check in `make check`: a show directory per live piece of work, a demo per landed ticket, no tracked renders beside their sources, demos that run.

Cut from the whole-feature review of figures-and-demos (`6c9ce66..5a322f6`), Tests axis. The feature fixed conventions that are cheap to read mechanically and that nothing reads. Each is a spec Property the Testing Decisions disposes as *reviewed*, and the review found a live violation of one of them on the branch (`agent/show/house-style-rulings/`, whose loose work had shipped on master), which no slice had seen.

## What to build

One check, run by `make check`, over four readings:

- Every directory under `agent/show/` has a ticket, a feature directory or a branch of that name; one with none is named and the check fails.
- Every ticket in `review` or `done` under a feature has `agent/show/<feature>/<NN-slug>/demo` at mode `100755`, unless its closing comment's Demo line says the diff is the demo.
- No render is tracked beside its source: `git ls-files 'agent/show/**/*.png' 'docs/figures/*.png'` is empty. The Property it reads is [figures-and-demos' own](figures-and-demos/spec.md), which scopes it to a render beside its source and says a document in the tree tracks the copy it reads.
- Every `demo` found by `fd -t x '^demo$' agent/show` runs with no arguments and exits 0, behind the `command -v` guards the demos already carry, in a fresh worktree.

All four pass on the branch as it stands.

The fourth reading is the open part, and the ticket may land without it. It costs minutes and a logged-in `claude` for `01-show-table/demo` and `02-spec-figures/demo`, which drive two live model sessions each; and both exit nonzero when the after arm draws no figure, which is right for a human reading one run and wrong for a gate, since the exit then depends on a model's behaviour. Either give it its own target rather than `make check`, or exclude those two and say in the check why. Settle it in the closing comment.

## Acceptance criteria

- [ ] Each reading fails, naming the file, on a tree where it is violated, and passes on the tree as it stands.
- [ ] A reading whose tool is absent on the machine skips with a line saying so, as [`render.py --check`](render-check.md) asks of its own.
- [ ] The fourth reading's home is settled and the closing comment says which way and why.
- [ ] Demo: `agent/show/show-conventions-checked/demo`, executable, no arguments: the check against a toy tree that violates each reading, and against one that does not.
