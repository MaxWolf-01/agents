---
status: open
blocked-by: [13, retro-semi-automated]
priority: 2
size: S
---

# The debrief is a ticket

## Brief

When a feature's frontier empties, the orchestrator files a proposed `debrief` ticket in the feature, instead of reporting the debrief in chat. It sits in the needs-me group with its calls under it and retires with the feature. It also names the feature's sessions and commit range, so a retrospective over them has a place to land.

Ruled by the user on 2026-09-23 (D79, "a ticket"). The user added that the debrief can have subagents scan the feature's sessions, commit history and diffs for patterns, roadblocks, and bad workflow or tooling. It waits on 13 so this feature's own close-out is the first to use it.

## What to build

`/mx:dispatch`'s close-out step 4 files `NN-debrief.md` in the feature, `proposed`: its brief says what the feature delivered, and its body holds the commits that fixed, the proposed tickets by number, and what was left with its reason. Every call only the user can make goes under its `## Questions`. The ticket lists the feature's sessions, read from the `Session:` trailers on the feature's commits, and its commit range, as the input a retrospective reads. The tracker conventions name the debrief ticket where they describe close-out. `/mx:orient` follows.

The retrospective itself is `retro-semi-automated`: this ticket gives it an input per feature and a home for its findings, and builds no scan of its own.

## Acceptance criteria

- [ ] `/mx:dispatch`'s close-out files a debrief ticket rather than a chat report, and nothing in the skills says the debrief goes to chat.
- [ ] The debrief ticket carries the feature's sessions and commit range.
- [ ] Demo: the skill text before and after, and board-orients' own debrief ticket as the first one written this way.

## Comments

**2026-09-23** The user ruled (D108) that the retro is a sub-step of the debrief, designed together with this ticket in `retro-semi-automated`'s grilling, so this build waits on that grilling.
