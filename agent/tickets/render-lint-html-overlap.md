---
status: done
priority: 2
size: S
diff: [7093bf7e44222c4420b26036a2b647c798f2a833..215cc74fac1802a4ecaecf81af236d7b3f135de4]
---

# render-lint sees HTML text colliding

## Brief

render-lint finds text that spills out of its own box, and SVG labels that run into each other. It misses two pieces of HTML text drawn on top of each other, which is how the board prototype's rows broke. Every `/mx:show` page and the board's no-overlap check would catch that failure once render-lint does.

Filed on the user's ruling on board-orients 01's D2 (2026-09-23): that ticket's no-overlap check runs render-lint, which its closing comment found blind to HTML-on-HTML overlap and to text a box clips rather than spills.

## What to build

render-lint reports two visible HTML text elements whose boxes intersect when neither contains the other, as the `overlap` kind it already has for SVG text. It also reports text that a box with `overflow: hidden` cuts off, whether by `text-overflow: ellipsis` or plain clipping, as a separate kind that never fails a run: a truncated title is sometimes the design.

## Acceptance criteria

- [x] A page with two absolutely positioned labels drawn over each other fails with an `overlap` finding naming both texts, and the same page with them apart passes.
- [x] Text inside a parent (a link inside a paragraph, a span inside a button) is not reported as overlapping that parent.
- [x] A clipped title is reported, and the run still exits 0.
- [x] Demo: render-lint run over the board prototype's rejected v3 layout, or a page reproducing its overlapping row marks, with the findings and their crops.

## Comments

render-lint reports HTML text drawn over HTML text as `overlap`, and text a box cuts off as
`clipped`, which never fails a run, on branch `ticket/master/render-lint-html-overlap`, not
merged. A board rendered from any tracker is clean under it, so the no-overlap check this was
cut from can be switched on; before the review rounds it was not, since a board row is a closed
`<details>` whose text Chrome keeps measurable.

**Demo**

    bash agent/show/render-lint-html-overlap/demo.sh

Two runs over one page of board rows, each mark placed at its own offset, then the same marks on
a grid. It ends on the work dir it used (`/tmp/render-lint-html-overlap.XXXX` unless you pass
one):

    == the marks at their own offsets: two rows whose text collides
    $ render-lint agent/show/render-lint-html-overlap/rows.html --crops .../collide
    rows.html: clipped  html        53.6px  'render-lint-html-overlap'
    rows.html: overlap  html                'open | Open questions on a ticket, and the needs-me group they put it into'
    rows.html: overlap  html                'claimed | render-lint sees HTML text colliding, and says what a box cuts off'
    3 findings, 2 fatal

    == the same marks on a grid: the cut-off feature tag, and nothing colliding
    rows.html?fixed: clipped  html        53.6px  'render-lint-html-overlap'
    1 findings, 0 fatal

Open the three crops under `collide/`: each overlap crop shows the two texts printed over each
other, one of them a nine-pixel collision that a page-sized screenshot does not show, and the
clipped crop shows the feature tag ending in an ellipsis. Then open the page itself,
`agent/show/render-lint-html-overlap/rows.html`, and the same page with `?fixed`, which is the
row on a grid; the scheme toggle is top right, and both schemes render.

The board prototype's own rejected v3 layout sits on another branch, so the page reproduces its
colliding row marks rather than being it, which is this criterion's second option.

**I need from you**

- [D1] **render-lint measures glyphs, so a mark painted across a title is still not a finding.**
  A badge whose border or fill is drawn over a title collides visibly while their letters do not
  touch, and nothing is reported; the ticket's words are "two visible HTML text elements whose
  boxes intersect", and measuring text against text is what makes the link-inside-a-paragraph
  criterion hold without a containment rule (A1). Either the limit stands, or seeing a painted
  box over text is a ticket of its own, needing paint order rather than text rects.
- [D2] **The clip pass should stop re-deriving CSS and ask the engine**, filed as
  `render-lint-asks-the-engine` (proposed), on this branch rather than the integration branch,
  since a worker writes only inside its worktree: move it when you land this. Five review rounds
  each found one more rectangle the walk gets wrong, and both of the last two reviewers
  prototyped and measured the alternative, hit-testing at sample points, at ~50ms on the largest
  committed page. It is the single most valuable follow-up either of them named.
- [D3] **`clipped` fires on every deliberate truncation.** Three pages already in the repo each
  report one: a line-clamped paragraph, an ellipsised tag, and a code frame in the house-style
  demo cutting its last comment by 3px, all true. It never fails a run, but it is a line in every
  `/mx:show` lint from now on. Either that nag is the point, or it wants a flag.
- [D4] **Five review rounds on an S ticket, and each found a real fatal-class bug in the few
  lines the round before it added** (five reports under `agent/reviews/`, all of them verified
  against a live Chromium). I stopped on the orchestrator's call, not on a clean round. The two
  findings the last round left are hazards on page shapes nobody in this repo has written, both
  fixed in `11fbb87`; what the pattern says about where this kind of work should stop is yours.

**Details, if you want them**

- [D5] Assumptions
  - A1 `mx/skills/show/render_lint.py:126`: an overlap is measured between text nodes' glyph
    rects rather than their elements' boxes. The ticket says boxes; glyphs are what the brief's
    "drawn on top of each other" means, and they make "text inside a parent is not reported"
    true by construction rather than by a containment exemption (D1).
  - A2 `mx/skills/show/render_lint.py:139`: two texts count as colliding when their glyph rects
    cross by at least half the shorter one's height, and by 2px across. Glyph rects run taller
    than the line advance, so text set at a leading under 1 overlaps its own neighbouring lines
    by about a quarter of their height; the ticket gives no number.
  - A3 `mx/skills/show/render_lint.py:121`: a rect a clip leaves under 4px of is text hidden on
    purpose, and leaves the run entirely rather than being reported as cut off. This is what
    keeps a screen-reader-only label from being a finding on every page that has one.
  - A4 `mx/skills/show/render_lint.py:48`: the kind is named `clipped` and joins `tight` as a
    kind that never fails a run. The ticket asks for the behaviour and not the name.
  - A5 `mx/skills/show/render_lint.py:107`: a box-less element's own `visibility: visible` does
    not win back text its parent hides, so `display: contents; visibility: visible` inside a
    hidden parent is painted and not reported. Round four found it, older than this branch; the
    fix is not one line, and the shape is rare.
  - A6 `mx/skills/show/render_lint.py:214`: the crop screenshot reads the whole page. Older than
    this branch: a finding below the first screen asked for a region outside the viewport, which
    ended the run on a traceback and wrote no crops at all, however many findings came first.
    Fixed here rather than filed, since the demo this ticket owes is crops.
  - A7 `mx/skills/show/test_render_lint.py:54`: the checks drive the command line, one Chromium
    launch each, 21 checks in 28s. The repo has no properties directory and this ticket no spec,
    so there is no Testing Decisions naming a seam; the browser's own measurements can be read
    nowhere else, and the file sits beside the script as the repo's other script tests do.
  - A8 `mx/skills/house-style/SKILL.md:57`: the house style points at `--help` for what
    render-lint measures, where it used to name the kinds; `mx/skills/show/SVG-FIGURES.md:49`
    keeps the enumeration. A review offered both halves of that split and this is the half I
    chose, so one copy of the list stands instead of three.
  - A9 `mx/skills/show/render_lint.py:165`: round one's finding that the two `overlap` kinds
    carry different JSON shapes is declined, premise wrong; both set `by: 0`, and round two
    confirmed it.
- [D6] Findings, from `/mx:code-review` light over five rounds, reports in `agent/reviews/`
  - `7093bf7..097b1ee`, nine findings. Fixed in `d2cc27c`: closed-`<details>` text measured as
    visible, which made every page with a disclosure fail and the board worst of all (1); a clip
    applied from ancestors an absolute box has escaped, which silenced the collision most likely
    to produce it (2); no check for a collapsed container (3); the skip list untrue of the new
    pass (4); no scheme toggle on the demo page (6); the demo running the lint twice per case
    (7); the kinds enumerated in three places (8); `v3` with no antecedent (9). Declined: the
    two overlap kinds' JSON shapes (5) → A9.
  - `097b1ee..d2cc27c`, six findings, all fixed in `ffc431e`: `contentVisibilityAuto` asking
    Chrome a question it had not recomputed, blinding the tool below the fold (1); `display:
    contents` text dropped whole (2); `perspective` and `backdrop-filter` missing from the
    containing-block list (3); the root elements' viewport clip walked past (4); the skip list's
    second half (5); the folded disclosure without its positive counterpart (6); two prose
    findings (7, 8).
  - `d2cc27c..ffc431e`, six findings, all fixed in `0e9a328`: the root clip measured as body's
    own box, which erased every text on a page whose marks are positioned (1); five properties
    that hold an absolute box missing and two claimed that do not (2); `display: contents` with
    `visibility: hidden` called visible (3, and its other half → A5); the viewport check passing
    on its page's collapsed body (4); the docstring's oracle sentence (6).
  - `ffc431e..0e9a328`, six findings, all fixed in `9acfebe`: the viewport clip bounded by the
    height the page asked for before the resize gave it (1); `will-change` matched by substring
    (2); the mirror of (1) on the horizontal axis (3, fixed a round later); the crop crash (4) →
    A6; two prose and test findings (5, 6).
  - `0e9a328..9acfebe`, eight findings, all fixed in `11fbb87`: a root that cannot scroll
    measured as if it could (1); `will-change` matched case-sensitively against a value that
    keeps the author's case, and `offset-path` hinted at but never read (2); the horizontal
    mirror (3); `wants()` dispatching on the shape of its argument (4); a self-contradicting
    comment (5); the oracle sentence again (6); the test helper unable to tell a crash from a
    lint failure (7); two page shapes unpinned and the crop check asserting only a filename (8).
- [D7] Friction
  - The board does not render on a worker host, so the tracker conventions' render after a
    ticket change did not run: `board` reads the tracker from the main checkout, which here is
    the bare repo the worktrees hang off. `board agent/tickets` does not override it either,
    since the assertion fires before the positional is read. Already filed as
    `board-renders-on-worker-hosts`; this is a second sighting, and the override path is worth
    a line in it.
  - Five review rounds took about two hours of wall clock, most of it waiting on reviewers that
    each spent twenty-five minutes doing what the tests now do in 28 seconds: writing a page,
    running the binary at two revisions, and reading the crop. Every round's findings were real,
    and all but two were in code the round before had written. What would have saved the time is
    the suite this ticket now has, written against the live browser from the first commit rather
    than after the first review; the checks that catch these bugs cost 1.4s each.
  - `render_lint.py` is a Python script wrapping a 120-line JavaScript string, so the part that
    holds all the difficulty gets no syntax checking, no formatter and no editor. Every error in
    it surfaced as a wrong finding on a page rather than as an error. A `.js` file beside the
    script, read at startup, would cost one line and give the JS a toolchain.
