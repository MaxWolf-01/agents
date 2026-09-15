---
status: done
diff: [3479b32a6f9e1fd4e35752d0d4617f1aacaa5243..cfe3384cf0cb77147be01f1020d9ebd5007f6e13]
---

# A proposed ticket is buildable; the user rules on its artifact

## What to build

The tracker and dispatch skills change what `proposed` means: not yet ruled by the user, and on the build frontier. A proposed ticket is claimed and built like an open one; the user rules on the review page and the demo the build produced, and need not read the ticket's text unless the artifact raises a question (they may whenever they want to). Accepting lands the ticket (status `done`, merged); rejecting deletes the ticket file and drops its branch, the commit message carrying the reason. `open` remains the state of a ruled ticket not yet built. The board's rendering of proposed tickets stays, with the review page link it already shows when one exists.

Dispatch's `claim` accepts a proposed ticket. Dispatch's sort of a worker's punts still files proposals, and now dispatches them within the feature's loop, one level deep: a proposal filed by the speculative build of another proposal waits for the user's ruling on the first, so a host left alone cannot chain proposals and the loop still reaches frontier-empty. At frontier-empty, before the debrief, dispatch runs a full code-review of the feature branch against the repo's integration branch with the spec as the spec axis, and one worker fixes what it finds, under the same aggregation rule as any review.

The tracker skill's state section, its claim rule and its retire rule say all of this; the dispatch skill's tick says it where the tick reads claims, sorts punts and ends.

## Acceptance criteria

- [x] `dispatch claim` on a proposed ticket flips it to claimed and commits, and the tracker's state section describes `proposed` as buildable and ruled on the artifact.
- [x] Accept and reject are each one described step: accept lands, reject deletes ticket and branch with the reason in the commit.
- [x] A proposal filed from a proposal's own build is not dispatched until the user rules on the first; the dispatch skill states the bound where it sorts punts.
- [x] The whole-feature review runs at frontier-empty, before the debrief, and its fixes land through one worker.
- [x] Property, reviewed: nothing built on a guess reaches the integration branch; speculation lives on the feature branch and merges only after the user's approval.
- [x] Property, reviewed: the unit of the flow stays one ticket, one worker, one branch, one review page.
- [x] Assumption to carry, anchored: the one-level bound on speculation is the agent's call from the spec, not the user's ruling.
- [x] Demo in the closing comment: a driven transcript of `dispatch claim` on a proposed ticket in a scratch feature, and the board rendered with that ticket claimed.

## Comments

### Closing comment

`proposed` now means "not yet ruled", not "not yet worked". The tracker's state section says what the status is and how a ruling resolves it, dispatch's tick dispatches its own proposals and bounds the chain at one level, its close-out runs the whole-feature review before the debrief, and `dispatch claim` takes a proposed ticket.

**Demo.** A scratch feature, a proposal cut from ticket 01's closing comment, claimed:

```
$ grep status: agent/tickets/lamp-ui/02-warm-preset.md
status: proposed
$ dispatch claim 02-warm-preset
+ git commit -q -m lamp-ui: claim 02-warm-preset -- agent/tickets/lamp-ui/02-warm-preset.md
local host: lamp-ui is already here
$ grep status: agent/tickets/lamp-ui/02-warm-preset.md
status: claimed
$ git log --oneline -1
a63fa7a lamp-ui: claim 02-warm-preset
$ dispatch claim 02-warm-preset   # again
dispatch: 02-warm-preset is claimed: only an open or proposed ticket is claimed
```

The board rendered from that tracker draws the ticket in the wave lanes with the amber `⟳ claimed` badge, the feature header reading `spec draft · 1/2 done · 1 claimed`; before the claim it sat in the `proposed — awaiting ruling` lane. To re-drive both, from any checkout of this branch:

```
D=/tmp/claim-demo; rm -rf $D; mkdir -p $D/agent/tickets/lamp-ui; cd $D
git init -q -b main . && git config user.email d@e && git config user.name demo
printf -- '---\nstatus: draft\n---\n\n# Lamp UI\n' > agent/tickets/lamp-ui/spec.md
printf -- '---\nstatus: done\n---\n\n# The brightness slider\n' > agent/tickets/lamp-ui/01-brightness-slider.md
printf -- '---\nstatus: proposed\n---\n\n# A warm preset beside the slider\n\nCut from 01 closing comment.\n' > agent/tickets/lamp-ui/02-warm-preset.md
git add -A && git commit -qm "lamp-ui: tickets" && git checkout -q -b lamp-ui
# superseded 2026-09-15: ticket 05 retired the per-feature keys and ticket 08 every recorded
# host, so nothing reads these; a spawn names its host with `dispatch ctl --host <host>`.
git config dispatch.lamp-ui.host local && git config dispatch.lamp-ui.scratch /tmp/ignored
<mx>/skills/dispatch/dispatch claim 02-warm-preset
uv run <mx>/skills/tracker/board.py agent/tickets --no-watch --no-open
```

**Action items**

- The README's ticket-state figure and its alt text (`mx/README.md:15`, `:69`) and the figure's source `agent/show/mx-readme-figures/ticket-state.html` still say `claim` refuses a proposed ticket, and orient's ticket table says `proposed` is off the frontier. Ticket 07 owns that surface; the one README sentence that stated the rule outright (`mx/README.md:96`) is fixed here.
- Ticket 05 (standalone dispatch) merges a ticket branch into the repo's integration branch. `claim`'s refusal was the only executable guard on "nothing built on a guess reaches the integration branch"; for a feature the feature branch is the container, for a standalone proposal there is none, so 05 needs its own answer for where a standalone proposal's build waits.

**Assumptions**

- A1 `mx/skills/dispatch/SKILL.md:41`: the one-level bound is the agent's call from the spec's "Speculation is one level deep", not the user's ruling, and so is how it is held: the held proposal's own provenance line names the proposal it came from, plus a queue entry for that first ruling. Three reviewers proposed `blocked-by` on the parent instead; it does not fit, because an edge clears when the parent is `done` and a worker writes `done` at the end of its build, before any ruling, which would release the next level on a host nobody is watching.
- A2 `mx/skills/dispatch/SKILL.md:72`: the whole-feature review runs as a filed ticket. The spec says "fixed by one worker before the debrief" and does not say how the worker is spawned; `dispatch ctl spawn` cuts its branch from a ticket file, and a ticket also gives the pass a review page, which keeps the unit of the flow intact.
- A3 `mx/skills/dispatch/SKILL.md:72`: that ticket is filed `open`, not `proposed`, though an agent files it. It is the flow's own step rather than a proposal about what to build, so there is nothing in it for the user to rule on.
- A4 `mx/skills/tracker/MARKDOWN.md:26`: `git revert -m 1` of the merge is how a rejected proposal's build leaves a feature branch that already carries it. The spec requires only that the integration branch stay clean; reverting on the feature branch is the cheapest way to get there without holding every proposal's branch unmerged until the user returns.
- A5 `mx/skills/tracker/MARKDOWN.md:26`: no frontmatter key marks "built, awaiting ruling"; the needs-human entry carries it. A key would have to reach the board, and this ticket keeps the board's rendering as it is.
- A6 `mx/skills/tracker/board.py:555`: the board still lanes every proposal outside the wave lanes and never derives `blocked` for one, so an unblocked proposal that is claimable now draws beside one that is gated. The ticket keeps the board's rendering; worth a ruling on whether the lane should now split.

**Findings** (`/mx:code-review` since 3479b32, four axes)

- Reject could not un-ship what it rejects (Correctness, Standards, Spec) → fixed, eec9aa9.
- A built-but-unruled proposal had no reading (Correctness, Tests) → fixed as a queue entry, eec9aa9; the frontmatter-key form declined, A5.
- "Held for a ruling" was invisible to a restarted orchestrator (Correctness, Standards) → fixed, eec9aa9; the `blocked-by` form declined, A1.
- The supersede sweep skipped `CONTEXT.md` (Standards) → fixed, eec9aa9.
- The close-out still said rulings flip tickets, and left the harden sort's proposals unhandled under the new frontier (Spec) → fixed, eec9aa9.
- Coined "build frontier"/"ship frontier" next to one defined **Frontier** (Standards) → fixed, eec9aa9.
- Sprawl in the close-out paragraph (Standards) → fixed as a numbered sequence, eec9aa9.
- The test's oracle line named a frontier rule no assertion pins (Standards, Tests) → fixed, eec9aa9.
- The board draws proposals by the retired rule, and the fixture has no unblocked proposal (Correctness, Tests) → declined, A6.
- The whole-feature review ticket is an agent's filing marked `open` (Standards) → declined, A2 and A3.
- `dispatch` has no test: repo practice, every Python script in `mx/` has a sibling test and no shell script does (Tests) → no action.

**Friction**

- The Spec reviewer reported writing `agent/research/code-review-spec.md` and the file never existed; its findings survived only because the return summary carried them. A reviewer that ends holding its report is the failure the on-disk delivery rule exists for, and nothing checks the file is there.
- The tracker's supersede rule names `CONTEXT.md` and the tickets as the sweep, and I missed it on the first pass: the rule is prose in a skill the implementing worker has no reason to open. A ticket that redefines a glossary term could carry the sweep in its acceptance criteria, or the criteria could name the term.
