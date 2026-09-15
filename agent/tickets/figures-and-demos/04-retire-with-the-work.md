---
status: proposed
---

# Retiring a ticket or feature retires its show directory and research notes

Slice of `spec.md`, building on Solution (you, r5), Decisions "Retired with the work, promoted deliberately" (you, r5: retire show and research at close; agent's call, r5: the `~/logs` interim), "Promotion is the agent's call, visible in the diff" (you, r5).

## What to build

A session retiring a feature removes its show directory in the same commit as its ticket directory; retiring a standalone ticket takes its show directory with it; a loose branch's show directory goes when the branch merges. The research notes the retired tickets cite leave the tree in the same step: untracked, they move to `~/logs/agent-research/<repo>/` rather than being deleted, until [One tracker for all of a user's repos](../one-tracker-per-user.md) rules on committing them. What a README or a PR needs is copied there in that commit, on the agent's judgment, and kept current where it lands. The tracker's retire step says all of this once; orient's artefact table rows for Show and Research agree with it in a phrase and point at it.

## Acceptance criteria

- [ ] The tracker's Retire section names the show directory and the research notes with their destinations, for a feature, a standalone ticket and a loose branch.
- [ ] Orient's artefact table gives Show and Research the retire lifecycle in a phrase each; the rule has one home.
- [ ] Property, reviewed: no show directory and no research note outlives the ticket or feature it served; a figure a README or PR needs is copied there and kept current there.
- [ ] Demo: `agent/show/figures-and-demos/04-retire-with-the-work/demo`, executable, no arguments: a toy repo with one shipped feature, the retire commands run, the tree before and after, and the research note's new path printed.
