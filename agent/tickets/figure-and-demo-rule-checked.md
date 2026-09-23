---
status: proposed
---

# A spec diff and a landing get read for the figure and the demo they owe

Cut from the whole-feature review of figures-and-demos (`6c9ce66..5a322f6`). The feature's Testing Decisions rests its enforcement on one sentence: "The Spec axis checks a spec diff for a listed shape without its figure and a closing comment for a demo whose output has no run behind it". The figure half was never built. `mx/skills/code-review/` is untouched by the branch: its Spec brief is the generic four-part brief, and neither it nor `SMELLS.md` mentions a figure, a demo or `/mx:show`'s table. No slice owned it, and the user story it serves (spec, story 16) is the one that says the rule has to apply "against the finished artefact and not only while drafting".

The cost was measured. The Correctness axis ran `agent/show/figures-and-demos/02-spec-figures/demo` once, independently: the after arm loaded this branch's grilling skill, delivered its round, wrote the spec, committed it, and drew no figure. Ticket 02's closing comment records three watched runs that all drew one; this was a fourth that did not, and a fifth during the review drew one again. The rule is rung 3, read while generating, and washes out, which is what PRINCIPLES.md #1 says it will.

## What to build

The Spec axis gains the figure check, in `mx/skills/code-review/SKILL.md`'s Spec brief: a decision in a spec diff whose shape hits a figure row of `/mx:show`'s table, with no figure linked and no figure source in the same commit, is a finding. The table is the source, so the brief points at it rather than restating the rows.

The demo half already has a home at the landing, in `/mx:dispatch`'s review bullet ("A demo that is missing, or that the worker's own run did not carry, goes back to the worker before the ruling"), which is rung 2 and reads the closing comment the Spec axis never sees. What the landing read cannot do is tell a ticket whose Demo line says the diff is the demo from one that lost its demo, which `dispatch --help` now says out loud. Decide whether that earns a second reading in the Spec axis or a fifth case in the landing's own driver, and say which in the closing comment.

Whether a grilling round also gets a reading of its own is the other open part: the Spec axis runs at a landing, on a ticket branch, and a grilling round is never dispatched and never reviewed, so nothing reads a round that skipped its figure.

## Acceptance criteria

- [ ] A spec diff stating a decision of a listed shape with no figure is a Spec-axis finding; one with its figure linked and its source in the commit is not.
- [ ] The brief points at `/mx:show`'s table for the rows rather than restating them.
- [ ] The closing comment settles where the missing-demo reading lives, and whether a grilling round gets one.
- [ ] Demo: `agent/show/figure-and-demo-rule-checked/demo`, executable, no arguments: the Spec axis run against a fixture spec diff with and without its figure, the finding and the clean pass side by side.
