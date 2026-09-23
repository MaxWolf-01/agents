---
status: claimed
blocked-by: [07]
priority: 3
size: S
---

# The dependency graph at full size

## Brief

The side column's graph becomes a preview that opens the graph full size in an overlay, or in its own window beside the board; clicking a node there takes the board to that ticket.

Slice of `spec.md`, building on the Decision on the side column.

## What to build

The side column shows the graph of the whole tracker, or of the feature under the cursor, as a preview. Opening it shows the graph full size in an overlay over the board, scrollable and pannable, where a click on a node closes the overlay on that ticket's row; the same view also opens as its own window, to sit beside the board, where a click on a node moves the board to that row. The feature and whole-tracker switch works in both.

## Acceptance criteria

- [ ] The demo tracker's whole-tracker graph is readable at full size in the overlay.
- [ ] A node clicked in the overlay, and in the separate window, brings the board to that ticket's row.
- [ ] The no-overlap check from 01 still passes.
- [ ] Demo: the demo tracker's board with the overlay open, and the separate window beside it, in both schemes.
