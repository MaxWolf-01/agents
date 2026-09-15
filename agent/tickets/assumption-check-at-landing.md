---
status: proposed
---

# A landing checks that a diff with judgment in it carries anchored assumptions

Cut from ticket 06's closing comment (one-flow): three toy workers given the same worker prompt and the same unpinned choice recorded it three ways, an anchored `A1` bullet, prose under a tag, and nothing at all, while the landing shape reproduced every time. Prose in the contract is doing all the work on the assumption discipline; the enforceable rung is the landing.

## What to build

`dispatch review`, which already projects a ticket's assumptions onto its review page, reads the ticket's closing comment and the branch's diff, and reports a ticket whose diff plainly carries choices (a new value, a new interface, a rename) but whose comment has no anchored bullet. The orchestrator sees it on the tick and sends the worker back for its assumptions before the merge, the way a property edit already goes back. What counts as "judgment in the diff" needs a rule a script can apply, or a reviewer axis that names it; deciding which is part of this ticket.

## Acceptance criteria

- [ ] A landing whose diff changes behaviour and whose closing comment has no `A<n>` anchor is reported before the merge, and the report names the hunks that look like choices.
- [ ] A landing with anchors, or a purely mechanical diff, passes silently.
- [ ] Demo in the closing comment: two toy landings, one that trips it and one that passes.
