---
name: orient
description: "Which mx skill or flow fits the current situation: a router over the mx workflow. Call it before starting nontrivial work in a project with an agent/ directory, and whenever unsure which skill or flow fits."
---

# Orient

A **flow** is a path through the skills. Most work travels one **main flow**, with an on-ramp that merges onto it. Everything else is standalone, or a vocabulary layer that runs underneath.

## The artefacts

| Object            | Location                             | Lifecycle                                                             | Content                                                                                                                                                                                        |
| ----------------- | ------------------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Glossary          | `CONTEXT.md` (repo root)             | durable, edited in place                                              | domain terminology, opinionated, with avoid-lists                                                                                                                                              |
| ADR               | `decisions/NNNN-slug.md`             | durable, append-only                                                  | one hard-to-reverse decision and why                                                                                                                                                           |
| Spec              | `agent/tickets/<feature>/spec.md`    | draft while grilling, confirmed when the user rules on the calls it carries; `git rm -r` when shipped | the design: the work order for one feature, single- or multi-session                                                                                                                           |
| Ticket            | `agent/tickets/<feature>/NN-slug.md` | `proposed` until the user rules on what it built, and built while it waits (`/mx:tracker`); retired with its feature | one vertical slice (what to build, blocked-by, acceptance criteria), or, with `type: research \| prototype \| grilling \| legwork`, a decision ticket: a decision to make, answered on resolution |
| Standalone ticket | `agent/tickets/<slug>.md`            | deleted once its build has merged, or rejected (`/mx:tracker`)        | a ticket with no spec: work needing no design round, or a decision ticket filed for later                                                                                                      |
| Board             | `agent/board.html`                   | gitignored, re-rendered on every tracker change                       | the whole tracker as one page: the needs-me group with its questions, features with spec status, dependency graphs, frontier, review-page links                                                                                       |
| Research          | `agent/research/NN-slug.md`          | gitignored, ephemeral                                                 | one question, cited findings                                                                                                                                                                   |
| Prototype         | `agent/prototypes/<slug>/`           | committed, kept                                                       | throwaway code that answered a design question + `ANSWER.md` (question, verdicts), kept as primary source                                                                                      |
| Show              | `agent/show/<slug>/`                 | committed once approved or acted on                                   | an explanation carried by an artefact: diagram, comparison, demo, explainer page                                                                                                               |

Layout, state, and claiming: `/mx:tracker`. A fact that fits none of these (a gotcha, a vendor quirk, knowledge not derivable from the code): an ADR if it constrained a decision, a code comment if it's code-local, the project CLAUDE.md if it's navigational.

## The main flow: intent → ship

One flow carries every piece of work: an intent arrives in chat; the session grills it as deep as it needs; the settled design lands on disk as a brief; a fresh worker builds from the brief; a fresh reviewer reads the result; the session holding the branch integrates it; the user judges the demo and the review page. What differs per piece is how much of the design lands on disk, and that decides who builds it.

1. **`/mx:grill-with-docs`**: sharpen the intent by interview, as deep as its ambiguity needs, from one question to a full interview. Stateful: the design lands in the spec as it settles (a draft each round), terms in `CONTEXT.md`, hard-to-reverse decisions in `decisions/` (both via `/mx:domain-modelling`). Not working in a repo? Plain `/mx:grilling`. External inputs (a meeting transcript, a client brief, a bug report) feed in here too: grill through their unstated assumptions. Planning that outgrows the session keeps going: the open questions leave as decision tickets on the tracker, the next session claims one, grills it, and rewrites the spec sections it names; how many sessions the frontier takes is discovered, not declared.
2. **Branch: are there rival shapes?** Several designs to compare, or one that has to be seen or driven before anyone can judge it: detour through `/mx:prototype`, bridged by `/mx:handoff` in both directions: handoff out, fresh session, throwaway code, handoff back; the prototype's `ANSWER.md` carries the verdicts. A user-visible surface the user is blank on belongs here rather than in another grilling round: surface judgment is **render-triggered**, and a human blank on "how should it look" produces sharp criticism in front of a render. A design with one clear shape is built instead and judged as the thing itself (`/mx:prototype`).
3. **Loose, ticket or spec.** What lands on disk decides who builds, and one question decides it: would a stranger need a brief to build this right? Loose: the instruction is the change; a stranger could apply it from the chat line without reading code (a keybinding, a version bump, "rename X to Y"). Ticket: a builder must read code, choose and test, but the what fits one what-to-build plus acceptance criteria, every open choice is an implementation choice behind a settled interface, and it fits one worker. Spec: the builder would have to ask the user something, about behaviour they have taste on, an interface, a data shape, a term, or the work spans several slices. Writing the ticket is itself the test: a ticket that needs the conversation to make sense marks a decision that has not been made, and the fix is a grilling round, not a bigger brief.

   - **Loose** is the absence of a brief: no ticket, no worker, no agent review. The session commits on its own branch with the `loose` trailer, and the review page is the gate before the user sees it.
   - **A ticket** is published standalone (`agent/tickets/<slug>.md`, `/mx:tracker`) and dispatched by the session that wrote it, which can then be cleared: the worker outlives it and any later session integrates the result.
   - **A spec** is sliced by `/mx:to-tickets` into one ticket or many: a feature always slices. The session that grilled it can build a slice, as that slice's worker, in a worktree of its own and under the worker contract, which is [`worker-prompt.md`](../dispatch/worker-prompt.md): read it as the worker would.

4. **`/mx:dispatch` works the tickets**, a feature's and a standalone one alike, by the same scripts and the same host selection: one orchestrator, a fresh worker per ticket in its own worktree, one at a time or in waves, the board as the standing view. Each ticket is self-contained, so a worker's context is disposable. A worker's whole contract is the prompt dispatch appends to it ([`worker-prompt.md`](../dispatch/worker-prompt.md)): the ticket and its spec, `/mx:testing` when it writes tests, `/mx:code-review` at the end. Reach for either on its own too.

   **The build never waits for the user to ratify a call.** It starts once the frontier is empty, that is, once you have no question left to put to them; every call they have not ruled on travels into the tickets as an assumption its worker anchors to the line it shaped, and the review page is where they rule on it. A round still carrying an open question waits for that answer instead. A speculative build waits on its own ticket branch for the user's ruling: the feature branch carries only what they accepted, a ticket's dependents start only after it is accepted, and the ruling is accept, amend, redo or reject (`/mx:tracker`).

5. **The landing: the demo, then the page, then QA.** Every ticket is a tracer bullet, demoable the moment it lands. The demo has two parties: the worker specifies it in its closing comment, and the session holding the branch performs it and opens the result beside the review page. The user drives it while the remaining frontier keeps running, and taste lands here; that is why there is no skill for it. Findings become new tickets with blocking edges; the frontier absorbs them. Where no drivable surface exists yet, the closest render stands in (a screenshot, a driven transcript) and says so, and taste debt accumulates knowingly, which is why greenfield builds keep the first milestone small and end-to-end.
6. **The review session: where iteration re-enters.** Scheduled at *first drivable*, not when the frontier empties. The human dogfoods the landed surface and dumps raw findings; the agent rebuilds the holistic picture (drives the app itself, reads the feature's proposed tickets and its debrief, which is where dispatch already sorted the workers' comments and the harden report, fires a background architecture review when structure smells); then grilling rounds. The outputs sort themselves: defects the agent just fixes, verdicts land on tickets and ADRs, the human rules on the proposed tickets, threads too big for the session become new decision tickets or a handed-off grilling session, structural friction routes to `/mx:improve-codebase-architecture`; what the session itself finds worth doing and nobody asked for is filed `proposed` (`/mx:tracker`). Iteration is not a new ceremony: the board absorbs new tickets, and a reopened decision gets grilled and superseded.

**The user's stations, and no others**: the open questions of a grilling round, the demo and the review page per landed slice, QA, and the board's needs-me group, where every ticket question waits (`/mx:tracker`). No step blocks on them reading a brief; a ticket an agent wrote is dispatched, not presented.

### Context hygiene

Keep the planning steps (1 to 3) in **one unbroken context window** (no handoff until after `/mx:to-tickets`) so the grilling, spec, and tickets all build on the same thinking. Each worker then starts fresh, working from ticket + spec. The limit is the **smart zone**: the stretch within which reasoning stays sharp; degradation becomes noticeable from roughly 30% of the window used, long before the advertised size fills. If a session nears it before to-tickets, don't push on degraded: end with the frontier open (`/mx:grilling`, Across sessions: the sharp questions become decision tickets, the spec carries the rest) or `/mx:handoff` mid-round, and continue in a fresh thread. The spec and the tickets, not the conversation, carry the thinking across the boundary.

## On-ramp

- **Something's broken** → `/mx:diagnosing-bugs`. For the hard ones: the bug that resists a first glance, the intermittent flake, the regression between two known-good states. It refuses to theorise until it has a **tight feedback loop** (one command that already goes red on _this_ bug), then fixes with a regression test. Its post-mortem hands off to `/mx:improve-codebase-architecture` when the real finding is a missing seam.

## Codebase health

Not feature work, upkeep.

- **`/mx:improve-codebase-architecture`**: survey the codebase for **deepening opportunities**; picking one generates an idea to take into the main flow at `/mx:grill-with-docs`.
- **`/mx:bloat-audit`**: an over-engineering audit, a ranked list of what to delete, simplify, or replace with stdlib.

## Vocabulary underneath

Two model-invoked references that run _beneath_ the other skills, each the single source of truth for its vocabulary. Reach for them directly when the **words**, not the process, are the problem.

- **`/mx:domain-modelling`**: the project's _domain_ language. Challenge a fuzzy term, resolve an overloaded word, record a hard-to-reverse decision as an ADR.
- **`/mx:codebase-design`**: the deep-module vocabulary (module, interface, depth, seam, adapter, leverage) for designing a module's _shape_. `/mx:testing` and `/mx:improve-codebase-architecture` speak it.

## Phase boundaries

A **phase** is a chunk of work inside a session: the grilling, the implementation, the QA. At the **boundary** between two, decide what to do with the context you've built. Four options, worked top to bottom ([PHASE-BOUNDARIES.md](PHASE-BOUNDARIES.md) has the ordered tree, the reasoning behind each branch, and the primary-source cost that makes Continue the one to rule out first):

- **Continue**: the only move that keeps the session a primary source. Rule it out before anything else.
- **`/clear`**: when nothing here matters to what's next.
- **Subagent**: a tightly-scoped AFK task in its own window: `/mx:fork` when it needs the current mental model, a fresh background agent with a brief when it doesn't.
- **`/mx:handoff`**: compact the conversation into an inspectable file; open a fresh session on it. The terminal rung, and the move whenever work must travel (new harness, new directory, a colleague, a mid-phase side-quest). `/mx:transcript` is the full-export variant.

No `/compact` on the ladder: a deterministic reset from a file you can proofread beats a summary you can't (auto-compact is disabled for the same reason). Decide **at** a boundary; mid-phase, continue or split the remainder into subagents.

## Standalone

- **`/mx:grilling`**: the interview primitive itself (rounds that deliver the design whole and write it to the spec, the frontier, facts are the agent's job and decisions are the user's). `/mx:grill-with-docs` wraps it with docs. Reach for it bare when the discussion has no repo under it.
- **`/mx:research`**: investigate a question against **primary sources**; leaves a cited artefact in `agent/research/`. Research feeds the thinking, it doesn't replace it.
- **`/mx:to-questionnaire`**: when what's blocking you isn't in your head or the codebase but in **someone else's**, write them a questionnaire to fill in. The inverse of grilling: it interviews you about the **send** (who it's going to, what you need back) and aims the questions at the gap. What comes back is material for `/mx:grill-with-docs`.
- **`/mx:wizard`**: for the steps only a **human** can take: provisioning infrastructure, credentials and CI secrets, an unfamiliar third-party dashboard, a one-off migration. Generates an interactive bash script that opens each URL, captures each value, and writes it where it belongs. Model-invoked: the agent reaches for it when it hits a wall only you can pass; anything the agent can do itself, it should.
- **`/mx:wait-what`**: the corrective for a message that didn't land: the agent re-pitches what it just said with the context you were missing, in plain language, using the `CONTEXT.md` vocabulary.
- **`/mx:codex`**: second opinion from a different model.
- **`/mx:review-pr`**: review an existing GitHub PR: fetches it, then drives `/mx:code-review` against its merge-base.
- **`/mx:recap`**: structured status report: findings, decisions (explicit vs implicit), open questions.
- **`/mx:writing-for-agents`**: reference for writing any document agents consume: skills, CLAUDE.md, specs, tickets, reusable prompts.
- **`/mx:writing-for-humans`**: its counterpart for text read cold by whoever finds it: docs, comments, UI copy, ticket prose. Also the cheap standalone de-slop pass on a file (`/mx:code-review` carries its rules on every diff).
