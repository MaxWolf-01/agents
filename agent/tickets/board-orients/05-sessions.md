---
status: review
blocked-by: [04]
priority: 2
size: S
---

# The sessions behind a ticket

## Brief

An opened ticket lists the sessions whose commits changed it, each with its title and a button that copies the command resuming it; only sessions you can resume on this machine show.

Slice of `spec.md`, building on the Decision on sessions from `Session:` commit trailers.

## What to build

The board reads the `Session:` trailers of every commit that changed the ticket file, on every branch, and lists each session with its first and last commit. The title is the session's `/rename` name, else Claude Code's own title, and the working directory comes from its transcript on this machine; a session with no transcript here, a worker on another host, is left out. Each listed session has a button showing and copying `cd <dir> && claude --resume <id>`. With no trailers, the ticket lists no sessions and says nothing.

## Acceptance criteria

- [x] The listed-session and render-without-transcripts checks from 01 pass and their annotations are gone.
- [x] Property, reviewed: a copy button shows what it copies.
- [x] `test_board.py` covers trailers across branches, a transcript present and absent, and a renamed session's title.
- [x] Demo: the demo tracker's ticket with three sessions in its commits, two listed and the worker's left out, and a copied resume command run.

## Questions

- [D1] **The session that built a ticket is never the one the ticket lists.** A dispatched worker runs on another host, whose transcripts are not on your machine, so what a landed build shows is the sessions that filed and claimed it, never the one that wrote the code. That is what the spec asks for (story 17, "only sessions I can resume listed"), and the block now says *sessions on this machine* so the short list explains itself. Reaching the worker's session at all means its transcript travelling back with its branch, which is a ticket of its own.
- [D2] **The board-wide copy-button check cannot see the resume button.** 01's check of the reviewed Property pins the kinds of button on the board and asserts each one's note names the file it copied from (`the demo's path`, `D1 of flaky-upload-test.md`). A resume command has no file, so its note names the session (`the command resuming Grilling the CSV import`) and the new button has a check of its own instead of joining that one. Either the note rule becomes per-kind and one check covers all five buttons, or the two checks stand.
- [D3] **A renumbered ticket starts its session list at the rename.** The log is read in one pass over the whole repo and keyed by path, and git's rename following works on neither a repo-wide pass nor `--all`, so a slice renumbered when a breakdown is re-cut keeps only the sessions that committed on its current name. Leaving it costs a short list on a renamed ticket; following renames costs a git call per ticket and still cannot see across branches.

## Comments

An opened ticket lists the sessions whose commits changed its file, under *sessions on this
machine*: the title each session carries, the days it committed on the ticket, and a button that
copies the command resuming it. They come from the `Session:` trailer on every commit, read in one
pass over every branch, and are named by their transcript under `$CLAUDE_CONFIG_DIR/projects`; a
session with no transcript here is a worker on another host and is left out, which on a dispatched
build is the session that wrote the code (D1). On branch `ticket/board-orients/05-sessions`, not
merged.

**Demo**

    agent/show/board-orients/05-sessions/demo

builds the demo tracker, renders its board against the tracker's own transcripts, prints the page
and says what to click. From a checkout on this branch:

    $ agent/show/board-orients/05-sessions/demo
    /tmp/board-demo/agent/board.html

    Open the page above and click "Map columns once per bank" in needs me.

    Under *sessions on this machine* are the two of its four sessions this machine can name:

        Grilling the CSV import         2026-09-14                  copy resume
        Dispatching csv-import, wave 1  2026-09-17 -> 2026-09-18     copy resume
    ...

Open `/tmp/board-demo/agent/board.html` and click that row. Four sessions committed on the ticket;
the two above are listed, the worker that built it on another host is not, and the fourth never
touched this ticket. Hover either button for the command it copies, and click it:

    cd /tmp/board-demo && claude --resume a1f3c9e2-4b7d-4e21-9c35-7d2e8f1b6a04
    claude --resume b52e7d10-9a3c-4f68-8e17-3c9b2a5d4e81

The second has no `cd` because the feature worktree it ran in is gone, which is where every locally
dispatched session ends up. Both sessions are the fixture's invention, so running either answers
`No conversation found with session ID: …`. What a command of that shape does against a session
that exists, run here on this host:

    $ cd /tmp/sstest && claude -p --resume 4ed6973f-d461-4235-a60c-2faf6df02c3c "Reply with exactly: RESUMED"
    RESUMED

Your own tracker is where both halves meet: its commits carry your sessions' trailers, and their
transcripts are on the machine you read the board on.

**Details, if you want them**

- [D4] Assumptions
  - A1 `mx/skills/tracker/board.py:869`: a session whose working directory is gone is listed all the
    same, and its command is `claude --resume <id>` with no `cd`. The ticket asks for `cd <dir> &&
    claude --resume <id>`; `claude --resume` finds a session from wherever it is run (checked on
    this host), and dispatch removes the worktree a session ran in, so the alternative was to drop
    every locally dispatched session from the list.
  - A2 `mx/skills/tracker/board.py:1078`: the block is labelled *sessions on this machine*, which is
    the prototype's wording, so a list shorter than the ticket's commits says why (D1).
  - A3 `mx/skills/tracker/board.py:902`: the log is read once for the whole repo, not once per
    ticket, and keyed by each file's path from the top of its checkout, which is the name every
    worktree gives it. One git call per render instead of forty (0.08s over this repo's 1038
    commits). A merge commit names no file, so a merge that resolved a conflict in a ticket does
    not put its session on that ticket; a renamed ticket keeps only its current name's sessions (D3).
  - A4 `mx/skills/tracker/board.py:1638`: the transcripts absence is said whenever the transcripts
    directory is missing, whatever the tracker's commits carry, where the review-page note beside it
    is withheld when there was nothing to serve. A missing directory is a fact about the machine
    rather than about this tracker; saying it only when a trailer named a session nothing could
    resolve is the other reading.
  - A5 `mx/skills/tracker/demo_tracker.py:42`: the demo tracker's sessions now ran in the demo repo
    itself and in a feature worktree beside it that dispatch has removed, so a copied command cds
    somewhere that exists and the removed-worktree case is in the fixture. Its transcripts moved to
    `claude/projects` under the fixture, a `CLAUDE_CONFIG_DIR` of its own, which is how the demo
    points the board at them.
  - A6 `mx/skills/tracker/test_board_layout.py:69`: both layout property checks now render the demo
    with its own transcripts, so the block this slice adds is inside the no-overlap Property and the
    hover probe rather than beside them. Their assertions are untouched; only the input carries the
    block. They are 02-rows' checks.
  - A7 `mx/skills/tracker/board.py:1638`: `absences` reads `TRANSCRIPTS` itself rather than taking it
    as an argument (a review finding). That global is the one home for where this machine keeps
    transcripts, and threading it through `render` and `render_page` for one boolean would add a
    parameter to a signature five checks call directly.
  - A8 `mx/skills/tracker/board.py:881`: `ticket_sessions` keeps its `transcripts` parameter, which
    only 01's property check passes (a review finding). That check is this seam's oracle and not
    mine to edit; everything else steers the same fact by the global.
  - A9 `mx/skills/tracker/board.py:952`: the branches the suite cannot tell from their absence are
    left as the review listed them: escaping a title that carries markup, a transcript line
    truncated mid-write, which of two transcripts of one session wins, and author date against
    committer date. Each needs a fixture shaped for it alone, and none changes what the board shows
    on the trackers this repo has.
- [D5] Findings, from `/mx:code-review` over `a870b72..99366d1`, four axes, reports in
  `agent/reviews/a870b72..99366d1/`
  - Fixed in `c34f990`: a session attributed to any file sharing its name and its directory's name,
    which this repo's committed fixture trackers already collide with (correctness 1, spec C1, tests
    d7); a date range rendering backwards, since the walk is in commit order while the dates are the
    author's (correctness 3, spec C5); a resume command dying on the `cd` into a worktree dispatch
    had removed (correctness 2); the sessions block sitting outside the layout Property and the
    hover probe, which both render the demo without its transcripts (correctness 4, spec A3 and A4,
    standards 12, tests F2); the dead `Ticket.sessions` and `Standalone.sessions` fields and the
    defaulted `worked` parameter (standards 3, spec B1 and B2, tests F5); the `repo is None` guard
    duplicated at both call sites where `branch_text` answers it in the callee (standards 4); the
    leaving-out rule restated in three docstrings and the log key's in two (standards 1); a
    transcript with no working directory read as a worker on another host (standards 2, spec C3);
    the block's label dropping the prototype's "on this machine" (standards 2); the stride-3 zip
    over a NUL-split log, which turned out to be hiding a bug — `git()`'s strip eats a leading
    `\x1e` and the first commit in the repo went missing with it, which the look-alike check caught
    (standards 7); the prefilter's hand-cut `"Title"` key (standards 9); the hanging-indent
    signature (standards 10); `path_with` missing from the new render checks (standards 11);
    `shlex.quote` on a fixture where every path was quote-free (standards 13, tests d3); the
    `demo = transcribed` alias the same commit contradicted (standards 8); the title falling back to
    the session id, with no session too new to have one (tests d4); the module caches surviving
    between checks (tests F3); the render-time cache clear with no check of its own (tests d1); a
    resume command longer than a button shows, which the new check could not have seen (tests F1);
    a docstring restating another check's fixture (standards 6); the comment speculating about a
    squash carrying two sessions (spec B3); `demo_tracker.transcript` returning a path nobody reads
    (standards 3).
  - Declined, with the reason in the assumption it stands on: the board-wide copy-button check not
    reaching the new button (standards 6, tests F1) → D2; `absences` reading the global (standards
    5) → A7; the `transcripts` parameter being test-only (tests F4) → A8; a renamed ticket losing
    its old name's sessions (spec C2) → A3 and D3; the transcripts note's rule against the
    review-page note's (spec C4) → A4; the long tail of unreachable mutations (tests d5, d8, d11,
    d12, d13, d14) → A9; `.sessions .stitle` without `overflow-wrap` (standards 12) → two reviewers
    measured a title of 88 characters at 450px and found nothing, and the layout check now measures
    the block at fourteen widths.
- [D6] Friction
  - The fixture's sessions cannot be resumed, so the ticket's own demo criterion is unrunnable as
    written: a transcript the board can read is not a transcript `claude --resume` will open, and
    making one would mean inventing the conversation format rather than the two records the board
    reads. What I could run was the shape against a real session on this host. A demo of this kind
    wants the machine the sessions are on, which is the orchestrator's, not a worker's.
  - `board` still cannot render this repo's own tracker on a worker host: the main checkout is the
    bare repo the worktrees hang off (01, 02, 03 and 04 all said so). I cloned the worktree into
    `/tmp` to see the board this slice changes against real trailers, which is also how I found that
    every trailer on this tracker names the orchestrator's session and none of them resolves here.
    `board --tracker <path> --repo <path>` that trusts what it is given would have saved that.
  - Four reviewers found four things a run would have found and one it would not: every finding I
    fixed on the correctness axis was reproducible in a scratch repo in under a minute, and the one
    that mattered most (a session attributed to a look-alike file) became a two-line fixture change.
    The reviewers reproduced them; I had not thought to. A finder that mutates the new lines and
    runs the suite, which is what `make harden` does per feature, would have caught the dead field
    and the unexercised `shlex.quote` before the review.
  - Hypothesis still prints `git apply .hypothesis/patches/...` after every `make test` while an
    expected failure stands (01 said so). It will keep doing that until 07 and 09 land.
