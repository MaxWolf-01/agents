---
status: claimed
blocked-by: [07, 08, 09, 11]
priority: 2
size: S
---

# Whole-feature review of board-orients

## Brief

A full four-axis review of the whole board-orients feature against master, with the spec as the Spec axis. No slice was reviewed against the others, and incoherence between slices shows only here. It runs on top of 07, 08, 09 and 11 before you have ruled on them, so it is done by the time you have.

The flow's own close-out step, not a proposal.

## What to build

Run `/mx:code-review` over the feature: the fixed point is `master`, the range the merge-base with `master` to this branch's tip, and `agent/tickets/board-orients/spec.md` is the Spec axis. Read `mx/skills/code-review/SKILL.md` from this tree. The Spec reviewer checks every reviewed Property against the whole feature.

What this pass exists for: slices that disagree with each other, two homes for one rule, a pointer to a thing that moved, and a skill still describing what another slice retired. The needs-human queue, the "needs my review" group, and the questions in a closing comment are the retired things to hunt for.

Dispose of every finding under the review skill's rule: fix it on this branch in `Workflow-stage: review` commits, file it as a proposed ticket when it is too large, or decline it as an anchored assumption. A finding that would rewrite a spec Decision or Property is not yours to make: put it under `## Questions`.

## Questions

- [D1] **Which of 07's D3 and 09's D1 survives?** 07 asks you to rule on a gap (a merged pull request never ages out on a quiet tracker) that 09 closed with the watcher's GitHub clock, so the board invites you to rule twice on the same thing, once as a hole and once as its price. Ruling on one is what removes the other.
- [D2] **The Property "a render that finds nothing changed makes no GitHub request and no model call" is no longer what the watcher does.** Two landed behaviours sit outside it, both anchored and both right on the merits: a watched board naming any `gh` reference asks again once its answer lapses, and a watcher starting on a tracker that has not moved writes a first briefing, which is exactly the board you open after a week away. The sentence wants amending, or one of the two goes.
- [D3] **`An opened ticket reads as blocks: the brief, its questions, ...` says the brief is in the opened body; the build leaves it on the row.** 02's A6 and 04's A4 made that call and 04's D3 asks you to ratify it. The code removes the section from the body so it cannot come back, so the spec's line and the board disagree today.
- [D4] **`Links stay the house accent` against a GitHub link wearing its state's colour.** 07's ticket asked for the colour and its A5 says the sentence is older than the ticket. 07's D4 asks the same question from the other side: whether colour alone should separate open, waiting on changes and merged.
- [D5] **The briefing session retires on `an idle hour or a cap on pings or context`, and nothing reads context.** `claude -p` does not report it and the cache file cannot hold it (09's A3), and the Property's own wording already dropped it. The Decision is the sentence to amend.
- [D6] **Eight questions sit unruled on two tickets this feature already landed**, 05's D1 to D3 and 10's D1 to D5. A done ticket shows none, deliberately, so they reach you through no channel at all: each wants a `Ruled` line or a proposed ticket, and the board cannot tell you that.
- [D7] **The tracker pass 10's D6 wrote out for master is drifting.** `agent/tickets/needs-human.md` still holds its two entries, 34 of the roughly 45 live tickets carry no priority, size or brief, and seven decision tickets still head their subject `## Question`, which the board's parser cannot read; meanwhile master has gained tickets both with the fields and without. Apply the listing, or build the `ticket-meta` command 10's friction asked for and apply it with that.
- [D8] **Four of this feature's slices landed with no demo file**: 02, 03, 04 and 10 carry typed command listings in their closing comments instead. They landed before the figures-and-demos rule merged into this branch, so the feature ships under two contracts and `fd -t x '^demo$' agent/show` finds five of its nine. Retrofit them, or let the rule start from where it landed.
- [D9] **The Testing Decisions is three seams where the feature enters at five.** The watcher's pass and the browser probe are both seams a slice created and no line names (08's A5, and the Tests axis's T9); 09's A8 names five checks at seams it made; 02's A12 adds a second check for "every mark explains itself"; 01's D2 wants the limit of what `render-lint` reaches written down; and "a listed session's resume command resumes it" is disposed executable where only the first half of it can be. One amendment covers them.

## Acceptance criteria

- [x] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [x] `make check` and `make test` pass on the branch after the fixes.
- [x] No skill, README line, figure, glossary entry or spec line describes the needs-human queue, the "needs my review" group, or a worker's calls in its closing comment as current.
- [x] Demo: the diff is the demo; the closing comment carries the finding index and the command that lists the reports.

## Comments

Four axes over `7093bf7..be76e6c`, fifty-eight findings, twenty-nine fixed in four `Workflow-stage: review` commits, four filed as proposed tickets, sixteen declined as anchored assumptions and nine put to you above; on branch `ticket/board-orients/13-whole-feature-review`, not merged. `make check` passes and `make test` is 241 passed, up from 228.

**Demo**

The diff is the demo. The reports the axes wrote are what it was read from:

    $ ls -1 "/home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/7093bf7..be76e6c"
    correctness.md
    spec.md
    standards.md
    tests.md

They are gitignored and die with this worktree, so the index below is what survives the merge.

**Details, if you want them**

- [D10] Assumptions
  - A1 `agent/tickets/needs-human.md:3`: master's queue file, the thirty standalone tickets with no priority, size or brief and the seven `## Question` headings stay listed rather than migrated here, under 10's A1 and your ruling of 2026-09-23; D7 asks whether that listing still holds.
  - A2 `mx/skills/tracker/test_board.py:2115`: the needs-me enumeration keeps the spec's own sentence as its expectation, which the baseline calls a tautology, because the loader-seam check beside it already holds the Property against a set written out by hand.
  - A3 `mx/skills/tracker/briefing.py:43`: a run that answered nothing keeps saying so through a module global rather than a return value, since what carries every other answer is the cache file, and a run that wrote no file has none.
  - A4 `agent/prototypes/board-orients/board.py:8`: the prototype gets a tombstone and its two stale ticket copies go, and no `ANSWER.md` is written, because a verdict reconstructed from the spec by an agent that was not in that session reads as a record of it and is not one.
  - A5 `agent/tickets/board-orients/spec.md:23`: the spec's two pointers at `/var/tmp/board-orients-demo/` are corrected in place rather than escalated, a path being neither a Decision nor a Property.
  - A6 `agent/tickets/board-orients/02-rows.md:57`: 02's demo walks the reader through a group 03 removed, and stays as it is; a done ticket's closing comment is the record of what that slice landed, not an instruction anyone runs today.
  - A7 `mx/skills/tracker/board.py:1904`: the briefing renders as markdown with raw HTML passing through, under 09's A7, and ticket bodies have always gone the same way.
  - A8 `mx/skills/tracker/test_board.py:1101`: the note a copy button leaves once clicked is read per kind, the resume button naming its session where the other four name a path, which is the reading 05's D2 asked you for.
  - A9 `mx/README.md:71`: the four slices with no demo file are left as they landed, because writing demos now for work you have already accepted is a ticket rather than a review fix; D8 is where that call sits.
  - A10 `agent/tickets/board-orients/13-whole-feature-review.md:18`: the axes read `git diff master...HEAD` as the ticket says, so their range holds figures-and-demos and render-lint work already reviewed under their own tickets; each brief named the commit this feature's own work starts from and asked for findings there only where they contradict it.
- [D11] The finding index, by axis, for the agent that merges this branch. Fixed findings name their commit; filed ones their ticket; declined ones their assumption.
  - Correctness. C1 the GitHub clock disarmed by a briefing render, C4 a quiet run of the model never reaching the open tab, C5 the done group's copy-all, C6 a done standalone blocker dropped from the graph, C7 an external reference counted twice: `46b551f`. C2 three checks shadowed by a later definition: `92c425f`. C3 the layout matrix opening the graph with the wrong address: `c33a927`. Its one note, `board` failing on a worker host, is already [board-renders-on-worker-hosts](../board-renders-on-worker-hosts.md).
  - Standards. S1 `92c425f`. S3 the landing figure, S4 the needs-me rule's four homes, S6 the prototype's tombstone, S7 the moved demo tracker, S10 three spellings of the sit-down types, S14 the scale stated twice in one file, S15 two glossary entries carrying their mechanism, S16 em dashes, S17 the briefing prompt's prose standard, S18 dispatch restating the `Ruled` line: `408ddcb`. S8 filed as [one-demo-tracker](../one-demo-tracker.md), S12 as [layout-probes-are-scripts](../layout-probes-are-scripts.md), S13 as [board-splits-at-its-seams](../board-splits-at-its-seams.md). S2 declined as A1, S5 as A2, S9 as A9, S11 as A3, and S6's missing `ANSWER.md` as A4.
  - Spec. P2 the landing figure, P12 a live ticket linking a deleted queue, P17 the prototype, P18 the README's two missing pieces: `408ddcb`. P14 the briefing session reading the user's global CLAUDE.md wherever `CLAUDE_CONFIG_DIR` is set: `46b551f`. P13 the every-mark guard inverted, P15 the fifth copy button, P12's other half in the sidecar check: `c33a927`. P10 is already [12-explainer-superseded](12-explainer-superseded.md). P3 is D6, P4 D1, P5 D2, P6 and P11 D7, P7 D3, P8 D4, P9 D5, P19 D8. P1 declined as A1, P16 as A6, P20 as A7. P21 found no speculative generality that a ticket's assumptions do not already name.
  - Tests. T1 and T2 `92c425f`; T3 the ping's whole answer path, T4 the graph never laid out, T5 the watcher's re-render, T6 a Property asserted where it cannot fail, T7 render-lint's HTML `escapes`, T8 the unreachable ping cap, T12's first half: `c33a927`. T10 filed as [the-board-reads-what-a-box-cuts-off](../the-board-reads-what-a-box-cuts-off.md). T9 and T12's second half are D9; T11 declined as A2. Nine mutations the Tests axis ran survive no longer.
- [D12] Friction. Three things cost time. The dispatch note said `mx/skills/code-review/` holds a `review` script that launches the axes; this tree has only `SKILL.md`, `SMELLS.md` and `TEST-SMELLS.md`, so the axes were spawned by hand from the skill, which is what the skill describes and took a detour to establish. The review's fixed point is `master`, which lags this branch by three landed features, so a third of every reviewer's reading was work already reviewed under its own ticket; a whole-feature review wants the point the feature branched from, which is the second parent of the merge that brought master in. And the layout matrix is a minute and a half of browser per run, which is the right price, but it means a change to the page and a change to the matrix cannot be checked in the same loop as the rest of the suite: the three times I touched it I ran it alone first and `make test` after.
