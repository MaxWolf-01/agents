---
status: draft
---

# Figures and demos: the shape is shown at both stations

## Problem Statement

The user judges at two stations, and at both the agent tells where it should show.

At the grilling round, the spec's Decisions describe schemas, message exchanges, state machines and module boundaries in prose. Prose hides shape: a missing relation, a cycle, a fourth party in an exchange are invisible in sentences and obvious in a figure. `/mx:show` exists for this and never fires during grilling: its triggers are reactive (an explanation ballooning, the user struggling), and grilling's one pointer ("a visual that would help a round is a show artefact") names no shape that demands one. The figures that did get built (soup, skilltree) were single HTML pages, never linked from a spec, never rebuilt as the design moved, so each one now teaches a design that no longer exists.

At the landing, the worker's closing comment opens with a demo, and the demo is prose about the change: the script's rules, the hook's prompt, the model's fields. What the user wants is the change as it is met: the command and the output it actually produced, the model as a serialized sample, the hook's feedback on a sloppy reply, the page open, the session driven. The worker contract asks for "the command and its expected transcript", which invites a transcript written from the head rather than pasted from a run, and the same slot in loose work has no rule at all.

Artefacts outlive the work they served. Show directories and research notes stay on disk after their ticket or feature is retired, and agents in later sessions read them as current and correct the design toward them; this has happened repeatedly and nothing in the retire step names them.

A heavy artefact at either station is built by a fork of the session today (`/mx:show`, Heavy artifacts fork). Half a million tokens in, a fork is the most expensive agent there is, and the artefact's sources are the code and the spec on disk, which a fresh agent reads from a brief.

## Solution

One table of shapes, in `/mx:show`, with two media columns: the **figure** a design decision of that shape gets in the spec, and the **demo** a delivered change of that shape gets at the landing. The spec format, the worker contract and the landing message shape each point at the table from the slot they already have, so the choice needs no judgment and its absence is checkable. `(you, r4)`

Figures live under `agent/show/<feature>/`, linked from the decision they carry, re-rendered in the round that moves the decision, and opened for the user before the round's message. `(you, r2, r5)`

A demo is one executable file, `demo`, in the show directory of the work it demonstrates, for every piece of work that lands: a feature's slice, a standalone ticket, loose work alike. Running it is the whole demo: it prints the sample, serializes the instance, feeds the hook, opens the page. The closing comment or landing message carries the command and the output of one run, pasted. `(you, r4)`

At the landing the demo is staged, not run: the ticket branch gets a worktree beside the feature's and a detached tmux session named after the ticket, made through `job`, with the demo's path typed at the prompt; the user presses Enter on their own machine. `(you, r8)`

Retiring a ticket or a feature retires its show directory and the research notes its tickets cite; what a README or a PR needs is moved there in the same commit, source and renderer with it, and kept current there. `(you, r5; moved rather than copied, r7)`

The landing as a sequence: [landing.html](../../../docs/figures/landing.html), which draws itself in either colour scheme when opened. `(figure, r6: redrawn to the round-5 design; it had kept the dropped landing warning and the old file name through two rounds. Promoted into the README by ticket 05 and redrawn in that page's house style, so this is the one copy)`

## User Stories

1. As the user judging a grilling round, I want a schema decision to arrive as an ER diagram, so that a missing relation or a wrong cardinality is visible at a glance.
2. As the user judging a grilling round, I want a multi-party exchange to arrive as a sequence diagram, so that ordering and a forgotten party show.
3. As the user judging a grilling round, I want a state model to arrive as a state chart, so that an unreachable state or a missing transition shows.
4. As the user judging a grilling round, I want a module-boundary decision to arrive as a dependency diagram, so that a cycle or a hub shows.
5. As the user judging a grilling round, I want a record shape to arrive with a sample instance (a row, a JSON line) beside its diagram, so that I see what one will look like in the file or on the wire.
6. As the user reading a round, I want the figure already open in my browser when the message arrives, so that I do not read the prose first and find the picture at the end.
7. As the user returning to a spec after days, I want the linked figures to match the spec's current decisions, so that a stale figure never teaches me a design the spec has since left.
8. As the user opening a PR, I want the feature's figures in the description and the demo's output below them, so that a collaborator sees what the PR is without reading the spec.
9. As the user ruling on a landed script or hook, I want its demo to be an invocation and the output that run produced, so that I judge what it does and not what its author says it does.
10. As the user ruling on a landed data model or API, I want a serialized sample instance beside the type, so that I see the shape as it will be met in a file or on the wire.
11. As the user ruling on a landed page or UI, I want it open in front of me or shot, so that I judge it as a render.
12. As the user ruling on a landed prompt, skill or process change, I want a driven transcript of what a session now shows me, before and after where the difference is the point, so that I judge the experience and not the wording.
13. As the user in QA a week later, I want the demo re-runnable from the branch by one command I can find without asking, so that I can drive the slice again without reconstructing the steps from a comment.
14. As the user at a landing, I want the demo staged in a tmux session named after the ticket, the command typed and Enter left to me, so that running it on my machine is one keystroke when I choose, and nothing runs on my laptop before I say so.
15. As an agent writing a spec's Decisions, a closing comment or a landing message, I want the table to tell me the medium for the shape at hand, so that no slot needs a judgment call.
16. As an agent reviewing a spec diff or a landing, I want a decision or a change of a listed shape without its figure or demo to be a finding, so that the rule is applied against the finished artefact and not only while drafting.
17. As a session deep in its context, I want a heavy artefact built by a fresh agent from a brief, so that the build costs a fresh context and not a copy of mine.
18. As an agent in a later session, I want no retired show or research artefact left on disk, so that I never correct a design toward a stale one.

## Properties

- A figure states the decision as it stands in the spec; a figure whose decision moved is re-rendered in the same round, never left standing.
- A figure's source is committed; its raster render is regenerated and never tracked beside its source (this repo ignores `agent/show/**/*.png` and `docs/figures/*.png` already). A document in the tree that embeds a render tracks the copy it reads, since the document is read from the tree.
- Every landing whose change has a shape the table gives a demo has one `demo` file in its show directory, and the demo's output in the comment or message is pasted from a run of that file under the command, with the file's absolute path; a landing with no such shape says in its Demo line that the diff is the demo `(you, r9: not every change wants a demo; the absolute path)`.
- A demo file takes no arguments and runs from its branch on any host where the project is installed; what it produces lands beside it.
- No show directory and no research note outlives the ticket or feature it served; a figure a README or PR needs is moved there, source and renderer with it, and kept current there.
- A slot is never padded: a spec with no decision of a listed shape has no figure, and the table's absence of a row is a valid result.

## Decisions

- **One table, two media columns, in `/mx:show`.** Rows are shapes of a thing to be judged; each row names the figure for a decision of that shape and the demo for a delivered change of that shape. Show owns the medium craft already; the spec format, the worker contract and the landing message shape point at the table from the slot they have. Extending, cutting or generalising the rest of show while the table lands is in scope. `(you, r4)`
- **Trigger by shape, not size, on every artefact.** A one-column change gets no figure; a two-table schema gets its ER diagram. A keybinding's demo prints the keystroke and what it does; a script's demo runs the script. ADRs and any other document take the same table: most ADRs hit no row, and none is padded to hit one. `(you, r5)`
- **The rows.** Figures: a new entity or relation → ER diagram; a record shape (a row, a document, a payload) → a sample instance beside the diagram, a CSV row or a JSON line; three or more parties exchanging messages, or an ordering that matters → sequence diagram; a state with named transitions → state chart; a new or moved module boundary → dependency diagram; a prompt, a skill or a process change → an excerpt of the session it would produce, or that session role-played as a stand-in; a script, a hook or a CLI → example invocations, or the interface with sample outputs; a page or a UI → a prototype of it (`/mx:prototype`), a rough render judged before the page is built; a config or a keybinding → nothing; a before/after → side-by-side, whatever else the shape gives it. Demos: a script, a hook or a CLI → the invocation and its captured output, `--help` included for a CLI; a data model, a schema or an API → a serialized sample instance, a request and its response; a page or a UI → the page opened, a screenshot per state, a tutorial that walks the reader through it, or a recording; a prompt, a skill or a process change → a driven session transcript, before and after where the difference is the point; a long or interactive flow → a recording, a walkthrough the demo starts, or a tmux pane the user attaches to; a config or a keybinding → the keystroke or the setting and what it does; a state with named transitions or a module boundary → nothing. Show's medium craft overrides any default a better medium beats. `(my call, r2 to r5; the sample-instance row is yours, r5; the figure cells for a prompt and a script, and the dropped mermaid default, are your comments on ticket 01, C3, C4, C7; the page row is my call, ticket 06, unconfirmed)`
- **The demo's reader has the product sense and none of the weeds.** A demo explains as it shows: annotated beside what happened, the commands under what they mean, a rendered page or figure where the shape allows, the raw transcript kept as evidence in `out/`. The terminal transcripts this feature's own demos printed are the material, not the demo; the rule binds every demo from here. `(you, r9)`
- **The demo is one file named `demo`.** `agent/show/<feature>/NN-<slug>/demo` for a feature's slice, `agent/show/<slug>/demo` for a standalone ticket, `agent/show/<branch>/demo` for loose work. Executable with a shebang, in whatever language the demo needs (a one-off script is not a CLI, so `/mx:tyro-cli` does not bind it), taking no arguments. It writes what it produces (a transcript, a sample file, a screenshot) beside itself, and opens what it produced when a display is there, so a worker on a headless host runs it for the files and the user's own run opens them. The fixed name is what makes every demo findable and runnable without reading anything: `fd -t x '^demo$' agent/show`. `(you, r4, r5)`
- **The landing stages the demo in a tmux session.** The orchestrator adds the ticket branch's worktree beside the feature's, named after the ticket, and creates one detached tmux session per demo through a staged mode of `job`: the session named after the ticket, its working directory in that worktree, the demo's path typed at the prompt and Enter not sent. The landing message names the session. When the user runs it, `job`'s wrapper carries it, so its log and status land where every job's do, and the demo opens what it produces. The ruling ends it: accept, redo and reject through `ctl cleanup`, amend at the next fetch, since git refuses to fetch into a branch a worktree holds. The orchestrator runs no demo itself. A window in the user's attached session was rejected as a hand on their layout; one shared session with a window per ticket as unaddressable by name from chat. `(you, r8)`
- **The staged mode of `job` lives in dotfiles**, where `job` does, and lands as loose work before ticket 03 starts; a worker cannot add a tool outside its worktree. `(my call, r8; unconfirmed)`
- **A heavy artefact goes to a fresh agent with a brief**, at either station: the artefact spec, the output path, the sources on disk to read. A fork is the exception, taken only when the conversation itself is the source the artefact needs and no file carries it. Replaces show's "Heavy artifacts fork" rule. `(you, r4)`
- **The figure is the decision's home.** The Decisions entry links the figure and states only what the figure cannot: the why, the rejected alternative. The figure's source is text (an ER diagram in mermaid reads like DDL), so an agent reading the spec cold reads the source as easily as the prose it replaces, and a human reads the render. `(my call, r5; you delegated it, r5)`
- **Figures live in `agent/show/<feature>/`**, one directory per feature, committed with the round. Not inline in the spec: diffview shows markdown as source, so an inline diagram is invisible at judgment time, and a rendered-markdown view is a general tool grown for one idea. `(you, r2)`
- **File shape of a figure.** Two shapes, by how the picture is made. A diagram whose layout mermaid solves is one source file per figure with its SVG beside it (`<name>.mmd`, `<name>.svg`), and the SVG is what gets opened in the browser, since it scales with zoom where a PNG does not. A picture whose coordinates are placed by hand is one self-contained HTML file, which draws itself in either colour scheme from that one source; a figure heading for a document wants this shape, and this feature's landing figure was the mermaid pair until its promotion redrew it as `docs/figures/landing.html`. Either way the PNG is rendered on demand for embedding and stays untracked beside its source; an `index.html` only when several figures need one page, and there every image sits at `width:100%; height:auto` so it scales too. `(you, r4, r5; the second shape is my call, ticket 06, unconfirmed)`
- **Re-render with the round.** Grilling's end-of-round spec rewrite includes the figures whose decisions moved; the round's diffview range covers `agent/show/<feature>/`, so a figure's source diff sits beside the spec diff. `(you, r5)`
- **The figure is opened before the round is read.** The session opens it (`claude-browser`, else `xdg-open`) and the round's message says so in its first line, instead of narrating the figure's content. `(you, r5)`
- **Retired with the work, promoted deliberately.** Retiring a feature is `git rm -r` of `agent/tickets/<feature>/` and `agent/show/<feature>/` together; retiring a standalone ticket takes `agent/show/<slug>/` with it; a loose branch's show directory goes when the branch merges. Research notes the retired tickets cite are removed from disk in the same step; being untracked, they are moved to `~/logs/agent/<repo>/research/` rather than deleted, since that directory is in the restic backups and the XDG cache is not; a tracker the repo does not track sends its retired tickets to `~/logs/agent/<repo>/tickets/` by the same reasoning, in place of an in-tree done directory (you, r7); until [One tracker for all of a user's repos](../one-tracker-per-user.md) decides whether committing them makes the move moot. `(you, r5: retire show and research at close; my call, r5: the `~/logs` interim)`
- **Promotion is the agent's call, visible in the diff.** A figure the README or a PR description needs moves out of the show directory: the render, its source and the script that regenerates it go where the document's assets live (`docs/figures/` for this repo's README), references are repointed in the same commit, and no show directory outlives the work it belongs to, whatever still reads it. What the destination takes varies: a PNG the README embeds, an HTML page linked through `sftpgo-share upload`, a demo's output pasted into the PR as a code block or screenshots, a demo that asserts moved under `make check`; it is kept current where it lands. No ruling gates it: the user sees the diff and says so when a promotion is wrong or missing. `(you, r5; moves rather than copies, r7)`
- **The landing figure goes into the README** once the tickets have landed, as documentation of the flow beside the one-flow figures, through the promotion rule above: the first promotion done for real. `(you, r6)`

## Testing Decisions

Prose in skills has no executable seam; every property is **reviewed**. The Spec axis checks a spec diff for a listed shape without its figure and a closing comment for a demo whose output has no run behind it; the orchestrator's landing read checks that the demo file exists and that the worker's own run of it is pasted in the closing comment, and stages it without running it (round 8); the retire step in `/mx:tracker` names the show directory and the research notes, so a retirement that leaves them is a Spec finding. A slice whose change has an executable surface asserts it in its demo, and a demo that asserts is promoted under `make check` when the work it demonstrates outlives its show directory. `(my call, ticket 06, unconfirmed)`

## Out of Scope

- A rendered-markdown view in diffview: a general tool grown for one idea; the show seam already exists and yields a shareable file. `(you, r2)`
- A `dispatch review` warning on a missing demo: no landing has yet arrived without one, and a check is added after the failure is observed, not before it. `(you, r4)`
- Publishing the ticket breakdown before the quiz: landed in one-flow (`/mx:to-tickets`, step 5), which went further and removed the quiz. `(you, r2; done elsewhere)`
- Rendering the grilling round itself as a page: the spec diff on diffview is the round's render; a second page duplicates it. `(my call, r1)`
- The comment-density lint the user raised in the same session: [Comment density in a diff gets a mechanical ceiling](../comment-density-ceiling.md).
- One tracker spanning every repo, with research committed: [One tracker for all of a user's repos](../one-tracker-per-user.md); this spec's `~/logs` interim yields to its answer.
- The `sftpgo` command in dotfiles (`~/.dotfiles/.claude/commands/sftpgo.md`): making it model-invocable, fixing one default share setting for everything, and cutting the copy of the scripts' `--help` out of it. Its own ticket in dotfiles; the promotion rule here names the script, not the command. `(you, r5)`

## Fog

None.
