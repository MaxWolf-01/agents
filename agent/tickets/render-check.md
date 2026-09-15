---
status: proposed
---

# `render.py --check`: a committed figure must match its source

Cut from ticket 07's closing comment (one-flow): a committed PNG has no check that it matches the HTML beside it. The worker shipped `mx/assets/one-flow.png` rendered before the last edit to its source and caught it only by rendering the README by hand for the demo.

## What to build

`agent/show/mx-readme-figures/render.py --check` renders every figure to a temporary file and compares it with the committed PNG beside the source and with the copy under `mx/assets/`, exiting nonzero and naming each stale one. `make check` runs it, so a stale figure fails the release target.

## Acceptance criteria

- [ ] `--check` passes on a tree whose PNGs were just rendered and fails, naming the file, after an edit to any figure's HTML.
- [ ] `make check` includes it; a headless browser absent on the machine makes it skip with a line saying so, not fail.
- [ ] Demo in the closing comment: the two runs above.
