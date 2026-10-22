---
name: pickup
description: "Start this session from a handoff, a file in an agent/handoffs/ directory. Use when the user gives a handoff's path, or says to continue or pick up from one."
argument-hint: "<handoff path>"
---

Your first act is `${CLAUDE_SKILL_DIR}/../handoff/pickup.py <the handoff's absolute path>`. What it prints is the handoff in full, so read the handoff there: the script also retires the file from the agent repo and links the session pages, and the file is gone once it has run. Then carry on with what the handoff says the next session is for.
