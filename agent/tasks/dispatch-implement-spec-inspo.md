---
status: open
---

# Take what upstream's implement-spec does better into dispatch

Rough intent, not yet grilled. Upstream `skills/in-progress/implement-spec` (mattpocock/skills, 84b5ee5 + 5b15a47) is a small dispatch: implementer subagents per frontier ticket in own worktrees, a merger subagent, one PR. Revisit once it leaves `in-progress/`.

Ideas it has that `/mx:dispatch` lacks:

- An optional exploration subagent up front, writing notes to a shared directory (`agent/research/`) so implementers don't re-explore the codebase.
- One whole-feature code-review pass after every ticket has landed, fixed in a single implementer; dispatch reviews per ticket via implement and never the integrated branch.
- A smaller dispatch for the common case: no worker hosts, no watchers, no board.
