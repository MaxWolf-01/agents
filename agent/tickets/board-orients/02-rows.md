---
status: review
blocked-by: [01]
priority: 1
size: M
---

# Rows that say what they are

## Brief

The board redone in the house style: every row shows what it asks of you, its short name and brief, your time and its priority in fixed columns, each mark explained on hover, readable in the day scheme and never overlapping at any zoom.

Slice of `spec.md`, building on the Decisions under "The ticket file" (priority, size, the H1 as name, `## Brief`) and "The board" (groups aside: fixed columns, marks, hover, readability, reflow, house style, the review link once).

## What to build

A user reads each row left to right in the same columns: feature, number, what the row asks (to rule on, your answer, design session, prototype, research, legwork, build) as a tinted tag, the short name with its review link and GitHub references, the brief under it, the user's time, the priority as a word, and the blockers. Priority and size come from the ticket's frontmatter, the name from its H1, the brief from its `## Brief`; a ticket without them shows its row without those marks. Rows sort by priority, then size, within each group. Every mark says in words on hover what it means, a blocker included ("waits on 01, done"). The page wears the house style in both schemes, with the colours drawn from the mwolf.dev callouts, the time's hue picked again, the day scheme readable at 100% zoom, and a row that reflows below a width instead of overlapping. A feature's filter counts its proposed tickets too, so a breakdown just cut reads 0/4, not 0/0. Groups, keys, the filter, the feature filters, the graph panel and copy-path keep working.

The prototype at `agent/prototypes/board-orients/` is where this shape was settled; its code is a reference, not a floor.

## Acceptance criteria

- [x] The no-overlap check from 01 passes and its annotation is gone.
- [x] Property, reviewed: every mark on a row explains itself on hover in words.
- [x] Property, reviewed: a ticket's priority, size and kind are read from the ticket file.
- [x] `test_board.py` covers frontmatter priority and size, the H1 as name, the Brief section and the sort.
- [x] Demo: the demo tracker's board opened in both schemes, and one real ticket of this repo given priority, size and a brief, on the real board.

## Comments

The board's rows as the spec has them: fixed columns, marks that say what they mean on hover, the
house style in both schemes, sorted by priority and by your time; on branch
`ticket/board-orients/02-rows`, not merged. Two things beyond the ticket's text: the review-page
server's absence is now said on the page (01's D3, D2 below), and the layout check grew a browser
probe, which is what caught the marks whose hover words no reader could see.

**Demo**

The demo tracker's board, in both schemes:

    $ uv run mx/skills/tracker/demo_tracker.py /tmp/board-demo
    /tmp/board-demo/agent/tickets
    $ cd /tmp/board-demo && board agent/tickets --no-watch --no-open
    /tmp/board-demo/agent/board.html

Open `/tmp/board-demo/agent/board.html`. The switch at the top right flips the scheme, `t` does
too, and `?theme=day` / `?theme=night` on the address pin one. What to look for, day scheme at 100%
zoom first, since that is the one that could not be read before:

- Each row reads left to right in the same columns: the feature, the number, what it asks of you as
  a tinted tag, the name with its review page and GitHub references, the ticket brief under it, your
  time, the priority as a word, what it waits on.
- Hover every mark: the words appear under the row. `to rule on`, `p1 now`, `1 h`, the struck-through
  `01` ("Waits on 01, done."), the number (the path a click copies), the feature, the review page.
- Each group is sorted: `needs my review` has p1 before p2, and `frontier` runs p1 15 min, p1 1 h,
  p2 15 min down to p5 several sessions.
- Narrow the window past 1000px: the time, the priority and the blockers move under the name. Past
  620px the name takes the row's width. Nothing overlaps at any width.
- `j` / `k` move the cursor and the graph follows; `a`, `b`, `/`, the feature pills and a click on a
  number all still work.

This repo's own board, for a ticket that carries the new fields:

    board --no-watch --no-open

Open `agent/board.html` and look at `board-orients` 01 and 02: both show `20 min` / `1 h`, a
priority word and their brief, and the feature's pill reads `board-orients 0/10` rather than `0/0`,
which is the proposed-counting the ticket asks for. I could not run that half here: on a dispatch
worker host the main checkout is the bare repo the worktrees hang off, so `board` stops with
`no tracker at .../agents.git/agent/tickets` (01's friction, still true). I rendered the same
tracker from a copy in a scratch repo to check it renders, which is how I know those rows look
right, but the render you open is yours to make.

**I need from you**

- [D1] **The day scheme's colours, in front of the render.** The spec defers the exact hues and
  sizes to agent taste, so these are mine: the priority now ramps on one hue (p1 and p2 filled, p3
  faint, p4 and p5 plain) instead of the prototype's four, which frees the blue and the slate its
  research and legwork tags had taken; the time's teal is re-picked away from the moss accent it
  read as; and every tinted day value is deepened until 12px text on its own tint clears 4.6:1,
  which the prototype's values did not (3.9:1 for research and for p1).
- [D2] **The review-page server's absence is now said on the page.** That is 01's D3, which asked
  you whether "says each absence once" covers all four sources; the orchestrator told me to build it,
  so I did, with a check beside 01's other absence checks. If that reading stands, the spec's
  Property is as written and 01's D3 is answered; if not, the note and its two checks come out.
- [D3] **"Mark" means two things now.** `CONTEXT.md` defines a mark as the provenance tag on a call
  in a draft spec; the confirmed spec and this build use it for a row's visual marks throughout
  (`every mark explains itself`). The glossary can hold both senses or one of them can be renamed;
  it is not a slice's call, and ticket 10 owns the glossary edits.
- [D4] **`render-lint` and this board, in what order.** The branch `ticket/master/render-lint-html-overlap`
  teaches render-lint the HTML-on-HTML overlap that 01's D2 says the no-overlap check cannot see.
  Run against this board it finds no real overlap at any of the check's fourteen widths in either
  scheme (see the friction below), but about two hundred false ones per page: its text walk measures
  text inside a closed `<details>`, which Chromium lays out at the row's position and never paints.
  `el.checkVisibility()` in that walk is the whole fix. If that branch merges before this one, this
  ticket's layout check goes red on those false positives.
- [D5] **The layout check now costs 47s of a 91s suite.** Fourteen widths x two schemes x folded and
  opened, plus a browser probe at two widths. It is the matrix the Property states rather than a
  sample of it, and it is what catches a broken row; if that is too slow for every later worker, the
  cheapest cut is the probe at one width instead of two.

**Details, if you want them**

- [D6] Assumptions
  - A1 `mx/skills/tracker/board.py:1238`: the priority is a ramp on one hue, not a category per
    level, since it is ordinal and five hues would collide with the seven the asks column needs (D1).
  - A2 `mx/skills/tracker/board.py:1119`: the time's hue is the prototype's teal re-picked, shifted
    toward blue and away from the moss accent; the spec says the prototype's read off (D1).
  - A3 `mx/skills/tracker/board.py:1091`: the day-scheme readability fix is a darker `--muted` than
    the house token plus the board's own type sizes, which is the spec's Deferral standing.
  - A4 `mx/skills/tracker/board.py:1296`: a mark's words are a styled tooltip on `data-tip`, as the
    prototype settled, not a native `title`, so they can carry several lines; they appear under the
    row at its left edge, which is the only box that is always on screen and never hides its
    overflow, so no mark can clip or strand its own words wherever in the row it sits.
  - A5 `mx/skills/tracker/board.py:1254`: the row reflows at 1000px and again at 620px, and the graph
    panel moves beside the rows at 1400px; the seven fixed columns need about 670px, so a side panel
    any earlier takes the name's width.
  - A6 `mx/skills/tracker/board.py:572`: the `## Brief` section is taken out of the text that folds
    under the row, so the brief has one home and the row is it.
  - A7 `mx/skills/tracker/board.py:1049`: the review-page server's absence is derived from a page
    linked as a `file://`, so a tracker with no review page rendered yet says nothing about a server
    it has no pages for (D2).
  - A8 `mx/skills/tracker/board.py:847`: `asks()` takes the open-question flag that
    03-questions-and-needs-me will pass, and `ASKS` carries the `your answer` entry the spec's seven
    words name; until 03 lands no ticket row asks for an answer, and the check says so.
  - A9 `mx/skills/tracker/board.py:1244`: the blockers' column is as fixed as the rest and a long
    cross-feature reference wraps inside it; the prototype let that column grow, which pulled the
    time and the priority out of line on exactly the rows that have blockers.
  - A10 `mx/skills/tracker/board.py:556`: a priority or size the tracker does not know stops the
    render with the file named, as an unknown status and a malformed `gh` reference already do.
  - A11 `mx/skills/tracker/board.py:876`: a ticket whose frontmatter says neither priority nor size
    sorts after the ones that do, since nothing is known about what it costs.
  - A12 `mx/skills/tracker/test_board_layout.py:150`: the reviewed Property "Every mark explains
    itself" has a check at two seams: the words in the markup, at the loader-and-page seam the
    Testing Decisions names, and the words on screen, at the layout seam. The spec's Testing
    Decisions dispositions that Property as reviewed; both checks are cheap and the second is what
    found the clipped tooltips, so the disposition is worth amending when this lands.
  - A13 `mx/skills/tracker/demo_tracker.py:440`: the demo tracker gains an L and an XL ticket, so
    every size and every priority is laid out somewhere and the two widest time labels are under the
    no-overlap check.
- [D7] Findings, from `/mx:code-review` over `6268bad..f42427d`, four axes, reports in
  `agent/reviews/6268bad..1ede913/`
  - Fixed in f42427d: the clipped `.asks` and `.ftag` tooltips (correctness 2, standards 1, spec C1);
    the scheme switch blanking every graph (correctness 1, spec C2); the time and priority tooltips
    running off the left of a 900px window (correctness 4); the graph panel sitting below every row
    between 1000 and 1400px (correctness 5, spec C4); the day tints at 3.9-4.2:1 (correctness 6);
    the row number no longer naming the path it copies (spec C3, tests c); a truncated name
    recoverable nowhere (correctness 3) and collapsing to 40px at 640px (standards 15); the graph's
    node names and the absence note's sentence set in mono (standards 4, 5); the two tips restating
    the maps they explain, already drifted (standards 6, tests d4); dead `--c-lav` and `.mono`
    (standards 7, spec B2); `needs_row` writing the row contract a second time (standards 8); the
    queue entry's word written by hand (standards 9, spec B1); a rule attributed to `/mx:tracker`
    that lives in the spec (standards 10); three change-narrating comments (standards 11); the
    graph-ink check no longer tying a status to a token (standards 13); the tautological asks and
    tip expectations (tests F1, F3), the `pri p1` filter that could never match (tests F2, standards
    3), the `?theme=` precondition satisfied by template text (tests F4, spec A2), the anchored page
    asserted to have opened nothing and painted no graph (tests F5, standards 2, spec A2), the
    layout assert stopping at the first width (tests F6), the unlaid-out L, XL and p5 labels (tests
    d4, spec A3), the stamp's three new fields (tests d5), the brief in the search text (tests d7),
    a tracker with no review page at all (tests d8), and the undeclared fixture coupling (tests F8).
  - Declined, with the reason in the assumption it stands on: render-lint's blindness to
    HTML-on-HTML overlap and to clipped text (tests b, spec's no-overlap note) -> D4 and A12;
    "mark" against the glossary (standards 12) -> D3; the review-page absence answering 01's D3
    (standards 14, spec C5) -> D2 and A7; `asks()`'s unreachable branch (standards 9, spec B1) -> A8;
    the schemes not differing in geometry (tests F7) -> the probe now checks that `?theme=` paints
    two different schemes, which is what that leg was insurance for.
  - One report is about something else: the standards axis measured a page in `/tmp` that the tests
    axis had rendered from a mutated tree, and read its crushed name column as where the CSS might
    be heading. It was a mutation, reverted; the committed value is `minmax(0, 1fr)`.
- [D8] Friction
  - The reviewed Property "every mark explains itself on hover" passed a check that read the
    attribute and never a render, and two of the marks this slice adds showed nothing at all. Three
    of the four axes found it independently, by hovering in a browser. The check that now holds it
    took about forty lines, and the same run doubles as the evidence for `?theme=`, the anchor and
    the graph. A reviewed Property about something a browser does wants a browser in the loop, or the
    words "checked by eye" in the closing comment and nothing else.
  - The no-overlap check's own docstring told me the graph was measured on the anchored pages. It was
    not: under render-lint's loop mermaid had not come back, and the rule I had just added to take an
    unrendered graph source out of the layout made that state look exactly like a measured one. The
    check now asserts the graph painted before it trusts the width.
  - The other worker's branch, `ticket/master/render-lint-html-overlap`, was the strongest tool I had
    for the one hazard the orchestrator told me to look at by hand, and it is a `git show` away. What
    made it usable was reading its diff first: run as it stands it floods with false positives on
    this page (D4), and the two-line filter that clears them is the difference between "0 fatal at
    fourteen widths" and an unreadable wall.
  - Two review agents and I all wrote scratch renders into `/tmp` under names general enough to
    collide (`/tmp/demo`, `/tmp/review-demo`), and one report ended up describing a page another
    agent had rendered from a mutated tree. A scratch path per agent would have cost nothing.
  - `board` still cannot render this repo's own board on a dispatch worker host (01's friction), so
    half this ticket's demo is unproducible here and I verified it from a copied tracker in a
    scratch repo instead.
