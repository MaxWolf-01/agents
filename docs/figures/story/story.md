# The mx workflow

mx is a plugin for Claude Code that runs work too large for one agent session. You say what you want; agents plan it with you, build it in worktrees of their own while you are away, check it, and bring back only the decisions that are yours to make.

The problems it answers are the ones Lauren Tan (poteto) describes in [a conversation with Matt Pocock](https://www.youtube.com/watch?v=MN9dGgmLyso) about shipping 2,500 pull requests a month with agents: relaying by hand between the agent and the browser, agents skipping the rules they were given, intent that stays in your head, and more output than anyone can review line by line.

## The whole workflow

figure: workflow-map

With agents, the bottleneck moves to how clearly you can say what you want, and to how much of what comes back you can check. mx starts every piece of work at a gate that decides how much has to be settled before anything is built, and asks for you only at the numbered stops on the map.

step: 1
An intent typed in chat reaches the gate first. The session drafts a ticket, the file a worker builds from, and the draft shows whether the intent can be built as it stands. One with a single sensible shape is dispatched at once. A worker, an agent that works one ticket unattended in a worktree of its own, builds it while the session stays with you. At the landing the build's calls are sorted, and only the ones that are yours wait for your ruling.

step: 2
The draft can also send an intent down one of three other routes. An intent too foggy to brief is grilled first (`/mx:grilling`): round by round, the agent sets out the design as it stands and asks only the questions that change what gets built. An intent with several sensible shapes gets a prototype or a figure per shape, and you pick between them side by side. Work a stranger could do from one chat line, such as a rename, gets no ticket: the session commits it, and you read it on a review page.

step: 3
Work too big for one worker is cut into child tickets, each a thin slice you can run on its own. A slice that later slices build on, a hinge, is ruled on alone. The rest are ruled on with their parent, after the full test suite and a code review of the whole tree.

step: 4
Every landing is something you can drive. You try it on your own machine while other workers keep going; in a review session your findings become new tickets, and a decision you reopen goes back to grilling.

step: 5
What agents find on their own, such as a worker's friction or a reviewer's finding, is filed as a proposed ticket and waits outside the frontier (the tickets that can be worked now). A triage groups the pile by cause, and only what you promote is built.

step: 6
What outlives every session is on disk: the tickets, with each call marked by who settled it, the glossary of the project's terms, the decisions that are hard to reverse, and the needs-me group on the board, which holds everything waiting on you.

## Planning across sessions

figure: session-boundary

An agent reasons worse as its context fills, well before the window is full, and a plan held in one conversation is gone when the session ends. In mx a plan lives in a ticket, which any later session can pick up where the last one stopped.

step: 1
Each grilling round is one turn on the session page, the page a session answers on. It shows the design as a whole first, then the open questions, each with its options and the agent's pick. You answer by number.

step: 2
The round rewrites the ticket, a markdown file in the agent repo (a git repo of its own inside the project). Every call in the ticket carries a mark saying who made it: you in a given round, the agent (yours to veto), or nobody yet. A call nobody ruled on keeps its mark, so silence never counts as a yes.

step: 3
A session that ends with questions still open files them as child tickets that need you, carrying the options as the last round put them, and commits a handoff. The board shows the questions until you answer.

step: 4
A fresh session picks up the handoff, reads the ticket from the top, claims one of the child tickets, grills it, and writes the answer into the parent ticket. Each session's page records are committed to the agent repo as it ends, so the conversation behind a decision can be read later.

step: 5
When no open question is left, the ticket is cut into child tickets, or built as it stands if it is a single slice.

## A ticket's life

figure: ticket-life

Rules an agent reads in a prompt get skipped, most of all near the end of a task. mx moves the mechanical rules into two scripts, `tracker` and `dispatch`, which refuse what the rules forbid, and leaves the agent only the judgment. [Its principles](https://github.com/MaxWolf-01/agents/blob/master/PRINCIPLES.md) put it as: a script that does the thing beats a paragraph of prompt about it.

step: 1
A ticket's status is a field in its file, and one of five. Proposed: an agent filed it and you have not ruled on it. Open: ruled, not yet built. Claimed: a session or a worker holds it. Review: the build is finished and waits for your ruling. Done: your accept has landed it. `tracker` refuses any move between them that the rules do not allow.

step: 2
Tickets start with you. One you ask for is filed open, since your asking is its ruling, and so are the slices an agent cuts a ticket into. One an agent files on its own reading, such as a worker's friction or a review finding, is filed proposed and waits for your triage, where you drop it, merge it into another, or promote it to open.

step: 3
The orchestrator, the one agent that hands tickets to workers and merges what they build, reads the frontier on every pass of its loop, claims a ticket with `dispatch claim`, and starts a worker on a host it picks. `dispatch` refuses to start a worker on a ticket that needs you, and a worker writes no ticket file: `tracker` refuses one written from a worker's branch.

step: 4
`dispatch review` imports the worker's report into the ticket, renders the review page, and writes review. A question waits in the board's needs-me group until you answer it, and `tracker rule` records your answer.

step: 5
An amend resumes the same worker's conversation on the same branches, so the ticket stays claimed. A redo, or a session that is lost, sends the ticket back to open for a fresh worker.

step: 6
Done is written only once your accept is merged and verified, and `dispatch accept` refuses a tree that still holds an unfinished child ticket. A finished tree leaves the live tracker with `tracker retire`, and git keeps it. Nothing moves back from done: a decision reopened once code depends on it becomes a new ticket that supersedes the old one.

## The board

screenshot: board-overview

With many agents at work, the scarce resource is your own time, and the board shows where it is needed. `board` renders the whole tracker as one page, shown here for a demo project, a small ledger app.

step: 1
region: 0 .06 .72 .53
At the top is the needs-me group: every ticket whose next step takes your own time, whether a build to rule on, a question to answer, or work you do together with an agent. Each open question sits under its row, with a button that copies it.

step: 2
region: .08 .12 .56 .1
Each row says what it asks of you, how long it will take you, and how soon it matters. The time is yours, not the agent's: a ticket a worker spent hours on can be a fifteen-minute ruling.

step: 3
region: 0 .6 .72 .4
Below come the frontier, the tickets that can be worked now, and the claimed ones a worker holds. Nothing there waits on you.

step: 4
region: .74 .06 .26 .58
The briefing on the right is written by a model that has read the tracker: where things stand, and what to take up next.

step: 5
region: .75 .65 .25 .12
Under it is a preview of the dependency graph, the order in which the tickets can be built.

## One ticket opened

screenshot: board-feature

Findings acted on one at a time hide the pattern behind them; read together a few days later, they can show it. In mx, work an agent finds that nobody asked for is filed as a proposed ticket and waits for a triage.

step: 1
region: .07 0 .32 .04
Each chip at the top shows or hides one tree of tickets. Here only the saved-views tree is showing.

step: 2
region: 0 .08 .72 .18
The opened row is a hinge, a child ticket ruled on alone because the tickets after it would have to be rewritten if it were wrong. Its question lists the options and what each one costs.

step: 3
region: 0 .26 .55 .12
Below the question are the sessions that worked on the ticket, each with a button that copies the command to resume it, and the artefacts made for it: here, three rendered takes on the list to choose between.

step: 4
region: 0 .9 .72 .1
At the bottom are the proposed tickets. A triage (`/mx:triage`) groups them by shared cause before you drop, merge or promote each one, so a recurring problem arrives as one group rather than as scattered fixes.

## A landing

figure: landing

Verification is what lets an agent run and inspect its own work, instead of a person relaying between the agent and the browser. And nobody can review everything a group of agents builds, so review has to sample rather than block. When a worker's build lands, mx checks it twice and puts in front of you only the calls that are yours.

step: 1
Three parties take part: the worker, which builds one ticket on any host; the orchestrator, which holds the branch the work merges into; and you, who see only the calls that are yours to make.

step: 2
The worker builds the ticket and tests it as it goes: type checks and single test files, then the full suite and the full-path checks, which drive the real thing, such as a browser on the page (`/mx:testing`). It reviews its own branch with `/mx:code-review` and gives every finding a disposition. Then it commits its report: what landed, each assumption anchored to the line it shaped, the friction it hit, and the questions only you can answer.

step: 3
The orchestrator reads the diff against the ticket and its ancestry, and sends what the brief missed back to the worker. Friction, such as a slow suite or a missing check, is filed as a proposed ticket, so the fix goes into the project or into mx rather than into one worker's next attempt. It imports the report, renders the review page, and sorts the build's calls into three kinds: calls you already made, the agent's own calls about how it is built, and calls that change what you asked for.

step: 4
Only the last kind reaches you. A build with none of those merges on your standing yes, the accept you gave in advance, and is announced in one line. Each call that is yours arrives on the session page with the smallest artefact that shows it, and stays in the needs-me group until you rule. Unless the diff alone makes the change plain, a fork also builds one show, an artefact explaining what was built, and lints and looks at its own render (`render-lint`) before you see it.

step: 5
Your ruling is one of four. Accept merges the build; amend sends your comments back to the same worker; redo discards the build and keeps the ticket for a fresh worker; reject drops both.

## The review page

screenshot: review-page

Reading every line an agent wrote does not scale, and a diff alone does not say why a line is there. The review page puts the worker's reasons on the lines they concern.

step: 1
region: .24 .03 .76 .5
`dispatch review` renders a review page for every landed ticket, linked from its row on the board: a side-by-side diff with a file tree, driven from the keyboard.

step: 2
region: .27 .58 .6 .13
The worker's assumptions appear as agent blocks on the lines they shaped. This one cites the parent ticket's property P2 for why a line that cannot be read is reported rather than dropped.

step: 3
region: 0 .04 .24 .22
A file the worker left alone on purpose is listed as untouched, with its note, so a missing change reads as a decision.

step: 4
region: .67 0 .3 .04
Comments you write on the page export as markdown, to paste back to the agent. Its next report names the comments it addressed.

## Sessions in the hub

screenshot: hub

The corrections you made in past sessions are material for better rules, as long as the sessions are kept. Every session you sit at answers on its session page, and the page's records are committed to the agent repo when the session ends. The [container hub](https://github.com/MaxWolf-01/dotfiles/blob/master/bin/container-hub), a local server from the author's dotfiles and not part of mx, gathers every session's page in one browser tab; the sessions shown are made up.

step: 1
region: .14 .03 .4 .45
A session page holds the questions waiting on you at the top, then the turns, newest first, each linking what it made.

step: 2
region: 0 0 .14 .7
The rail on the left has one entry per session, with its state and the headline of its newest turn.

step: 3
region: .14 .88 .4 .12
When a session's context fills up, it commits a handoff file for a fresh session to start from. The box at the bottom types into the session's terminal, and hands it off once the handoff is committed.

step: 4
region: .54 0 .46 1
The panes on the right hold the pages the session's turns opened: here a figure comparing two answers, and a review page.
