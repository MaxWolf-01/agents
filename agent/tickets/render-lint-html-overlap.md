---
status: open
priority: 2
size: S
---

# render-lint sees HTML text colliding

## Brief

render-lint finds text that spills out of its own box, and SVG labels that run into each other. It misses two pieces of HTML text drawn on top of each other, which is how the board prototype's rows broke. Every `/mx:show` page and the board's no-overlap check would catch that failure once render-lint does.

Filed on the user's ruling on board-orients 01's D2 (2026-09-23): that ticket's no-overlap check runs render-lint, which its closing comment found blind to HTML-on-HTML overlap and to text a box clips rather than spills.

## What to build

render-lint reports two visible HTML text elements whose boxes intersect when neither contains the other, as the `overlap` kind it already has for SVG text. It also reports text that a box with `overflow: hidden` cuts off, whether by `text-overflow: ellipsis` or plain clipping, as a separate kind that never fails a run: a truncated title is sometimes the design.

## Acceptance criteria

- [ ] A page with two absolutely positioned labels drawn over each other fails with an `overlap` finding naming both texts, and the same page with them apart passes.
- [ ] Text inside a parent (a link inside a paragraph, a span inside a button) is not reported as overlapping that parent.
- [ ] A clipped title is reported, and the run still exits 0.
- [ ] Demo: render-lint run over the board prototype's rejected v3 layout, or a page reproducing its overlapping row marks, with the findings and their crops.
