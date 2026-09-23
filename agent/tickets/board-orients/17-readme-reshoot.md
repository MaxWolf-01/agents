---
status: open
blocked-by: [13, 14]
priority: 3
size: XS
---

# The README's board screenshots, re-shot at close-out

## Brief

11's screenshots show the board as 11 left it. 13's fixes and 14's single question list change what an opened row looks like, so the README is re-shot once they land, with 11's own pipeline, and every figure PNG goes through lossless compression.

Ruled by the user on 2026-09-23 when accepting 11: merge it, and adapt it to what the remaining fixes change. The compression is 11's D2.

## What to build

`docs/figures/board-fixture/`'s pipeline run again on the feature's tip, and the README's board screenshots replaced. Every PNG under `mx/assets/` goes through a lossless compressor such as `oxipng`, with the pipeline running it, so a later re-shoot stays small.

## Acceptance criteria

- [ ] The README's board screenshots show the board as the feature ships it.
- [ ] The PNGs under `mx/assets/` are smaller than they were, with no pixel changed.
- [ ] Demo: the byte sizes before and after, and the README's board section rendered.
