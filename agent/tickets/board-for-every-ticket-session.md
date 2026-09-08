---
status: open
type: grilling
---

# The tracker board as the standing view of every ticket session

## Question

The board (`dashboard.py`: every feature, its dependency graph, the needs-human queue, the diffview links) is the overview max wants whenever tickets exist, including a single session working them in sequence; today it is rendered only when dispatch runs. How does a serial ticket session get the board: which skill renders it, when, and who re-renders it as tickets change state?

Before the design round: run `/pocock-sync`; upstream carries an in-progress "mini dispatch" skill, to be read for inspiration and then done here in mx's own shape whether or not it is finished.

## Comments

Raised by max in chat, 2026-09-07, while grilling grilling-absorbs-wayfinder: "I rlly like the dashboard and it's kinda necessary, even when working on all tickets in sequence, for me, to have the overview of what tickets exist without having to constantly check in terminal". Not decided.
