---
status: proposed
priority: 3
size: M
---

# render-lint asks the engine what a reader can see

## Brief

render-lint decides what a reader sees of a text by re-deriving CSS from computed styles: which
ancestors clip a box, which of them its position escapes, what rectangle the root's overflow
stands for. Chromium already knows.

Cut from render-lint-html-overlap's five review rounds (2026-09-23), each of which found one more
rectangle the walk gets wrong. The containing-block table is finishable and is now probed
declaration by declaration against Chrome; the geometry is not, and every miss has cost either a
page that cannot be made to pass or a collision nobody sees.

## What to build

The reachability half of the clip pass asks the engine: for each text rect, sample points and
take `document.elementsFromPoint` membership as the answer to "is this text painted here".
Pairing two rects into an overlap stays geometric, since hit-testing has nothing to say about it.

Measured on this branch (`agent/reviews/ffc431e..0e9a328/light.md`, last section): ~50ms for
4500 points on the largest committed page, against a run dominated by browser startup, and no
false negative on the two largest. Three failure modes it brings, all named there:

- `pointer-events: none` reads as unreachable. Injecting `* { pointer-events: auto !important }`
  before measuring fixes it and moves no layout.
- Points outside the viewport return nothing, so the resize has to cover the page, which it does
  not today on a layout sized in `vh`.
- The `clipped` kind's pixel count comes out at sampling resolution; the exact number needs a
  binary search per edge, or stays derived.

## Acceptance criteria

- [ ] Each page the five review rounds turned up gets its verdict from the engine rather than the
      derivation, `mx/skills/show/test_render_lint.py`'s checks among them.
- [ ] Text under `pointer-events: none` still collides.
- [ ] A page whose layout grows under the viewport resize is measured whole.
- [ ] `clipped` reports the same pixel count it reports today, to the pixel, or the ticket records
      why a coarser one is enough.
- [ ] Demo: the run over the committed pages before and after, showing the same findings, and over
      the pages under `agent/reviews/` that the derivation gets wrong.
