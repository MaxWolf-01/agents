---
status: proposed
priority: 3
size: XS
---

# The SVG guide and the README's figure set disagree; one of them is wrong

## Brief

The SVG guide rules out three things every committed figure does. One of the two is wrong, and the way to tell is looking at the renders rather than the text.

Cut from ticket 05 of figures-and-demos (its D3, 2026-09-18). `/mx:show`'s `SVG-FIGURES.md` rules out a tracked all-caps eyebrow, middle dots inside labels, and more than two `alt` regions in a sequence diagram; every figure under `docs/figures/` has all three, and the seventh, drawn to match its siblings, broke the guide the same way. A guide the landed set contradicts teaches every new figure the wrong thing, or the set does.

## What to build

Decide which is right, by looking at the renders rather than the text: either the guide gains the exceptions the set has settled on (and says why they read well), or the set is redrawn to the guide, one commit per figure, `render.py` regenerating the PNGs under `mx/assets/`.

## Acceptance criteria

- [ ] The guide and every figure under `docs/figures/` agree on the three points; the commit says which side moved and why.
- [ ] Demo: `agent/show/svg-guide-vs-figure-set/demo`, executable, no arguments: the figures rendered before and after, side by side, opened.
