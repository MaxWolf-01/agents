# Every merge into the integration branch is `--no-ff`, single-commit branches included

A branch holding one commit still merges `--no-ff`, so GitHub's commit list (flat, date-sorted, no first-parent view) shows its subject twice: the merge, then the commit. `tracker land` finds a merged ticket's range by that merge commit, the one whose second parent is the ticket's tip, and guessing a range for a tip merged without one (`tip^..tip`) would hold only while every branch is one commit. A cleaner GitHub list is not worth a lost landing, and an "always" rule needs no exception.

## Consequences

A tip merged with no merge commit of its own gets no range, since git cannot tell it from a branch that committed nothing. A fast-forwarded repo drops out of the ticket's ranges, and a round fast-forwarded in every repo reads as one that built nothing and never lands. The commit keeps its `Workflow-stage:` trailer and `--first-parent` still shows one line per ticket either way.
