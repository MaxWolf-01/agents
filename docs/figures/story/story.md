# The mx workflow

mx is a plugin for Claude Code that every piece of work goes through, from the intent you type to the merge. It keeps one overview of all the work in flight, runs many agents in parallel, hands the steps that need no judgment to scripts, and brings you only the decisions that are yours, each shown as something you can look at.

A machine makes every check a machine can make, and your attention goes to design decisions and taste, at the numbered stops on the map below. Agents work in an environment that checks their work before it reaches you: tests, scripts that refuse what the rules forbid, a reviewer with a fresh context. What does reach you comes as a figure, a rendered page or a build you can run, so judging it takes less reading.

Some of the problems mx answers, and some of its principles, are described well elsewhere: by Lauren Tan (poteto) in a conversation with Matt Pocock, written up as [Lauren Tan (poteto) on the trust ladder, verification and shipping 2,500 PRs a month](https://share.mwolf.dev/2fe77089ce57b60a1882d8875b4cec85/), and by Matt Pocock in two talks, [Software Fundamentals Matter More Than Ever](https://youtu.be/v4F1gFy-hqg) and [Full Walkthrough: Workflow for AI Coding](https://youtu.be/-QFHIoCo-Ko). Earlier inspiration came from [State of Agentic Coding with Armin Ronacher and Ben Vinegar](https://www.youtube.com/watch?v=9UAxrdcDjjU&list=PLg3sejGUAdUZMKADp-KCcC6m5qKjD88bT), Armin Ronacher's [agent-stuff](https://github.com/mitsuhiko/agent-stuff) and the [diagram-design](https://github.com/cathrynlavery/diagram-design) skill.

## The whole workflow

figure: workflow-map

Lauren Tan, in the conversation above, puts the bottleneck at how clearly you can get your intent across to the agent. mx starts every piece of work at a gate, where the session drafts a ticket, the file a worker builds from; how far that draft gets decides what has to be settled before anything is built.

step: 1
An intent typed in chat reaches the gate, and the session drafts a ticket for it. An intent with one sensible shape is filed and dispatched at once: a worker, an agent that works one ticket unattended in a worktree of its own, builds it while the session stays with you.

step: 2
When the build lands, only the calls that change what you asked for are put to you, each with the smallest artefact that makes it visible, and you accept, amend, redo or reject. A build that carries none goes ahead on your standing yes, the accept you gave in advance.

step: 3
An intent too foggy to brief is grilled first (`/mx:grilling`). The skill is adapted from Matt Pocock's Grill Me; in Software Fundamentals Matter More Than Ever he says he wrote it because he and the agent did not share an idea of what they were building. The design lands in the ticket as it settles, and the build starts once no question is left.

step: 4
An intent with several sensible shapes gets a throwaway prototype or a concept figure per shape, and you pick in front of the renders; the verdict goes into the ticket. Matt Pocock's walkthrough does the same for front-end work, asking for three prototypes to click between.

step: 5
Work a stranger could do from one chat line, such as a rename, gets no ticket, no worker and no agent review. The session commits it, you read the diff on a review page, and it merges on your word.

step: 6
Work bigger than one worker is cut into child tickets, each a vertical slice through every layer it touches, and they go through the same dispatch, workers and landing into the parent's branch. Matt Pocock's walkthrough says why vertical: an agent left to itself builds layer by layer, and gets no feedback on the whole until the last layer is done.

step: 7
A slice the later slices build on, such as an interface or a data shape, is a hinge. It is ruled on alone, so a wrong one is caught before anything depends on it.

step: 8
Once the last slice has landed, the close-out runs the full suite and a code review of the whole branch, where an incoherence between slices shows, and writes a debrief.

step: 9
You rule on the tree once, on the calls the debrief puts to you. A single child ticket can still be amended, redone or rejected on its own.

step: 10
Every slice can be driven the moment it lands. You try it on your own machine while the remaining tickets keep running, and what you find becomes new tickets. Matt Pocock's walkthrough calls this QA, the step where he puts his own taste into what was built.

step: 11
A review session is held as soon as there is something to drive. You use what landed and dump your findings raw; the agent fixes the defects and writes your verdicts onto the tickets.

step: 12
A decision you reopen goes back to grilling, and the new ticket supersedes the old one.

step: 13
What agents find on their own, such as a worker's friction, work a build deferred, or a reviewer's finding, is filed as a proposed ticket. It waits outside the frontier, the tickets that can be worked now.

step: 14
A triage, which you start (`/mx:triage`), groups the proposed tickets by shared cause, and you drop, merge or promote each. Only what you promote is built.

step: 15
What outlives every session is on disk. The tickets carry the design, with every call marked by who settled it.

step: 16
The glossary holds the terms grilling settled, so you, the agents and the code use the same words. In Software Fundamentals Matter More Than Ever, Matt Pocock calls this a ubiquitous language, after domain-driven design.

step: 17
Decisions that are hard to reverse are kept one per file. A changed decision gets a new file that supersedes the old one.

step: 18
The needs-me group on the board holds every open ticket question and every build waiting in review, so between sessions everything that waits on you is in one place.

## Grilling across sessions

figure: session-boundary

An agent reasons worse as its context fills, well before the window is full. Matt Pocock's walkthrough calls the two stretches the smart zone and the dumb zone, and he clears the context rather than compacting it. In mx a plan lives in a ticket, which a fresh session picks up where the last one stopped.

step: 1
An idea too foggy to brief goes from the gate to grilling first.

step: 2
Each grilling round is one turn on the session page, the page a session answers on. It sets out the design as a whole, then asks only the questions where two options survive, and you answer by number. A question of taste comes as a blind test: you pick between samples of each option without knowing which option made which.

step: 3
While a round waits on your answer, the session carries a dot in the list of sessions on the hub, the page shown in the last chapter.

step: 4
Every round rewrites the ticket, a markdown file in the agent repo, a git repo of its own inside the project. The design is on disk from the first round.

step: 5
Each call in the ticket carries a mark saying who made it. A call nobody ruled on keeps its mark, so silence never counts as a yes, and a call the agent made stays yours to veto.

step: 6
A session that ends with questions still open files them as child tickets that need you. Each carries the options and the agent's pick as the last round put them, and names the sections of the ticket its answer may rewrite.

step: 7
A question has two numbers: Qn while it is asked on the session page, Dn once a ticket holds it, which is the number the board and `tracker rule` use.

step: 8
The session commits a handoff, a file a fresh session starts from, which you can read and correct first. Once it is committed, the hub marks the session ready and can start the fresh one.

step: 9
The fresh session claims one of the child tickets, reads its comments first, and grills it. The answer lands on the parent ticket, marked with the child's name.

step: 10
Before it grills, it reads the parent ticket from the top: the brief, the marks, what is still foggy, the child tickets still open.

step: 11
From there it runs rounds like any other. The same loop covers one session or many, and how many is found out on the way.

step: 12
When no question is left, a ticket that several sessions wrote is read whole once, since each session saw only its part. Then it is cut into child tickets, each filed open, or built as one slice, and calls nobody ruled on keep their marks.

## A ticket's life

figure: ticket-life

Agents take shortcuts, Lauren Tan says in the conversation above, so she takes the deterministic parts of her skills out into code and leaves the agent only what needs judgment. mx does the same with two scripts, `tracker` and `dispatch`, which refuse any move the rules forbid. [Its principles](https://github.com/MaxWolf-01/agents/blob/master/PRINCIPLES.md) put it as: a script that does the thing beats a paragraph of prompt about it.

step: 1
A ticket is one file in the agent repo, and its status is a field in that file. One an agent files on its own reading starts proposed: nobody has ruled on it, and it stays off the frontier.

step: 2
Promoted, it is open: ruled on, not yet built. An open ticket that nothing blocks is on the frontier, the tickets that can be worked now.

step: 3
Claimed means a session holds it, and a worker resumed to revise its build still does. Where several agents run at once, one of them alone writes claims.

step: 4
Finished, it is in review: the build is done and waits for your ruling. `tracker` refuses any move between statuses that its rules forbid.

step: 5
Your accept, given or standing, makes it done once the work has reached the branch your accept merges it into. Nothing moves back from done.

step: 6
The board marks each status the same way and adds one, blocked: open, but held by a ticket not yet done. A done ticket appears there only as a blocker, for context.

step: 7
A ticket you ask for is filed open, since your asking is its ruling. A decision reopened once code depends on it becomes a new ticket that supersedes the old one.

step: 8
When an agent cuts a ticket into slices, each slice is filed open as its child, since the cut is the agent's call. You judge the built tree at its close-out.

step: 9
What the orchestrator finds on its own, a worker's friction, work a build deferred, a finding of the review one level up, it files as proposed with `tracker new`. Filing is not a ruling.

step: 10
A triage is yours to start (`/mx:triage`). It groups the proposed tickets by shared cause, and you drop, merge or promote each; saying "build this" promotes one at once.

step: 11
A dropped ticket leaves the live tracker. Its file stays in git, with the reason in the commit that took it out.

step: 12
On each pass the orchestrator reads the frontier: open tickets nobody holds, that nothing blocks and that do not need you. `dispatch` refuses to start a worker on a ticket that needs you.

step: 13
It plans the wave: tickets that touch disjoint files run together, and tickets that share a surface go to one worker in turn. Each ticket's host is picked as its worker starts.

step: 14
`dispatch claim` writes claimed, and the worker starts from a prompt. The ticket and its ancestry are its whole brief.

step: 15
Each worker runs in a worktree of its own, on the branch `ticket/<slug>`. It builds, reviews its code and finishes by committing its report; it writes no ticket file.

step: 16
`dispatch review` imports the report into the ticket, renders the review page and writes review. A child ticket that is no hinge merges into its parent's branch as soon as the orchestrator has read it.

step: 17
Your ruling is accept, amend, redo or reject, on the calls the landing shows you. A build with none of your calls merges on your standing yes.

step: 18
A question waits in the board's needs-me group until you answer it, and `tracker rule` records the answer. One you give while the build runs reaches the worker when it resumes.

step: 19
An amend takes the ticket from review back to claimed: `dispatch ctl resume` gives your comments to the same worker, which revises on the same branches.

step: 20
A resumed worker continues its own conversation, with your guidance or the word "continue", never a recap. The ticket stays claimed throughout.

step: 21
A redo discards the build and keeps the ticket, which goes back to open with your reason.

step: 22
A worker whose session is lost is cleaned up with `dispatch ctl cleanup`, and its ticket goes back to open. The ticket carries everything a fresh worker needs.

step: 23
A reject drops the ticket with `tracker drop`, your reason in the commit message.

step: 24
Done is written only once your accept is merged and verified. `dispatch accept` refuses a tree that still holds a child ticket neither done nor merged.

step: 25
`tracker retire` takes a finished tree out of the live tracker, and git keeps it.

## The board

screenshot: board-overview

With many agents at work, what runs short is your own time, and the board shows where it is needed. `board` renders the whole tracker as one page, shown here for a demo project, a small ledger app.

step: 1
region: 0 .06 .72 .53
At the top is the needs-me group: every ticket whose next step takes your own time.

step: 2
region: .25 .18 .26 .035
Each open question sits under its ticket's row, with a button that copies it to paste into a session.

step: 3
region: .17 .13 .08 .44
The tag on each row says what the ticket asks of you: a build to rule on, a question to answer, or work you do together with an agent.

step: 4
region: .5 .13 .07 .44
The time is how long the ticket will take you, not the agent: a build a worker spent hours on can be a fifteen-minute ruling.

step: 5
region: .565 .13 .065 .44
The priority beside it says how soon the ticket matters: now, next, soon or later.

step: 6
region: 0 .6 .72 .17
Below comes the frontier, the tickets that can be worked now. Nothing there waits on you.

step: 7
region: 0 .8 .72 .2
Then the claimed tickets, each held by a session or a worker.

step: 8
region: .75 .07 .25 .57
The briefing on the right is written by a model that has read the tracker: where things stand, and what to take up next.

step: 9
region: .75 .65 .25 .11
Under it is a preview of the dependency graph, the order in which the tickets can be built.

## One ticket opened

screenshot: board-feature

Lauren Tan has one of her agents append the bad patterns it finds to a document instead of fixing them, and reads the document every few days: read together, the findings show patterns that fixing them one at a time would miss. In mx, work an agent finds that nobody asked for is filed as a proposed ticket and waits for a triage.

step: 1
region: .08 0 .29 .03
Each chip at the top shows or hides one tree of tickets. Here only the saved-views tree is showing.

step: 2
region: .01 .08 .71 .095
The opened row is a hinge, a child ticket ruled on alone because the tickets after it would have to be rewritten if it were wrong.

step: 3
region: .02 .175 .52 .08
Its question sets out the options, what each one costs, and which later ticket builds on the pick.

step: 4
region: .02 .26 .5 .058
Below are the sessions that worked on the ticket, each with a button that copies the command to resume it.

step: 5
region: .02 .32 .52 .052
Then the artefacts made for it: here, three rendered takes on the list to choose between, and the command that serves them.

step: 6
region: 0 .91 .72 .09
At the bottom are the proposed tickets. A triage (`/mx:triage`) groups them by shared cause before you drop, merge or promote each, so a recurring problem arrives as one group rather than as scattered fixes.

## A landing

figure: landing

Lauren Tan calls verification the most important skill: the agent runs and inspects its own work, where she had been the "meat proxy" between her agent and Chrome DevTools. At her volume she samples the agents' changes rather than reviewing each one, which Matt Pocock sums up in the same conversation as sampling instead of blocking. In mx a landed build is read by two agents before it reaches you, and you see only the calls in it that are yours.

step: 1
Three parties take part: the worker, the orchestrator and you. The two agents act first, and you only where the build holds a call of yours.

step: 2
The worker tests as it goes, with type checks and single test files, then runs the full suite and every full-path check its host can drive, such as a browser on the page (`/mx:testing`).

step: 3
Meanwhile the orchestrator idles, with a watcher on each worker in the background. Its mark on the hub says nothing there needs you.

step: 4
The worker reviews its own branch with `/mx:code-review`, whose reviewers each start with a context of their own; Matt Pocock's walkthrough points out that a reviewer sharing the implementer's context reviews in the dumb zone. Every finding gets a disposition.

step: 5
Then it writes its report: what landed, the criteria it meets, its friction, each assumption anchored to the line it shaped, and the questions only you can answer.

step: 6
Committing the report is the worker's last act, so a committed report is the sign it has finished.

step: 7
The orchestrator starts on the landing: it checks which workers have exited and fetches their branches. A worker that left no report is resumed, after its log has said how the run ended.

step: 8
It reads the diff against the ticket and its ancestry. It holds the whole tree, so a detail the brief missed is its to catch, and a criterion the build missed goes back to the worker.

step: 9
It files the punts, the work the build deferred: each becomes a question on its ticket or a proposed ticket waiting for your triage.

step: 10
`dispatch review` imports the report: the questions and assumptions enter the ticket, the review page shows the worker's reasons on the lines they concern, and the ticket waits in review.

step: 11
A child ticket ruled with its parent merges into the parent's branch on this read, so its siblings build on it. Its calls wait for the parent's close-out.

step: 12
It sorts the build's calls into three kinds: calls you already made, the agent's own calls about how it is built, and calls that change what you asked for.

step: 13
A build with nothing yours to make merges once it has the yes its merge needs: your standing yes for a hinge, your word for work going into the integration branch, the one the whole project merges into. You get one line about it, with the show and the review page.

step: 14
Each call that is yours becomes a question on its ticket and arrives on your session page with the smallest artefact that makes it visible. A forked agent builds one show, an artefact explaining what was built, around them all.

step: 15
Only now does the orchestrator need you. The board's needs-me group holds the build until you rule, and this is the one point in a landing that asks for you.

step: 16
You rule on the page or in a line of chat, and `tracker rule` records each answer on the ticket. The orchestrator goes back to work.

step: 17
Accept merges the build with `--no-ff` and runs the project's verification. A failing run or a conflict goes back to the worker, which rebases and reports again.

step: 18
Amend sends your comments back to the same worker, which revises on the same branches. A revision that only applies your comments is accepted without a second round; a new call it makes is sorted again.

step: 19
Redo discards the build and keeps the ticket, back to open with your reason, for a fresh worker.

step: 20
Reject drops the ticket with its build, your reason in the commit message.

## The review page

screenshot: review-page

Asked in his walkthrough how to keep up with the code agents produce, Matt Pocock expects to do more code review and says he does not know the answer yet. In mx a landing puts in front of you only the calls that are yours, and the review page is where you go when you want the code: it puts the worker's reasons on the lines they concern.

step: 1
region: .25 .045 .735 .55
`dispatch review` renders a review page for every landed ticket, linked from its row on the board: a side-by-side diff of the ticket's branch.

step: 2
region: 0 .06 .235 .115
The file tree on the left marks each changed file as added or modified, with a bar for how much of it changed.

step: 3
region: 0 .175 .235 .075
A file the worker left alone on purpose is listed as untouched, with its note, so a missing change reads as a decision.

step: 4
region: .28 .59 .58 .11
The worker's assumptions appear as agent blocks on the lines they shaped. This one cites the parent ticket's property P2 for why a line that cannot be read is reported rather than dropped.

step: 5
region: .42 0 .26 .04
Each control in the bar names its key, so the page is driven from the keyboard.

step: 6
region: .74 0 .22 .04
Comments you write on the page export as markdown, to paste back to the agent. Its next report names the comments it addressed.

## Sessions in the hub

screenshot: hub

Lauren Tan calls past chats a treasure trove of context: the times you corrected an agent are what to turn into skills and lint rules. Only kept sessions can be mined. Every session you sit at answers on its session page, and the page's records are committed to the agent repo when the session ends. The [container hub](https://github.com/MaxWolf-01/dotfiles/blob/master/bin/container-hub), a local server from the author's dotfiles and not part of mx, gathers every session's page in one browser tab; the sessions shown are made up.

step: 1
region: .143 .15 .25 .33
A session page holds the questions waiting on you at the top, each with its options and the agent's pick.

step: 2
region: .143 .48 .25 .42
Below them are the session's turns, newest first, each linking what it made.

step: 3
region: 0 .14 .14 .56
The rail on the left has one entry per session, with its state and the headline of its newest turn.

step: 4
region: .143 .9 .4 .033
When a session's context fills up, it commits a handoff file for a fresh session to start from.

step: 5
region: .143 .93 .4 .07
The box at the bottom types into the session's terminal, and hands the session off once the handoff is committed.

step: 6
region: .54 0 .19 1
The panes on the right hold the pages the session's turns opened. This one is a figure comparing two answers to a question.

step: 7
region: .73 0 .27 1
This one is the review page of a build that landed.
