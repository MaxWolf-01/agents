---
status: open
type: grilling
priority: 3
size: M
---

# The retro, a step of the feature debrief

## Brief

When a feature closes, its debrief ticket ([The debrief is a ticket](debrief-ticket.md), moved out of board-orients) lists the feature's sessions and commit range; the retro is the debrief's step that has subagents read those sessions, commits and diffs for recurring patterns, roadblocks, and workflow or tooling that fought the agents, and files what it finds as proposed tickets. This grilling designs that step together with the debrief ticket, before that ticket is built.

Rough intent, not yet grilled. Retros don't happen today. Wanted: a way to run them with little attention, combining Victor Taelin's optmem idea with the session index (`~/.dotfiles/bin/session-index`), so a retro reads indexed sessions rather than one live conversation.

Upstream `skills/in-progress/retro` (mattpocock/skills, 8fa1886 + 3ec8e23 + 6654f6b, still a stub) has the useful part: seven categories to look for — navigation pointers, automated checks, coding standards for the reviewer, global AGENTS.md size, tool economy, no-op instructions, information access. Revisit once it leaves `in-progress/`.

The per-session half of this (what fought the agent, what it would build) is the closing rule in the worker contract (`mx/skills/dispatch/worker-prompt.md`), whose output is proposed tickets on the tracker. What is left for this ticket is the cross-session view.

## Comments

**2026-09-23** The user wants the retrospective to run per feature, from its debrief: subagents scan the feature's sessions, commit history and diffs for patterns, roadblocks, and bad workflow or tooling. board-orients 15 makes the debrief a ticket that lists the feature's sessions (from `Session:` commit trailers) and its commit range, which is this ticket's input per feature.

**2026-09-23** Ruled by the user (D108): priority 3, grilled together with board-orients 15, the retro a sub-step of the debrief; "debrief" is the name for the whole close-out account.

**2026-09-23** Ruled by the user (D93): the rule "a defect a tool could have caught gets its check proposed" (text overlapping on a render, a prose tell, a convention broken: fix it, and file a ticket extending the tool that owns that kind of check) belongs to the workflow, not to the global `claude/CLAUDE.md`, and is designed in this grilling. The drafted wording, a `CLAUDE.md` sentence plus a worker-contract friction line, is branch `claude-md/propose-checks` (`f58ed36`), unmerged.
