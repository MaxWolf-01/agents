---
status: open
---

# Semi-automated session retrospectives

Rough intent, not yet grilled. Retros don't happen today. Wanted: a way to run them with little attention, combining Victor Taelin's optmem idea with the session index (`~/.dotfiles/bin/session-index`), so a retro reads indexed sessions rather than one live conversation.

Upstream `skills/in-progress/retro` (mattpocock/skills, 8fa1886 + 3ec8e23 + 6654f6b, still a stub) has the useful part: seven categories to look for — navigation pointers, automated checks, coding standards for the reviewer, global AGENTS.md size, tool economy, no-op instructions, information access. Revisit once it leaves `in-progress/`.

The per-session half of this (what fought the agent, what it would build) is the closing rule in the worker contract (`mx/skills/dispatch/worker-prompt.md`), whose output is proposed tickets on the tracker. What is left for this ticket is the cross-session view.

## Comments

**2026-09-23** The user wants the retrospective to run per feature, from its debrief: subagents scan the feature's sessions, commit history and diffs for patterns, roadblocks, and bad workflow or tooling. board-orients 15 makes the debrief a ticket that lists the feature's sessions (from `Session:` commit trailers) and its commit range, which is this ticket's input per feature.
