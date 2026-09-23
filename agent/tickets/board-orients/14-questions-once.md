---
status: open
blocked-by: [13]
priority: 2
size: XS
---

# An opened row shows its questions once

## Brief

An opened row lists its questions twice: under the row, with a headline and a copy button each, and again in the questions block, with their detail. While the row is open, the list under it goes, and the questions block carries each question's copy button beside its detail.

Ruled by the user on 2026-09-23 (D77, "once"), from the orchestrator's before/after of an opened row. It waits on 13 only because both edit `board.py`.

## What to build

When a row is open, the question list under its summary is hidden, and the questions block shows a copy button on each open question, copying what the row's button copied. A folded row keeps its list as it is. The row's "copy all" moves with the list.

## Acceptance criteria

- [ ] An opened row shows each open question once, with its detail and a copy button that shows what it copies.
- [ ] A folded row is unchanged.
- [ ] Demo: an opened row before and after, with where-to-look notes.
