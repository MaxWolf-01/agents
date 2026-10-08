---
name: orient
description: "Which mx skill or flow fits the current situation: a router over the mx workflow. Call it before starting nontrivial work in a project with an agent/ directory, and whenever unsure which skill or flow fits."
---

# Orient

A **flow** is a path through the skills. Most work travels one **main flow**, with an on-ramp that merges onto it. Everything else is standalone, or a vocabulary layer that runs underneath.

## The artefacts

| Object            | Location                             | Lifecycle                                                             | Content                                                                                                                                                                                        |
| ----------------- | ------------------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Glossary          | `GLOSSARY.md` (repo root)             | durable, edited in place                                              | domain terminology, opinionated, with avoid-lists                                                                                                                                              |
| ADR               | `decisions/NNNN-slug.md`             | durable, append-only                                                  | one hard-to-reverse decision and why                                                                                                                                                           |
| Ticket            | `agent/tickets/<slug>.md`            | `proposed` until the user rules on what it built, and built while it waits (`/mx:tracker`); retired once its tree is finished | one piece of work: the brief, its blocking edges and acceptance criteria, plus whatever design it holds (properties, decisions, testing seams). `parent:` makes it the child of another, and its context is its own body plus every ancestor's |
| Board             | `agent/board.html`                   | gitignored, re-rendered on every tracker change                       | the whole tracker as one page: the needs-me group with its questions, the trees, dependency graphs, frontier, review-page links                                                                                       |
| Research          | `agent/research/NN-slug.md`          | committed; retired with the tickets citing it (`/mx:tracker`)         | detail too long for the ticket that asked the question, cited                                                                                                                                                                  |
| Prototype         | `agent/prototypes/<slug>/`           | committed; retired with the work it served (`/mx:tracker`)             | throwaway code that answered a design question + `ANSWER.md` (question, verdicts)                                                                                      |
| Show              | `agent/show/<slug>/`, `<branch>/`    | committed with the round or the landing that made it; retired in the commit that retires the ticket or branch it served (`/mx:tracker`) | an explanation carried by an artefact: diagram, comparison, run output, explainer page                                                                                                           |
| Handoff           | `agent/handoffs/YYYY-MM-DD-slug.md`  | committed; retired by the session that picks it up (`/mx:handoff`)    | a session compacted for a fresh one to start from                                                                                                                                              |
| Transcript        | `agent/transcripts/`                 | gitignored                                                            | a session's full export (`/mx:transcript`)                                                                                                                                                     |

Every `agent/` row above is in the **agent repo**, a git repo of its own inside the one it plans. Layout, state, and claiming: `/mx:tracker`. A fact that fits none of these (a gotcha, a vendor quirk, knowledge not derivable from the code): an ADR if it constrained a decision, a code comment if it's code-local, the project CLAUDE.md if it's navigational.

## The main flow: intent → ship

One flow carries every piece of work: an intent arrives in chat; the gate picks the first artefact the user judges; the design lands on disk as a ticket; a fresh worker builds from it; a fresh reviewer reads the result; the session holding the branch integrates it; the user rules on the calls it shows them, or on none. What differs per piece is how much of the design lands on disk, and that decides who builds it.

**The gate.** Draft the ticket first: writing it is the test of how far a build can run ahead of the user. The first answer to an intent is the cheapest artefact the user can judge, and the draft picks it:

- **Fog**: no brief can be written. Grill it (step 1) until the ticket can be written and a sensible first version built; `/mx:grilling` says what its questions lean to. The round's design and figures are the artefact.
- **Rival shapes**: several sensible shapes survive the draft. Prototype or draw them (step 2); the rivals rendered side by side are the artefact.
- **One sensible shape**: build it (steps 3 to 5); the review page and the landing's show are the artefact, and the ticket's brief on the board says what the session understood.

Implementation calls are the session's, marked `(my call)` in the ticket (`/mx:grilling`), since nothing leaves its ticket tree before the user rules (step 4), and taste is judged in front of the render at the landing (step 5). Where a build rests on a call the user may want to set, the message that starts the build names the call and the choice made: an answer that arrives while it runs is written to the ticket's Comments and reaches the worker as guidance on resume, and one that does not is ruled where the landing shows it (`/mx:dispatch`). When one sensible shape cannot be told from fog, build, and open the brief with the doubted call. A build that misses gets no new ruling: an amend where the user can say the miss in comments, otherwise a grilling round in front of the build that rewrites the ticket, then a redo.

One intent per route, from mx's own tracker:

- `dispatch-remote-args-survive-ssh`, built: an empty argument lost over ssh has one fix, quote each argument; filed and built the same day, ruled on its review page.
- `context-checkpoints`, rivals drawn: how a long session compacts had three sensible designs (the plugin's, the harness's, both), drawn side by side and ruled in front of the drawing.
- `session-page`, grilled: how a session is shown to the user could not be briefed at first; four grilling rounds with figures came before the cut.

1. **`/mx:grilling`**, the fog route: sharpen the intent by interview, as deep as its ambiguity needs, from one question to a full interview. Stateful: the design lands in the ticket as it settles, terms in `GLOSSARY.md`, hard-to-reverse decisions in `decisions/` (both via `/mx:domain-modelling`). External inputs (a meeting transcript, a client brief, a bug report) pass the gate like any intent; the foggy ones are grilled here through their unstated assumptions. Planning that outgrows the session keeps going (`/mx:grilling`, Across sessions); how many sessions the frontier takes is discovered, not declared.
2. **`/mx:prototype`**, the rival-shapes route; where the rivals differ in how they fit rather than in how they run, a concept figure per rival (`/mx:show`) is the cheaper render. A prototype is forked out by `/mx:handoff` into a fresh session that builds the throwaway code; the prototype's `ANSWER.md` carries the verdicts back. A user-visible surface the user is blank on belongs here rather than in another grilling round: surface judgment is **render-triggered**, and a human blank on "how should it look" produces sharp criticism in front of a render.
3. **Loose, or a ticket.** What lands on disk decides who builds, and one question decides it: would a stranger need a brief to build this right? Loose: the instruction is the change; a stranger could apply it from the chat line without reading code (a keybinding, a version bump, "rename X to Y"). Everything else is a ticket, carrying the draft and whatever design a grilling or a prototype settled. A ticket that needs the conversation to make sense marks a decision that has not been made: the gate's fog route, not a bigger brief.

   - **Loose** is the absence of a brief: no ticket, no worker, no agent review. The session commits code on its own branch with the `loose` trailer, and its show in `agent/show/<branch>/` (`/mx:show`); `/mx:tracker` has how both leave. The review page is the user's station for it, over the code branch's range; its artefacts in the agent repo are opened as themselves. Its landing is step 5's with one session playing both parts.
   - **A ticket** is filed per `/mx:tracker` and dispatched at once by the session that wrote it, with no permission asked. A ticket the gate sent straight to the build is filed `open`, since the user voiced it, its framing marked agent-sketched (`/mx:tracker`, provenance), and the session stays with the user instead of waiting on the build; it can also be cleared, since the worker outlives it and any later session integrates the result.
   - **Work bigger than one fresh worker** is cut into **child tickets** first (`/mx:tracker`, SLICING.md), each a vertical slice of the ticket holding the design. The session that grilled it can build one, as that slice's worker, in a worktree of its own and under the worker contract, which is [`worker-prompt.md`](../dispatch/worker-prompt.md): read it as the worker would.

4. **`/mx:dispatch` works the tickets**, a lone ticket and a tree of them alike, by the same scripts and the same host selection: one orchestrator, a fresh worker per ticket in its own worktree, one at a time or in waves, the board as the standing view. A ticket and its ancestry are the whole brief, so a worker's context window is disposable. A worker's whole contract is the prompt dispatch appends to it ([`worker-prompt.md`](../dispatch/worker-prompt.md)). Reach for either on its own too.

   **The build never waits for the user to ratify a call.** It starts once the frontier is empty, that is, once you have no question left to put to them; every call they have not ruled on stays marked in its ticket (`/mx:grilling`), or is an assumption its worker anchors to the line it shaped, and the landing puts the ones that change what they asked for in front of them (`/mx:dispatch`). A round still carrying an open question waits for that answer instead. Nothing reaches the branch above a parent ticket's before the user's ruling, which is accept, amend, redo or reject (`/mx:tracker`). A parent ticket is ruled whole at its close-out, and a hinge alone (`/mx:tracker`, The tree).

5. **The landing: the calls that are the user's, shown, then QA.** Every ticket is a tracer bullet, drivable the moment it lands. The worker builds, tests and reports; the session holding the branch sorts the build's calls (`/mx:dispatch`) and shows the user only those that are theirs to make, each with the smallest artefact that makes it visible, the review page the drill-down and one show for everything that landed together (`/mx:show`, A landing's show). A build carrying none merges as far as a standing yes carries it (`/mx:tracker`, State). The user rules on the calls shown and drives what they want to on their own machine while the remaining frontier keeps running, and taste lands here; that is why there is no skill for it. Findings become new tickets with blocking edges; the frontier absorbs them. Where nothing is drivable yet, the show is concept figures alone (`/mx:show`), and taste debt accumulates knowingly, which is why greenfield builds keep the first milestone small and end-to-end.
6. **The review session: where iteration re-enters.** Scheduled at *first drivable*, not when the frontier empties. The human dogfoods the landed surface and dumps raw findings; the agent rebuilds the holistic picture (drives the app itself, reads the tree's proposed tickets and its debrief, which is where dispatch already sorted the workers' comments and the review one level up, fires a background architecture review when structure smells); then grilling rounds. The outputs sort themselves: defects the agent just fixes, verdicts land on tickets and ADRs, the human rules on the proposed tickets, threads too big for the session become new tickets or a handed-off grilling session, structural friction routes to `/mx:improve-codebase-architecture`; what the session itself finds worth doing and nobody asked for is filed `proposed` (`/mx:tracker`). Iteration is not a new ceremony: the board absorbs new tickets, and a reopened decision gets grilled and superseded.

**The user's stations, and no others**: the open questions of a grilling round; the calls a landing shows them, which are only those they have not made that change what they asked for, none for a build carrying nothing new; QA; and the board's needs-me group, where every ticket question waits (`/mx:tracker`). No step blocks on them reading a brief.

### Context hygiene

Keep the planning steps (1 to 3) in **one unbroken context window** (no handoff until the tickets are cut) so the grilling, the ticket and its child tickets all build on the same thinking. Each worker then starts fresh, working from its ticket and the ancestry above it. The limit is the **smart zone**: the stretch within which reasoning stays sharp; degradation becomes noticeable from roughly 30% of the window used, long before the advertised size fills. If a session nears it before the cut, don't push on degraded: end with the frontier open (`/mx:grilling`, Across sessions) or `/mx:handoff` mid-round, and continue in a fresh thread. The tickets, not the conversation, carry the thinking across the boundary.

## On-ramp

- **Something's broken** → `/mx:diagnosing-bugs`. For the hard ones: the bug that resists a first glance, the intermittent flake, the regression between two known-good states. It refuses to theorise until it has a **tight feedback loop** (one command that already goes red on _this_ bug), then fixes with a regression test. Its post-mortem hands off to `/mx:improve-codebase-architecture` when the real finding is a missing seam.

## Codebase health

Not product work, upkeep.

- **`/mx:improve-codebase-architecture`**: survey the codebase for **deepening opportunities**, then grill through them in order of impact.
- **`/mx:bloat-audit`**: an over-engineering audit, a ranked list of what to delete, simplify, or replace with stdlib.

## Vocabulary underneath

Two model-invoked references that run _beneath_ the other skills, each the single source of truth for its vocabulary. Reach for them directly when the **words**, not the process, are the problem.

- **`/mx:domain-modelling`**: the project's _domain_ language. Challenge a fuzzy term, resolve an overloaded word, record a hard-to-reverse decision as an ADR.
- **`/mx:codebase-design`**: the deep-module vocabulary (module, interface, depth, seam, adapter, leverage) for designing a module's _shape_. `/mx:testing` and `/mx:improve-codebase-architecture` speak it.

## Phase boundaries

A **phase** is a chunk of work inside a session (the grilling, the implementation, the QA), and what to do with the context built is decided **at** the boundary between two: continue, `/clear`, a subagent, or `/mx:handoff`, the first that fits in that order. [PHASE-BOUNDARIES.md](PHASE-BOUNDARIES.md) is the tree, with the reasoning behind each branch and why `/compact` is not on it.

## Standalone

- **`/mx:grilling`**: off the main flow too, for a plan, a design or a decision with no repo under it, or no build to follow.
- **`/mx:research`**: investigate a question against **primary sources**; the findings land in the ticket that asked, detail too long for it in `agent/research/`. Research feeds the thinking, it doesn't replace it.
- **`/mx:to-questionnaire`**: when what's blocking you isn't in your head or the codebase but in **someone else's**, write them a questionnaire to fill in. The inverse of grilling: it interviews you about the **send** (who it's going to, what you need back) and aims the questions at the gap. What comes back is material for `/mx:grilling`.
- **`/mx:wizard`**: for the steps only a **human** can take: provisioning infrastructure, credentials and CI secrets, an unfamiliar third-party dashboard, a one-off migration. Generates an interactive bash script that opens each URL, captures each value, and writes it where it belongs. Model-invoked: the agent reaches for it when it hits a wall only you can pass; anything the agent can do itself, it should.
- **`/mx:wait-what`**: the corrective for a message that didn't land: the agent re-pitches what it just said with the context you were missing, in plain language, using the `GLOSSARY.md` vocabulary.
- **`/mx:codex`**: a second opinion from another model family.
- **`/mx:review-pr`**: a review of a PR on GitHub, where `/mx:code-review` takes a local branch.
- **`/mx:recap`**: where the work in flight stands, when its thread is lost.
- **`/mx:writing-for-agents`**: the rules for what an agent reads.
- **`/mx:writing-for-humans`**: the rules for what a person reads cold, and the cheap standalone de-slop pass on a file (`/mx:code-review` carries its rules on every diff).
