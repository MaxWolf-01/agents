---
status: open
blocked-by: [07, 08, 09, 11]
priority: 2
size: S
---

# Whole-feature review of board-orients

## Brief

A full four-axis review of the whole board-orients feature against master, with the spec as the Spec axis. No slice was reviewed against the others, and incoherence between slices shows only here. It runs on top of 07, 08, 09 and 11 before you have ruled on them, so it is done by the time you have.

The flow's own close-out step, not a proposal.

## What to build

Run `/mx:code-review` over the feature: the fixed point is `master`, the range the merge-base with `master` to this branch's tip, and `agent/tickets/board-orients/spec.md` is the Spec axis. Read `mx/skills/code-review/SKILL.md` from this tree. The Spec reviewer checks every reviewed Property against the whole feature.

What this pass exists for: slices that disagree with each other, two homes for one rule, a pointer to a thing that moved, and a skill still describing what another slice retired. The needs-human queue, the "needs my review" group, and the questions in a closing comment are the retired things to hunt for.

Dispose of every finding under the review skill's rule: fix it on this branch in `Workflow-stage: review` commits, file it as a proposed ticket when it is too large, or decline it as an anchored assumption. A finding that would rewrite a spec Decision or Property is not yours to make: put it under `## Questions`.

## Acceptance criteria

- [ ] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [ ] `make check` and `make test` pass on the branch after the fixes.
- [ ] No skill, README line, figure, glossary entry or spec line describes the needs-human queue, the "needs my review" group, or a worker's calls in its closing comment as current.
- [ ] Demo: the diff is the demo; the closing comment carries the finding index and the command that lists the reports.
