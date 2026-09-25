---
status: done
parent: board-orients
blocked-by: [board-orients-rows]
priority: 1
size: M
diff: [bb7bea673d3ec6454daff2e8fd41c34ddf9f555f..5fb0de9bab8c857d94212cf0dd1935a2f9238ccd]
---

# Ticket questions and the needs-me group

## Brief

Every question lives on its ticket and shows under it in one needs me group, copyable one at a time or all at once; an answer recorded under a question clears it from the board.

Slice of the parent ticket, building on the Decisions on `## Questions`, a build in review read from its ticket branch, the groups, questions under their ticket, and copy buttons.

## What to build

The board reads a ticket's `## Questions`: each item tagged `[Dn]` with a bold headline, open until a `Ruled <date>:` line sits under it. A build in review is read from its ticket branch (`ticket/<feature>/<NN-slug>`, or `ticket/<integration branch>/<slug>` for a standalone ticket), where its questions and closing comment are until the merge. One group, needs me, holds every ticket that is not done and is a build in review, has an open question, or is a design or prototype decision at p1 or p2 that nobody has claimed; the separate "needs my review" group goes. Under each needs-me row its open questions show as tag and headline, each with a copy button that shows what it copies; a ticket's "copy all" and the group's "copy all" copy every open question with its tag and ticket path, for pasting into an editor.

The board keeps reading the `needs-human.md` queues until ticket 10 migrates them.

## Acceptance criteria

- [x] The needs-me and ruled-question checks from 01 pass and their annotations are gone.
- [x] `board-orients#P1`, reviewed: a question on the board always belongs to a ticket.
- [x] `board-orients#P9`, reviewed: a copy button shows what it copies.
- [x] `board-orients#P10`, reviewed: a ticket's questions are read from the ticket file.
- [x] Demo: the demo tracker's needs me group; a group "copy all" pasted into a file; a question cleared by adding a `Ruled` line.

## Comments

The board reads a ticket's `## Questions` and shows the open ones under its row, in one needs-me
group that the old "needs my review" folds into; each question copies on its own, a ticket's copy
together, and the group's all at once. A build in review is read from its own ticket branch, where
the worker's questions and closing comment are until the merge, while the tracker's copy keeps
saying where the ticket stands and is where a `Ruled` line answers a question. On branch
`ticket/board-orients/03-questions-and-needs-me`, not merged.

Two things beyond the ticket's text: what a row asks when a decision ticket has an open question,
which is the seam 02 left open and nothing settles (D1), and the two skill sentences that named the
group that has gone (A10). One thing the ticket's own text defers: no ticket in this repo's tracker
carries a `## Questions` section yet, since a worker's calls reach one only when ticket 10 changes
the contract, so this repo's board shows a needs-me group with no questions under any row. The demo
is on the demo tracker, which has them.

**Demo**

Three legs, from a checkout on this branch:

    $ repo=$PWD
    $ uv run mx/skills/tracker/demo_tracker.py /tmp/board-demo
    /tmp/board-demo/agent/tickets
    $ cd /tmp/board-demo && $repo/mx/bin/board agent/tickets --no-watch --no-open
    /tmp/board-demo/agent/board.html

*The needs-me group.* Open `/tmp/board-demo/agent/board.html`. One group holds everything waiting
on you: eight rows, the queue entry among them until ticket 10 retires it, and no "needs my review"
group anywhere. Under each row its open questions, tag and headline: three under `02 Map columns
once per bank`, whose ticket file in the checkout has none: they are on its branch
`ticket/csv-import/02-map-columns`, with the closing comment the row folds open. Hover `D1` for what
a tag is, the headline for the question's full words, any `copy` for what it will copy. `The flaky
upload test` shows `D1` and not its `D2`, which a `Ruled` line answered. Rows that ask you a question
say `your answer`; `Retire the QIF exporter` says `design session`, since that question is the
session (D1).

*A group "copy all" pasted into a file.* Click `copy all 10 questions` beside the group's heading
and paste. Ten questions in seven blocks, each under the path of the ticket it is on, as markdown:

    /tmp/board-demo/agent/tickets/csv-import/02-map-columns.md
    - [D1] **Remember the mapping per bank or per file name?** Per bank asks one more question on the first import; per file name breaks when a bank renames its export.
    - [D2] **Amounts with a comma as the decimal separator** are read as thousands today. Guess from the file, or ask once per bank?
    - [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?

*A question cleared by a `Ruled` line.* Answer one the way a session would, at the path the button
just handed you:

    $ printf '  - Ruled 2026-09-23: hyphen-dt, the small one.\n' >> /tmp/board-demo/agent/tickets/pick-a-date-library.md
    $ cd /tmp/board-demo && $repo/mx/bin/board agent/tickets --no-watch --no-open

Reload: `A date library` has left needs me for the frontier, and the group's button reads `copy all
9 questions`. (`board agent/tickets` without `--no-watch` re-renders the open tab on the edit
instead.)

**I need from you**

- [D1] **What a decision ticket's row asks when a question is open on it.** 02 left `asks()` the
  flag and no precedence, and the seven words need one. As built: a grilling or a prototype keeps
  its word (`design session`, `prototype`) whether or not its question is written down, because
  sitting down together *is* that work; research and legwork yield to an open question and say
  `your answer`, because an agent does those alone and a question is what stopped it. The reading
  it replaces, where any type always shows its type, put rows in needs me reading `research`, whose
  own hover words say "An agent reads up on this alone", telling you it waited on nobody. The third
  reading, an open question always winning, would leave `design session` on no row of the demo
  tracker at all.
- [D2] **The group's "copy all" ignores the feature filter.** Hide a feature with its pill and the
  group's count drops while the button still says, and copies, every open question on the board
  (user story 10, "all on the board"). The button now names its unit so the two numbers are not
  read as one, but if you want the filter to narrow what it copies, that is a change to make.
- [D3] **01's needs-me property states the rule by re-typing it.** Its check enumerates every
  ticket shape and compares `needs_me` against the same boolean written out in the test, so it
  cannot disagree with a misreading of the spec, and its fixture has no row that only the "near
  design session" clause or the "not done" amendment puts in or out of the group. Two of the review
  axes proposed the same fix: two more tickets in the demo tracker and two more ids in the
  property's `NEEDS_ME` literal. A slice may not edit a property, so I wrote a check of my own
  beside it (A12) and left the property as 01 has it; whether that literal is 01's to strengthen,
  or the next slice's, is yours to say.

**Details, if you want them**

- [D4] Assumptions
  - A1 `mx/skills/tracker/board.py:971`: `asks()`'s precedence, the seam 02's A8 left: the two
    decision types the user sits in keep their word ahead of an open question, the two an agent
    takes away yield to one (D1).
  - A2 `mx/skills/tracker/board.py:606`: a build in review takes its questions and its closing
    comment from its branch; its status, priority, size and brief stay the tracker's copy, so a
    branch that never flipped its own status cannot pull a build out of needs me, and a row shows
    the checkout's brief over the branch's questions.
  - A3 `mx/skills/tracker/board.py:746`: a `Ruled` line in the tracker's copy answers a question
    the branch asks. The board hands out that path on the clipboard, so it is where the session
    taking your answer writes; the branch is the worker's and does not move again before the merge.
  - A4 `mx/skills/tracker/board.py:792`: a feature ticket reads only `ticket/<feature>/<NN-slug>`;
    a standalone ticket's integration branch is not knowable from its file, so the sole branch
    ending in its slug is its own, and an ambiguous one is named on stderr rather than as an
    absence on the page: a ticket at `review` need not be a build with a branch at all, so the note
    would fire on ordinary states (a declined finding).
  - A5 `mx/skills/tracker/board.py:1165`: the questions sit inside the row's name column, under the
    brief, rather than in a row of the summary's own grid, so they take the width the name has and
    a row without them grows no taller.
  - A6 `mx/skills/tracker/board.py:1120`: what a button copies is the ticket's path and its
    questions, one line of markdown each, whitespace collapsed; what it shows on hover is the first
    220 characters of exactly that.
  - A7 `mx/skills/tracker/board.py:1104`: the group's button copies every open question on the
    board whatever the filter hides (D2).
  - A8 `mx/skills/tracker/board.py:1096`: a ticket's copy-all appears only from two questions up,
    since with one it copies what the button beside it does.
  - A9 `mx/skills/tracker/board.py:756`: `## Questions` stays in the text that folds under the row,
    where the row shows only the open ones' headlines; ticket 04 owns what an opened ticket reads
    as.
  - A10 `mx/skills/tracker/MARKDOWN.md:27`: two sentences in the tracker conventions and the
    dispatch skill named the group that has gone, so they name the one that replaced it; everything
    else the workflow has to learn is ticket 10's.
  - A11 `mx/skills/tracker/board.py:240`: the watcher's snapshot carries the ticket branches' tips,
    since a worker cutting a branch or committing on one moves no file under the tracker, and its
    questions are what the board would otherwise never show.
  - A12 `mx/skills/tracker/test_board.py:985`: the needs-me clauses the demo tracker has no row for
    get a check of their own at the same seam, rather than an edit to 01's property (D3).
  - A13 `mx/skills/tracker/test_board_layout.py:163`: the browser probe grew the question marks and
    the copy buttons, and clicks one to read the clipboard back. 02's A12 said a reviewed Property
    about something a browser does wants a browser in the loop; this is the second half of that
    Property and of "a copy button shows what it copies".
  - A14 `mx/skills/tracker/demo_tracker.py:335`: the demo tracker gains a research ticket with no
    question, so the word `research` still has a row on the board after A1.
- [D5] Findings, from `/mx:code-review` over `20bc2a7..9d6e857`, four axes, reports in
  `agent/reviews/20bc2a7..9d6e857/`
  - Fixed in `5d29344`: a `Ruled` line written at the path the copy button hands out never cleared
    the question, for exactly the tickets this slice is about (correctness 1); `Ruled` taking any
    token as its date, so an ordinary "Ruled out:" rationale silently closed a question and could
    drop a ticket out of needs me (correctness 2); only the first `## Questions` section being read,
    though appending a second is how a worker's questions reach a ticket (correctness 3); the
    property check for "a copy button shows what it copies" passing a button that showed nothing
    (tests F1) and asserting the cap against itself (F3, standards S11); the note after a click
    pinned only by its length (F4); `open_questions` meaning two things at once, a trap for 04
    (spec C1, tests d6); `copy all 1` beside the one `copy` it duplicated (spec C4); the needs-me
    clauses with no fixture row (tests F6) and the parser shapes the generated check cannot draw
    (F5), both as checks beside the properties rather than edits to them; the branch read's
    negative cases, the watcher's new term and the cache clear, none of which had a check (tests
    d1-d5); the clipboard's fidelity and the row's own markup (d7, d8, d9); the click handler that
    no test drove (d10); `qtag` carrying no hover words while both `MARKS` lists stayed as they
    were, so the "every mark explains itself" guard had stopped covering the row (standards S1,
    spec's reviewed Property, tests c); a feature ticket able to read another feature's branch
    (standards S6); the ticket-branch naming rule written four times and the refspec twice (S2);
    the `--help` restating a Property already amended once (S3); `repo` threaded as an optional
    argument whose omission silently read the wrong copy (S5), now the tracker's own checkout
    (S4); three sibling class names where the file answers with base and modifier (S7); `account`'s
    name and the third copy of the frontmatter-to-brief read (S8); two docstrings the reader had
    falsified (S9, spec C5); a test regex coupled to attribute order (S10); `qhead` and `qcopy`
    outside the browser probe (S12, spec A1); `clipped`'s flag bool (S14); a stale palette comment
    (S15); `copy_button`'s first parameter named `kind`, which means a ticket type everywhere else
    in the file (S16); and the group's coupling to `GROUPS` left unwritten (spec C6).
  - Declined, with the reason in the assumption it stands on: an absence note for a build in review
    whose branch the board cannot find (spec C2) -> A4; the group's copy-all against the feature
    filter (spec C3) -> A7 and D2; 01's enumeration re-typing the implementation (tests F2) -> A12
    and D3; a `Roots` refactor through the two loaders that take a feature directory rather than a
    tracker (standards S4's second half) -> those two learn a repo, not a tracker; `- [D1]` written
    with two spaces or a `*` bullet (spec C7) -> the format is the spec's own.
- [D6] Friction
  - `board` still cannot render this repo's own tracker on a dispatch worker host, where the main
    checkout is the bare repo the worktrees hang off (01's friction, 02's again). Worse for this
    slice, which reads branches: the clone I rendered from needed every branch fetched into
    `refs/heads/*` before a ticket branch existed to read, which is a detached-HEAD dance and about
    ten minutes. A `board --tracker <path> --repo <path>` that trusts what it is given would have
    made the real board a one-liner.
  - The check carrying a reviewed Property passed a button that showed nothing, and what found it
    was a reviewer hand-writing 32 mutations of `board.py`. `make harden` measures that per feature
    when the frontier empties, which is after every slice that could have used it; a worker cannot
    ask "which of my new lines can I delete with the suite green" without writing the harness
    itself.
  - Two axes proposed the same strongest fix, and the worker contract forbids it: strengthening a
    property's fixture is indistinguishable, to the rule and to the orchestrator's grep, from
    weakening it. I wrote a parallel check instead, which costs a second fixture and leaves the
    property's own fixture symmetric in the dimension it tests. A stated way to hand a property
    edit back to whoever owns it would have been cheaper than either.
  - Playwright reaches the clipboard only through a context permission, and without it
    `navigator.clipboard.writeText` returns a promise that never settles, so the page's own note
    never appeared and the check failed with nothing to read. One browser run is a minute, so each
    guess costs one.
