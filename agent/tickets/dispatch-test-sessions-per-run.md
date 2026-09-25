---
status: proposed
priority: 3
size: XS
---

# Dispatch test sessions named per run

## Brief

The dispatch checks spawn real tmux sessions named after the toy repo and the ticket's slug, so a session an earlier crashed run left behind is reused by the next: a check that stages a demo passed with no demo staged at all, and two runs hung typing their worker into a session whose worktree was gone. The checks now kill such sessions on either side of themselves, which tidies the class up without ending it; a session name that carries the run makes the collision impossible.

Cut from `workers-report-orchestrator-writes-tickets`'s closing comment (its D6 and D9 friction), filed at `ticket-file-contract`'s close-out on the user's go.

## Acceptance criteria

- [ ] Two runs of `mx/skills/dispatch/test_dispatch.py` at once, and a run after one killed mid-way, pass without either touching the other's sessions, and nothing in the checks kills a session it did not start.

## Comments
