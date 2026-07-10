---
name: orient
description: Which mx skill or flow fits the current situation — a router over the mx workflow.
disable-model-invocation: true
---

# Orient

You don't remember every skill, so ask.

A **flow** is a path through the skills. Most work travels one **main flow**, with an on-ramp that merges onto it. Everything else is standalone, or a vocabulary layer that runs underneath.

## The artefacts

| Object     | Location                        | Lifecycle                        | Content                                                          |
| ---------- | ------------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| Glossary   | `CONTEXT.md` (repo root)        | durable, edited in place         | domain terminology — opinionated, with avoid-lists                |
| ADR        | `decisions/NNNN-slug.md`        | durable, append-only             | one hard-to-reverse decision and why                              |
| Spec       | `agent/tasks/<feature>/spec.md` | committed; `git rm -r` when shipped | the work order for one feature                                 |
| Ticket     | `agent/tasks/<feature>/NN-slug.md` | retired with its feature      | one vertical slice: what to build, blocked-by, acceptance criteria |
| Small task | `agent/tasks/<slug>.md`         | deleted when done                | ticket-shaped, no spec                                            |
| Research   | `agent/research/NN-slug.md`     | gitignored, ephemeral            | one question, cited findings                                      |

Layout, state, and claiming: the `tracker` skill. A fact that fits none of these (a gotcha, a vendor quirk — knowledge not derivable from the code): an ADR if it constrained a decision, a code comment if it's code-local, the project CLAUDE.md if it's navigational.

## The main flow: idea → ship

1. **`/mx:grill-with-docs`** — sharpen the idea by interview. Stateful: terms land in `CONTEXT.md`, hard-to-reverse decisions in `decisions/` (both via `/mx:domain-modelling`). No codebase? Plain `/mx:grilling`. External inputs — a meeting transcript, a client brief, a bug report — feed in here too: grill through their unstated assumptions.
2. **Branch — does a question need a runnable answer?** (state, business logic, a UI you have to see) Detour, bridged by `/mx:handoff` in both directions: handoff out, fresh session, `/mx:prototype` to answer with throwaway code, handoff back.
3. **Branch — is this a multi-session build?**
   - **Yes** → `/mx:to-spec` (thread → spec), then `/mx:to-tickets` (spec → tracer-bullet tickets with blocking edges). Then `/mx:implement` per ticket, working the frontier, **clearing context between tickets**. Independent frontier tickets can run in parallel — `/mx:dispatch` orchestrates the waves (one orchestrator, N implements).
   - **No** → `/mx:implement` right here, in the same context window.

   `/mx:implement` drives `/mx:tdd` internally — one red-green slice at a time — and closes with `/mx:code-review`. Reach for either on its own too.

4. **QA — the human, per landed slice.** Every ticket is a tracer bullet, demoable the moment it lands: the agent announces what now works and how to exercise it (straight from the ticket's What-to-build and acceptance criteria), and the human drives it while the remaining frontier keeps running. Taste lands here — that's why there is no skill for it. Findings become new tickets with blocking edges; the frontier absorbs them.

### Context hygiene

Keep steps 1–3 in **one unbroken context window** — don't compact or clear until after `/mx:to-tickets` — so the grilling, spec, and tickets all build on the same thinking. Each `/mx:implement` then starts fresh, working from ticket + spec. The limit is the **smart zone**: reasoning degrades past ~100k tokens regardless of the advertised window size (a 1M window is more retrieval room, not more reasoning room). If a session approaches it before to-tickets, don't push on degraded — `/mx:handoff` and continue in a fresh thread.

## On-ramp

- **Something's broken** → `/mx:diagnosing-bugs`. For the hard ones: the bug that resists a first glance, the intermittent flake, the regression between two known-good states. It refuses to theorise until it has a **tight feedback loop** — one command that already goes red on _this_ bug — then fixes with a regression test. Its post-mortem hands off to `/mx:improve-codebase-architecture` when the real finding is a missing seam.

## Codebase health

Not feature work — upkeep.

- **`/mx:improve-codebase-architecture`** — survey the codebase for **deepening opportunities**; picking one generates an idea to take into the main flow at `/mx:grill-with-docs`.
- **`/mx:bloat-audit`** — over-engineering audit: a ranked list of what to delete, simplify, or replace with stdlib.

## Vocabulary underneath

Two model-invoked references that run _beneath_ the other skills — each the single source of truth for its vocabulary. Reach for them directly when the **words**, not the process, are the problem.

- **`/mx:domain-modelling`** — the project's _domain_ language: challenge a fuzzy term, resolve an overloaded word, record a hard-to-reverse decision as an ADR.
- **`/mx:codebase-design`** — the deep-module vocabulary (module, interface, depth, seam, adapter, leverage) for designing a module's _shape_. `/mx:tdd` and `/mx:improve-codebase-architecture` speak it.

## Crossing sessions

- **`/mx:handoff`** — compact the conversation into a file; open a **new session** referencing it. Forks.
- **`/mx:transcript`** — full session export, the lazy handoff.
- **`/compact`** (built-in) — same conversation, earlier turns summarized. Continues. Don't compact mid-phase.

## Standalone

- **`/mx:research`** — investigate a question against **primary sources**; leaves a cited artefact in `agent/research/`. Research feeds the thinking, it doesn't replace it.
- **`/mx:codex`** — second opinion from a different model.
- **`/mx:review-pr`** — review an existing GitHub PR: fetches it, then drives `/mx:code-review` against its merge-base.
- **`/mx:recap`** — structured status report: findings, decisions (explicit vs implicit), open questions.
- **`/mx:todos`** — overview of `agent/tasks/`: what's open, what's on the frontier.
- **`/mx:reflect`** — post-implementation self-critique, within session.
- **`/mx:writing-skills`** — reference for writing and editing skills well.
