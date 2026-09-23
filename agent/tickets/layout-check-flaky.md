---
status: open
priority: 2
size: S
---

# The board's layout check passes or fails by machine

## Brief

`test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme` in `mx/skills/tracker/test_board_layout.py` runs `render-lint` over the board and fails by machine and moment rather than by code, so it is marked an expected failure (non-strict) until this ticket is done. Either it is made reliable and useful, or it is deleted: the user's test (2026-09-23) is whether the check helps make better-looking pages and figures or only costs time.

What is known:

- On agent@pc it failed 2 of 4 runs in one checkout and twice in another under a full `make test`, passing alone; findings were `#toast` escaping by half its width on a `?graph=1` page, and a text box in the graph overlay at a negative x.
- On zephylux it passed in full runs until about 21:10 UTC on 2026-09-23, then failed every run, alone too, on every commit tried, including ones it had passed on an hour earlier. The finding there was the board's note "Nothing is serving the review pages, so they open as files…" overlapping the controls of the graph overlay (`dependencies`, `feature`, `all`, `window`, `close`, `?`) at 450px. The web fonts were reachable. What changed on the machine is not known; several `diffview --serve` processes were running for other worktrees.

## What to build

Find why the result depends on the machine, and fix that, or conclude the check is not worth its cost. Either way a failure names the element it measured and the state the page was in, and a finding that is a real layout defect (the note drawn over the overlay's controls may be one) is fixed or filed.

## Acceptance criteria

- [ ] The cause is named, with the evidence that shows it.
- [ ] Either the check is reliable (ten consecutive full `make test` runs pass, on agent@pc and zephylux) and its expected-failure mark is removed, or it is deleted with the reason, and the user has ruled on which.
- [ ] A failure message names the element and the page state.
- [ ] Demo: the check's result on the page state that used to fail, before and after.
