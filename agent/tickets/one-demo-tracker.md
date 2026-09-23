---
status: proposed
priority: 4
size: M
---

# One demo tracker behind both the checks and the figures

## Brief

The repo builds the same fictional tracker twice: `mx/skills/tracker/demo_tracker.py` for the board's checks and `docs/figures/board-fixture/` for the README's screenshots. Same product, the same two features, overlapping standalone tickets, one set written as Python string literals and the other as markdown files on disk. A change to what a row shows has to be made in both, and the screenshots and the suite can come to disagree about what the board does; one shared ticket has already drifted in slug.

Cut from the whole-feature review of board-orients (`7093bf7..be76e6c`, Standards axis, S8), which named it a judgement call: the two genuinely need different extras, the checks wanting git history and transcripts, the figures wanting a real diffview page. The two sets are also uneven, nine standalone tickets against two, so reconciling them is a design pass rather than a merge.

## What to build

One module owning the ticket bodies, with each builder adding on top of it what only it needs.

## Acceptance criteria

- [ ] A ticket's priority, size, name, brief or question is written in one place and reaches both the checks and the figures.
- [ ] The board's checks pass and the README's screenshots re-render with no visible change.
- [ ] Demo: the diff is the demo.
