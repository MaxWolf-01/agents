---
status: claimed
blocked-by: [02]
priority: 1
size: M
---

# Ticket questions and the needs-me group

## Brief

Every question lives on its ticket and shows under it in one needs me group, copyable one at a time or all at once; an answer recorded under a question clears it from the board.

Slice of `spec.md`, building on the Decisions on `## Questions`, a build in review read from its ticket branch, the groups, questions under their ticket, and copy buttons.

## What to build

The board reads a ticket's `## Questions`: each item tagged `[Dn]` with a bold headline, open until a `Ruled <date>:` line sits under it. A build in review is read from its ticket branch (`ticket/<feature>/<NN-slug>`, or `ticket/<integration branch>/<slug>` for a standalone ticket), where its questions and closing comment are until the merge. One group, needs me, holds every ticket that is not done and is a build in review, has an open question, or is a design or prototype decision at p1 or p2 that nobody has claimed; the separate "needs my review" group goes. Under each needs-me row its open questions show as tag and headline, each with a copy button that shows what it copies; a ticket's "copy all" and the group's "copy all" copy every open question with its tag and ticket path, for pasting into an editor.

The board keeps reading the `needs-human.md` queues until ticket 10 migrates them.

## Acceptance criteria

- [ ] The needs-me and ruled-question checks from 01 pass and their annotations are gone.
- [ ] Property, reviewed: a question on the board always belongs to a ticket.
- [ ] Property, reviewed: a copy button shows what it copies.
- [ ] Property, reviewed: a ticket's questions are read from the ticket file.
- [ ] Demo: the demo tracker's needs me group; a group "copy all" pasted into a file; a question cleared by adding a `Ruled` line.
