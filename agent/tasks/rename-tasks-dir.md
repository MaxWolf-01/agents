---
status: open
type: grilling
---

# Rename agent/tasks/ to match the ticket vocabulary

## Question

The skills say "ticket" and "spec" everywhere; the directory that holds them is `agent/tasks/`, and the standalone file is called a "task", which is also one of the four decision-ticket types. Is the directory renamed (`agent/tickets/`, `agent/tracker/`, or another name), or does "task" stay as the file-level word and the directory keeps its name? A rename touches every skill, `dispatch-ctl`, `dashboard.py`, the diffviews mirror, and every project already carrying `agent/tasks/`.

## Comments

Raised by max in the review of the decision-ticket change (agent/show/decision-tickets/), 2026-09-07: "a bit annoying that the dir is called tasks when we say tickets everywhere". Not decided.
