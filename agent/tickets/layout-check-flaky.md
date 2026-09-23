---
status: proposed
priority: 3
size: XS
---

# The board's layout check fails under load

## Brief

Cut from two board-orients workers' friction on 2026-09-23 (tickets 14 and 16): `test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme` in `mx/skills/tracker/test_board_layout.py` failed 2 of 4 runs in one checkout and twice in another under a full `make test`, and passes when its file runs alone. The findings were `#toast` escaping by half its width on a `?graph=1` page, and a text box in the graph overlay measured at a negative x. It reproduced on the merge-base, so no slice caused it. A 100-second check that fails when the machine is busy teaches everyone to rerun red, the same shape as `harden-e2e-flaky`.

## Acceptance criteria

- [ ] The check passes in ten consecutive full `make test` runs on a loaded machine, or the cause is named and fixed.
- [ ] A failure names the element it measured and the state the page was in.
