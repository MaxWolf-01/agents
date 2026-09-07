---
name: tracker
description: "Issue tracker conventions: how specs, tickets, and wayfinder maps are published, fetched, claimed, and retired on this project's tracker backend. Use when publishing or fetching a spec or ticket, picking work from the frontier, or when another skill says \"publish to the issue tracker\"."
---

# Tracker

The conventions are backend-specific and each backend file is self-contained:

- **Default**: markdown files in `agent/tickets/`; read [MARKDOWN.md](MARKDOWN.md).
- The project's CLAUDE.md or other context declares GitHub Issues as its tracker: read [GITHUB.md](GITHUB.md).
- It declares some other tracker: follow the project's own conventions.

## Provenance (all backends)

A ticket's framing names who holds it: an Options or approach section an agent sketched says so inline ("options sketched by agent <date>, frame unconfirmed"); one the user decided points at the decision (ADR, spec decision, grilling verdict). Unmarked framing reads as agent-sketched. Write acceptance criteria that keep the option space open ("decision recorded; options outside this list count") so the session working the ticket settles the problem, not just the menu it arrived with.

## Decision tickets (all backends)

A **decision ticket** is a ticket whose deliverable is an answer: a decision sharp enough to state now (one question, or a few that share their context and fit one session), whose answer is missing. It carries a `type`, one of `research | prototype | grilling | legwork` (`/mx:wayfinder`'s Ticket Types say how each resolves), and its body is the question; resolving it records the answer and closes it, the way the backend does. A ticket without a `type` is a **build ticket**. Both kinds share one numbering, one frontier and one claim rule, so a build ticket that needs the answer names the decision ticket in its blocking edges.

**The sort** for any piece of design, from grilling, to-tickets, a wayfinder session or a review session alike: the question can be stated sharply now, answered or not → a decision ticket (or, once answered, the spec and a build ticket); the question itself cannot yet be phrased → **fog**, held in the spec's Further Notes (a map's Not yet specified) until a resolution sharpens it. A decision ticket is resolved with the human, or by a background research agent; never by an implementing worker.
