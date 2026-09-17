---
status: proposed
---

# `render.py --check`: a committed figure must match its source

Cut from ticket 07's closing comment (one-flow): a committed PNG has no check that it matches the HTML beside it. The worker shipped `mx/assets/one-flow.png` rendered before the last edit to its source and caught it only by rendering the README by hand for the demo.

## What to build

`docs/figures/render.py --check` renders every figure to a temporary file and compares it with the committed PNG beside the source and with the copy under `mx/assets/`, exiting nonzero and naming each stale one. `make check` runs it, so a stale figure fails the release target.

Two renderers, not one: `docs/figures/demo/build.py` shoots the board and review-page screenshots from a live render. The whole-feature review of one-flow found the board shots stale by one ticket, which is the same failure this ticket is for. Whatever `--check` becomes, it covers both. (One-flow's byte-for-byte copy of `render.py` retired with that feature's show directory, `git show a2cfd9f:agent/show/one-flow/render.py`.)

## Acceptance criteria

- [ ] `--check` passes on a tree whose PNGs were just rendered and fails, naming the file, after an edit to any figure's HTML.
- [ ] `make check` includes it; a headless browser absent on the machine makes it skip with a line saying so, not fail.
- [ ] Demo in the closing comment: the two runs above.
