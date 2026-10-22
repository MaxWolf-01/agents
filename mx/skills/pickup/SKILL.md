---
name: pickup
description: "Start this session from a handoff, a file in an agent/handoffs/ directory. Use when the user gives a handoff's path, or says to continue or pick up from one."
argument-hint: "<handoff path>"
---

Run `${CLAUDE_SKILL_DIR}/../handoff/pickup.py <the handoff's absolute path>` first and read the handoff from its output: the script retires the file.
