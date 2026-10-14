# Every merge into the integration branch is `--no-ff`, single-commit branches included

A branch holding one commit still merges `--no-ff`, so GitHub's commit list (flat, date-sorted, no first-parent view) shows its subject twice: the merge, then the commit. `tracker land` finds a merged ticket's range by that merge commit, the one whose second parent is the ticket's tip, and guessing a range for a tip merged without one (`tip^..tip`) would hold only while every branch is one commit. A cleaner GitHub list is not worth a lost landing, and an "always" rule needs no exception.

## Consequences

A ticket branch is never fast-forwarded, because the tracker sees a ticket's work land only through the merge commit that brought it in. A fast-forward leaves no merge commit, and git cannot tell a fast-forwarded branch from one that committed nothing. So:

- the fast-forwarded repo records no commit range for the ticket;
- a ticket fast-forwarded in every one of its repos looks as if it built nothing, and is never marked `done`.

The git history itself loses nothing: the commits keep their `Workflow-stage:` trailers, and `git log --first-parent` still shows one line per ticket.
