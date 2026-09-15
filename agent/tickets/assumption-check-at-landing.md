---
status: proposed
---

# Warn at landing when a worker made choices but recorded no assumptions

When a worker builds a ticket, the choices it made on its own (a value the ticket did not pin, a name, an interface) are supposed to appear in its closing comment as anchored assumptions (`A1 path:line: what and why`), so the review page can show each one on the line it shaped and the user can rule on it. Ticket 06 tested this with three workers under the same prompt and the same unpinned choice: one wrote the assumption, one mentioned it in prose, one wrote nothing. The prompt alone does not make workers record their choices.

## What to build

At landing, when `dispatch review` renders a ticket's page, it also compares the branch's diff with the closing comment: if the diff plainly contains choices (new constants, new names, new interfaces, changed defaults) and the comment has no `A<n>` bullet, it prints a warning naming the hunks that look like choices. The orchestrator then sends the worker back for its assumptions before the ruling, the way it already sends back a slice that edits a property. Part of this ticket is deciding what "looks like a choice" in a diff: a rule a script can apply, or a small reviewer prompt that names them.

## Acceptance criteria

- [ ] A landing whose diff changes behaviour and whose closing comment has no assumption bullet is reported before the ruling, naming the suspect hunks.
- [ ] A landing with assumption bullets, or a purely mechanical diff (a rename, a version bump), passes silently.
- [ ] Demo in the closing comment: two toy landings, one that trips the check and one that passes.
