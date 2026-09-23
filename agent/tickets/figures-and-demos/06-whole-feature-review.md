---
status: claimed
---

# Whole-feature review of figures-and-demos against master

## What to build

The flow's own close-out step, not a proposal: no slice of this feature was reviewed against the whole, and that is where incoherence between slices shows. Run a full `/mx:code-review` of the `figures-and-demos` branch against the repo's integration branch, `master`, with `agent/tickets/figures-and-demos/spec.md` as the spec axis: the fixed point is `master`, so the range is the merge-base with `master` to the branch tip, and the reports land under `agent/reviews/<range>/`. The spec disposes every Property as **reviewed**; read them as the reviewed list and check each holds on the branch. Where the slices disagree with each other (a skill that still describes what another slice retired, two homes for one rule, a pointer to a file that moved), that is the finding this pass exists for.

The branch took master in after ticket 05 (the house style, render-lint, the board's served review links); `mx/skills/show/SKILL.md` was resolved by hand in that merge and is worth a second read against both parents.

Dispose of every finding under the review skill's own rule: fix it on this branch as `Workflow-stage: review` commits, file it as a proposed ticket when it is too large, decline it as an anchored assumption. A finding that rewrites a spec Decision or Property is not yours to make: file it as a needs-human entry in `agent/tickets/figures-and-demos/needs-human.md`. The plugin installed on the host predates this branch's skills; follow the branch's `code-review` skill as written.

## Acceptance criteria

- [ ] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [ ] `make check` and `make test` pass on the branch after the fixes.
- [ ] No skill, README line, figure or spec line on the branch describes a mechanism another slice of this feature retired (show's "Heavy artifacts fork" rule, the worker contract's "expected transcript", a promotion that copies rather than moves, the `agent/show/mx-readme-figures/` pipeline, the `landing.mmd`/`landing.svg` pair).
- [ ] Demo: the diff is the demo; the closing comment carries the finding index and the commands that list the reports on disk.
