---
name: code-review
description: "Review the changes since a fixed point (a commit, branch or tag). Use when the user asks to review a branch or work in progress, to \"review since X\", or for a \"light review\"."
---

Review of the diff between `HEAD` and a fixed point, along four axes:

- **Correctness**: does the change work, without breaking callers, contracts, or edge cases?
- **Standards**: does it conform to the repo's documented standards and the smell baseline?
- **Spec**: does it faithfully implement the originating ticket / issue / spec?
- **Tests**: do the tests it touches enter at the agreed seams, take their expectations from an oracle, and use inputs that can discriminate a bug? It runs the suite rather than only reading it, which makes it the one axis that executes the tip under review.

The axes run as separate reviewers so they don't pollute each other's context, and their reports are read by the session or worker that owns the branch (step 5). [`review`](review), beside this file, runs them; this skill is the judgment around that script.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point: a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, default to "since the last review": the most recent commit bearing a `Workflow-stage: review` trailer (`git log --grep='^Workflow-stage: review$' -1 --format=%H`, anchored, or a commit merely *discussing* the trailer matches); when none exists, `@{upstream}` if it resolves and differs from `HEAD`, else the merge-base with the default branch. Whichever candidate is nearest `HEAD` wins. Ask only when none produces a non-empty diff, which the script's own refusal tells you.

### 2. Identify the spec source

Look for what the work was ordered by, in this order:

1. A path, URL, or text the user passed as an argument.
2. The ticket the branch builds: `tracker context <slug>` is its body with every ancestor's, which is the whole order for this work, and a branch named `ticket/<slug>` names its slug.
3. Issue/PR references in the commit messages (`#123`, `Closes #45`), fetched via `gh`.
4. A specification the repo keeps outside the tracker: `docs/`, `specs/` matching the branch name.
5. If nothing is found, ask the user where it is, unless the work is plainly loose in-session work that never had one.

It travels to the reviewers as a file, so a fetched issue body or text the user pasted is written to one. Anything else the reviewers must not reopen goes in that file too: linked issues, a PR's prior review discussion.

Where no order was found, run **light** (below), which takes none. With one in hand, the axes are the default for a large diff or one touching a contract others depend on; for a small diff that touches no such contract, light mode's single reviewer reads the same source for less, and what it costs is the axes' separation and the Tests axis, the one that runs the suite. The reviewer's call, and the worker contract reads it the same way ([`worker-prompt.md`](../dispatch/worker-prompt.md)).

### 3. What binds the review

The standards sources are the script's to gather, and the brief it writes for each axis is the record of which ones bound this review:

- [`SMELLS.md`](SMELLS.md), beside this file, the **smell baseline**: a fixed set of code smells the Standards axis applies to every diff, even when the repo documents nothing.
- [`TEST-SMELLS.md`](TEST-SMELLS.md), beside it, the **test-smell baseline**: the Tests axis's own source, and a standards source for whoever reads the tests when no Tests axis runs, the one light reviewer included.
- `/mx:writing-for-humans` (its `SKILL.md` and, beside it, [`CATALOGUE.md`](../writing-for-humans/CATALOGUE.md), the catalogue of prose tells the reviewer cites by rule id), for **every** diff: their rules bind all artifact text wherever it lives (code comments, docstrings, UI strings, help text, docs, READMEs).
- `/mx:writing-for-agents` (its `SKILL.md`), when the diff touches process documents (skills, `AGENTS.md`/`CLAUDE.md`, commands, output styles, prompt templates).
- [`CONTEXT-FORMAT.md`](../domain-modelling/CONTEXT-FORMAT.md) and [`ADR-FORMAT.md`](../domain-modelling/ADR-FORMAT.md), when the diff touches a glossary (`CONTEXT.md`, `CONTEXT-MAP.md`) or an ADR (`decisions/`): each entry or record is checked against its format's rules, and `glossary-lint` runs on every touched glossary. The agent that wrote an entry has just settled the mechanism behind it and reads that as the definition; the reviewer reads the entry cold.
- The repo's own standards documents, at its root and only there: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `PRINCIPLES.md`.

### 4. Run the reviewers

`review`, beside this file and on `PATH`, does the mechanics: the range, each axis's brief from the templates in [`briefs/`](briefs), the axes as `claude -p` reviewers, and the reports under the range they read. `review --help` is its reference. It takes minutes and narrates one line per reviewer, so run it where you can watch it (`/mx:tmux`). A zero exit means every report landed; a nonzero one names the axis that left none, and the command to re-run it. The judgment it leaves you is `--effort`: lower than its default for a small or trivial diff. A brief that needs changing is one file in `briefs/`. For a cross-model review, run the same briefs through `/mx:codex` instead.

### 5. Aggregate

The caller aggregates: the session or worker that owns the branch, once the script has returned. Nothing about findings goes out before that, no per-axis narration as reviewers land.

Read the reports per axis and give every finding one of three dispositions:

- **Fixed**: a follow-up commit carrying `Workflow-stage: review`, never an amend, so the commit's diff is the review's measurable effect.
- **Filed**: worth acting on, too large for that commit, so it becomes a proposed ticket (`/mx:tracker`).
- **Declined**: the finding's premise is wrong, or the fix costs more than the finding is worth, and the entry says which. It lands anchored in the `Assumptions` block of the closing comment the caller writes (`` - A7 `src/importer.py:118`: the finding, and why it stands ``; ids continue from the highest already in the ticket, which is the id rule a worker carries in its contract, [`worker-prompt.md`](../dispatch/worker-prompt.md)), so the ticket's review page projects it onto the line it concerns, which is where the user rules on it.

Two callers hold no ticket. A bare "review this branch" anchors its declines and its index on the review page as notes. A review of a branch the caller does not own, an incoming PR, delivers every finding where the review is happening, the PR's comments or the reply: nothing there is the caller's to fix, so every finding is one of the user's calls.

Where a ticket holds the work, its closing comment carries a **finding index** under a line naming the range, written exactly as ``review range `<merge-base>..<head>` `` (the range the reports' directory is named by); `dispatch review` checks the build's commits against every such line in the ticket and the round's report. The index is one line per finding, fixed → the commit, filed → the ticket, declined → the assumption id. The agent that merges the branch reads that index, never the reports.

A review's reader is the agent that owns the branch, never the user. It fixes, files or declines each finding, and what it cannot dispose of alone (a declined finding worth a ruling, a question the review raised) it escalates through its own closing comment, under the worker contract. Findings the review fixed, per-axis summaries and verification lists stay in the reports, which die with the worktree.

A clean diff gets one line: ``review range `<merge-base>..<head>` ``, and that the axes came back empty.

## Light mode

`--light` folds the correctness and standards briefs into one reviewer, which judges the diff against `--spec` as well where one is given. What it buys is cost; what it costs is the axes' separation and the Tests axis, so nobody runs the suite. The right trade for a diff small enough that one reader sees all of it, and for work nothing ordered. Step 5 runs as written: one report to read, the same three dispositions, the same delivery.

## Why separate axes

A change can pass any axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks a caller → **Spec pass, Correctness fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**
- Code that is correct, conventional and asked for, under tests that would pass without it → **every other axis passes, Tests fail.**

Each axis is read and disposed on its own; folding the four into one ranked list would let three passes bury the one failure.
