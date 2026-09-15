---
status: draft
---

# Figures and demos: the shape is shown at both stations

## Problem Statement

The user judges at two stations, and at both the agent tells where it should show.

At the grilling round, the spec's Decisions describe schemas, message exchanges, state machines and module boundaries in prose. Prose hides shape: a missing relation, a cycle, a fourth party in an exchange are invisible in sentences and obvious in a figure. `/mx:show` exists for this and never fires during grilling: its triggers are reactive (an explanation ballooning, the user struggling), and grilling's one pointer ("a visual that would help a round is a show artefact") names no shape that demands one. The figures that did get built (soup, skilltree) were single HTML pages, never linked from a spec, never rebuilt as the design moved, so each one now teaches a design that no longer exists.

At the landing, the worker's closing comment opens with a demo, and the demo is prose about the change: the script's rules, the hook's prompt, the model's fields. What the user wants is the change as it is met: the command and the output it actually produced, the model as a serialized sample, the hook's feedback on a sloppy reply, the page open, the session driven. The worker contract asks for "the command and its expected transcript", which invites a transcript written from the head rather than pasted from a run, and the same slot in loose work has no rule at all.

A heavy artefact at either station is built by a fork of the session today (`/mx:show`, Heavy artifacts fork). Half a million tokens in, a fork is the most expensive agent there is, and the artefact's sources are the code and the spec on disk, which a fresh agent reads from a brief.

## Solution

One table of shapes, in `/mx:show`, with two media columns: the **figure** a design decision of that shape gets in the spec, and the **demo** a delivered change of that shape gets at the landing. The spec format, the worker contract and the landing message shape each point at the table from the slot they already have, so the choice needs no judgment and its absence is checkable. `(you, r4)`

Figures live under `agent/show/<feature>/`, linked from the decision they carry, re-rendered in the round that moves the decision. `(you, r2)`

A demo is one executable file, `demo`, in the show directory of the work it demonstrates, for every piece of work that lands: a feature's slice, a standalone ticket, loose work alike. Running it is the whole demo: it prints the sample, serializes the instance, feeds the hook, opens the page. The closing comment or landing message carries the command and the output of one run, pasted. `(you, r4)`

The landing as a sequence: [landing.svg](../../show/figures-and-demos/landing.svg), source `landing.mmd` beside it. `(figure, r3)`

## User Stories

1. As the user judging a grilling round, I want a schema decision to arrive as an ER diagram, so that a missing relation or a wrong cardinality is visible at a glance.
2. As the user judging a grilling round, I want a multi-party exchange to arrive as a sequence diagram, so that ordering and a forgotten party show.
3. As the user judging a grilling round, I want a state model to arrive as a state chart, so that an unreachable state or a missing transition shows.
4. As the user judging a grilling round, I want a module-boundary decision to arrive as a dependency diagram, so that a cycle or a hub shows.
5. As the user returning to a spec after days, I want the linked figures to match the spec's current decisions, so that a stale figure never teaches me a design the spec has since left.
6. As the user opening a PR, I want the feature's figures in the description and the demo's output below them, so that a collaborator sees what the PR is without reading the spec.
7. As the user ruling on a landed script or hook, I want its demo to be an invocation and the output that run produced, so that I judge what it does and not what its author says it does.
8. As the user ruling on a landed data model or API, I want a serialized sample instance beside the type, so that I see the shape as it will be met in a file or on the wire.
9. As the user ruling on a landed page or UI, I want it open in front of me or shot, so that I judge it as a render.
10. As the user ruling on a landed prompt, skill or process change, I want a driven transcript of what a session now shows me, before and after where the difference is the point, so that I judge the experience and not the wording.
11. As the user in QA a week later, I want the demo re-runnable from the branch by one command I can find without asking, so that I can drive the slice again without reconstructing the steps from a comment.
12. As the orchestrator landing a ticket, I want the demo to be a file I run, so that performing it on the user's machine is one command and its output is real by construction.
13. As an agent writing a spec's Decisions, a closing comment or a landing message, I want the table to tell me the medium for the shape at hand, so that no slot needs a judgment call.
14. As an agent reviewing a spec diff or a landing, I want a decision or a change of a listed shape without its figure or demo to be a finding, so that the rule is applied against the finished artefact and not only while drafting.
15. As a session deep in its context, I want a heavy artefact built by a fresh agent from a brief, so that the build costs a fresh context and not a copy of mine.

## Properties

- A figure states the decision as it stands in the spec; a figure whose decision moved is re-rendered in the same round, never left standing.
- A figure's source is committed; its raster render is regenerated and never tracked (this repo ignores `agent/show/**/*.png` already).
- Every landing, whatever its size, has one `demo` file in its show directory, and the demo's output in the comment or message is pasted from a run of that file under the command that ran it.
- A demo file takes no arguments and runs from its branch on any host where the project is installed; what it produces lands beside it.
- A feature's show directory is retired with the feature; what outlives it is promoted deliberately.

## Decisions

- **One table, two media columns, in `/mx:show`.** Rows are shapes of a thing to be judged; each row names the figure for a decision of that shape and the demo for a delivered change of that shape. Show owns the medium craft already; the spec format, the worker contract and the landing message shape point at the table from the slot they have. Extending, cutting or generalising the rest of show while the table lands is in scope. `(you, r4)`
- **Trigger by shape, not size.** A one-column change gets no figure; a two-table schema gets its ER diagram. A keybinding's demo prints the keystroke and what it does; a script's demo runs the script. `(my call, r1; unconfirmed)`
- **The rows.** Figures: a new entity or relation → ER diagram; three or more parties exchanging messages, or an ordering that matters → sequence diagram; a state with named transitions → state chart; a new or moved module boundary → dependency diagram; a before/after → side-by-side. Demos: a script, a hook or a CLI → the invocation and its captured output, `--help` included for a CLI; a data model, a schema or an API → a serialized sample instance, a request and its response; a page or a UI → the page opened, or a screenshot per state; a prompt, a skill or a process change → a driven session transcript, before and after where the difference is the point; a long or interactive flow → a recording, a walkthrough the demo starts, or a tmux pane the user attaches to; a config or a keybinding → the keystroke or the setting and what it does. Mermaid is the default figure renderer, validated per `/mx:mermaid`; show's medium craft overrides any default a better medium beats. `(my call, r2 and r3; unconfirmed)`
- **The demo is one file named `demo`.** `agent/show/<feature>/NN-<slug>/demo` for a feature's slice, `agent/show/<slug>/demo` for a standalone ticket, `agent/show/<branch>/demo` for loose work. Executable with a shebang, in whatever language the demo needs (a one-off script is not a CLI, so `/mx:tyro-cli` does not bind it), taking no arguments. It writes what it produces (a transcript, a sample file, a screenshot) beside itself, and opens what it produced when a display is there, so a worker on a headless host runs it for the files and the orchestrator runs it on the user's machine for the opening. The fixed name is what makes every demo findable and runnable without reading anything: `fd -t x '^demo$' agent/show`. `(you, r4: one file, always; my call, r4: the name, the place, no arguments, produce-then-open)`
- **A heavy artefact goes to a fresh agent with a brief**, at either station: the artefact spec, the output path, the sources on disk to read. A fork is the exception, taken only when the conversation itself is the source the artefact needs and no file carries it. Replaces show's "Heavy artifacts fork" rule. `(you, r4)`
- **The figure is the decision's home.** The Decisions entry links the figure and states only what the figure cannot: the why, the rejected alternative. `(my call, r1; unconfirmed)`
- **Figures live in `agent/show/<feature>/`**, one directory per feature, committed with the round. Not inline in the spec: diffview shows markdown as source, so an inline diagram is invisible at judgment time, and a rendered-markdown view is a general tool grown for one idea. `(you, r2)`
- **File shape of a figure.** One source file per figure with its SVG beside it (`landing.mmd`, `landing.svg`); the PNG is rendered on demand for embedding and stays untracked. The SVG is what gets opened in the browser, since it scales with zoom where a PNG does not; an `index.html` only when several figures need one page, and there every image sits at `width:100%; height:auto` so it scales too. `(you, r4: source plus render; my call, r4: SVG for viewing, PNG for embedding, the scaling rule)`
- **Re-render with the round.** Grilling's end-of-round spec rewrite includes the figures whose decisions moved; the round's diffview range covers `agent/show/<feature>/`, so a figure's source diff sits beside the spec diff. `(my call, r2; unconfirmed)`
- **Retired with the feature, promoted deliberately.** `git rm -r agent/show/<feature>/` alongside `agent/tickets/<feature>/`. What outlives it is promoted in that same commit: a figure into the README or the PR description (the PNG inline; an HTML page as a link through `sftpgo-share upload`), a demo's output into the PR description (the steps as a code block, the screenshots inline), a demo that asserts into a check `make check` runs. `(you, r4: retire and promote, PR as a target; my call, r4: the mechanics)`
- **Loose work demos the same way.** The landing message's demo slot points at the same table and the same file; one command or ten, no threshold to argue about. `(you, r4)`
- **The round message points at the figure** instead of re-describing its shape. `(my call, r1; unconfirmed)`
- **ADRs get no figure.** One to three sentences; a figure there is decoration. `(my call, r1; unconfirmed)`

## Testing Decisions

Prose in skills has no executable seam; every property is **reviewed**. The Spec axis checks a spec diff for a listed shape without its figure, and a closing comment for a demo whose output has no run behind it; the orchestrator's landing read checks that the demo file exists and runs.

## Out of Scope

- A rendered-markdown view in diffview: a general tool grown for one idea; the show seam already exists and yields a shareable file. `(you, r2)`
- A `dispatch review` warning on a missing demo: no landing has yet arrived without one, and a check is added after the failure is observed, not before it. `(you, r4)`
- Publishing the ticket breakdown before the quiz: landed in one-flow (`/mx:to-tickets`, step 5), which went further and removed the quiz. `(you, r2; done elsewhere)`
- Figures in ADRs: too short to carry one. `(my call, r1)`
- Rendering the grilling round itself as a page: the spec diff on diffview is the round's render; a second page duplicates it. `(my call, r1)`
- The comment-density lint the user raised in the same session: its own decision ticket, [Comment density in a diff gets a mechanical ceiling](../comment-density-ceiling.md).

## Fog

None.
