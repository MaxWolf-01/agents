---
status: review
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

## Acceptance criteria

- [x] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [x] `make check` and `make test` pass on the branch after the fixes.
- [ ] No skill, README line, figure, glossary entry or spec line describes the needs-human queue, the "needs my review" group, or a worker's calls in its closing comment as current.
- [x] Demo: the diff is the demo; the closing comment carries the finding index and the command that lists the reports.

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
- [D14] **Acceptance criterion 3 cannot be met without ruling on 12 first.** Every skill, README line, figure, glossary entry and spec line is clean; the one artefact left is `agent/show/board-orients/index.html`, whose source-map figure still draws `I need from you [Dn] · Ruled: Dn` as where the board reads a build's questions. Tombstoning it is one of the two options [12](12-explainer-superseded.md) puts to you, so taking it here would answer 12 rather than this ticket, and the criterion is left unticked instead.

## Comments

Four axes over `7093bf7..be76e6c`, then four more over this branch's own fixes: fifty-eight findings on the feature and fifty-one on the review of it, each given one disposition in the index below, across five `Workflow-stage: review` commits and one that files four proposed tickets; on branch `ticket/board-orients/13-whole-feature-review`, not merged. `make check` passes and `make test` is 240 passed, against 228 before the review; the net is thirteen checks added and one deleted, which had been asserting something no implementation could fail. Acceptance criterion 3 is the one left unticked, for the reason D14 gives.

**Demo**

The diff is the demo. The eight reports are what it was read from:

    $ ls -1 "/home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/"*/*.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/7093bf7..be76e6c/correctness.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/7093bf7..be76e6c/spec.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/7093bf7..be76e6c/standards.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/7093bf7..be76e6c/tests.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/be76e6c..9939a8a/correctness.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/be76e6c..9939a8a/spec.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/be76e6c..9939a8a/standards.md
    /home/agent/repos/dispatch/agents-board-orients-13-whole-feature-review/agent/reviews/be76e6c..9939a8a/tests.md

They are gitignored and die with this worktree, so the index below is what survives the merge.

**Details, if you want them**

- [D10] Assumptions
  - A1 `agent/tickets/needs-human.md:3`: master's queue file, the thirty standalone tickets with no priority, size or brief and the seven `## Question` headings stay listed rather than migrated, under 10's A1 and your ruling of 2026-09-23; two of the seven were filed on this branch rather than master, and their conversion is 10's unruled D5 and more than a heading rename, so they wait with the rest. D7 asks whether the listing still holds.
  - A2 `mx/skills/tracker/test_board.py:2115`: the needs-me enumeration keeps the spec's own sentence as its expectation, which the baseline calls a tautology, because the loader-seam check beside it already holds the Property against a set written out by hand.
  - A3 `mx/skills/tracker/briefing.py:38`: a run that answered nothing keeps saying so through a module global rather than a return value, since what carries every other answer is the cache file, and a run that wrote no file has none; the ordering hazard that shape carried in the watcher is fixed rather than declined.
  - A4 `agent/prototypes/board-orients/board.py:6`: the prototype is tombstoned and its two stale ticket copies deleted, and no `ANSWER.md` is written, because a verdict reconstructed from the spec by an agent that was not in that session reads as a record of it and is not one.
  - A5 `agent/tickets/board-orients/spec.md:23`: the spec's two pointers at `/var/tmp/board-orients-demo/` are corrected in place rather than escalated, a path being neither a Decision nor a Property.
  - A6 `agent/tickets/board-orients/02-rows.md:57`: 02's demo walks the reader through a group 03 removed, and stays as it is; a done ticket's closing comment is the record of what that slice landed, not an instruction anyone runs today.
  - A7 `mx/skills/tracker/board.py:1906`: the briefing renders as markdown with raw HTML passing through, under 09's A7, and ticket bodies have always gone the same way.
  - A8 `mx/skills/tracker/test_board.py:1105`: the note a copy button leaves once clicked is read per kind, the resume button naming its session where the other four name a path, which is the reading 05's D2 asked you for.
  - A9 `mx/README.md:71`: the four slices with no demo file are left as they landed, because writing demos now for work you have already accepted is a ticket rather than a review fix; D8 is where that call sits.
  - A10 `agent/tickets/board-orients/13-whole-feature-review.md:18`: the axes read `git diff master...HEAD` as the ticket says, so their range holds figures-and-demos and render-lint work already reviewed under their own tickets; each brief named the commit this feature's own work starts from and asked for findings there only where they contradict it.
  - A11 `mx/skills/testing/test_no_shadowed_checks.py:1`: the shadowed-name guard is a check in the suite rather than a ruff rule, because this repo installs no linter and `make check` runs none, so `ruff --select F811` would be a tool to add and a target to wire before it caught anything; the check runs today.
  - A12 `agent/show/board-orients/index.html:177`: the superseded explainer keeps its stale strings, since tombstoning it is one of the two options [12](12-explainer-superseded.md) puts to you and taking it here would answer 12; it is why criterion 3 is unticked, and D14 says so.
  - A13 `mx/skills/tracker/test_briefing.py:102`: the ping cap is bounded against the two hours `briefing.py` names beside it rather than a number of its own, since the spec gives none, and what the bound is for is that a cap the schedule can never reach leaves the Property unfalsifiable.
- [D11] The finding index for the first round, `7093bf7..be76e6c`, by axis. Fixed findings name their commit; filed ones their ticket; declined ones their assumption.
  - Correctness. C1 the GitHub clock disarmed by a briefing render, C4 a quiet run of the model never reaching the open tab, C5 the done group's copy-all, C6 a done standalone blocker dropped from the graph, C7 an external reference counted twice: `46b551f`. C2 three checks shadowed by a later definition: `92c425f`. C3 the layout matrix opening the graph with the wrong address: `c33a927`. Its one note, `board` failing on a worker host, is already [board-renders-on-worker-hosts](../board-renders-on-worker-hosts.md).
  - Standards. S1 `92c425f`. S3 the landing figure, S4 the needs-me rule's four homes, S6 the prototype's tombstone, S7 the moved demo tracker, S10 three spellings of the sit-down types, S14 the scale stated twice in one file, S15 two glossary entries carrying their mechanism, S16 em dashes, S17 the briefing prompt's prose standard, S18 dispatch restating the `Ruled` line: `408ddcb`. S8 filed as [one-demo-tracker](../one-demo-tracker.md), S12 as [layout-probes-are-scripts](../layout-probes-are-scripts.md), S13 as [board-splits-at-its-seams](../board-splits-at-its-seams.md). S2 declined as A1, S5 as A2, S9 as A9, S11 as A3, and S6's missing `ANSWER.md` as A4.
  - Spec. P2 the landing figure, P12 a live ticket linking a deleted queue, P17 the prototype, P18 the README's two missing pieces: `408ddcb`. P14 the briefing session reading the user's global CLAUDE.md wherever `CLAUDE_CONFIG_DIR` is set: `46b551f`, with the check it needed in `5d16011`. P13 the every-mark guard inverted, P15 the fifth copy button: `c33a927`. P10 is already [12-explainer-superseded](12-explainer-superseded.md). P3 is D6, P4 D1, P5 D2, P6 and P11 D7, P7 D3, P8 D4, P9 D5, P19 D8. P1 declined as A1, P16 as A6, P20 as A7. P21 found no speculative generality that a ticket's assumptions do not already name.
  - Tests. T1 and T2 `92c425f`; T3 the ping's whole answer path, T4 the graph never laid out, T5 the watcher's re-render, T6 a Property asserted where it cannot fail, T7 render-lint's HTML `escapes`, T8 the unreachable ping cap, T12's first half: `c33a927`. T10 filed as [the-board-reads-what-a-box-cuts-off](../the-board-reads-what-a-box-cuts-off.md). T9 and T12's second half are D9; T11 declined as A2.
- [D12] The finding index for the self-review of those fixes, `be76e6c..9939a8a`, which found three new defects inside them and four checks that did not hold. All of it is `5d16011` unless named otherwise.
  - Correctness. C1 a done standalone blocker entering the graph once per ticket waiting on it, the C6 fix's own bug. C2 a run answering an empty string clearing the note instead of writing it, which is the C4 case through the last door left open. C3 the `CLAUDE_CONFIG_DIR` fix frozen at import, so nothing could read it: the settings are assembled when the run is. C4 `state_line` handing the briefing session questions the board hides. C5 the generator edited and its render left behind, declined as A12.
  - Standards. S1 the em-dash sweep breaking a live `# noqa` directive, S2 the new check file missing the header and `__main__` block its eight siblings carry, S3 `watch`'s docstring and `board --help` still saying two things where three move, S5 the README claiming a trailer the plugin does not install, S6 and S7 the two glossary rewrites, S8 and S9 two wrong numbers and a wrong overlap in the filed tickets, S10 `## Questions` in a position no sibling uses, S11 three tombstones not in the prescribed form, S12 the ping seam absent from its file's docstring, S13 an invented bound (A13), S14 two names for one module, S15 the `escapes` cases absent from the docstring that enumerates them, S18 the same ordering hazard as the Tests axis's T2. S4 declined as A12, S16 as D14, S17 as A11. S19 and S20's small items are in the fixes above or left as judgement calls the report records.
  - Spec. P1 is Correctness C1, P3 the `Ruled` line's home lost in a trim, P4 the two-things docstrings, P5 the vacuous model-call check deleted rather than left beside its replacement, P6 and this index rewritten, P7 as A12, P8 as D14, P11 the every-mark guard's narrowing said in place. P2 the two `## Question` headings on this branch's own lineage, which A1 now names. P9, P10, P12, P13, P14 are wording the fixes above carry.
  - Tests. T1 a new check's clause that could not fail, T2 the watcher reading the quiet note after the thread that writes it, T3 and T4 two lines of the diff with surviving mutations, T5 the sidecar check widened to what the Property names, T6 the quiet-pass check driven so a run exists to not repeat, T7 the `CLAUDE_CONFIG_DIR` check, T8 the external-reference check reading the page's own words. T9 declined as A11; T10 to T12 are wording. Five mutations were re-run against the fixes and four died at once; the fifth, the duplicated ghost, died after the check grew a second waiter.
- [D13] Friction. Four things cost time. The dispatch note said `mx/skills/code-review/` holds a `review` script that launches the axes; this tree has only `SKILL.md`, `SMELLS.md` and `TEST-SMELLS.md`, so the axes were spawned by hand from the skill, which is what the skill describes and took a detour to establish. The review's fixed point is `master`, which lags this branch by three landed features, so a third of every reviewer's reading was work already reviewed under its own ticket; a whole-feature review wants the point the feature branched from, which is the second parent of the merge that brought master in. The self-review found three new defects inside the first round's fixes and four checks that could not fail, which is the strongest argument for the step and also says the first round's own checks wanted the same adversarial pass the code got. And the layout matrix is a minute and a half of browser per run, so a change to the page and a change to the matrix cannot be checked in the same loop as the rest of the suite: each time I touched it I ran it alone first and `make test` after.
