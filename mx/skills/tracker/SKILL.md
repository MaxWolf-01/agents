---
name: tracker
description: "Tracker conventions: where specs and tickets live, how they are published, fetched, claimed and retired, how each decision-ticket type resolves, and the board that shows them. Use when publishing or fetching a spec or ticket, picking work from the frontier, filing or resolving a decision ticket, rendering the board, or when another skill says \"publish to the issue tracker\"."
---

# Tracker

Tickets are markdown files in `agent/tickets/`: [MARKDOWN.md](MARKDOWN.md) has the layout, the state, the board. The tracker sits in the repo it plans, or, when features span repos or the tickets stay out of a shared repo, in a workspace repo that holds the clones as untracked directories and the tracker beside them.

## Provenance

A ticket's framing names who holds it: an Options or approach section an agent sketched says so inline ("options sketched by agent <date>, frame unconfirmed"); one the user decided points at the decision (ADR, spec decision, grilling verdict). Unmarked framing reads as agent-sketched. Write acceptance criteria that keep the option space open ("decision recorded; options outside this list count") so the session working the ticket settles the problem, not just the menu it arrived with.

## Decision tickets

A **decision ticket** is a ticket whose deliverable is an answer: a decision sharp enough to state now (one question, or a few that share their context and fit one session), whose answer is missing. It carries a `type`, one of `research | prototype | grilling | legwork` (Ticket Types, below), and its body is the question plus, when it belongs to a feature, the spec sections its answer may rewrite; resolving it records the answer, rewrites those sections (`/mx:grilling`, Across sessions), and closes it, per MARKDOWN.md. A ticket without a `type` is a **build ticket**. A ticket's name is its title. Both kinds share one numbering, one frontier and one claim rule, so a build ticket that needs the answer names the decision ticket in its blocking edges.

**The sort** for any piece of design, from grilling, to-tickets or a review session alike: the question can be stated sharply now, answered or not → a decision ticket (or, once answered, the spec and a build ticket); the question itself cannot yet be phrased → **fog**, held in the spec's Fog section until an answer sharpens it. A decision ticket is resolved with the human, or by a background research agent; never by an implementing worker.

## Supersede

A newer artefact that replaces an older one never leaves the old one looking live; agents read whatever exists as current truth. MARKDOWN.md says how.

**Amend or supersede a decision.** While nothing is built on a ticket's answer, a later decision that overturns it amends it in place: edit the answer, marking the changed claim inline (`(amended <date>, was <old>)`). Once code reads the answer, it is the reasoning behind that code: leave it, open a new ticket that supersedes it, and put a one-line forward pointer on the old one.

Either way the **spec sweep** follows in the same session: rewrite the spec sections the decision touches, and grep the retired claim across the tickets, `CONTEXT.md` and `decisions/`; a copy left standing is current truth to every later reader. When the sweep cannot run now, file a ticket for it with a blocking edge.

## Ticket Types

Every decision ticket is either **HITL** (human in the loop, worked *with* a human who speaks for themselves) or **AFK**, driven by the agent alone. A HITL ticket only resolves through that live exchange; the agent never stands in for the human's side of it (a grilling agent that answers its own questions has broken this).

- **Research** (AFK): Reading documentation, third-party APIs, or local resources like knowledge bases to surface a fact a decision waits on. Resolved by a background `/mx:research` agent: findings land as a research artefact (`agent/research/`), the ticket's answer gists and links it, and they reach the spec draft only through a grilling round that puts them to the user. Use when knowledge outside the current working directory is required.
- **Prototype** (HITL): Raise the fidelity of the discussion by making a cheap, rough, concrete artifact to react to: an outline, a rough take, a stub, or UI/logic code via `/mx:prototype`. Links the prototype and its `ANSWER.md` (the verdicts) as assets. Use when "how should it look" or "how should it behave" is the key question, and default to it for anything user-visible: surface judgment is render-triggered, and a surface question doesn't sharpen when other decisions land, only against a built artifact.
- **Grilling** (HITL): Conversation. The default case. Always invoke `/mx:grilling` and `/mx:domain-modelling`. When the user is blank on a question, the question is usually posed backwards ("what goes in the sidebar?" assumes a sidebar); convert the ticket to a prototype rather than extracting a conceptual answer that a render will overturn.
- **Legwork** (HITL or AFK): Manual work that must happen before a *decision* can be made: nothing to decide, prototype, or research, but the discussion is blocked until it's done. Signing up for a service so its API can be judged, provisioning access, moving data so its shape can be seen. This is the one type that *does* rather than decides, and it earns its place by unblocking a decision, not by delivering the feature. The agent drives it alone where it can (AFK); otherwise it hands the human a precise checklist (HITL). Resolved when the work is done; the answer records what was done and any resulting facts (credentials location, new URLs, row counts) later tickets depend on.
