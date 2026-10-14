# The mx workflow in pictures

How a piece of work moves through mx, a plugin for Claude Code, from an intent typed in chat to code you have accepted, told with the figures and screenshots of its README.

mx keeps work that spans many agent sessions in files: tickets in an agent repo (a git repo of its own inside the project), a glossary, decision records, and one page per session. "You" is the person the agents work for. Click a picture to open it over the page, then drag to pan, scroll or pinch to zoom, press 0 to fit it and Esc to close it.

The source is [mx on GitHub](https://github.com/MaxWolf-01/agents/tree/master/mx). [Its README](https://github.com/MaxWolf-01/agents/blob/master/mx/README.md) carries these pictures with longer descriptions, and [`/mx:orient`](https://github.com/MaxWolf-01/agents/blob/master/mx/skills/orient/SKILL.md) is the same flow as the agents read it.

## The flow at a glance

image: one-flow

Every piece of work starts as an intent in chat. The gate drafts a ticket first, and the draft decides what you judge first: an intent too foggy to brief is grilled, one with several sensible shapes is prototyped or drawn side by side, and one with a single sensible shape is built. One question then decides how much of it lands on disk: would a stranger need a brief to build this right? If not, the work is loose and the session commits it itself, with no ticket. If so, it becomes a ticket for a worker (an agent that works one ticket in its own worktree, unattended), or a ticket cut into child tickets with a worker each when it is bigger than one worker can take.

## The whole map

image: workflow-map

This is the same flow drawn as a transit map, with every route the gate can send an intent down. The main line is one ticket built by one worker; fog, rival shapes, loose work and work bigger than one worker leave it only where they need a step of their own. The numbered stops are the only places the workflow asks for you, and the key under the map says what each one asks. Between sessions, everything waiting on you sits in the board's needs-me group, shown further down.

## Planning that spans sessions

image: session-boundary

A foggy intent is grilled in rounds. Each round is one turn on the session page (the page a session answers on), holding the design as it stands and the open questions that are yours to answer, and it rewrites the ticket. Every call in the ticket carries a call mark saying who settled it: you, in a given round; the agent, for you to veto; or nobody yet. A session that ends with questions still open files them as child tickets that need you, and a later session claims one, grills it and writes the answer onto the parent ticket. Once the frontier is empty, with no open question left, the ticket is cut into child tickets, or built as it stands when it is one slice.

## A ticket and its status

image: ticket-state

A ticket is one markdown file in the agent repo, and a `parent:` line makes it the child of another, so tickets form trees. Its status is one of five: proposed (an agent filed it and you have not ruled on it yet; it is built while your ruling waits), open, claimed, review and done. A worker never writes a ticket file; the orchestrator, the one agent that hands tickets to workers and merges what they build, imports the report each worker commits. A build in review waits for your ruling: accept, amend, redo or reject.

## Where each status is written

image: ticket-flow

This figure gives each of the five statuses the command that writes it and the place that command is typed: a session you sit at, the orchestrator, or a worker host. `dispatch claim` writes claimed, `dispatch review` writes review once the worker's report is fetched, and done is written only after your accept has merged the work. The lines going back are the ways out of a build that missed: an amend resumes the same worker, while a redo or a lost session resets the ticket to open for a fresh one. Nothing moves back from done; a decision reopened once code depends on it is filed as a new ticket that supersedes the old one.

## The board

image: board-overview
source: docs/figures/board-fixture/build.py

`board` renders the whole tracker as one page, here for a demo project, a small ledger app. At the top is the needs-me group, every ticket whose next step is your own time: a build to rule on, a ticket stopped on a question, a ticket you work through together. Each open question sits under its row with a button that copies it, and each row says what it asks of you, how much of your time it takes and how soon it matters. Below come the frontier (what can be worked now) and the claimed work. The column on the right is the board briefing, written by a model that has read the repo, over a preview of the dependency graph.

## One tree, one ticket opened

image: board-feature
source: docs/figures/board-fixture/build.py

Each chip at the top shows or hides one tree of tickets; here a single tree is showing, and its dependency graph is the one on the right. The opened row is a hinge, a child ticket ruled alone because its dependents would have to be rewritten were it wrong. Opened, it shows its question with the options, the sessions that worked on it with a button copying the command that resumes each, its artefacts, and its acceptance criteria.

## A landing

image: landing

A worker builds and tests the ticket, reviews its own branch, and commits its report last: a closing comment, the assumptions it made, and the questions only you can answer. The orchestrator reads the diff against the ticket, imports the report, and sorts the build's calls into three kinds: those you already made, the agent's own about how it is built, and those that change what you asked for. Only the last kind reaches you, each with the smallest artefact that makes it visible; a build with none merges into its parent ticket's branch on your standing yes, the accept you gave in advance. Every landing also comes with one show, an artefact that explains what was built, unless the diff alone makes the change plain.

## The review page

image: review-page
source: docs/figures/board-fixture/build.py

Every landed ticket gets a review page, rendered by `dispatch review` and linked from its row on the board. It is a side-by-side diff with a file tree, driven from the keyboard. The worker's notes sit in the diff as agent blocks on the lines they explain, including on a file it left alone on purpose, which the file tree lists as untouched. Comments you write on the page export as markdown, to paste back to the agent that wrote the code.

## The session page, in the hub

image: hub
source: docs/figures/hub-fixture/build.py

Every session you sit at answers on its session page: the questions waiting on you at the top, then its turns, newest first, each linking what it made. The [container hub](https://github.com/MaxWolf-01/dotfiles/blob/master/bin/container-hub), a local server in the author's dotfiles and not part of mx, gathers every session's page in one browser tab; the sessions in this screenshot are made up. On the left is a rail with one entry per session, showing its state and the headline of its newest turn. Beside it is the selected session's page, with a box that types into that session's terminal and hands it off to a fresh session once its handoff is committed; the panes on the right hold the pages its turns opened.

## The whole cycle

image: full-cycle

Put together, an intent goes round this cycle. Grilling sharpens it into a ticket; once the frontier is empty the ticket is cut into child tickets, a worker builds each, and the tree closes out with the full test suite, a code review of the whole tree, and the orchestrator's debrief. Each landed slice comes with its review page, one show and your QA, where you drive what landed on your own machine. The review session, held once something is first drivable, is where your findings re-enter as new and proposed tickets, reopened decisions and new ideas. The board carries every ticket, and the glossary and the decision records in `decisions/` hold what outlives them.
