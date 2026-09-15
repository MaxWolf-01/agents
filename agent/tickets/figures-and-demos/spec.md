---
status: draft
---

# Figures and demos: the shape is shown at both stations

## Problem Statement

The user judges at two stations, and at both the agent tells where it should show.

At the grilling round, the spec's Decisions describe schemas, message exchanges, state machines and module boundaries in prose. Prose hides shape: a missing relation, a cycle, a fourth party in an exchange are invisible in sentences and obvious in a figure. `/mx:show` exists for this and never fires during grilling: its triggers are reactive (an explanation ballooning, the user struggling), and grilling's one pointer ("a visual that would help a round is a show artefact") names no shape that demands one. The figures that did get built (soup, skilltree) were single HTML pages, never linked from a spec, never rebuilt as the design moved, so each one now teaches a design that no longer exists.

At the landing, the worker's closing comment opens with a demo, and the demo is prose about the change: the script's rules, the hook's prompt, the model's fields. What the user wants is the change as it is met: the command and the output it actually produced, the model as a serialized sample, the hook's feedback on a sloppy reply, the page open, the session driven. The worker contract asks for "the command and its expected transcript", which invites a transcript written from the head rather than pasted from a run, and no machinery reads the demo: `dispatch review` renders the page and never checks that a demo exists or runs it.

## Solution

One table of shapes, in `/mx:show`, with two columns of media: the **figure** a design decision of that shape gets in the spec, and the **demo** a delivered change of that shape gets at the landing. The spec format and the worker contract each point at the table from the slot they already have (the Decisions section, the closing comment's Demo line), so the choice needs no judgment and its absence is checkable.

Figures live under `agent/show/<feature>/`, linked from the decision they carry, re-rendered in the round that moves the decision. `(you, r2)`

A demo is a runnable file on the ticket branch, `agent/show/<feature>/demo-<NN>.sh` (or the project's equivalent), that the orchestrator runs on the user's machine; its output in the closing comment is that run's, pasted. The demo's shape decides what the script does: prints the sample, serializes the instance, feeds the hook, opens the page. `(my call, r3)`

The landing as a sequence: [landing.png](../../show/figures-and-demos/landing.png), source `landing.mmd` beside it. `(figure, r3)`

## User Stories

1. As the user judging a grilling round, I want a schema decision to arrive as an ER diagram, so that a missing relation or a wrong cardinality is visible at a glance.
2. As the user judging a grilling round, I want a multi-party exchange to arrive as a sequence diagram, so that ordering and a forgotten party show.
3. As the user judging a grilling round, I want a state model to arrive as a state chart, so that an unreachable state or a missing transition shows.
4. As the user judging a grilling round, I want a module-boundary decision to arrive as a dependency diagram, so that a cycle or a hub shows.
5. As the user returning to a spec after days, I want the linked figures to match the spec's current decisions, so that a stale figure never teaches me a design the spec has since left.
6. As the user sharing a design with a team, I want each figure as a PNG or a self-contained HTML file, so that I can attach it to a PR or a message without the repo.
7. As the user ruling on a landed script or hook, I want its demo to be an invocation and the output that run produced, so that I judge what it does and not what its author says it does.
8. As the user ruling on a landed data model or API, I want a serialized sample instance beside the type, so that I see the shape as it will be met in a file or on the wire.
9. As the user ruling on a landed page or UI, I want it open in front of me or shot, so that I judge it as a render.
10. As the user ruling on a landed prompt, skill or process change, I want a driven transcript of what a session now shows me, before and after where the difference is the point, so that I judge the experience and not the wording.
11. As the user in QA a week later, I want the demo re-runnable from the branch, so that I can drive the slice again without reconstructing the steps from a comment.
12. As the orchestrator landing a ticket, I want the demo to be a file I run, so that performing it on the user's machine is one command and its output is real by construction.
13. As an agent writing a spec's Decisions or a closing comment, I want the table to tell me the medium for the shape at hand, so that neither slot needs a judgment call and a missing figure or demo is checkable.
14. As an agent reviewing a spec diff or a landing, I want a decision or a change of a listed shape without its figure or demo to be a finding, so that the rule is applied against the finished artefact and not only while drafting.

## Properties

- A figure states the decision as it stands in the spec; a figure whose decision moved is re-rendered in the same round, never left standing.
- A figure's source (mermaid, SVG, HTML) is committed beside its render, so the render can always be rebuilt.
- A demo's output in a closing comment is pasted from a run of the demo file, never written from the head; the command that produced it sits above it.
- A demo file runs from the branch it lands on with no state the comment has to describe.
- A feature's figures and demos are retired with the feature, or promoted deliberately `(open → Q4)`.

## Decisions

- **One table, two media columns, in `/mx:show`.** Rows are shapes of a thing to be judged; each row names the figure for a decision of that shape and the demo for a delivered change of that shape. Show owns the medium craft already; the spec format and the worker contract point at the table from the slot they have, and the table is the trigger show's description lacked. `(my call, r3; unconfirmed)`
- **Trigger by shape, not size.** A one-column change gets no figure; a two-table schema gets its ER diagram. A keybinding's demo is the keystroke and what happens; a script's demo is a run. `(my call, r1; unconfirmed)`
- **The rows.** Figures: a new entity or relation → ER diagram; three or more parties exchanging messages, or an ordering that matters → sequence diagram; a state with named transitions → state chart; a new or moved module boundary → dependency diagram; a before/after → side-by-side. Demos: a script, a hook or a CLI → the invocation and its captured output, `--help` included for a CLI; a data model, a schema or an API → a serialized sample instance, a request and its response; a page or a UI → the page opened, or a screenshot per state; a prompt, a skill or a process change → a driven session transcript, before and after where the difference is the point; a long or interactive flow → a recording or a tmux pane the user can attach to; a config or a keybinding → the keystroke or the setting and what it does. Mermaid is the default figure renderer, validated per `/mx:mermaid`; show's medium craft overrides any default that a better medium beats. `(my call, r2 and r3; unconfirmed)`
- **The figure is the decision's home.** The Decisions entry links the figure and states only what the figure cannot: the why, the rejected alternative. `(my call, r1; unconfirmed)`
- **Figures live in `agent/show/<feature>/`**, one directory per feature, committed with the round. Not inline in the spec: diffview shows markdown as source, so an inline diagram is invisible at judgment time, and a rendered-markdown view is a general tool grown for one idea. `(you, r2)`
- **File shape of a figure.** `(open → Q5)`
- **Re-render with the round.** Grilling's end-of-round spec rewrite includes the figures whose decisions moved; the round's diffview range covers `agent/show/<feature>/`, so a figure's source diff sits beside the spec diff. `(my call, r2; unconfirmed)`
- **The demo is a file.** `agent/show/<feature>/demo-<NN>.sh` for a feature's slice, `agent/show/<slug>/demo.sh` for a standalone ticket; a make target where the project keeps its demos that way (`/mx:ml`). The worker writes it and runs it, and pastes that run's output into the closing comment under the command; the orchestrator runs the same file on the user's machine and opens what it produces beside the review page. A demo that needs a display (a page, a screenshot) writes its render to the same directory, so the file is what the user opens. `(my call, r3; unconfirmed)`
- **A demo file is a landing check.** `dispatch review` warns when the ticket branch adds no demo file and the closing comment's Demo line names none; the orchestrator sends the worker back for it, as it does for a missing assumption ([Warn at landing when a worker made choices but recorded no assumptions](../assumption-check-at-landing.md)). `(my call, r3; unconfirmed)`
- **The demo may become a test.** A demo file that asserts is a check `make check` can run ([The dispatch scripts get a test, and the demo becomes one](../dispatch-scripts-under-test.md), rung 1); promotion is the feature's review session's call, not the worker's. `(my call, r3; unconfirmed)`
- **Loose work demos the same way.** The session's landing message carries the demo slot already (the output style); the medium comes from the same table. No file is required for loose work, since no worker and no orchestrator sit between the session and the user. `(my call, r3; unconfirmed)`
- **The round message points at the figure** instead of re-describing its shape. `(my call, r1; unconfirmed)`
- **ADRs get no figure.** One to three sentences; a figure there is decoration. `(my call, r1; unconfirmed)`
- **Retirement of a feature's figures and demos.** `(open → Q4)`

## Testing Decisions

Prose in skills has no executable seam. The landing check is the one executable piece: `dispatch review`'s warning, tested where the dispatch scripts get their tests. Every other property is **reviewed**: the Spec axis checks a spec diff for a listed shape without its figure, and a closing comment for a demo whose output has no run behind it.

## Out of Scope

- A rendered-markdown view in diffview: a general tool grown for one idea; the show seam already exists and yields a shareable file. `(you, r2)`
- Publishing the ticket breakdown before the quiz: landed in one-flow (`/mx:to-tickets`, step 5), which went further and removed the quiz. `(you, r2; done elsewhere)`
- Figures in ADRs: too short to carry one. `(my call, r1)`
- Rendering the grilling round itself as a page: the spec diff on diffview is the round's render; a second page duplicates it. `(my call, r1)`
- The comment-density lint the user raised in the same session: its own decision ticket, [Comment density in a diff gets a mechanical ceiling](../comment-density-ceiling.md).

## Fog

None.
