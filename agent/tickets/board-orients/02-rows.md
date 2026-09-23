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

- [ ] The no-overlap check from 01 passes and its annotation is gone.
- [ ] Property, reviewed: every mark on a row explains itself on hover in words.
- [ ] Property, reviewed: a ticket's priority, size and kind are read from the ticket file.
- [ ] `test_board.py` covers frontmatter priority and size, the H1 as name, the Brief section and the sort.
- [ ] Demo: the demo tracker's board opened in both schemes, and one real ticket of this repo given priority, size and a brief, on the real board.
