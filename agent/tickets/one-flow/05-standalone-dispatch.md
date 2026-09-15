---
status: claimed
blocked-by: [02]
---

# A standalone ticket is dispatched like a feature's

## What to build

A ticket with no spec, `agent/tickets/<slug>.md`, is worked by the same dispatch scripts as a feature's tickets: same host selection from the repo's setup, same pane, worklog, stop and resume, same fetch and review. What differs is only the branching: its ticket branch cuts from and merges into the repo's integration branch, there is no feature worktree and no feature branch, and its needs-human entries live in `agent/tickets/needs-human.md`. The host setup (the bare repo on the host, the host record) happens once per repo and is reused by every feature and every standalone ticket; a session that files a standalone ticket dispatches it from the checkout it is in, claiming by committing the status flip on the integration branch, and a collision between two sessions is an ordinary one-line conflict.

The scripts' `--help` and the dispatch skill describe the standalone case where they describe the feature case, without a second set of commands: a standalone ticket is the feature case with the integration branch as the feature branch and the ticket root as the feature directory.

A standalone ticket built while `proposed` has no feature branch to wait on, so its own ticket branch is the container: the review page renders from the fetched branch, the branch merges into the integration branch only when the user accepts on that page, and a rejection deletes the ticket and the branch with the integration branch never having seen it. Ticket 02 landed the claim rule and the reject path for features; this ticket states the standalone form of both.

## Acceptance criteria

- [ ] From a checkout on the integration branch, `dispatch setup`, `claim`, `prompt`, `ctl spawn`, `wait`, `fetch` and `review` work on `agent/tickets/<slug>.md` with no feature directory, and the review page lands at `agent/diffviews/<slug>.html` where the board already looks for it.
- [ ] The host setup is recorded once per repo and reused; a second feature or standalone ticket needs no new setup.
- [ ] The dispatch skill's setup and tick sections cover the standalone case in the same sentences as the feature case.
- [ ] Property, reviewed: one worker contract; a worker's obligations do not depend on what spawned it or where it runs.
- [ ] Property, reviewed: ticketed work always appears on the board.
- [ ] Demo in the closing comment: a toy standalone ticket dispatched end to end on the local host, the pane's log, the fetched branch, the review page, the board.
