---
status: confirmed
---

# The board a returning user reads

## Problem Statement

After a week away the user cannot read the board. It lists tickets by state and blocking edge, and nothing about what each is, how much it matters, what waits on the user, or which session did the work; recapping it took an agent five minutes and a long chat message (2026-09-22). The calls only the user can make are scattered: a build's questions live at the end of its worker's closing comment on an unmerged ticket branch, other questions float in `needs-human.md` queues belonging to no ticket, and the board's "needs my review" and "needs me" groups split one kind of work in two. A ticket opened on the board is a wall of worker prose. Sessions that touched a ticket are found by keeping tmux panes open. The marks that exist (status colours, a kind badge) do not say what they mean.

Five standalone tickets asked for pieces of this and are absorbed here: priority and size, a brief per ticket with its artefacts linked, one place for what needs the user, the sessions that touched a ticket, and the live state of GitHub links.

## Solution

The board stays one page. A ticket carries what the board needs in its own file: a priority, a size measured in the user's time, a short name, a ticket brief written for the user, and its open ticket questions. The board reads everything else from where it already is: sessions from a `Session:` trailer on every commit, titles from the transcripts on this machine, artefacts from the ticket's show directory, GitHub state from one query per render.

Every question belongs to a ticket. A ticket whose work waits on the user sits in one group, the **needs-me group**: a build to rule on, a ticket stopped on a question, a near design session. Its open questions show under it, each copyable, and an answer clears through a `Ruled:` line. The floating `needs-human.md` queues retire.

A side column opens with the **board briefing**: where things stand and the next picks, written by a model that explores the repo itself, and kept current by pinging that same session with what changed. The dependency graph sits under it as a preview that opens full size.

Rows are calm and legible: the house style with colour where it carries meaning: what the row asks of the user, its priority, its time. Every mark explains itself on hover. An opened ticket reads as structured blocks, not a wall of text.

The prototype that settled the shape: `agent/prototypes/board-orients/` (board v4, and the explainer at `agent/show/board-orients/index.html`, rendered from the demo tracker its `demo-tracker/build.sh` writes).

## User Stories

1. As the user back after a week, I want one sentence saying what waits on me and what is running, so that I know where I stand before reading any row.
2. As the user, I want the next few things to do named, each with why, so that I start where it counts.
3. As the user, I want every ticket's short name and a brief written for me, so that I know what a ticket is without opening it.
4. As the user, I want each row's priority shown as a word I can read (p1 now, p2 next), so that I sort by importance at a glance.
5. As the user, I want each row's size in my own time (20 min, 1 h), so that I pick what fits the time I have.
6. As the user, I want to know what a row asks of me (rule on a build, answer a question, a design session), in the same place on every row, so that I scan a column instead of reading each row.
7. As the user, I want every mark to explain itself on hover in plain words, so that I understand p3 or XL a month from now without a legend.
8. As the user, I want every ticket that waits on me in one group, so that I do not look in two places.
9. As the user, I want a ticket's open questions listed under it on the board, tagged, so that I see what I am being asked without opening the ticket.
10. As the user, I want to copy one question, or all of a ticket's, or all on the board, so that I answer them in any session or in my editor.
11. As the user, I want a copy button to show what it will copy, so that I know what lands on my clipboard.
12. As the user answering by voice in any session, I want the session that takes my answer to record it on the ticket, so that the question clears itself from the board.
13. As the user, I want an answered question gone from "needs me" without anyone cleaning up, so that the group only holds what still waits.
14. As the user, I want a question that belongs to no ticket filed as a proposed ticket, so that nothing floats on the board without a home.
15. As the user, I want the sessions that worked on a ticket listed with their titles, so that I recognise the one I want.
16. As the user, I want a button that copies the command resuming one of those sessions, so that I can close tmux panes freely.
17. As the user, I want only sessions I can resume listed, not workers on other hosts, so that every listed session works.
18. As the user, I want a ticket's demo path and figures on the ticket, so that I never hunt through `agent/show/`.
19. As the user, I want a GitHub link to say whether its pull request is open, merged or waiting on changes, so that I do not open each one.
20. As the user, I want an opened ticket to read as its brief, its questions, what to build, and its acceptance criteria, with the history folded away, so that it is not a wall of text.
21. As the user reviewing a build, I want the ticket as its branch has it, closing comment included, so that I read the worker's account before the merge.
22. As the user, I want to see what a ticket waits on and whether each blocker is done, in words on hover, so that a struck-through number is not a puzzle.
23. As the user, I want the dependency graph readable at full size when I need it, beside the board if I like, so that a tracker with many edges is still a map.
24. As the user, I want the board readable in the day scheme at 100% zoom, so that I do not zoom to 150% to read it.
25. As the user, I want nothing on a row to overlap anything else at any zoom I use, so that the page never looks broken.
26. As the user, I want the board to render when GitHub, the model, transcripts or the review-page server are unavailable, each absence said once, so that the board never fails for a missing extra.
27. As an agent filing a ticket, I want the priority, size, name and brief to be fields I fill at filing, so that the board has them from the start.
28. As an agent, I want to set a ticket's priority from what the user says and change it when they say so, so that the user never ranks tickets by hand.
29. As a worker closing a build, I want my calls for the user to go into the ticket's questions, so that the board shows them without reading my closing comment.
30. As an orchestrator relaying the user's answer, I want to record it as a `Ruled:` line under the question, so that the board and every later session see it answered.
31. As any session committing, I want my session id on each commit without thinking about it, so that the user can trace a commit to the session that made it.
32. As the user, I want the briefing written by a model that has explored the repo, so that it knows more than the tracker's fields say.
33. As the user, I want the briefing kept current as the tracker moves, without a fresh exploration each time, so that it stays current and cheap.
34. As the user, I want the briefing to say when it was written, so that I know whether it is stale.
35. As the user planning a dispatch, I want the next picks to mark which ones can run in parallel, so that a wave is one decision.

## Properties

- A question on the board always belongs to a ticket; nothing on the board floats free of one.
- A ticket is in "needs me" exactly when it is not done and is a build in review, has an open question, or is a design or prototype decision at p1 or p2 that nobody has claimed (amended 2026-09-23, was without "not done").
- A question with a `Ruled:` line under it never shows as open.
- Every mark on a row (what it asks, time, priority, blocker) explains itself on hover in words.
- At zoom 80% to 200% and window widths from 900px up, nothing on the board overlaps or escapes its box.
- A render that finds nothing changed makes no GitHub request and no model call, with two exceptions: a watched board asks GitHub again once its cached answer has lapsed, and a watcher starting where no briefing is cached writes a first one.
- A session listed on a ticket has a transcript on this machine, and its copied resume command resumes it.
- The board renders with any optional source missing (GitHub, the model, transcripts, the review-page server), and says each absence once.
- A copy button shows what it copies.
- A ticket's priority, size, kind and questions are read from the ticket file; the board keeps no side file about a ticket.
- The briefing session is pinged only on a ticket's status changing, once the tracker has gone five minutes without another and no sooner than ten minutes after the last run of the session, and never outlives its idle hour or its ping cap (amended 2026-09-23, was once per debounce window on any tracker change).

## Decisions

### The ticket file

- **Frontmatter gains `priority` and `size`.** Priority 1 to 5, named now, next, soon, later, someday; the agent sets it from what the user has said and changes it when the user says so, and it is never the user's chore. Size is the user's time on the ticket, not the agent's: reading, trying the demo, deciding, learning; XS under 15 min, S about 20 min, M about an hour, L half a day, XL several sessions. All ticket metadata lives in frontmatter.
- **The H1 is the short name**, a few words the board shows in a row; the sentence a title used to carry moves into the brief. Rejected: a `name:` field beside a long H1, which puts two titles on one ticket. Existing long titles render truncated until edited; nothing migrates them.
- **`## Brief` sits right under the H1**: two or three sentences written cold for the user, what it is and why it matters. Prose, not frontmatter, because YAML handles backticks and colons badly. Whoever files the ticket writes it: `/mx:to-tickets` for a slice, the filing session for a standalone ticket, the orchestrator for a proposal.
- **`## Questions` holds the calls only the user can make**, the queue moved into the ticket it belongs to. One item each, tagged with the ticket's running `Dn` sequence, a bold headline and its detail:

      ## Questions
      - [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing.
      - [D2] **Keep the test in the fast suite?** It takes four seconds either way.
        - Ruled 2026-09-21: keep it in the fast suite.

  A question is open until a `Ruled <date>:` line sits under it; the session that relays the user's answer writes that line. A question the ruling on a build leaves open is filed as a proposed ticket then, so a done ticket carries none (you, 2026-09-23). A worker's closing comment keeps its Demo, Assumptions, findings and friction, and its calls go into `## Questions` instead of an "I need from you" list, so the board reads one place.
- **`needs-human.md` retires**. A question with no ticket to hang on is filed as a proposed ticket, and ruling on the proposal is the answer. The existing queue files are migrated once: each entry moves to its ticket's questions or becomes a proposed ticket.

### What the board reads

- **Sessions come from `Session: <id>` commit trailers**, added by a `prepare-commit-msg` hook from `$CLAUDE_CODE_SESSION_ID`, which every Claude Code shell carries. The hook lives in the dotfiles' global git hooks, beside the existing pre-push hook, so it covers every repo on the machine. The board reads `git log --all` for the ticket file, and takes each session's title (the `/rename` name, else Claude Code's own) and working directory from its transcript on this machine; a session with no transcript here, a worker on another host, is left out, because the user does not resume those.
- **A build in review is read from its ticket branch**, `ticket/<feature>/<NN-slug>` or `ticket/<integration branch>/<slug>`, where its questions and closing comment are until the merge.
- **Artefacts come from the ticket's show directory**: the file named `demo` on a copy button showing its path, figures as links. No frontmatter declares them.
- **GitHub state**: the board resolves every `gh` reference in one GraphQL query per render, cached beside the board with a short lifetime, so the watcher's cadence makes one request rather than one per reference; no network or no `gh` auth leaves the links bare and says so once.
- **Review pages** are linked once per row, on the address diffview serves them on.

### The board

- **Groups**: the needs-me group, frontier, claimed, blocked, proposed, done (folded). "Needs my review" folds into the needs-me group; review stays a ticket status.
- **A row has fixed columns**: feature, number (a click copies the file's path), what the row asks, the name with its review link and GitHub references, the brief under the name, the user's time, priority, blockers. What the row asks is one of: to rule on, your answer, design session, prototype, research, legwork, build. Below a width the row reflows, time and priority moving under the name, so nothing overlaps at any zoom.
- **Marks carry colour where it carries meaning**: a tinted tag for what the row asks, a pill with a word for priority, the time in its own hue, taken from the mwolf.dev callouts and deepened for the day scheme. The prototype's teal for time reads off and is picked again against both schemes. Links stay the house accent, except a GitHub reference, which wears its pull request's state.
- **Every mark explains itself on hover** in words: what p1 to p5 mean and who sets them, that the time is the user's and what each size stands for, what the row asks, and for a blocker "waits on 01, done" or "not done yet".
- **The day scheme is readable at 100% zoom**: body text and small text sized up and contrasted for parchment; the night scheme already reads.
- **Questions show under their ticket in needs me**, tag and headline, each with a copy button; a ticket's "copy all" and the group's "copy all" copy every open question with its tag and ticket path, for pasting into an editor. A copy button shows what it copies, truncated: the resume command, the question's tag and headline, the path.
- **An opened ticket reads as blocks**: its questions (each with its detail and its own copy button; the list under the row's name goes while the row is open, so each question is read once), sessions, artefacts, what to build, the acceptance criteria as a checklist, and the comments folded as history.
- **The side column**: the briefing, then the dependency graph as a preview of the whole tracker or the cursor's feature. The preview opens the graph full size in an overlay on the board, pannable, a click on a node closing it on that row; the overlay also opens as its own window, to sit beside the board. Rejected: a bigger panel, which takes the rows' width for a view needed now and then.
- **House style**, both schemes, with the scheme switch.

### The board briefing

- **A briefing session writes it.** The first run is a fresh `claude -p` session on a short prompt of its own, never the user's system prompt: it is given the tracker's state as the board computes it (tickets with status, priority, size, brief and questions; recent landings) and explores the repo freely from there, commits, code and docs alike. It writes where things stand and three next picks, each with a reason, marking picks that can run in parallel as one wave for dispatch. The model picks; no rule does.
- **The session is pinged, not rerun.** A ticket's status changing, a new ticket and a retired one included, is sent to the same session with `--resume` as a short note of what changed, five minutes after the last status to move and no sooner than ten minutes after the last run of the session (amended 2026-09-23 on [The board briefing](09-briefing.md)'s D2, was any tracker change debounced by five to ten minutes); a ticket edited without its status moving is re-rendered and not sent. The session decides whether the briefing needs rewriting and what to look at for it (recent commits, a ticket, the code), building on what it already explored. The session retires after an idle hour or a cap on pings, whichever comes first, and the next change starts a fresh one. The board's watcher hosts the debounce; a board rendered once without watching shows the last briefing.
- **The cache file** beside the board holds the briefing, the time it was written, and the session's id, start, last activity and ping count, which the retirement rule reads. The board shows the time written.
- **Cost rests on the prompt cache.** A ping inside the cache's lifetime rereads the session's context at the cached price; the build confirms which lifetime the plan in use gives (five minutes by default, an hour where the longer cache applies) and sets the idle limit to match. A ping after the cache has lapsed still costs less than a fresh exploration.
- **The session runs on Opus 5.5 at medium effort, and without the user's output style**, which shapes a reply for a human at a terminal, as every noninteractive run does.
- **Fallback**: with no model available, or before the first briefing exists, the board writes the deterministic sentence the prototype does (counts of builds, questions, design sessions, running work) and orders next by priority, then what accepting unlocks, then the user's time.

### Where the workflow changes

- **Tracker**: the ticket file's new fields and sections, `needs me`, the retired queue, the `Ruled:` line.
- **To-tickets, grilling, dispatch, the worker contract**: a filed ticket carries priority, size, brief; a worker's calls go into `## Questions`; an orchestrator records an answer as `Ruled:`.
- **Dotfiles**: the `Session:` trailer hook; outside this repo, so not a worker's.
- **Glossary**: ticket brief, board briefing, ticket question, needs-me group, ticket priority and ticket size join `CONTEXT.md`; a ticket brief and the board briefing are two things with two names.

### Deferrals

- **The graph overlay's pan and zoom**: an interchangeable part behind a settled seam; a plain scrollable full-size SVG is the default if nobody picks a library.
- **The exact day-scheme sizes and hues**: agent taste, checked against both schemes with `render-lint` at several widths; if nobody decides, the prototype's values plus the readability fix stand.

## Testing Decisions

- **The board's loader and page** (`test_board.py`, the existing seam): a fixture tracker on disk in, groups, rows and marks out. Oracle: the tracker conventions and this spec's Decisions. New checks: frontmatter priority and size, the H1 as name, the Brief and Questions sections, a `Ruled:` line clearing a question, needs-me membership, sessions from trailers with a transcript present and absent, GitHub state from a stubbed query, the briefing fallback.
- **The rendered page's layout**: `render-lint` over the demo tracker, promoted from the prototype's `demo-tracker/build.sh` into the tests' fixtures, at several widths and both schemes. Oracle: the no-overlap Property.
- **The watcher's pass** (`look`, in `test_board.py`): the tracker, the cache files beside the page and the clock in; whether one pass renders, pings the session or asks GitHub again out. It carries what a fresh session is given, what a change tells it, and the board's own count. Oracle: the Properties on unchanged renders and on pings.
- **The browser probe** (`test_board_layout.py`): the rendered page driven in headless Chromium, for what lives in the page's script and style: hover explanations, the graph's overlay, the copy buttons, and what an opened row hides. Oracle: the no-overlap Property and the Decisions on marks and the graph.
- **The briefing session's schedule**: whether a status change pings the session, waits out the quiet window or the cadence, or retires the session and starts a fresh one, as a pure function of the cache file's state, the change's time and the clock, with `claude` stubbed as the review script's demo stubbed it. Oracle: the Property on pings and retirement. Its first clause, that only a status reaches the session, is not a property of that function: it is checked at the watcher's pass, over both halves of the tracker (amended 2026-09-23).
- **What a run of the briefing is launched with**: the model, the effort, the settings and the system prompt, read off the arguments a stubbed `claude` records. Oracle: the Decision above. What a launch really carries to the API is read off the wire by `agent/show/board-orients/16-briefing-cadence/demo`, which no check runs.

Properties:

- A question always belongs to a ticket: **reviewed**.
- Needs me membership: **executable**, at the loader seam.
- A ruled question never shows as open: **executable**, at the loader seam.
- Every mark explains itself: **reviewed**.
- No overlap from 80% to 200%, 900px up: **executable**, at the layout seam.
- No request or model call on an unchanged render: **executable**, at the loader seam with the query and `claude` stubbed.
- A listed session has a local transcript: **executable**, at the loader seam.
- Renders with every optional source missing: **executable**, at the loader seam.
- A copy button shows what it copies: **reviewed**.
- Ticket metadata only from the ticket file: **reviewed**.
- Pings and retirement of the briefing session: **executable**, at the schedule seam.

## Out of Scope

- An input box on the board that takes rulings: a ruling typed into a page reaches no agent until one reads it; copy and paste into a session does.
- A separate briefing page: the board is the page.
- Grouping standalone tickets by theme: the prototype's `themes` were a sketch for the rejected briefing page; features already group work.
- A `name:` frontmatter field: the H1 is the name.
- One tracker for all repos: its own ticket, [One tracker for all of a user's repos](../one-tracker-per-user.md).

## Fog

None.
