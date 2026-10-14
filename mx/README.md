# mx: Agent Workflow Plugin

File-based tickets, domain glossary + ADRs, research artefacts, and session continuity for multi-session work.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/one-flow.png">
  <img alt="One flow in five columns (chat, brief, worker, review, land) and three rows, by how much of the design lands on disk: the gate drafts the ticket first and sends fog to grilling, rival shapes to a prototype or a drawing, and one sensible shape to the build; one question, whether a stranger would need a brief, picks the row; a loose change has no brief, no worker and no agent review, the session committing it with the loose trailer and landing it over a review page and a show; a ticket is filed open and dispatched at once to a fresh worker that builds, tests, commits a report and reviews its own branch, light or on the full axes, before your ruling and QA; work bigger than one worker is cut into child tickets, built a worker per child on the parent's branch, reviewed per worker and once more one level up, and ruled whole at its close-out, a hinge alone; one orchestrator claims, spawns, reads and merges, and sorts each build's calls so only those yours to make reach the board's needs-me group; a strip of four dials (grilling, on disk, worker, review) sits underneath, and moss cards mark your only stations" src="assets/one-flow-light.png">
</picture>

<details>
<summary><b>The whole workflow as one map: the main line every piece of work rides, its branches, and the stops that are yours</b></summary>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/workflow-map.png">
  <img alt="The mx workflow as a transit map: one main line runs left to right from an intent through the gate, where the draft picks the route, to the ticket, filed and dispatched at once, then dispatch, workers, one per ticket, and the landing, where the calls are sorted, to your ruling and merged. Three branches leave at the gate: fog goes through grilling rounds and rival shapes through a prototype or a figure per rival judged side by side, and both rejoin at the ticket; loose runs along the top, the session committing with no ticket and no worker, to the review page and on to merged. Work bigger than one worker runs as a child-tickets track beside the main line: the cut into child tickets, the shared dispatch, workers and landing, then a hinge ruled alone, the close-out with the suite, the review one level up and the debrief, and your ruling on the whole tree before it merges. A loop under the build runs from the landing through QA and the review session back into dispatch, where findings become tickets. Eight numbered stops in the accent colour are the only places you are asked, the hinge drawn as a ring because it asks only when a call is yours, and a key under the map says what each asks of you and that every open ticket question and every build in review waits in the board's needs-me group" src="assets/workflow-map-light.png">
</picture>

</details>

<details>
<summary><b>The whole cycle, from an intent to shipped work</b></summary>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/full-cycle.png">
  <img alt="The full mx cycle: an intent, a brief or a bug report is grilled, each round showing the design and putting your questions to you, and rewriting the ticket; once the frontier is empty the ticket is cut into child tickets (one slice means no cut, the ticket itself is built); dispatch hands a fresh worker each frontier ticket; each landed slice shows you its calls, with a review page and one show, then your QA, and the close-out runs the full suite, the review and the debrief and has you rule the tree whole; the review session starts at the first drivable slice, where you drive it and grilling follows, and sends new tickets to the board and reopened calls back to grilling, while a codebase-health survey feeds grilling its candidates; along the bottom sit the glossary, the decisions and the board with its needs-me group, and moss marks your only stations" src="assets/full-cycle-light.png">
</picture>

</details>

<details>
<summary><b>A ticket's status, and the board that shows it</b></summary>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/ticket-state.png">
  <img alt="A ticket's status as a chain: an agent filing on its own reading (a cut's slices, a punt, a review finding) files it proposed with tracker new, and a session with you files what you asked for open; a proposal is built while your ruling waits, either ruled first into open or claimed as it stands; dispatch claim writes claimed, and a worker writes no ticket file; dispatch review imports the worker's report and writes review, where a child merged into its parent's branch that is no hinge unblocks its siblings; your ruling on the calls yours to make (accept merges then done, amend resumes the worker and claims it again, redo sends it back open for a fresh worker, reject drops it with its build, and a build with no call of yours merges on your standing yes) leads to done, which is your accept, given or standing; tracker retire then takes a finished tree out of the tracker, which is not a status. Beside it the board, the tracker as one page: the needs-me group, where a row asks you to rule on a build, for your answer or to work it with you, with a sample row and its question under it; the frontier, claimed, blocked, proposed and folded done groups; a dependency graph of the row's tree or every tree, with the build to rule on in the accent and proposals dashed; the briefing; an opened row's questions, sessions, artefacts and acceptance criteria; and the review pages. Moss marks only what waits on you" src="assets/ticket-state-light.png">
</picture>

</details>

<details>
<summary><b>A ticket's flow, and the command that writes each status</b></summary>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/ticket-flow.png">
  <img alt="A ticket's flow as a status chart threaded through four rows of place: a session you sit at, the tracker file in the agent repo's main checkout, the orchestrator holding the branch the tickets merge into, and the worker hosts. The five statuses sit on one rail in the tracker row (proposed, open, claimed, review and done), and each is written by a line from the command that types it, in its row. tracker new files a proposal from the orchestrator, or an open ticket from your session, where a reopened decision is filed the same way as a new ticket superseding the old. tracker set status=open rules a proposal before its build. dispatch claim writes claimed, a proposal claimed as it stands. dispatch review writes review once the report is fetched, and a parent enters review at its close-out by tracker set status=review. dispatch review or dispatch accept writes done after your accept is merged and verified, and tracker retire then takes a finished tree out. Below, a wave of workers spawned by dispatch ctl spawn, one per ticket on its host: one builds, tests, reviews its own branch and commits its report last; one is stopped or blocked and resumed with guidance or continue while it stays claimed; one is gone, cleaned up with dispatch ctl cleanup and sent back to open. Dashed tracks lead back: amend resumes the worker from review into claimed, while redo and a lost session reset the ticket to open. Reject drops it, and nothing moves back from done. Moss marks only your ruling on a build in review and the needs-user tickets whose questions wait in the needs-me group" src="assets/ticket-flow-light.png">
</picture>

</details>

<details>
<summary><b>Grilling across sessions: the ticket carries the design, child tickets carry the open questions</b></summary>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/session-boundary.png">
  <img alt="Grilling across sessions: an idea too foggy to brief enters a grilling round, which puts the design whole and then the frontier's questions on the session page, each answered by number, with a question of taste asked as a blind test; each round rewrites the ticket, whose sections hold the design and whose calls carry call marks saying who settled them; a session that ends with the frontier open files the open questions as child tickets that need you, filed open and needs-user, each a session's worth, keeping the options and the pick as the last round put them and naming the sections its answers may rewrite; a fresh session reads the ticket top-down, claims one child ticket, reads its comments, grills it as a round like any other, and lands the answer on the parent marked (you, &lt;slug&gt;); once the frontier is empty the ticket is read whole and cut into child tickets, or built as one slice, and calls still unruled keep their marks; each round is a turn on the session page, whose records are committed to the agent repo as the session ends. Moss marks the round and the child tickets, the two places that wait on you" src="assets/session-boundary-light.png">
</picture>

</details>

<details>
<summary><b>The board: the tracker as one page</b></summary>

`board`, run from anywhere in the repo, renders every ticket as a row in the group of its state, and everything that waits on you in one group at the top, with its open questions under the row and a copy button on each. A row says what it asks of you, how much of your time it wants and how much it matters, every mark explaining itself on hover, and it opens to the ticket's brief, its questions and its acceptance criteria. A chip hides a whole tree of tickets, a filter narrows the rows, and the column beside them carries a briefing, where things stand and what to pick up next, written by a model that has read the repo, over a preview of the dependency graph that opens full size. An opened ticket also lists the sessions that committed on it, each with the command that resumes it, read off the `Session:` trailer a session's commits carry where a `prepare-commit-msg` hook writes one; a GitHub reference on a row says whether its pull request is open, merged or waiting on changes. It watches the tracker and the open tab re-renders itself, so it stays current while the work is in flight. Screenshots of a demo tracker, rebuilt by [`docs/figures/board-fixture/build.py`](../docs/figures/board-fixture/build.py).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/board-overview.png">
  <img alt="The board: the needs-me group at the top, holding two builds to rule on (a test fix, and a whole tree at its close-out with its four child tickets folded under it and a child's question carried up), a prototype hinge and a ticket you work through together, and a slice stopped on a question, each open question under its row with a copy button beside it, and each row carrying what it asks of you, your time on it and its priority; the frontier and the claimed work below, a parent ticket with its merged child folded under it; beside the rows a briefing written on this tracker, saying where things stand and naming three picks with a reason each and that all three can run at once, over a preview of the whole tracker's dependency graph across two trees" src="assets/board-overview-light.png">
</picture>

One tree of tickets, the rest hidden by their chips; a ticket opened to its question, the sessions that worked on it, its artefacts and its criteria, and the tree's graph beside the rows:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/board-feature.png">
  <img alt="One tree on the board, the other tree and the loose tickets hidden by their chips: a hinge prototype in the needs-me group opened to its question with its detail, the two sessions that committed on it each with a button copying the command that resumes it, its show directory with a runnable script and a button copying the command that runs it, and its acceptance criteria as a checklist; below it a slice stopped on a question, the frontier, the claimed work, a blocked slice, and the proposed group, holding a ticket an agent filed that waits off the frontier for a triage, and the tree's dependency graph beside the rows with the opened ticket marked" src="assets/board-feature-light.png">
</picture>

</details>

<details>
<summary><b>A ticket's review page: the diff, with the agent's reasoning on the lines it concerns</b></summary>

Every landed ticket gets one, rendered by `dispatch review` and linked from its row on the board: side-by-side diff, keyboard-driven, comments you leave export as markdown to paste back to the agent that wrote the code. The agent's own notes arrive on the page as `AGENT` blocks, anchored to the lines they explain, including on a file the diff left alone deliberately.

<img alt="A review page: the file tree with an untouched-but-noted file, a side-by-side diff of the importer turning a stub into the parse report, and an inline agent note explaining why rejected lines are reported per line rather than per file" src="assets/review-page.png">

</details>

<details>
<summary><b>A landing, from the worker's report to your ruling</b></summary>

The worker's last act is its report: its closing comment, the questions only you can answer, and its assumptions, each anchored to the line of code it shaped. The orchestrator reads the diff against the ticket, imports the report into the ticket, renders the review page, and sorts the build's calls into those you already made, those that are the agent's (how it is built), and those yours to make (anything that changes what you asked for). Only the last reach you, each with the smallest artefact that makes it visible. Every landing also comes with one show of what was built, made by a fork of the orchestrating session, unless the diff alone makes the change plain at a glance.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/landing.png">
  <img alt="A landing as a sequence between the worker, the orchestrator and you. The worker builds and tests, reviews its own branch, and commits its report last, at agent/show/&lt;slug&gt;/report.md: its closing comment, its assumptions anchored to the lines they concern, its findings and friction, and its questions. The orchestrator runs dispatch ctl probe and dispatch fetch, reads the diff against the ticket and its ancestry, and runs dispatch review, which imports the report, renders the review page and writes review. A child ruled with its parent merges on that read into the parent's branch and waits there for the parent's close-out. For a hinge, a ticket from the integration branch, or a whole tree at its close-out, the orchestrator sorts the build's calls. With nothing yours to make, it merges on the yes the merge needs, a fork builds the landing's show, and one line tells you what landed. With calls yours to make, each becomes a [Dn] question on its ticket and reaches you on the session page with the artefact that shows it, and a show is built around them. Your ruling is accept, amend, redo or reject, each with what it runs" src="assets/landing-light.png">
</picture>

</details>

<details>
<summary><b>The session page, in the hub tab</b></summary>

Every session you sit at answers on its session page, which the bullet "A session answers on its page" below describes. The [container hub](https://github.com/MaxWolf-01/dotfiles/blob/master/bin/container-hub), a local server in the dotfiles and not part of mx, gathers every session's pages in one browser tab: a rail with one unit per session, its state and the headline of its newest turn, and the selected session's page in a sidebar, with the pages its turns opened in panes beside it, figures and shows on one side, review pages on the other. The box under the session page types into that session's terminal, and hands the session off to a fresh one once its handoff is committed. Screenshots of fictional sessions, rebuilt by [`docs/figures/hub-fixture/build.py`](../docs/figures/hub-fixture/build.py).

<img alt="The hub tab, dark. On the left, a rail of five orchestrator sessions on a small ledger app, each with its state mark, its newest turn as a status line and its context use: one blocked on a permission prompt (red), the selected one waiting on a question and ready to hand off (two rings), one with two new pages, one idle while its dispatched workers run, one at work. In the middle, the selected session's page: a bar naming its repo, session id and short name beside its context use; under the title, the session it continues; an open question at its top, whether a shared link carries the saved view or a snapshot of its rows, with two options and the agent's pick, and the turn that asked it below; beside them the timeline, each turn's headline with the artefacts it opened, a chat turn as a quieter row, and the previous session at its foot; under the page, a box that answers the session, jumps to its terminal or hands it off from its committed handoff. On the right, two panes: the figure comparing the two answers, and the review page of the slice that landed, with the agent's notes on the diff" src="assets/hub.png">

</details>

## Artefacts

| Object            | Location                             | Lifecycle                                                             | Content                                                                                                                                                             |
| ----------------- | ------------------------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Glossary          | `GLOSSARY.md` (repo root)             | durable, edited in place                                              | domain terminology, opinionated, with avoid-lists                                                                                                                   |
| ADR               | `decisions/NNNN-slug.md`             | durable, append-only                                                  | one hard-to-reverse decision and why                                                                                                                                |
| Ticket            | `agent/tickets/<slug>.md`            | `proposed` when an agent filed it, waiting off the frontier for your triage; retired once its tree is finished | one piece of work: its brief, blocking edges and acceptance criteria, plus whatever design it holds. `parent:` makes it the child of another, and a worker reads it with every ancestor |
| Board             | `agent/board.html`                   | gitignored, re-rendered on every tracker change                       | the whole tracker as one page: the needs-me group with its questions, the trees, dependency graphs, frontier, the briefing, review-page links       |
| Research          | `agent/research/NN-slug.md`          | committed; retired with the tickets citing it                         | detail too long for the ticket that asked, cited                                                                                                                    |
| Prototype         | `agent/prototypes/<slug>/`           | committed; retired with the work it served                            | code that answered a design question + `ANSWER.md`                                                                                                                  |
| Show              | `agent/show/<slug>/`, `<branch>/`    | committed with the round or the landing that made it; retired with the ticket or branch it served | an explanation carried by an artefact                                                                                                                               |
| Handoff           | `agent/handoffs/YYYY-MM-DD-slug.md`  | committed; retired by the session that picks it up                    | a session compacted for a fresh one to start from                                                                                                                  |

`/mx:tracker` defines the file conventions (status, blocked-by, frontier, claiming, the board); the tracker lives in the agent repo, which is a git repo of its own at the project's `agent/`.

## The main flow: intent → ship

The gate picks the first thing you judge: the session drafts the ticket, builds it when the intent has one sensible shape, prototypes the rivals when it has several, and grills it when no brief can be written yet (`/mx:grilling`: relentless interview; each round delivers the design whole and writes it to the ticket; glossary terms and ADRs land as residue). Then the cut into child tickets (tracer-bullet vertical slices with blocking edges, as soon as the interview has no question left for you; `/mx:tracker`) → `/mx:dispatch` works them: a fresh worker per ticket, its contract the prompt dispatch appends to it (testing inside, code-review at the end), serial or in waves, the board as the standing view. Work that is one slice stays one ticket and is dispatched as it is.

**`/mx:orient` is the map**: the gate, the question that routes an intent to loose work or a ticket, the main flow, its on-ramps, and when to reach for what.

Planning that outgrows one session keeps its artefacts: the open questions leave as child tickets that need you, the next session claims one and grills it, and the ticket grows until its frontier is empty.

## What's manual, what's AFK, and why

- **Grilling is where alignment happens on fog**: an intent too unclear to brief is grilled with you in the loop, non-negotiable, until the ticket can be written and a sensible first version built; `/mx:grilling` says what its questions lean to. Everything downstream trades on the shared understanding built there. An intent with one sensible shape skips it: you rule on the build, since a call is judged best in front of the concrete thing, and nothing merges before you do. A call the build rests on that you may want to set is named when it starts; answer it while it runs, or when the landing shows it to you. External inputs (a meeting transcript, a client brief, a bug report) pass the gate like any intent: the foggy ones are grilled through their unstated assumptions.
- **Plan in one window, respect the smart zone.** Grilling (which writes the ticket) → the cut into child tickets stays in one unbroken context window; but reasoning degrades noticeably from roughly 30% of the window used, regardless of advertised size. Approaching the limit mid-planning → end the session with the frontier open (the sharp questions become child tickets that need you) or handoff to a fresh thread; don't push on degraded.
- **The design is reviewed as it is written.** A wrong line of code is one wrong line; a wrong line in the design becomes hundreds of them, so the ticket is where a look pays most. Grilling writes it round by round and you review each round as it lands, the ticket in front of the figures that explain it, both linked from the round's turn on the session page (`/mx:grilling` has the mechanics); writing it down is itself a design step. A ticket assembled across sessions gets one whole-document read before it is cut, for drift between sessions.
- **The ticket breakdown is the agent's.** How a ticket is cut is the agent's call: the cut files the slices `open`, checks their shape itself (vertical, sized to one worker), and the workers start. You judge the built tree at its close-out, which is where a slice too coarse to demo shows up anyway.
- **Proposed tickets wait for your triage.** What an agent files on its own reading (a worker's friction, a review finding, a punt) is `proposed` and stays off the frontier, so the pile gets read together and a pattern across several tickets shows. You start a triage when you want one (`/mx:triage`): the pile is grouped by shared cause, and you drop, merge or promote each ticket. Your own "build this" makes a ticket open at once.
- **The build runs while you are away.** It starts when the interview has no question left for you; every call you have not ruled on stays marked in its ticket, or is an anchored assumption on the review page where a worker made it. A build carrying calls you have not made that change what you asked for waits for your ruling (accept, amend, redo or reject), and you are shown those calls alone, each with the artefact that makes it visible; one carrying none merges into its parent ticket's branch on your standing yes, and into the integration branch only on your word: a ship, merge or accept you give once you have seen it, or up front for a change you named yourself. Either way the landing comes with a show of what was built, for whenever you look, unless the diff alone makes the change plain at a glance. Nothing merges above a parent ticket's branch before you rule. You rule a parent ticket whole, with its children, at its close-out: a child merges into the parent's branch once the orchestrator has read it, and its siblings build on it unruled. A hinge, a child its dependents would have to be rewritten around were it wrong, you rule alone, and its dependents start only after you accept it.
- **Implementation is the AFK part.** Day shift plans and cuts the tickets; night shift works the frontier, fresh context per ticket.
- **QA is where you impose taste, per landed slice.** Manual, deliberately: automate the idea, the planning, *and* the QA and you get slop. Every ticket is a tracer bullet, drivable the moment it lands: the worker builds, tests and reports, and the landing hands you its review page and, unless the diff alone makes the change plain at a glance, one show of what was built, made by a fork of the session that lands it (`/mx:show`). The show opens with the intent and how the parts fit, goes a level lower only where the one above needs it, and a script it leaves that runs the thing gets a button on the ticket's board row; you drive what you want to on your own machine while the remaining frontier keeps running (`dispatch ps` lists every worker on every host, `dispatch peek <slug>` prints one's pane and `dispatch attach <slug>` takes it). Findings become new tickets with blocking edges; the board absorbs them.
- **Reviews run in fresh context.** A reviewer sharing the implementer's window reviews in the dumb zone; a worker closes with code-review in clean context for a reason.
- **A session answers on its page.** Every session you sit at has a page from its first reply, one browser page per session with the questions waiting on you at the top and the turns below, newest first, each linking the artefacts it made. A turn that delivers something (an answer, an artefact, a question, a landing) writes it there as a turn record; a turn that only reports where it stands ends on a line or two in the chat, which the page shows as a chat turn. A turn that writes a record ends on a chat recap of what waits on you, as action items, one plain line each that never points at the page; the questions themselves stay on the page. As the turn ends the Stop hook opens every artefact the turn linked in your browser, and the page with them the first time, or on every turn where the container hub runs (see "The session page, in the hub tab" above). Under the recap it shows one line of its own: the questions waiting on you and the link to the page. When the session ends, a hook commits its records (not the page, which re-renders from them) to the agent repo in a commit of their own, so what a session reported and asked outlives it. The agent writes plain-text turn records and hands every artefact to a subagent or a fork, so no HTML and no render loop fills its context (`mx/skills/session-page/RULES.md`, which `claude/CLAUDE.md` imports into every session).
- **A session page's prose has a reviewer too.** A turn that writes a record for its session page gets one light review the moment the record is written: a model reads it against the chat-scoped rules of `/mx:writing-for-humans`'s catalogue, seeing what you have seen on the page, and hands a few findings back while the turn still runs, so the session revises the record before it writes its recap. It fails open, stays out of a dispatched worker's session, and logs every decision; `mx/skills/session-page/turn_review.py` says where the log goes.
- **Feedback loops are the ceiling.** Agent output quality tracks the quality of the repo's tests and typechecks. Bad output → improve the loops, not the prompt (`/mx:improve-codebase-architecture`; deep modules: design the interface, delegate the implementation).
- **A test earns its place, and the full-path checks run on purpose.** A test holds a behaviour you rely on, pins a bug that reached you, or states an invariant of a seam; one doing none of those is deleted, and one that flakes is fixed or deleted the day it flakes (`/mx:testing`). `make test` is the fast suite every change runs; the full-path checks drive the real thing (a browser on the page, tmux, a paid API) and run when work reaching their path lands, and before a release. Property tests come with architecture work, where stating a seam's invariant is how the seam gets clear; a ticket's properties are prose each review checks the diff against. You read one debrief per tree beside the diff and rule on its proposals: anything an agent files on its own reading is `proposed`, and waits for your triage.
- **Done work gets deleted** (`git rm`). Closed tickets left in the tree are doc rot steering future agents wrong; git history keeps them.

## Skills & commands

| | |
| --- | --- |
| `/mx:orient` | the router; start here |
| `/mx:grilling` | sharpen a plan by interview; the design lands in the ticket as it settles |
| `/mx:domain-modelling`, `/mx:codebase-design` | vocabulary layers: domain language + ADRs, deep-module design |
| `/mx:testing`, `/mx:code-review` | what makes a test worth keeping, and when the full-path checks run; four-axis review |
| `/mx:dispatch` | work a ticket and its children: one orchestrator, a fresh worker per ticket, serial or in waves |
| `/mx:prototype` | throwaway code when shapes are rivals or one has to be driven to be judged |
| `/mx:triage` | the proposed tickets grouped by cause, and each dropped, merged or promoted |
| `/mx:to-questionnaire` | turn a decision someone else must answer into a questionnaire for them |
| `/mx:wizard` | bash wizard walking a human through steps only they can do (credentials, dashboards, migrations) |
| `/mx:wait-what` | that didn't land; re-pitch it in plain language |
| `/mx:show` | show, don't tell; explain via artifact (diagram, comparison, demo, explainer page, …) |
| `/mx:fork` | delegate to an agent that inherits the full conversation |
| `/mx:diagnosing-bugs` | tight-loop debugging for hard bugs |
| `/mx:improve-codebase-architecture`, `/mx:bloat-audit` | codebase health |
| `/mx:research` | primary-source investigation → findings on the ticket that asked |
| `/mx:codex` | second opinion from a different model |
| `/mx:handoff`, `/mx:transcript`, `/mx:recap` | session continuity & status |
| `/mx:writing-for-agents`, `/mx:writing-for-humans` | the writing references: documents that instruct agents (skills, CLAUDE.md, tickets) / artifact text read cold (docs, comments, UI copy) |

Plus assorted utilities: `tmux`, `mermaid`, `tyro-cli`, `project-setup`, `ml`, `house-style`, `session-name`, `restore-sessions`, `permissions-review`, `review-pr`, `github`, `gh-stack`, `expert`, `changelog`, `dependabot-triage`.

---

**Local development:**

```bash
rm -rf ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
ln -s /path/to/mx ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
```

`claude plugin update mx@MaxWolf-01` replaces the symlink.
