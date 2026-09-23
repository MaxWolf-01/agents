---
status: open
priority: 3
size: XS
---

# The README's board screenshots, re-shot

## Brief

The README's board screenshots show the board as board-orients 11 left it. Later changes to the board change what they should show, so the README is re-shot once the board's current round of edits is done, with 11's own pipeline, and every figure PNG goes through lossless compression.

Ruled by the user on 2026-09-23 when accepting 11: merge it, and adapt it to what the remaining fixes change. The compression is 11's D1.

Postponed by the user on 2026-09-23 and moved out of board-orients: further edits to the board follow right after that feature merges, so the re-shoot waits until they are done.

## What to build

`docs/figures/board-fixture/`'s pipeline run again, and the README's board screenshots replaced. Every PNG under `mx/assets/` goes through a lossless compressor such as `oxipng`, with the pipeline running it, so a later re-shoot stays small.

## Acceptance criteria

- [ ] The README's board screenshots show the board as it is after those edits.
- [ ] The PNGs under `mx/assets/` are smaller than they were, with no pixel changed.
- [ ] Demo: the byte sizes before and after, and the README's board section rendered.
