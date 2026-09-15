---
status: claimed
blocked-by: [04, 05]
---

# The worker's whole contract lives in the worker prompt; implement is deleted

## What to build

The implement skill's process moves into the worker prompt, the file the dispatch runner appends to every worker's system prompt in place of the user CLAUDE.md, and the implement skill directory is deleted. A worker then starts with its whole contract in context and no skill to load. The contract: read the ticket and its spec; read before writing (the files changed, their callers, the tests covering them); the expected failures naming the ticket in the properties directory are the oracle, made to hold then deleted; typecheck and single test files as you go, the full suite once at the end; the blast radius is the worktree and a missing system dependency is a blocker to report, never to solve; a decision made alone is an assumption, recorded with an anchored id; inherited framing is an assumption too; run the review (light without a spec, full with one) and aggregate its reports per ticket 04, with the finding index; close into the ticket's closing comment in the landing shape the spec's Decisions define, so the orchestrator relays it unchanged: one outcome line; the demo, as steps a stranger can run (the command, the path, the URL, what to look for), never performed by the worker, since on a host it can open nothing for the user; the orchestrating session performs them; "I need from you", the calls only the user can make, numbered and tagged `[Dn]`; "Details, if you want them", tagged in the same numbering: the assumptions block, the finding index, the friction hit. The orchestrator's duties (sorting friction, filing proposals, merging) and the chat duties (relaying the closing, opening the demo and the review page) are not in it.

Every pointer to the implement skill is repointed to the worker prompt or removed: the dispatch skill's worker contract line, orient, to-tickets, code-review, the README, the upstream sync skill's mapping (implement now maps onto the worker prompt).

## Acceptance criteria

- [ ] The implement skill directory is gone; `rg '/mx:implement'` across the repo finds nothing.
- [ ] The worker prompt carries the contract above and nothing addressed to a reader other than the worker.
- [ ] The closing comment's required parts are named in the prompt: demo, action items, assumptions, finding index, friction.
- [ ] Property, reviewed: the implement skill addresses only the worker (now: the worker prompt addresses only the worker).
- [ ] Property, reviewed: every landing is demonstrated as the thing itself before the user is asked to read code.
- [ ] Demo in the closing comment: the worker prompt as a worker receives it (the runner's assembled system prompt for a toy ticket), and this ticket's own closing comment written under the new contract.
