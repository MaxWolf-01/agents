---
status: review
blocked-by: [03]
priority: 1
size: S
---

# An opened ticket reads as blocks

## Brief

Opening a row shows the ticket as blocks, not a wall of text: its brief, its questions with their detail, its artefacts, what to build, the acceptance criteria as a checklist, and the comments folded away as history.

Slice of `spec.md`, building on the Decisions on an opened ticket and on artefacts from the show directory.

## What to build

A user opening a row reads, in order: the brief once, the questions each with its detail and answered ones marked answered, the artefacts (the demo's path on a copy button that shows the path, the figures in the ticket's show directory as links), what to build (or the question, for a decision ticket), the acceptance criteria as a checklist, and the comments folded until opened. A build in review shows its branch's text, closing comment included. Nothing declares artefacts in frontmatter; the show directory is read.

## Acceptance criteria

- [x] Property, reviewed: a copy button shows what it copies.
- [x] `test_board.py` covers the block order, a folded comments section, and artefacts read from a show directory.
- [x] Demo: the demo tracker with a build in review and a ticket stopped on a question opened, in both schemes.

## Comments

An opened row is the ticket as blocks: its questions with the detail the row has no room for and
the ruling on each answered one, its artefacts, then the ticket's own sections in the order the
file writes them, with the comments folded away as history and the acceptance criteria read as the
checklist they are written as. The artefacts come from the ticket's show directory, read rather
than declared: the file named `demo` on a button that copies its path, every other file as a link.
On branch `ticket/board-orients/04-opened-ticket`, not merged.

Two things the ticket's text does not settle and nobody else owns: where a ticket's show directory
is and who writes it (D1), and that a build in review shows no artefacts at all, because its demo
is on its branch and the board reads the disk (D2). The block exists and is tested; on this repo's
own tracker it appears on no row until D1 is answered.

**Demo**

From a checkout on this branch:

    $ repo=$PWD
    $ uv run mx/skills/tracker/demo_tracker.py /tmp/board-demo
    /tmp/board-demo/agent/tickets
    $ cd /tmp/board-demo && $repo/mx/bin/board agent/tickets --no-watch --no-open
    /tmp/board-demo/agent/board.html

Open `/tmp/board-demo/agent/board.html` and click two rows in *needs me*.

*A build in review*, `02 Map columns once per bank`. It has one of every block, in this order:
**questions**, three, each with the detail its row cuts; **artefacts**, the demo path with a `copy
path` button that shows on hover exactly what it will copy and `mapping.svg` as a link; **what to
build**; **acceptance criteria**, one ✓ and one ○ — the ✓ came from the ticket's own branch, where
the worker ticked it, as did the questions; **comments**, folded. Click `comments` for the closing
account the branch carries. Hover a ○ or a ✓ for what it means, and the `D1` beside a question for
what a tag is.

*A ticket stopped on a question*, `The flaky upload test`. Its row lists one question; opened, it
has both, and `D2` reads `Ruled 2026-09-21: keep it in the fast suite.` with its tag and headline
given way — an answered question stays as history. It has no artefacts block: nothing has been
built on it.

*Both schemes.* The switch at the top right, or `?theme=day` / `?theme=night` on the address. Then
reload with the comments open: they come back open, as an opened row does.

**I need from you**

- [D1] **Where a ticket's artefacts live, and who writes them there.** The board reads
  `agent/show/<feature>/<NN-slug>/`, and `agent/show/<slug>/` for a standalone ticket, which is the
  shape the prototype settled and the demo tracker writes. `/mx:show` and `/mx:orient` both say
  `agent/show/<slug>/` with no feature and no ticket number, ticket 10's scope does not cover it,
  and the spec says only "the ticket's show directory". Rendering this repo's own tracker today
  gives zero artefacts blocks across forty rows and eleven show directories, all of them named for
  a feature or a topic. Two I would defend: the skills learn the per-ticket path (a line in
  `/mx:show`, and the worker contract's Demo pointing at it), which is what "the ticket's show
  directory" means; or the board falls back to the feature's own directory, which puts one demo on
  every row of the feature and keeps the skills as they are.
- [D2] **A build in review shows no artefacts, which is the row the block exists for.** The ticket's
  text comes from its branch while its show directory is read from the disk, where an unmerged
  demo is not. Three ways out: `dispatch review` checks the show directory out of the branch tip
  beside the status flip, which also makes the path on the clipboard a path that exists; the board
  resolves the branch's worktree and links into it, which holds only while that worktree is there
  and never for a worker on another host; or the board says the absence in words rather than
  rendering nothing. The first is the one I would build.
- [D3] **The brief is not one of the blocks, though the spec's Decision lists it first.** It stays
  on the row, where it is read without opening anything, which is 02-rows' A6 and still unruled.
  The ticket asks for "the brief once" and this is the reading that keeps it once. Either the
  spec's line gets the amendment or a later slice repeats the brief inside the body.

**Details, if you want them**

- [D4] Assumptions
  - A1 `mx/skills/tracker/board.py:984`: the show directory's path shape, `agent/show/<feature>/<NN-slug>/`
    and `agent/show/<slug>/`, taken from the prototype and written nowhere else (D1).
  - A2 `mx/skills/tracker/board.py:974`: the demo is the file named `demo` and nothing else; every
    other file under the directory is a figure link, however deep, except under `out/`, which is
    where a demo writes what it regenerates.
  - A3 `mx/skills/tracker/board.py:875`: the block order. The questions and the artefacts stand
    above the ticket's own sections, which keep the file's order, and the comments sink to the end
    whatever place the file gives them. The sessions block the spec lists between them is 05's.
  - A4 `mx/skills/tracker/board.py:880`: the brief is on the row and not repeated in the body (D3).
  - A5 `mx/skills/tracker/board.py:751`: a question carries the words of the ruling that answered
    it, not only its date, so the block shows what was decided and not only that it was.
  - A6 `mx/skills/tracker/board.py:887`: whatever a `## Questions` section says besides its items
    is the ticket's own and stands above them, rather than being dropped with the section.
  - A7 `mx/skills/tracker/board.py:774`: the fence masking reaches into 03's `read_questions` as
    well as the new section scan, so a closing comment that quotes a ticket's shape does not ask
    the board's questions. It is a slice's edit to the slice below it, on one shared reading.
  - A8 `mx/skills/tracker/board.py:248`: the watcher learns the show directories, since an artefact
    landing moves no file under the tracker.
  - A9 `mx/skills/tracker/board.py:1756`: the checklist's glyph and the block's tag carry hover
    words, though the reviewed Property scopes "every mark explains itself" to the row's marks: ✓
    against ○ is the mark a cold reader could read either way.
  - A10 `mx/skills/tracker/demo_tracker.py:143`: the demo tracker's build in review gains a second
    criterion and ticks it on its branch, so the checklist has a met and an unmet case and the
    ticked one proves the branch is what the board read.
  - A11 `mx/skills/tracker/demo_tracker.py:510`: the fixture commits the show directory on `master`
    while the questions stay on the branch, which is the post-accept world rather than the one
    dispatch produces; it stays as it is until D2 says what the pre-accept world should look like.
- [D5] Findings, from `/mx:code-review` over `5fb0de9..a86f3bd`, four axes, reports in
  `agent/reviews/5fb0de9..a86f3bd/`
  - Fixed in `a5fa3ba`: prose under `## Questions` dropped from the page (correctness 5, spec C3,
    tests 12); a `##` line inside a fenced block splitting a ticket into broken blocks, and with
    the same masking a quoted `- [Dn]` item read as a real question (correctness 4); a loose
    criteria list leaving raw `[ ]` on screen (correctness 6, spec C4); `out/` listed as artefacts
    where the prototype excluded it (correctness 2); the checklist glyph saying met or not met in
    no words, and the block's tag dropping the words its row twin carries (spec d, tests c); the
    lists' `padding: 0` losing to `.body ul` on specificity (standards 2); the comments a reader
    opened lost on the next render (standards 3); curly apostrophes in the new tip (standards 4);
    `.qtag` duplicated by `.asked .tag` and `.artefacts a` restating `.body a` (standards 5); the
    ticket's prose taken out of the body's vertical rhythm (standards 6); `--accent-2` on a ruling
    against both the house style's role for it and the comment beside it (standards 7); the
    unexercised default on `Question.answer` (standards 8); the artefacts check reading a flat
    two-file directory, which is symmetric in the dimension the code varies, and pinning neither
    the order nor the count (tests a, d1-d4); the ruling's words crossing from the tracker's copy
    to the branch's question, which no check reached (tests d5); a question with no detail, a
    checkbox outside the criteria, and a ticket with no comments, none of which had a check (tests
    d6, d10, d14); the two `"<h2>Brief</h2>" not in page` assertions the blocks left unfalsifiable,
    and the `.body h2` rules dead with them (tests a); the question parts compared as a dict, which
    could not see their order (tests 13).
  - Declined, with the reason in the assumption it stands on: a build in review reading its
    artefacts from its branch (correctness 1, spec C1) -> D2; the show directory's path shape
    (correctness 3, spec C2, standards 1) -> D1 and A1; the brief as a block (spec A1) -> A4 and
    D3; a section written after `## Comments` keeping its place (spec C5) -> A3, since what is
    folded away is read last; a `demo/` directory read as a wall of links (spec C6) -> A2, the demo
    is a file to run; `Question.ruled` and `answer` as one `Ruling` value (standards 8) -> the
    invariant is read in one place and the property below them names `ruled` by that name; one map
    from heading to treatment in place of the three that dispatch on it (standards 9) -> the three
    treatments differ in kind, so the map would be indirection for three cases; the demo path shown
    both in the artefacts block and in the closing comment under it (standards 10) -> the worker
    contract's, and ticket 10's if anyone's; the per-branch show directory in the watcher, which no
    check reaches (tests d11) -> the main checkout's is pinned and a worktree's artefact lands one
    render late.
- [D6] Friction
  - `board` still cannot render this repo's own tracker on a worker host (01, 02 and 03 all said
    so). This slice made it sharper: the whole question of whether the artefacts block ever appears
    on a real tracker could only be answered by copying the repo into a scratch repo, which is what
    the review had to do. `board --tracker <path> --repo <path>` that trusts what it is given would
    have made it a one-liner, and would have surfaced D1 in the first ten minutes instead of the
    last hour.
  - What found the real gaps in my tests was a reviewer hand-writing 24 mutations of `board.py`;
    twelve survived, and five of those were worth fixing. `make harden` measures exactly that, once
    per feature when the frontier empties, which is after every slice that could have used it. 03
    said this too. A worker cannot ask "which of my new lines can I delete with the suite green"
    without building the harness itself.
  - A tooltip's containing block is decided by CSS, and the only way to see it is a browser run of
    about a minute, so each guess costs one. Two of the review's findings were of that kind.
  - I cannot open a browser for the user, so "in both schemes" is a headless screenshot I read
    myself. That works for judging a render but not for driving one: the demo above is written for
    a machine that has a browser.
