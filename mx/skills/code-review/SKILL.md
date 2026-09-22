---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along four axes: Correctness (does it break anything?), Standards (repo coding standards plus a smell baseline), Spec (does it match what the originating ticket/issue asked for?), and Tests (what do the tests it touches actually catch?). Runs the axes as parallel reviewers; specless work runs light, one reviewer and no spec axis. Use when the user wants to review a branch, work-in-progress changes, finished unspecced work, or asks to \"review since X\" or a \"light review\"."
---

Review of the diff between `HEAD` and a fixed point, along four axes:

- **Correctness**: does the change work, without breaking callers, contracts, or edge cases?
- **Standards**: does it conform to the repo's documented standards and the smell baseline?
- **Spec**: does it faithfully implement the originating ticket / issue / spec?
- **Tests**: do the tests it touches enter at the agreed seams, take their expectations from an oracle, and use inputs that can discriminate a bug?

The axes run as separate reviewers so they don't pollute each other's context. [`review`](review), beside this file, runs them: it writes each brief from the templates in [`briefs/`](briefs) and leaves the reports on disk under the range they read, for the session or worker that owns the branch to act on (step 5). This skill is the judgment around that script.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point: a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, default to "since the last review": the most recent commit bearing a `Workflow-stage: review` trailer (`git log --grep='^Workflow-stage: review$' -1 --format=%H`, anchored, or a commit merely *discussing* the trailer matches); when none exists, `@{upstream}` if it resolves and differs from `HEAD`, else the merge-base with the default branch. Whichever candidate is nearest `HEAD` wins. Ask only when none produces a non-empty diff, which the script's own refusal tells you.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. A path, URL, or text the user passed as an argument.
2. Issue/PR references in the commit messages (`#123`, `Closes #45`), fetched via `gh`.
3. A spec file: a feature's `agent/tickets/<feature>/spec.md`, or `docs/`, `specs/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is, unless the work is plainly loose in-session work that never had one.

A standalone ticket has no spec, so it takes light mode by default, the full axes when its diff is large or touches a contract others depend on: the reviewer's call, and the worker contract reads it the same way ([`worker-prompt.md`](../dispatch/worker-prompt.md)).

No spec → run **light** (below): one reviewer, no Spec axis, instead of the full spawn.

### 3. What binds the review

The standards sources are the script's to gather, and the brief it writes beside each report names them: the smell baseline [`SMELLS.md`](SMELLS.md) and the test-smell baseline [`TEST-SMELLS.md`](TEST-SMELLS.md) beside this file, which bind every diff even where the repo documents nothing; `/mx:writing-for-humans` and, beside it, [`CATALOGUE.md`](../writing-for-humans/CATALOGUE.md), the catalogue of prose tells the reviewer cites by rule id, whose rules bind all artifact text wherever it lives (code comments, docstrings, UI strings, help text, docs, READMEs); `/mx:writing-for-agents` where the diff touches process documents; and the repo's own standards documents at its root.

### 4. Run the reviewers

`review <fixed-point> [--spec <path>] [--light] [--model <model>]`, beside this file and on `PATH`, does the mechanics: the range, each axis's brief from the templates in [`briefs/`](briefs), the axes as `claude -p` reviewers two at a time, and the reports under the range they read. It takes minutes and narrates one line per reviewer, so run it where you can watch it (`/mx:tmux`); `review --help` is its reference. Its exit is the reading: zero with every report on disk, and nonzero naming an axis that left none, to re-run with `--axes`. A brief that needs changing is one file in `briefs/`, never a prompt assembled here.

The model is the judgment it leaves you: Opus by default, Sonnet when the diff is small or trivial, never Fable unless the user names it for this review. For a cross-model review, run the same briefs through `/mx:codex` instead.

### 5. Aggregate

The caller aggregates: the session or worker that owns the branch, once the script has returned. Nothing about findings goes out before that, no per-axis narration as reviewers land.

Read the reports per axis and give every finding one of three dispositions:

- **Fixed**: a follow-up commit carrying `Workflow-stage: review`, never an amend, so the commit's diff is the review's measurable effect.
- **Filed**: worth acting on, too large for that commit, so it becomes a proposed ticket (`/mx:tracker`).
- **Declined**: the finding's premise is wrong, or the fix costs more than the finding is worth, and the entry says which. It lands anchored in the `Assumptions` block of the ticket's closing comment (`` - A7 `src/importer.py:118`: the finding, and why it stands ``; ids continue from the highest already in the ticket, which is the id rule a worker carries in its contract, [`worker-prompt.md`](../dispatch/worker-prompt.md)), so the ticket's review page projects it onto the line it concerns, which is where the user rules on it.

Two callers hold no ticket. A bare "review this branch" anchors its declines and its index on the review page as notes. A review of a branch the caller does not own, an incoming PR, delivers every finding where the review is happening, the PR's comments or the reply: nothing there is the caller's to fix, so every finding is one of the user's calls.

Where a ticket holds the work, its closing comment carries a **finding index** under the review range: one line per finding, fixed → the commit, filed → the ticket, declined → the assumption id. The agent that merges the branch reads that index, never the reports.

A review's reader is the agent that owns the branch, never the user. It fixes, files or declines each finding, and what it cannot dispose of alone (a declined finding worth a ruling, a question the review raised) it escalates through its own closing comment, under the worker contract. Findings the review fixed, per-axis summaries and verification lists stay in the reports, which die with the worktree.

A clean diff gets one line: the range, and that the axes came back empty.

## Light mode

For specless work, or when the user asks for it: `--light` is **one** reviewer over the correctness and standards briefs joined, reporting as the `light` axis. A diff touching tests adds the test-smell baseline to that reviewer rather than a Tests axis, since light mode has no Testing Decisions to check the tests against. Model rule inverted from step 4: Sonnet by default, Opus by your judgment when the diff is complex enough to warrant it. Step 5 runs as written: one report to read, the same three dispositions, the same delivery.

The fold trades the separate axes for cost, which is fine exactly when there is no spec for a Spec axis to check.

## Why separate axes

A change can pass any axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks a caller → **Spec pass, Correctness fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**
- Code that is correct, conventional and asked for, under tests that would pass without it → **every other axis passes, Tests fail.**

Each axis is read and disposed on its own; folding the four into one ranked list would let three passes bury the one failure.
