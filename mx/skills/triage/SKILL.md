---
name: triage
description: "Triage the proposed tickets: group the pile by shared cause, then drop, merge or promote each. Use when the user starts a triage."
---

# Triage

The pile is every proposed ticket: `tracker data | jq -r '.tickets[] | select(.status == "proposed") | .slug'`, each read with `tracker context`. The project's retro report, `retro/report.md` in its agent repo, is one more input where one exists, since it may already group the pile by cause.

Every drop, merge and promotion is the user's call: put each group to them with your pick, and write only what they rule. A promotion is `tracker set <slug> status=open`; a drop is `tracker drop <slug>`; a merge writes what the dropped ticket adds into the one it joins, then drops it. Commit in the agent repo with the reason in the message, and render the board (`/mx:tracker`).
