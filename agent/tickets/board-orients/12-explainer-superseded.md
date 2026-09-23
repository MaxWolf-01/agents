---
status: proposed
priority: 4
size: XS
---

# The prototype's explainer says the build has not happened

## Brief

`agent/show/board-orients/index.html` is the page the prototype was judged in front of, and it still reads as current: its table says "the build: not yet", its "what the demo found" list carries as open the very thing 08 built, and it says there is no `spec.md` for board-orients. A reader who opens it today is told this feature does not exist.

Cut from the code review of 08-graph-overlay (spec axis, 2026-09-23), which found the line "the whole-tracker graph is too small to read in the side column" still listed as open on a page the slice had just answered. The page is stale as a whole, not in one line, so it wants a ruling rather than an edit.

## What to build

A ruling on which of the two the page should be, then that:

- **Tombstoned**: the one-line header the tracker conventions prescribe for a superseded artefact, so the page stays readable as the reasoning trail it is and nobody reads it as current.
- **Regenerated**: `page.py` beside it rewritten against the landed board, its "still open" table cut to what is still open and its screenshots retaken, so it becomes the feature's explainer rather than the prototype's.

Options sketched by agent 2026-09-23, frame unconfirmed; an answer outside this pair counts, deleting the page among them.

## Acceptance criteria

- [ ] No claim on the page contradicts what the feature landed.
- [ ] Nothing in `agent/show/board-orients/` reads as current while describing the prototype.
