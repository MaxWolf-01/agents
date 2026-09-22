---
status: proposed
---

# The figure and demo rules get a check against the finished artefact

Cut from the whole-feature review of figures-and-demos (`6c9ce66..5a322f6`). The feature's own Testing Decisions rests the enforcement half of it on one sentence: "The Spec axis checks a spec diff for a listed shape without its figure and a closing comment for a demo whose output has no run behind it". Nothing was built. `mx/skills/code-review/` is untouched by the branch: its Spec brief is the generic four-part brief, and neither it nor `SMELLS.md` mentions a figure, a demo or `/mx:show`'s table. No slice owned it, and the user story it serves (spec, story 16) is the one that says the rule has to apply "against the finished artefact and not only while drafting".

The cost is measured, not hypothetical. The Correctness axis ran `agent/show/figures-and-demos/02-spec-figures/demo` once, independently: the after arm loaded this branch's grilling skill, delivered its round, wrote the spec, committed it, and drew no figure. Ticket 02's closing comment records three watched runs that all drew one; this was a fourth that did not. The rule is rung 3 (read while generating) and washes out, which is what PRINCIPLES.md #1 says it will.

## What to build

The Spec axis gains the check, in `mx/skills/code-review/SKILL.md`'s Spec brief: a decision in a spec diff whose shape hits a figure row of `/mx:show`'s table, with no figure linked and no figure source in the same commit, is a finding; a closing comment whose Demo line carries output with no run behind it, or no Demo line at all where the change hits a demo row, is a finding. The table is the source, so the brief points at it rather than restating the rows.

Whether a grilling round also gets a rung-1 or rung-2 reading of its own is the open part: the Spec axis runs at a landing, on a ticket branch, and a grilling round is never dispatched and never reviewed, so nothing reads a round that skipped its figure. Decide that in the closing comment or file it on.

## Acceptance criteria

- [ ] A spec diff stating a decision of a listed shape with no figure is a Spec-axis finding; one with its figure linked and its source in the commit is not.
- [ ] A closing comment whose Demo line has no run behind it is a Spec-axis finding; one carrying a pasted run is not.
- [ ] The brief points at `/mx:show`'s table for the rows rather than restating them.
- [ ] Demo: the two Spec-axis runs above, against a fixture diff, with the finding and the clean pass side by side.
