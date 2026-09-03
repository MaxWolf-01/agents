---
name: orient
description: "Which mx skill or flow fits the current situation: a router over the mx workflow. Call it before starting nontrivial work in a project with an agent/ directory, and whenever unsure which skill or flow fits."
---

# Orient

A **flow** is a path through the skills. Most work travels one **main flow**, with an on-ramp that merges onto it. Everything else is standalone, or a vocabulary layer that runs underneath.

## The artefacts

| Object     | Location                        | Lifecycle                        | Content                                                          |
| ---------- | ------------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| Glossary   | `CONTEXT.md` (repo root)        | durable, edited in place         | domain terminology, opinionated, with avoid-lists                |
| ADR        | `decisions/NNNN-slug.md`        | durable, append-only             | one hard-to-reverse decision and why                              |
| Spec       | `agent/tasks/<feature>/spec.md` | committed; `git rm -r` when shipped | the work order for one feature                                 |
| Ticket     | `agent/tasks/<feature>/NN-slug.md` | retired with its feature      | one vertical slice: what to build, blocked-by, acceptance criteria |
| Small task | `agent/tasks/<slug>.md`         | deleted when done                | ticket-shaped, no spec                                            |
| Map        | `agent/tasks/<effort>/map.md` + `questions/` | retired when the effort ships | wayfinder effort: destination, decisions-so-far index, fog  |
| Research   | `agent/research/NN-slug.md`     | gitignored, ephemeral            | one question, cited findings                                      |
| Prototype  | `agent/prototypes/<slug>/`      | committed, kept                  | throwaway code that answered a design question + `ANSWER.md` (question, verdicts), kept as primary source |
| Show       | `agent/show/<slug>/`            | committed once approved or acted on | an explanation carried by an artefact: diagram, comparison, demo, explainer page |

Layout, state, and claiming: `/mx:tracker`. A fact that fits none of these (a gotcha, a vendor quirk, knowledge not derivable from the code): an ADR if it constrained a decision, a code comment if it's code-local, the project CLAUDE.md if it's navigational.

## The main flow: idea → ship

1. **`/mx:grill-with-docs`**: sharpen the idea by interview. Stateful: terms land in `CONTEXT.md`, hard-to-reverse decisions in `decisions/` (both via `/mx:domain-modelling`). Not working in a repo? Plain `/mx:grilling`. External inputs (a meeting transcript, a client brief, a bug report) feed in here too: grill through their unstated assumptions. Too big and foggy for one session? **`/mx:wayfinder`** instead: chart the effort as a shared map of decision tickets on the tracker and resolve them across sessions (threads you can't pull now become tickets, never lost context), merging back onto the flow at `/mx:to-spec`.
2. **Branch: does a question need a runnable answer?** (state, business logic, a UI you have to see) Detour, bridged by `/mx:handoff` in both directions: handoff out, fresh session, `/mx:prototype` to answer with throwaway code, handoff back; the prototype's `ANSWER.md` carries the verdicts. User-visible surfaces default here: surface judgment is **render-triggered**, so a human who is blank on "how should it look" in the abstract will produce sharp criticism in front of a render, and a blank answer means prototype, not more grilling.
3. **Branch: is this a multi-session build?**
   - **Yes** → `/mx:to-spec` (thread → spec), then `/mx:to-tickets` (spec → tracer-bullet tickets with blocking edges). Then `/mx:implement` per ticket, working the frontier, **clearing context between tickets**; each ticket is self-contained, so the last one's context is disposable. Independent frontier tickets can run in parallel; `/mx:dispatch` orchestrates the waves (one orchestrator, N implements).
   - **No** → `/mx:implement` right here, in the same context window.

   `/mx:implement` drives `/mx:tdd` internally, one red-green slice at a time, and closes with `/mx:code-review`. Reach for either on its own too.

4. **QA: the human, per landed slice.** Every ticket is a tracer bullet, demoable the moment it lands: the agent announces what now works and how to exercise it (straight from the ticket's What-to-build and acceptance criteria), and the human drives it while the remaining frontier keeps running. Taste lands here; that's why there is no skill for it. Findings become new tickets with blocking edges; the frontier absorbs them. Human QA is gated on **demo cost**: before a drivable surface exists, the agent's closing evidence (screenshots, driven transcripts, the ticket's annotated review page) substitutes, and taste debt accumulates knowingly until the surface arrives, which is why greenfield builds keep the first milestone small and end-to-end.

5. **The review session: where iteration re-enters.** Scheduled at *first drivable*, not when the backlog empties. The human dogfoods the landed surface and dumps raw findings; the agent rebuilds the holistic picture (drives the app itself, reads the landed tickets' comments and assumptions, fires a background architecture review when structure smells); then grilling rounds. The outputs sort themselves: defects the agent just fixes, verdicts land on tickets and ADRs, threads too big for the session become new question tickets or a handed-off grilling session, structural friction routes to `/mx:improve-codebase-architecture`. Iteration is not a new ceremony: the board absorbs new tickets, a reopened decision gets grilled and superseded, and wayfinding resumes only when the next chunk is again too big and foggy for one session.

### Context hygiene

Keep steps 1–3 in **one unbroken context window** (no handoff until after `/mx:to-tickets`) so the grilling, spec, and tickets all build on the same thinking. Each `/mx:implement` then starts fresh, working from ticket + spec. The limit is the **smart zone**: the stretch within which reasoning stays sharp; degradation becomes noticeable from roughly 30% of the window used, long before the advertised size fills. If a session nears it before to-tickets, don't push on degraded: `/mx:handoff` and continue in a fresh thread. And when the planning itself can't fit one window, that's `/mx:wayfinder`'s job: the map, not the conversation, carries the thinking across resets.

## On-ramp

- **Something's broken** → `/mx:diagnosing-bugs`. For the hard ones: the bug that resists a first glance, the intermittent flake, the regression between two known-good states. It refuses to theorise until it has a **tight feedback loop** (one command that already goes red on _this_ bug), then fixes with a regression test. Its post-mortem hands off to `/mx:improve-codebase-architecture` when the real finding is a missing seam.

## Codebase health

Not feature work, upkeep.

- **`/mx:improve-codebase-architecture`**: survey the codebase for **deepening opportunities**; picking one generates an idea to take into the main flow at `/mx:grill-with-docs`.
- **`/mx:bloat-audit`**: an over-engineering audit, a ranked list of what to delete, simplify, or replace with stdlib.

## Vocabulary underneath

Two model-invoked references that run _beneath_ the other skills, each the single source of truth for its vocabulary. Reach for them directly when the **words**, not the process, are the problem.

- **`/mx:domain-modelling`**: the project's _domain_ language. Challenge a fuzzy term, resolve an overloaded word, record a hard-to-reverse decision as an ADR.
- **`/mx:codebase-design`**: the deep-module vocabulary (module, interface, depth, seam, adapter, leverage) for designing a module's _shape_. `/mx:tdd` and `/mx:improve-codebase-architecture` speak it.

## Phase boundaries

A **phase** is a chunk of work inside a session: the grilling, the implementation, the QA. At the **boundary** between two, decide what to do with the context you've built. Four options, worked top to bottom ([PHASE-BOUNDARIES.md](PHASE-BOUNDARIES.md) has the ordered tree, the reasoning behind each branch, and the primary-source cost that makes Continue the one to rule out first):

- **Continue**: the only move that keeps the session a primary source. Rule it out before anything else.
- **`/clear`**: when nothing here matters to what's next.
- **Subagent**: a tightly-scoped AFK task in its own window: `/mx:fork` when it needs the current mental model, a fresh background agent with a brief when it doesn't.
- **`/mx:handoff`**: compact the conversation into an inspectable file; open a fresh session on it. The terminal rung, and the move whenever work must travel (new harness, new directory, a colleague, a mid-phase side-quest). `/mx:transcript` is the full-export variant.

No `/compact` on the ladder: a deterministic reset from a file you can proofread beats a summary you can't (auto-compact is disabled for the same reason). Decide **at** a boundary; mid-phase, continue or split the remainder into subagents.

## Standalone

- **`/mx:grilling`**: the interview primitive itself (rounds, the frontier, facts are the agent's job and decisions are the user's). `/mx:grill-with-docs` wraps it with docs; `/mx:wayfinder` runs it inside tickets. Reach for it bare when the discussion has no repo under it.
- **`/mx:research`**: investigate a question against **primary sources**; leaves a cited artefact in `agent/research/`. Research feeds the thinking, it doesn't replace it.
- **`/mx:to-questionnaire`**: when what's blocking you isn't in your head or the codebase but in **someone else's**, write them a questionnaire to fill in. The inverse of grilling: it interviews you about the **send** (who it's going to, what you need back) and aims the questions at the gap. What comes back is material for `/mx:grill-with-docs` or `/mx:to-spec`.
- **`/mx:wizard`**: for the steps only a **human** can take: provisioning infrastructure, credentials and CI secrets, an unfamiliar third-party dashboard, a one-off migration. Generates an interactive bash script that opens each URL, captures each value, and writes it where it belongs. Model-invoked: the agent reaches for it when it hits a wall only you can pass; anything the agent can do itself, it should.
- **`/mx:wait-what`**: the corrective for a message that didn't land: the agent re-pitches what it just said with the context you were missing, in plain language, using the `CONTEXT.md` vocabulary.
- **`/mx:codex`**: second opinion from a different model.
- **`/mx:review-pr`**: review an existing GitHub PR: fetches it, then drives `/mx:code-review` against its merge-base.
- **`/mx:recap`**: structured status report: findings, decisions (explicit vs implicit), open questions.
- **`/mx:reflect`**: post-implementation self-critique, within session.
- **`/mx:writing-for-agents`**: reference for writing any document agents consume: skills, CLAUDE.md, specs, tickets, reusable prompts.
- **`/mx:writing-for-humans`**: its counterpart for text read cold by whoever finds it: docs, comments, UI copy, ticket prose. Also the cheap standalone de-slop pass on a file (`/mx:code-review` carries its rules on every diff).
