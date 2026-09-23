---
status: done
blocked-by: [13]
priority: 2
size: XS
diff: [298cff22a7e82f4ed7eda573db85e6b9b0cdcc72..f969633f8b5e8ed81968699d4c4f917175fef392]
---

# An opened row shows its questions once

## Brief

An opened row lists its questions twice: under the row, with a headline and a copy button each, and again in the questions block, with their detail. While the row is open, the list under it goes, and the questions block carries each question's copy button beside its detail.

Ruled by the user on 2026-09-23 (D77, "once"), from the orchestrator's before/after of an opened row. It waits on 13 only because both edit `board.py`.

## What to build

When a row is open, the question list under its summary is hidden, and the questions block shows a copy button on each open question, copying what the row's button copied. A folded row keeps its list as it is. The row's "copy all" moves with the list.

## Acceptance criteria

- [x] An opened row shows each open question once, with its detail and a copy button that shows what it copies.
- [x] A folded row is unchanged.
- [x] Demo: an opened row before and after, with where-to-look notes.

## Questions

- [D1] **An opened row now has no button that copies all of its questions.** "The row's copy all moves with the list" reads two ways: the button goes when the list does, which is what this builds, or it moves into the questions block beside the per-question buttons. Each question in the block has its own button and the needs-me group's copy-all still takes every question on the board, so what an opened row loses is one click for one ticket's worth.
  - Ruled 2026-09-23: as built: the copy-all goes with the list; each question's own button and the group's copy-all remain.
- [D2] **The spec's Decisions say nothing about an opened row's questions, so these checks' oracle is this ticket.** "Questions show under their ticket in needs me, tag and headline, each with a copy button" and "An opened ticket reads as blocks: its questions (each with its detail)" are both still written for a row that shows them twice. Whichever way D1 goes, the Decisions want a sentence for it and the Testing Decisions a clause putting what the page's style does in the browser probe's scope; a confirmed spec is not a worker's to amend, so it is written here.
  - Ruled 2026-09-23: the spec's opened-ticket Decision and the browser probe's scope now say it.

## Comments

An opened row shows each of its questions once: the list under the name goes while the row is open, and the questions block carries the copy button beside each open question's detail; a folded row is unchanged. On branch `ticket/board-orients/14-questions-once`, not merged. `make check` passes and `make test` is 252 passed, against 250 before the slice.

**Demo**

`agent/show/board-orients/14-questions-once/demo` renders the demo tracker's board and walks from a folded row to the opened one and its buttons. Beside it, `agent/show/board-orients/14-questions-once/figure.html` is the before and after: the opened row as this slice was cut from it, the same row now, and a folded row unchanged, each panel a driven browser with numbered where-to-look notes, in both schemes.

```
$ /home/agent/repos/dispatch/agents-board-orients-14-questions-once/agent/show/board-orients/14-questions-once/demo
/tmp/board-questions-demo/agent/board.html

The board is the page above, opened here if this machine has a display. In *needs me*, "Retire the
QIF exporter" is folded, and this slice leaves a folded row alone: under its name are its two
questions, each with a *copy* button, and *copy all 2* under them.

Now click "Map columns once per bank", the build in review. Before this slice the row kept that
same list while it was open, and repeated all three questions in the block below it. Open, it now
reads:

    Map columns once per bank            review page  ledger-org/ledger#57
    You tell the importer once which column holds the date, the amount and the payee; ...

    questions
    D1  Remember the mapping per bank or per file name?                          copy
        Per bank asks one more question on the first import; per file name breaks ...
    D2  Amounts with a comma as the decimal separator                            copy
        are read as thousands today. Guess from the file, or ask once per bank?
    D3  The mappings live in ~/.config/ledger/mappings.toml.                     copy
        Fine there, or beside the ledger file so they travel with it?

The list under the name is gone: each question is read once, where its detail is. The *copy* button
at the end of a question's line is the one the list carried. Hover it to read what it will copy:

    Click to copy this question under the path of its ticket, to answer in any session.

    /tmp/board-questions-demo/agent/tickets/csv-import/02-map-columns.md
    - [D1] **Remember the mapping per bank or per file name?** Per bank asks one more question ...

Click it, and that is what lands on the clipboard. Fold the row again and the list is back, its
*copy all 3* with it: the whole list moves with the row's own summary.

A question the user has already ruled on carries no button in either place, since a ruling is what
clears it; open "The flaky upload test" in *needs me* to see the answered one, D2, greyed and
buttonless beside the open one.
```

**Details, if you want them**

- [D3] Assumptions
  - A1 `mx/skills/tracker/board.py:2421`: the question's copy button is pushed to the end of its line while the sessions' and the artefacts' buttons hug their content, which Standards reads as one question answered two ways; a question's line is a headline over a detail, so a button hugging it lands at a ragged left, and the other two blocks are not this ticket's to restyle.
  - A2 `agent/show/board-orients/14-questions-once/demo:10`: the demo opens the board where the machine has a display, which `/mx:show` asks of a demo and the feature's four sibling demos do not do; on this host it only prints the path.
  - A3 `agent/tickets/board-orients/14-questions-once.md:29`: this comment carries no "I need from you" list, though the worker contract asks for one; the calls are `## Questions` D1 and D2, where the spec's Decisions and 13's close-out put a worker's, and where the board reads them.
- [D4] The finding index. Correctness, Standards and Spec over `298cff2..1129539`, fixed in `b9ee063`; Tests over `298cff2..b9ee063`, fixed in `f3c8c49`. Declined findings name their assumption; `agent/reviews/` holds the four reports and dies with this worktree.
  - Correctness. No blocking finding. The block rendered from a status `load_tickets` may still change to `blocked`, so the row and the block read two of them: fixed by the check that holds the two readings to one answer, which fails the moment `shown_questions` branches on a second status. The layout docstring counting itself wrong: fixed. The third finding is D1.
  - Spec. No requirement missing, no scope creep, and the four Properties the Testing Decisions disposes *reviewed* hold. Fixed: the copy button keyed on a question's tag, which nothing keeps unique across a branch copy and the tracker's; `row`'s docstring still describing the list unconditionally; the demo dropping one question's detail with no elision mark.
  - Standards. Fixed: the open-question rule in two homes, `shown` taking a name two locals in the file already use, the thin wrapper with no docstring, the style comment restating two docstrings, the module docstring changing referent mid-clause, the call sites' bare arguments, the artefacts markup in two places, the check's past-tense name, the probe spelling its two row ids nine times, two `figure.py` comments. Declined: the right-aligned button as A1, the demo's display probe as A2.
  - Tests. Fixed, all four: the probe counting the block's buttons as nodes, which the markup check already pins, so a style hiding all but the first passed the whole suite; `margin-left: auto` with no oracle; two equality checks with neither end outside the renderer; and the style-only behaviour no run without a browser could see. Both mutations were run against the new probe and both now fail it. Two notes stand as decisions: no browser run clicks a copy button inside an opened row's body, the same delegated handler the folded row's click exercises, and the `Ruled` Property's own check does not reach the block's button, which the example check does. The axis's fifth finding is D2.
  - Outside the diff, from the Tests axis: `test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme` failed 2 of 4 runs in its own checkout, each time on `#toast` escaping by half its width on a `?graph=1` page, which nothing here touches. It did not reproduce in this worktree: five runs, five green. Worth a ticket if anyone else sees it, since it is a 100-second check.
- [D5] Friction. Four things.
  - The Tests reviewer ran 31 minutes and died on "You've hit your weekly limit · resets Sep 25", leaving no report; a one-line `claude -p` probe answered normally a minute later, so the axis was re-run against the tip and finished. An hour went to it. A cheap probe before `review` spawns four reviewers, or a retry on that message, would have caught it at the start.
  - No commit here carries the `Session:` trailer: 06's hook lives in the dotfiles and this host has none, so the board will not list this session on the ticket's row, and nothing on the row says why.
  - The layout suite is about 110 seconds of browser per run, so a change to the page or to the probe cannot ride the same loop as the rest of the suite; each one here was a run of that file first and `make test` after.
  - The worker contract names the expected failures under the properties directory as the oracle; this project has no properties directory and none names this ticket, so the oracle was the spec's Testing Decisions and the ticket. Nothing was blocked by it, but a worker reading the contract cold looks for a directory that is not there.
