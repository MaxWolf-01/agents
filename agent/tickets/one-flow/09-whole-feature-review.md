---
status: open
---

# Whole-feature review of one-flow against master

## What to build

The flow's own close-out step, not a proposal: no slice of this feature was reviewed against the whole, and that is where incoherence between slices shows. Run a full `/mx:code-review` of the `one-flow` branch against the repo's integration branch, `master`, with `agent/tickets/one-flow/spec.md` as the spec axis: the fixed point is `master`, so the range is the merge-base with `master` to the branch tip, and the reports land under `agent/reviews/<range>/`. Read the spec's Properties as the reviewed list: every one is disposed **reviewed** and each has an acceptance criterion somewhere in tickets 01 to 08. Where the slices disagree with each other (a skill that still describes what another slice retired, two homes for one rule, a pointer to a file that moved), that is the finding this pass exists for.

Dispose of every finding under the review skill's own rule: fix it on this branch as `Workflow-stage: review` commits, file it as a proposed ticket when it is too large, decline it as an anchored assumption. The plugin installed on the host predates this branch's skills; follow the branch's `code-review` skill as written.

## Acceptance criteria

- [ ] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [ ] `make check` and `make test` pass on the branch after the fixes.
- [ ] No skill, README line or figure on the branch describes a mechanism another slice of this feature retired (the size call at the gate, `dispatch setup`, the implement skill, the standalone message, the per-batch review rule).
- [ ] Demo in the closing comment: the finding index, and the commands that show the reports on disk.
