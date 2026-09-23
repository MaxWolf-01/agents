---
status: open
blocked-by: [09, 10]
priority: 3
size: XS
---

# The README shows the board as it is

## Brief

The README's two board screenshots and their alt text show the board before this feature: a needs-human queue, a debrief as a queue entry, no priority, time or questions on a row. Once the last board slice has landed, re-render them from the README's fixture tracker and rewrite the alt text to match.

Filed on the user's review comment on 10 (C1, 2026-09-23): a stale figure gets updated, and one pass after the other slices is cheaper and more accurate than one per slice.

## What to build

`mx/assets/board-overview.png` and `mx/assets/board-feature.png` rendered again from the board fixture tracker the README's caption names, in the board this feature built. The fixture tickets carry what the new rows show: priority, size, a brief, and at least one open question. The alt text in `mx/README.md` describes what the new screenshots show. The ticket-state figure's labels for the retired needs-human queue go the same way, together with `ticket-state-figure-review` where it is still open.

## Acceptance criteria

- [ ] Both screenshots show the needs-me group with questions under a row, and rows with their marks.
- [ ] No figure or alt text in the README names the needs-human queue.
- [ ] Demo: the README's board section before and after, side by side.
