---
status: claimed
blocked-by: [03]
priority: 1
size: M
---

# The workflow writes what the board reads

## Brief

The skills teach the new ticket file: every filed ticket gets a priority, a size, a short name and a brief; a worker's questions go into `## Questions`; an answer is recorded as a `Ruled` line; the `needs-human.md` queues retire and their entries move onto tickets.

Slice of `spec.md`, building on the Decisions under "The ticket file" and "Where the workflow changes".

## What to build

An agent following the skills writes tickets the board can read, with no step left to memory:

- The tracker conventions define `priority`, `size`, the H1 as the short name, `## Brief`, `## Questions` with its `Ruled` line, and needs me; the queue file is gone from them.
- `/mx:to-tickets` and `/mx:grilling` give every ticket they file a priority, a size, a short H1 and a brief.
- `/mx:dispatch` and the worker contract send a worker's questions to the ticket's `## Questions` instead of an "I need from you" list, and have the session relaying the user's answer write the `Ruled` line; a question with no ticket to hang on is filed as a proposed ticket.
- `/mx:orient` and every other skill that names the queue follow.
- The board stops reading `needs-human.md`.
- One pass over this repo's tracker: every `needs-human.md` entry moves onto its ticket's questions or becomes a proposed ticket, and every live ticket gets a priority, a size and a brief.

`claude/CLAUDE.md` and the worker contract carry copies of the same blocks (the repo's `CLAUDE.md` says so); an edit to one is checked against the other.

## Acceptance criteria

- [ ] Property, reviewed: a question on the board always belongs to a ticket.
- [ ] No `needs-human.md` remains in this repo's tracker, and no skill tells an agent to write one.
- [ ] Every live ticket in this repo's tracker carries a priority, a size and a brief.
- [ ] Demo: the diff is the demo; the closing comment lists each migrated queue entry and where it went.
