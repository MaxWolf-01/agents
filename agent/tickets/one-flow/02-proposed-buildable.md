---
status: claimed
---

# A proposed ticket is buildable; the user rules on its artifact

## What to build

The tracker and dispatch skills change what `proposed` means: not yet ruled by the user, and on the build frontier. A proposed ticket is claimed and built like an open one; the user rules on the review page and the demo the build produced, and need not read the ticket's text unless the artifact raises a question (they may whenever they want to). Accepting lands the ticket (status `done`, merged); rejecting deletes the ticket file and drops its branch, the commit message carrying the reason. `open` remains the state of a ruled ticket not yet built. The board's rendering of proposed tickets stays, with the review page link it already shows when one exists.

Dispatch's `claim` accepts a proposed ticket. Dispatch's sort of a worker's punts still files proposals, and now dispatches them within the feature's loop, one level deep: a proposal filed by the speculative build of another proposal waits for the user's ruling on the first, so a host left alone cannot chain proposals and the loop still reaches frontier-empty. At frontier-empty, before the debrief, dispatch runs a full code-review of the feature branch against the repo's integration branch with the spec as the spec axis, and one worker fixes what it finds, under the same aggregation rule as any review.

The tracker skill's state section, its claim rule and its retire rule say all of this; the dispatch skill's tick says it where the tick reads claims, sorts punts and ends.

## Acceptance criteria

- [ ] `dispatch claim` on a proposed ticket flips it to claimed and commits, and the tracker's state section describes `proposed` as buildable and ruled on the artifact.
- [ ] Accept and reject are each one described step: accept lands, reject deletes ticket and branch with the reason in the commit.
- [ ] A proposal filed from a proposal's own build is not dispatched until the user rules on the first; the dispatch skill states the bound where it sorts punts.
- [ ] The whole-feature review runs at frontier-empty, before the debrief, and its fixes land through one worker.
- [ ] Property, reviewed: nothing built on a guess reaches the integration branch; speculation lives on the feature branch and merges only after the user's approval.
- [ ] Property, reviewed: the unit of the flow stays one ticket, one worker, one branch, one review page.
- [ ] Assumption to carry, anchored: the one-level bound on speculation is the agent's call from the spec, not the user's ruling.
- [ ] Demo in the closing comment: a driven transcript of `dispatch claim` on a proposed ticket in a scratch feature, and the board rendered with that ticket claimed.
