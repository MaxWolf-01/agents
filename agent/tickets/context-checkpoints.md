---
status: open
type: grilling
priority: 2
size: S
---

# A long session hears where its context stands

## Brief

Asked for by the user on 2026-09-23, while ruling on board-orients 13's D5: every long session, a dispatcher above all and any interactive one, should be told where its context window stands at checkpoints, around 200k, 400k and at the latest 600k tokens, so the model can decide whether to write a handoff or recommend one to the user and continue in a fresh session. Reasoning degrades well before the window is full and the model cannot feel it (PRINCIPLES §8), so the reading has to come from outside the model. Nothing hands off automatically; the user was explicit that an automated handoff is not wanted yet.

What a session knows about its own context today, and what could tell it (a hook reading the transcript's token counts, the statusline's `context_window.used_percentage`, a Claude Code setting), is for this grilling to find.

## Acceptance criteria

- [ ] Decided, by the user: which sessions hear it, at which thresholds, what the note says, and what the session does on hearing it; options outside this brief count.
- [ ] A session crossing a threshold is told once per threshold, by a mechanism (not a rule it is asked to remember), and a demo shows a session crossing one.
