---
status: review
---

# Whole-feature review of figures-and-demos against master

## What to build

The flow's own close-out step, not a proposal: no slice of this feature was reviewed against the whole, and that is where incoherence between slices shows. Run a full `/mx:code-review` of the `figures-and-demos` branch against the repo's integration branch, `master`, with `agent/tickets/figures-and-demos/spec.md` as the spec axis: the fixed point is `master`, so the range is the merge-base with `master` to the branch tip, and the reports land under `agent/reviews/<range>/`. The spec disposes every Property as **reviewed**; read them as the reviewed list and check each holds on the branch. Where the slices disagree with each other (a skill that still describes what another slice retired, two homes for one rule, a pointer to a file that moved), that is the finding this pass exists for.

The branch took master in after ticket 05 (the house style, render-lint, the board's served review links); `mx/skills/show/SKILL.md` was resolved by hand in that merge and is worth a second read against both parents.

Dispose of every finding under the review skill's own rule: fix it on this branch as `Workflow-stage: review` commits, file it as a proposed ticket when it is too large, decline it as an anchored assumption. A finding that rewrites a spec Decision or Property is not yours to make: file it as a needs-human entry in `agent/tickets/figures-and-demos/needs-human.md`. The plugin installed on the host predates this branch's skills; follow the branch's `code-review` skill as written.

## Acceptance criteria

- [x] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [x] `make check` and `make test` pass on the branch after the fixes.
- [ ] No skill, README line, figure or spec line on the branch describes a mechanism another slice of this feature retired (show's "Heavy artifacts fork" rule, the worker contract's "expected transcript", a promotion that copies rather than moves, the `agent/show/mx-readme-figures/` pipeline, the `landing.mmd`/`landing.svg` pair).
- [x] Demo: the diff is the demo; the closing comment carries the finding index and the commands that list the reports on disk.

## Comments

**2026-09-22** Four axes ran against the merge-base with `master` and every finding is disposed: 27 fixed on this branch across ten `Workflow-stage: review` commits, 7 filed as the user's calls in the feature's queue, 13 filed to five standalone tickets, the rest declined or noted. A self-review then ran on those fixes and found twelve more, which are fixed here too. Nothing is merged: the work is on `ticket/figures-and-demos/06-whole-feature-review`, eleven commits of fixes from `5a322f6` to `6a9de09`, and this comment after them.

**Demo**

The diff is the demo; there is no surface this pass added. The reports the two passes wrote are on disk, in the worktree and gitignored:

```
$ ls agent/reviews/*/
agent/reviews/5a322f6..95014c4/:
correctness.md  spec.md  standards.md  tests.md

agent/reviews/6c9ce66..5a322f6/:
correctness.md  spec.md  standards.md  tests.md

$ make check && make test
manifests parse, hooks point at executables, bin/ answers --help
============================= 101 passed in 23.79s =============================
```

All five demos were re-run on this host after the fixes, green: `01` drew its page and its SVG, `02`'s after round drew its page and said so in the first line of its message, `03` is 13/13 against the real `dispatch`, `04` is 8/8, and the worktree was clean after every run.

**I need from you**

- [D1] **Seven calls rewrite a spec Decision, a Property, a Solution line or the Testing Decisions**, which is a round's pen and not a worker's, so they wait in `agent/tickets/figures-and-demos/needs-human.md` with the edit each would take: promotion copies in two lines where round 7 ruled moves; the staging ends on two rulings where the code, the figure and the skill say four; the figure's file shape names a mermaid pair where every figure this repo ships is an authored page; the rows Decision is narrower than the table your own comments on ticket 01 produced; **your C5 asked for a page figure, ticket 01's comment says it landed, and the Figure cell still reads `none`**; a Property says a render is never tracked where the README's two are, deliberately; and the Testing Decisions has no line for the twenty-five assertions this feature's demos carry.
- [D2] **The third acceptance criterion stays unticked**, and only because of the first of those: four of its five named mechanisms are gone from the branch, and "a promotion that copies rather than moves" survives in exactly the two spec lines this ticket forbids me to rewrite. Tick it when you take that edit.
- [D3] **`job` still has no staged mode**, so the feature's central mechanism has never run against its real dependency. `job --help` on this host lists `run | wait | probe | log | stop | rm`. The spec files it to dotfiles as loose work "before ticket 03 starts"; ticket 03 raised it as its `[D1]` and shipped a shim inside its own demo. Every landing since has printed "the `job` here has no staged mode; nothing staged" and carried on, which is the right shape, but user story 14 has never been exercised end to end. It is outside every worktree, so it is yours.
- [D4] **`agent/show/house-style-rulings/` is deleted on this branch.** Its work shipped on master and the rule this feature lands says the merge that lands loose work carries the removal; it arrived here in the master merge, so no slice saw it. `git show master:agent/show/house-style-rulings/index.html` brings it back if you still want the comparison.

**Details, if you want them**

- [D5] Assumptions
  - A1 `claude/output-styles/max.md:10`: the landing shape names the demo's path and the staged session and does not point at `/mx:show`'s table, where the spec says all three slots point at it (Spec A3). An always-loaded file is the last place to spend words, and the loose landing reaches the table through orient's loose bullet, which names both the file and the skill.
  - A2 `mx/skills/tracker/MARKDOWN.md:58`: the loose-branch clause is what `agent/show/house-style-rulings/` was owed, so this branch pays it rather than leaving the rule's first counter-example in its own repo. Reversible in one command; that is D4.
  - A3 `agent/tickets/figures-and-demos/05-readme-figure.md:19`: the criterion is reworded to the landed rule and ticked, on the strength of the accept that closed that ticket after its `[D1]` offered to revert the move. A `done` ticket with an unticked criterion reads as work missing.
  - A4 `agent/tickets/figures-and-demos/06-whole-feature-review.md:17`: four axes ran, not three. The skill spawns Tests only when the diff touches a test file and this one touched none; the ticket asked for four, and the axis earned its place, since what the branch leaves untested is most of what it added.
  - A5 `agent/tickets/harden-has-no-target.md:2`: the three tickets this pass filed are committed on this branch, not in the main checkout where standalone tickets live, since a worker writes only inside its worktree. The board shows them tagged with the branch until they are moved.
  - A6 `agent/show/figures-and-demos/02-spec-figures/demo:251`: a run whose after arm draws no figure exits nonzero. It is right for a human reading one run, since a skipped figure otherwise reads exactly like a drawn one, and wrong for a gate, since the exit then depends on a model's behaviour. `show-conventions-checked.md` carries that as its open part rather than this file hedging.
  - A7 `agent/show/figures-and-demos/03-landing-demo/demo:212`: the staged-path check pins the relative form the script types today. A move to staging the absolute path would fail it for the wrong reason; the strong oracle is the check two lines below, which reads what the user's Enter produced.
- [D6] **Finding index**, `6c9ce66..5a322f6`, four axes, 61 findings. Fixed: the promotion rule's two homes and the tracker's two repo-specific facts (Standards H1, H2, Spec C1, Correctness F6) → `9fbae2c`; `dispatch --help`'s wrong names, the `job`-absent and diff-is-the-demo readings, the echoed `job rm`, the hyphen dashes (Correctness F2, F5, Standards H4, H7, J3, J13, Spec C5) → `99e5872`; the figure's one file shape, the missing diff-is-the-demo home, the helper-beside-a-demo reading, the output style's harness name, orient's missing failure branch, the spec format's ordering (Standards J2, J4, J5, J6, J7, J8, Spec C2 skill half, C7) → `e90238b`; the board guard's untested skip (Tests B3) → `6adbdc5`; the orphan show directory (Spec C6, Standards J11, Tests C3) → `04378aa`; three stale pointers and an anchor inside the feature's own tickets (Standards H6, J12, Spec A5) → `0f906ce`; 04's tracked transcript, both demos' silent no-figure exit, 01's missing isolation and plugin guard, 03's two weak assertions (Correctness F3, F4, Standards H3, J1, Spec C3, Tests A1, A2) → `126736e`. Filed as the user's: Standards H5, Spec B1, C4, the Properties' P2 wording, Tests B1, C1, and the page-row finding the self-review added → `needs-human.md` (`95014c4`). Filed as tickets: Spec A1 and Correctness F4's design half → `figure-and-demo-rule-checked.md`; Tests C1, C3, C4, C5 → `show-conventions-checked.md`; Tests D1, D2, D5 → `dispatch-scripts-under-test.md`; Tests D3, A4 → `render-check.md`; Standards J10 → `skills-holistic-pass.md`. Declined: Spec A3 → A1. Carried here rather than fixed: Spec A2 → D3, Spec A4 (the five landed comments print a relative path, and the absolute-path clause is round 9, later than all of them; the rule is in place for the next landing), Standards J9 (the demo register rule has no instance yet and five counter-instances, which `dispatch-shown.md` is the first chance to fix), Spec C8 and Tests A3 (notes, no action). Everything else in the reports is a note or a clean check.
- [D7] **Finding index**, `5a322f6..95014c4`, the self-review, four axes, 12 findings, all fixed in `d1d8688` and `6a9de09`: the escape hatch narrowed past two table rows (Standards H1, Correctness 1); the figure paragraph sanctioning a second tracked copy, which the same pass files as the user's call (Standards H7, Correctness 2); the tracker keeping the clause the commit was there to move (H5); `unstage_demo` silent where it actually undid something, and ticket 03's `[D7]` left describing the fix it re-decided (H4, J1); orient covering one of two `job` states (J8); 04's criterion and marker placement (H2, J12); 02's A4 falsified by the reorder (H3, fixed in `a94952f`); the queue's rows entry, its assertion count and its five line anchors (H6, J6, J10); the show-conventions ticket's blocker with no edge (H8, Correctness 3); the two filed tickets' demo criteria and prose (J3, J5, J9, J13); the board test's two surviving mutants (Tests F1, F2); the demos' figure-shape blindness, failure ordering, unasserted skill copy and weak content check (Tests F4, F5, F6, F10, Correctness 4). Filed: Tests F3 → `harden-has-no-target.md`; Tests F7 → `dispatch-scripts-under-test.md`; Tests F11 → `figure-and-demo-rule-checked.md`; Tests F12 → `show-conventions-checked.md`. Declined: Tests F9 → A7, F12's exit status → A6. Tests F8 is a note.
- [D8] Friction
  - **`make harden` has no target in this repo**, which two skills prescribe at exactly this moment. Every survivor this pass found was found by hand, one mutation at a time, and the self-review then found two more survivors of the one test I wrote. That is `harden-has-no-target.md`, and it is one line of Makefile.
  - **The board cannot render from a worker's worktree.** `board agent/tickets` reads the main checkout and dies with "no tracker at .../agents.git/agent/tickets", so I could not see the queue I wrote as the user will. I parsed it through `load_needs_human` instead, which reads the entries but not the page.
  - **Two of this feature's five demos cost ten minutes and four live Sonnet sessions to re-run**, and I re-ran them twice, once to verify the isolation port and once after the self-review's findings. That is the right cost for what they demonstrate and the wrong cost for a check; it is what makes `show-conventions-checked.md`'s fourth reading an open question rather than a line.
  - **The installed plugin predates this branch**, so my own worker contract asks for "the command and its expected transcript" where the branch's asks for a demo file and a pasted run. The ticket warned me; a worker whose ticket does not would follow the older rule.
