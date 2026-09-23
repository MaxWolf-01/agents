---
status: review
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

- [x] The demo tracker's whole-tracker graph is readable at full size in the overlay.
- [x] A node clicked in the overlay, and in the separate window, brings the board to that ticket's row.
- [x] The no-overlap check from 01 still passes.
- [x] Demo: the demo tracker's board with the overlay open, and the separate window beside it, in both schemes.

## Questions

- [D1] **Should the window of its own follow the board, or hold still?** Its switch has to reach the board either way, so the two talk; what is mine is that it also follows the board's cursor and its colour scheme, which costs a hello a second between the two windows. Holding still means a window that goes stale the moment you move on the board, and a mark on a row you have left.
- [D2] **The graph at full size pans but does not zoom.** The spec defers pan and zoom together and names a plain scrollable full-size SVG as the default; the ticket asks for pannable, so pan is thirty lines of drag-to-scroll and no library. A tracker three times this one's size is readable at full size but wants more dragging than a zoom-out would. Worth a slice, or is dragging enough?
- [D3] **The figure carries its screenshots in the file, 207 KB of base64.** `.gitignore` says regenerable PNGs leave git, and 07's figure lifted live rows instead of shooting them; an overlay and a second window exist only after a browser has been driven into them, so a picture is the only way to show them. The alternative is a figure that has to be rebuilt before it can be opened.

## Comments

The side column's graph stays where it is as a preview, and the same graph now opens at its own
size over the board and in a window of its own beside it, both scrolling and dragging to pan, both
carrying the feature and whole-tracker switch, and both taking the board to a ticket's row when a
node is clicked. On branch `ticket/board-orients/08-graph-overlay`, not merged. My calls for you
are this ticket's `## Questions`.

**Demo**

    agent/show/board-orients/08-graph-overlay/demo

builds the demo tracker, renders its board, then drives a browser through the three moves and
prints what the board did at each, rather than telling you to make them. Run here:

    $ agent/show/board-orients/08-graph-overlay/demo

    The board: /tmp/board-graph-demo/agent/board.html

      1. The preview beside the rows draws the csv-import graph 323px wide, which is the column it is given.
      2. `full` opens the same graph over the board, and the switch in the overlay's head puts it on the whole tracker: 8 nodes, 1565px wide, 139px of it past the edge of the box, which scrolls and drags to pan. 1 node is ringed: the row the cursor is on.
      3. A click on the node for t-csv-import-04 closed the overlay and left the board on t-csv-import-04.
      4. `window` opens the same view in a window of its own, to sit beside the board: 8 nodes in the whole tracker graph, in the board's own scheme.
      5. The switch in that window moves the board's own graph with it: the window is on 'csv-import' and the board's preview says 'csv-import'.
      6. A click on the node for t-csv-import-04 there moves the board behind it to t-csv-import-04, and the window stays open.

The rest of what it prints is where to look on the board it leaves behind, which is yours to open
and drive by hand. `--scheme night` runs the same walkthrough in the other scheme.

**The figure**

    agent/show/board-orients/08-graph-overlay/figure.py    # writes figure.html beside it

`agent/show/board-orients/08-graph-overlay/figure.html` is the before and the after: four panels,
each a screenshot of a browser driven into the state its caption names, with a numbered badge
sitting where each note points, placed from the box that browser measured for that element. The
`before` panel runs the board as `5ced2d5` had it, read out of git, so it is what the board did
rather than an account of it. Both schemes are captured and the day/night switch picks one. It is
committed, so opening it needs no build.

**Details, if you want them**

- [D4] Assumptions
  - A1 `mx/skills/tracker/board.py:2384`: the window of its own follows the board's cursor, mode and scheme rather than being painted once at opening, and the two talk by message because the board is a `file://` page whose origin a reload replaces (D1).
  - A2 `mx/skills/tracker/board.py:1676`: pan is thirty lines of drag-to-scroll rather than a library, and there is no zoom; the spec defers both and names plain scroll as the default (D2).
  - A3 `agent/show/board-orients/08-graph-overlay/figure.py:1`: the figure's four panels are screenshots inlined as base64, against `.gitignore`'s rule that regenerable PNGs leave git (D3).
  - A4 `mx/skills/tracker/board.py:2583`: `f`, `w`, `?graph` on the address, a click on the preview, a click on the backdrop and `Esc` are entry points the ticket does not name; they follow the page's own keys and the help table carries the two new ones.
  - A5 `mx/skills/tracker/test_board_layout.py:233`: the browser probe is a fourth seam, where the spec's Testing Decisions names three; 02 and 03 established it and this slice is the third to use it, since everything here lives in the page's script. It serves the Property "No overlap from 80% to 200%, 900px up" and the two behavioural criteria above, and the Decisions wants a sentence for it when this lands.
  - A6 `mx/skills/tracker/board.py:2396`: a message is acted on whoever sent it. A `file://` page has an opaque origin, so there is nothing to check against, and the only things a message moves are the board's own cursor and its graph mode.
  - A7 `mx/skills/tracker/board.py:1664`: what the two full size views do is a Python string run in two realms rather than a shared module, because the window is another document and, after the board's first re-render, another origin.
  - A8 `mx/skills/tracker/board.py:2339`: a full size view is mermaid re-run from the preview's own source, not the preview's drawing cloned, so element ids stay unique within a document and the drawing comes out at the size mermaid measured it for.
- [D5] Findings, from `/mx:code-review` over `5ced2d5..f65cf1e`, four axes, reports in `agent/reviews/5ced2d5..f65cf1e/`
  - Fixed in 3f03bc8: the window dying at the board's next re-render, since a `file://` reload mints a new origin and `opener.boardGraph` threw from there on, leaving a live window saying the board was gone while the board sat beside it, and `w` then writing into the stale window and throwing with nothing said (correctness 1); the window's labels in Georgia, its font links never copied (correctness 3); a pan released on the overlay's backdrop closing the overlay and throwing the pan away, which is where panning the whole tracker leftward ends (spec C1, correctness 4); the grabbing cursor left on after a release outside the box (correctness 4); the overlay repainting on every cursor move, putting the reader's pan back to the top left (standards 3); two paints landing in the order mermaid finished them (correctness 2, spec C3); `#graph` opening the overlay on the placeholder, so the layout check's two new pages measured a head bar and a line of grey text at fourteen widths (tests F1, spec A1, standards 9); the window never measured by the no-overlap check (spec A2); one paint written twice and the two views' markup written twice (standards 4, 5); the four reads of a node's href in two spellings (standards 6); `.gfhead .gname` re-declaring every property `.gname` already has (standards 2); `git archive` bypassing the file's own `run`, so a bad `--before` blamed tar (standards 7); the demo removing the directory it was pointed at (standards 8); two em dashes (standards 1); `--help` carrying the key bindings the page's help table owns, and the five-clause sentence carrying them (standards 14, 15); the stale "four pages" 170 lines from the six (standards 10); chromium's absence dying inside playwright (standards 11); the figure measuring badges in both schemes and using one, now a check that the two agree (standards 12); the page-seam check locating the overlay by markup adjacency and whitespace (tests F2); three fixed sleeps where a condition was what was waited for (tests F3); the window's assertions weaker than the overlay's in the same run (tests F4); `still_open` reading a class rather than visibility (tests F5); the window's switch clicked in the direction the board was already in, so the assertion could not fail (correctness 5); `test_board.py`'s literal graph count and its docstring's "all three" (standards 16).
  - Also fixed there, from the same reading: the preview now says in words that it opens (spec, "every mark explains itself"), and `window` inside the overlay gives the board back with it, which the figure's note had claimed (spec C4).
  - Covered by the same commit's probe, from the tests axis's list of what no check could tell from its absence: the `f` and `w` keys, Escape taking the overlay before the open row, the preview's click and the `a` guard that keeps a node in it going to its row, the drag that pans and the click it ends with, `?graph`, the backdrop click, `gwinfull`, the window's mark following the board's cursor, the orphan reading, and the height half of the full size sizing, now read against the viewBox rather than against another graph.
  - Filed as 12-explainer-superseded: `agent/show/board-orients/index.html` still says this feature has not been built, and lists as open the thing this slice answers.
  - Declined, with the reason in the assumption it stands on: the window's live-follow (spec B1) → A1 and D1; hand-rolled pan against the deferral's stated default (spec B4) → A2 and D2; the committed base64 screenshots (standards 13) → A3 and D3; the entry points the ticket does not name (spec B2) → A4; the browser probe as an unnamed seam (tests b) → A5. Four of the tests axis's untellable-from-absence list stay untold: the blocked-popup toast and the second `w` focusing rather than re-creating both need a browser configured to block popups or two popups counted, the `fullCache` needs `mermaid.render` wrapped from outside, and the overlay surviving a re-render needs the stamp file touched mid-run; each is a check about the machinery rather than about what the board does, and the first three cost more setup than the line they hold. The demo's `--tracker` flag where the two older demos take a positional (standards 8, minor) stands: the demo has two flags and both read better named.
- [D6] Friction
  - The board is opened as a file, and a `file://` page's origin is not just opaque but new on every load. Nothing says so: the window worked perfectly until the board re-rendered, which is a thing that happens on its own, minutes later, with nobody watching. What found it was a reviewer driving a reload; what would have found it sooner is the probe I wrote afterwards, which now reloads the board in the middle of the run. A second window is the first thing this board has that outlives one of its own renders, and the reload is the only interesting moment in its life.
  - `render-lint` reads pages off disk, and the window of its own is a document that only exists once a browser has opened it. The probe now hands its `outerHTML` back for linting, which works, but every new rendered surface of the board will have the same shape of hole: the thing to lint is a render rather than a file. A `render_page`-shaped function per surface would let the check write each one out; the window's is the first that is built by string concatenation in JS instead.
  - Two of this slice's own checks were vacuous in ways the run could not show: `#graph` measured an empty overlay at fourteen widths, and the window's switch was clicked in the direction the board was already in. Both read as green. The file already had the answer to the first, twice, in the two `assert seen[...]` preconditions its other anchors carry; I added a third anchor without its precondition. A layout matrix whose entries each carry the assertion that the page reached the state they name would have made both impossible.
  - The demo tracker's whole-tracker graph is 1565px wide, and the probe's window is 1600px, so "the box pans" rested on 35px of overflow that any edit to the fixture would take away. The check now drags and reads `scrollLeft`, which is the behaviour; the overflow is the precondition beside it. A fixture that has to be wide enough for a check is a fixture that will be narrowed by the next person who edits it for another reason.
