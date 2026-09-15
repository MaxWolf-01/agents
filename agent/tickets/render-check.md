---
status: proposed
---

# `render.py --check`: a committed figure must match its source

Cut from ticket 07's closing comment (one-flow): a committed PNG has no check that it matches the HTML beside it. The worker shipped `mx/assets/one-flow.png` rendered before the last edit to its source and caught it only by rendering the README by hand for the demo.

## What to build

`agent/show/mx-readme-figures/render.py --check` renders every figure to a temporary file and compares it with the committed PNG beside the source and with the copy under `mx/assets/`, exiting nonzero and naming each stale one. `make check` runs it, so a stale figure fails the release target.

Two renderers, not one: `agent/show/one-flow/render.py` is a byte-for-byte copy of this one, kept so the feature's before-and-after figure has a renderer beside it (ticket 07, A12), and `agent/show/mx-readme-figures/demo/build.py` shoots the board and review-page screenshots from a live render. The whole-feature review of one-flow found the board shots stale by one ticket, which is the same failure this ticket is for. Whatever `--check` becomes, it covers all three, and where that means one script with three call sites rather than a copy, say so in the closing comment.

## Acceptance criteria

- [ ] `--check` passes on a tree whose PNGs were just rendered and fails, naming the file, after an edit to any figure's HTML.
- [ ] `make check` includes it; a headless browser absent on the machine makes it skip with a line saying so, not fail.
- [ ] Demo in the closing comment: the two runs above.

## Comments

The figures-and-demos feature (ticket 04, 2026-09-16) moves the README figure pipeline out of `agent/show/mx-readme-figures/` to `docs/figures/` and deletes `agent/show/one-flow/`, so there is one renderer, at the new path; `--check` covers `docs/figures/render.py` and `docs/figures/demo/build.py`.
