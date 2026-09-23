---
status: proposed
priority: 2
size: M
blocked-by: [02]
---

# A spec renders into its spec page, figures inside and the round's changes marked

## Brief

A spec renders into its own page: its figures shown in place, its provenance marks as tags, and every block the round changed marked where it sits. It replaces diffview for specs.

Slice of `spec.md`, building on its Decisions under The spec page (the spec rendered, a link into the feature's show directory is a figure, it replaces diffview for specs, in this feature as its own slice) and Where it lives (`spec.html` beside `spec.md`, untracked), and on its Floors.

## What to build

A command that takes a feature's `spec.md` and a base commit and writes the spec page beside it: the spec in the house style with a contents list, its provenance marks as small tags whether written bare or in code spans, each figure the spec links shown in place with a button to open it in its own tab, and every block that changed since the base marked in place: new and edited blocks visibly, removed ones reachable but out of the way, an edited block's word diff one click away. The same renderer as the session page, so both pages share their styling and their keys; `d`/`D` jump between changes. The spec page's path is untracked, as the board's is.

## Acceptance criteria

- [ ] The spec renderer's property from 01 passes, its expected failure lifted.
- [ ] The prototype at `agent/prototypes/session-page/` is the quality floor: match it or consciously beat it; its incidental slop is not the target; name deviations in the closing comment.
- [ ] A move either page shares with diffview is on diffview's key (spec, Properties).
- [ ] `render-lint` reports nothing fatal in either scheme at the default width and at 900px.
- [ ] Demo: this feature's own spec rendered against `185d279`, the page opened on its first changed block.
