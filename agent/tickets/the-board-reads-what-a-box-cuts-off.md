---
status: proposed
priority: 4
size: XS
---

# The board reads what a box cuts off

## Brief

The board's layout check drops every `clipped` finding render-lint reports, board-wide. The marks that truncate on purpose are why, but the filter also drops a brief, a briefing paragraph or an overlay label cut off by a box that was never meant to cut anything. `render-lint-html-overlap` was cut to give the board that signal, and the board discards all of it.

Cut from the whole-feature review of board-orients (`7093bf7..be76e6c`, Tests axis, T10).

## What to build

Narrow the filter to what truncates by design. Those elements carry `class="clip"` (`board.clipped_html`) and the finding carries its text, so the filter can name them rather than the kind.

## Acceptance criteria

- [ ] A `clipped` finding on an element that does not truncate by design fails the layout check.
- [ ] The check passes on the board as it stands, or the findings it now sees are fixed with it.
- [ ] Demo: the diff is the demo.
