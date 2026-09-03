---
name: tracker
description: "Issue tracker conventions: how specs, tickets, and wayfinder maps are published, fetched, claimed, and retired on this project's tracker backend. Use when publishing or fetching a spec/ticket/task, picking work from the frontier, or when another skill says \"publish to the issue tracker\"."
---

# Tracker

The conventions are backend-specific and each backend file is self-contained:

- **Default**: markdown files in `agent/tasks/`; read [MARKDOWN.md](MARKDOWN.md).
- The project's CLAUDE.md or other context declares GitHub Issues as its tracker: read [GITHUB.md](GITHUB.md).
- It declares some other tracker: follow the project's own conventions.

## Provenance (all backends)

A ticket's framing names who holds it: an Options or approach section an agent sketched says so inline ("options sketched by agent <date>, frame unconfirmed"); one the user decided points at the decision (ADR, spec decision, grilling verdict). Unmarked framing reads as agent-sketched. Write acceptance criteria that keep the option space open ("decision recorded; options outside this list count") so the session working the ticket settles the problem, not just the menu it arrived with.
